"""Служебные команды: миграции схемы БД, тестовые данные, учётные записи.

    python -m app.manage migrate [--seed]   применить новые миграции (и тестовые данные в пустую БД)
    python -m app.manage status             показать применённые и ожидающие миграции
    python -m app.manage set-password EMAIL задать пароль сотруднику (пароль читается из stdin/запроса)

Подключение берётся из MIGRATE_DATABASE_URL (роль-владелец схемы), иначе из DATABASE_URL.
"""
import argparse
import getpass
import hashlib
import os
import sys
import time
from pathlib import Path

import psycopg2
from werkzeug.security import generate_password_hash

DB_DIR = Path(os.environ.get("DB_DIR", Path(__file__).resolve().parent.parent / "db"))
MIGRATIONS_DIR = DB_DIR / "migrations"
SEED_FILE = DB_DIR / "seed.sql"
LOCK_ID = 727001  # pg_advisory_lock: две миграции одновременно не выполнятся
APP_ROLE = "studio_app"


def database_url():
    return os.environ.get("MIGRATE_DATABASE_URL") or os.environ.get(
        "DATABASE_URL", "postgresql://postgres@localhost:5432/studio")


def available_migrations():
    """Файлы вида NNNN_описание.sql в порядке номеров."""
    result = []
    for path in sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql")):
        sql = path.read_text(encoding="utf-8")
        result.append({
            "version": path.name[:4],
            "name": path.stem[5:],
            "sql": sql,
            "checksum": hashlib.sha256(sql.encode("utf-8")).hexdigest(),
        })
    return result


def _ensure_journal(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version       VARCHAR(4)   PRIMARY KEY,
            name          VARCHAR(200) NOT NULL,
            checksum      CHAR(64)     NOT NULL,
            applied_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
            execution_ms  INTEGER      NOT NULL
        )""")


def _applied(cur):
    cur.execute("SELECT version, checksum FROM schema_migrations ORDER BY version")
    return dict(cur.fetchall())


def _baseline_if_legacy(cur, migrations, log):
    """БД версии 1.0 создавалась скриптом 01_schema.sql без журнала миграций.
    Если таблицы уже есть, а журнал пуст, отмечаем 0001 как применённую (baseline)."""
    if _applied(cur):
        return
    cur.execute("SELECT to_regclass('public.projects') IS NOT NULL")
    if cur.fetchone()[0]:
        first = migrations[0]
        cur.execute(
            "INSERT INTO schema_migrations (version, name, checksum, execution_ms) VALUES (%s, %s, %s, 0)",
            (first["version"], first["name"], first["checksum"]),
        )
        log(f"baseline: схема версии 1.0 уже существует, {first['version']}_{first['name']} отмечена применённой")


def migrate(url=None, seed=False, log=print):
    migrations = available_migrations()
    conn = psycopg2.connect(url or database_url())
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
            conn.autocommit = False
            _ensure_journal(cur)
            _baseline_if_legacy(cur, migrations, log)
            conn.commit()

            applied = _applied(cur)
            for m in migrations:
                if m["version"] in applied and applied[m["version"]] != m["checksum"]:
                    raise SystemExit(f"Миграция {m['version']} изменена после применения: "
                                     "исправления оформляются новой миграцией")
            pending = [m for m in migrations if m["version"] not in applied]
            for m in pending:
                started = time.monotonic()
                try:
                    cur.execute(m["sql"])
                    ms = int((time.monotonic() - started) * 1000)
                    cur.execute(
                        "INSERT INTO schema_migrations (version, name, checksum, execution_ms) VALUES (%s, %s, %s, %s)",
                        (m["version"], m["name"], m["checksum"], ms),
                    )
                    conn.commit()  # каждая миграция — отдельная транзакция: либо целиком, либо никак
                except Exception:
                    conn.rollback()
                    log(f"ОШИБКА в миграции {m['version']}_{m['name']}, изменения откачены")
                    raise
                log(f"applied {m['version']}_{m['name']} ({ms} ms)")
            if not pending:
                log("схема актуальна, новых миграций нет")

            if seed:
                cur.execute("SELECT count(*) FROM users")
                if cur.fetchone()[0] == 0:
                    cur.execute(SEED_FILE.read_text(encoding="utf-8"))
                    conn.commit()
                    log("загружены тестовые данные db/seed.sql")
                else:
                    log("тестовые данные не загружались: в БД уже есть сотрудники")

            _grant_app_role(cur)
            conn.commit()
            cur.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))
            conn.commit()
        return [m["version"] for m in pending]
    finally:
        conn.close()


def _grant_app_role(cur):
    """Роль приложения получает только DML-права на всё, что создали миграции (идемпотентно)."""
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (APP_ROLE,))
    if not cur.fetchone():
        return
    cur.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}")
    cur.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}")
    # журнал миграций приложение только читает (версия схемы в /api/health)
    cur.execute(f"REVOKE INSERT, UPDATE, DELETE ON schema_migrations FROM {APP_ROLE}")


def status(url=None):
    conn = psycopg2.connect(url or database_url())
    try:
        with conn.cursor() as cur:
            _ensure_journal(cur)
            cur.execute("SELECT version, name, applied_at, execution_ms FROM schema_migrations ORDER BY version")
            rows = {r[0]: r for r in cur.fetchall()}
        conn.rollback()
    finally:
        conn.close()
    for m in available_migrations():
        r = rows.get(m["version"])
        mark = f"applied {r[2]:%Y-%m-%d %H:%M:%S} ({r[3]} ms)" if r else "PENDING"
        print(f"{m['version']}  {m['name']:<28} {mark}")


def set_password(email, password, url=None):
    if len(password) < 8:
        raise SystemExit("Пароль должен быть не короче 8 символов")
    conn = psycopg2.connect(url or database_url())
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s, token_version = token_version + 1 "
                "WHERE lower(email) = lower(%s) RETURNING id",
                (generate_password_hash(password), email),
            )
            if cur.fetchone() is None:
                raise SystemExit(f"Сотрудник {email} не найден")
        conn.commit()
    finally:
        conn.close()
    print(f"пароль для {email} обновлён")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m app.manage")
    sub = parser.add_subparsers(dest="command", required=True)
    m = sub.add_parser("migrate", help="применить миграции")
    m.add_argument("--seed", action=argparse.BooleanOptionalAction, default=False,
                   help="загрузить тестовые данные, если БД пустая")
    sub.add_parser("status", help="состояние миграций")
    p = sub.add_parser("set-password", help="задать пароль сотруднику")
    p.add_argument("email")
    args = parser.parse_args(argv)

    if args.command == "migrate":
        migrate(seed=args.seed)
    elif args.command == "status":
        status()
    elif args.command == "set-password":
        password = sys.stdin.readline().strip() if not sys.stdin.isatty() else getpass.getpass("Новый пароль: ")
        set_password(args.email, password)


if __name__ == "__main__":
    main()
