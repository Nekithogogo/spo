"""Механизм миграций (ПР №10): применение по порядку, baseline базы версии 1.0, защита от правок."""
import subprocess
from pathlib import Path

import psycopg2
import pytest

from app import manage
from tests.conftest import TEST_DATABASE_URL

V1_SCHEMA = subprocess.run(["git", "show", "9f2069d:db/01_schema.sql"], capture_output=True, text=True,
                           cwd=Path(__file__).resolve().parent.parent).stdout


def _fresh():
    conn = psycopg2.connect(TEST_DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    return conn


def _scalar(conn, sql):
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()[0]


def test_migrations_apply_in_order_and_are_idempotent():
    conn = _fresh()
    assert manage.migrate(TEST_DATABASE_URL, log=lambda *_: None) == ["0001", "0002", "0003", "0004"]
    assert manage.migrate(TEST_DATABASE_URL, log=lambda *_: None) == []   # повторный запуск ничего не делает
    assert _scalar(conn, "SELECT string_agg(version, ',' ORDER BY version) FROM schema_migrations") == "0001,0002,0003,0004"
    conn.close()


@pytest.mark.skipif(not V1_SCHEMA, reason="нет истории git с версией 1.0")
def test_upgrade_of_v1_database_keeps_data():
    """База, созданная скриптом версии 1.0 (без журнала миграций), обновляется до 2.0 без потери данных."""
    conn = _fresh()
    with conn.cursor() as cur:
        cur.execute(V1_SCHEMA)
        cur.execute("INSERT INTO users (full_name, email, role) VALUES ('Тест', 'Test@Studio.Local', 'producer')")
        cur.execute("INSERT INTO clients (name, email) VALUES ('Клиент', 'c@x.local')")
        cur.execute("INSERT INTO projects (title, client_id, producer_id, status) VALUES ('Старый проект', 1, 1, 'shooting')")
    logs = []
    assert manage.migrate(TEST_DATABASE_URL, log=logs.append) == ["0002", "0003", "0004"]
    assert any("baseline" in line for line in logs)
    assert _scalar(conn, "SELECT title FROM projects WHERE id = 1") == "Старый проект"
    assert _scalar(conn, "SELECT email FROM users WHERE id = 1") == "test@studio.local"      # миграция данных 0002
    assert _scalar(conn, "SELECT new_status FROM project_status_history WHERE project_id = 1") == "shooting"  # 0003
    conn.close()


def test_changed_migration_is_rejected(monkeypatch):
    _fresh().close()
    manage.migrate(TEST_DATABASE_URL, log=lambda *_: None)
    original = manage.available_migrations

    def tampered():
        items = original()
        items[1] = {**items[1], "checksum": "0" * 64}
        return items

    monkeypatch.setattr(manage, "available_migrations", tampered)
    with pytest.raises(SystemExit, match="изменена после применения"):
        manage.migrate(TEST_DATABASE_URL, log=lambda *_: None)


def test_failed_migration_is_rolled_back(monkeypatch, tmp_path):
    conn = _fresh()
    for f in manage.MIGRATIONS_DIR.glob("*.sql"):
        (tmp_path / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "0005_broken.sql").write_text(
        "CREATE TABLE half_done (id int);\nALTER TABLE no_such_table ADD COLUMN x int;", encoding="utf-8")
    monkeypatch.setattr(manage, "MIGRATIONS_DIR", tmp_path)
    with pytest.raises(psycopg2.Error):
        manage.migrate(TEST_DATABASE_URL, log=lambda *_: None)
    assert _scalar(conn, "SELECT to_regclass('public.half_done')") is None    # частичных изменений нет
    assert _scalar(conn, "SELECT max(version) FROM schema_migrations") == "0004"
    conn.close()


def test_constraints_added_by_migrations(app):
    from app.db import execute
    with app.app_context():
        with pytest.raises(psycopg2.errors.UniqueViolation):   # регистронезависимая уникальность e-mail
            execute("INSERT INTO users (full_name, email) VALUES ('Дубль', 'ORLOVA@studio.local')", returning=False)
        with pytest.raises(psycopg2.errors.CheckViolation):    # роль в проекте не может быть пустой
            execute("INSERT INTO project_members VALUES (4, 1, '  ')", returning=False)
        with pytest.raises(psycopg2.errors.CheckViolation):    # формат e-mail
            execute("INSERT INTO users (full_name, email) VALUES ('X', 'без собаки')", returning=False)
