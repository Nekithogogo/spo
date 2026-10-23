"""Интеграционные тесты идут на отдельной БД (TEST_DATABASE_URL); перед каждым тестом схема пересоздаётся."""
import os
from pathlib import Path

import psycopg2
import pytest

from app import create_app

DB_DIR = Path(__file__).resolve().parent.parent / "db"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres@localhost:5432/studio_test")


def reset_database():
    conn = psycopg2.connect(TEST_DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        cur.execute((DB_DIR / "01_schema.sql").read_text(encoding="utf-8"))
        cur.execute((DB_DIR / "02_seed.sql").read_text(encoding="utf-8"))
    conn.close()


@pytest.fixture
def client():
    reset_database()
    app = create_app({"TESTING": True, "DATABASE_URL": TEST_DATABASE_URL})
    return app.test_client()
