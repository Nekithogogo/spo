"""Интеграционные тесты идут на отдельной БД (TEST_DATABASE_URL); перед каждым тестом схема
пересоздаётся теми же миграциями, что и на сервере, и заполняется db/seed.sql."""
import os

import psycopg2
import pytest

from app import create_app
from app.manage import migrate

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres@localhost:5432/studio_test")
PASSWORD = "studio2026"


def reset_database():
    conn = psycopg2.connect(TEST_DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    conn.close()
    migrate(TEST_DATABASE_URL, seed=True, log=lambda *_: None)


class AuthClient:
    """Тестовый клиент, который добавляет заголовок Authorization ко всем запросам."""

    def __init__(self, client, token):
        self._client, self.token = client, token

    def __getattr__(self, method):
        def call(*args, headers=None, **kwargs):
            headers = {"Authorization": f"Bearer {self.token}", **(headers or {})}
            return getattr(self._client, method)(*args, headers=headers, **kwargs)
        return call


@pytest.fixture
def app():
    reset_database()
    return create_app({"TESTING": True, "DATABASE_URL": TEST_DATABASE_URL})


@pytest.fixture
def anon(app):
    return app.test_client()


@pytest.fixture
def login(anon):
    def _login(email):
        r = anon.post("/api/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.get_json()
        return AuthClient(anon, r.get_json()["token"])
    return _login


@pytest.fixture
def client(login):
    """Администратор — для тестов, где права не важны."""
    return login("orlova@studio.local")


@pytest.fixture
def producer(login):
    return login("kuznetsov@studio.local")   # продюсер проектов 1 и 3


@pytest.fixture
def editor(login):
    return login("volkov@studio.local")      # монтажёр, исполнитель задач 4, 7, 8
