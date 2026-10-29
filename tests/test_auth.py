"""Вход, токены, роли и защита API (ПР №12)."""
import pytest

from tests.conftest import PASSWORD, AuthClient


def test_api_requires_token(anon):
    r = anon.get("/api/projects")
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"
    assert r.get_json()["error"] == "Требуется вход в систему"


@pytest.mark.parametrize("path", ["/api/health", "/api/openapi.json", "/api/docs", "/login", "/"])
def test_public_resources(anon, path):
    assert anon.get(path).status_code == 200


def test_login_and_me(anon):
    r = anon.post("/api/auth/login", json={"email": "Kuznetsov@Studio.local ", "password": PASSWORD})
    assert r.status_code == 200
    body = r.get_json()
    assert body["token_type"] == "Bearer" and body["expires_in"] == 8 * 3600
    assert body["user"] == {"id": 2, "full_name": "Кузнецов Дмитрий Игоревич",
                            "email": "kuznetsov@studio.local", "role": "producer"}
    assert "password_hash" not in body["user"]
    me = AuthClient(anon, body["token"]).get("/api/auth/me")
    assert me.status_code == 200 and me.get_json()["role"] == "producer"


def test_wrong_password_same_message_as_unknown_user(anon):
    r1 = anon.post("/api/auth/login", json={"email": "orlova@studio.local", "password": "wrong-pass"})
    r2 = anon.post("/api/auth/login", json={"email": "nobody@studio.local", "password": "wrong-pass"})
    assert r1.status_code == r2.status_code == 401
    assert r1.get_json() == r2.get_json() == {"error": "Неверный e-mail или пароль"}


def test_login_validation(anon):
    r = anon.post("/api/auth/login", json={})
    assert r.status_code == 400 and set(r.get_json()["details"]) == {"email", "password"}


def test_bruteforce_lockout(anon):
    for _ in range(5):
        assert anon.post("/api/auth/login", json={"email": "belova@studio.local", "password": "x" * 8}).status_code == 401
    r = anon.post("/api/auth/login", json={"email": "belova@studio.local", "password": PASSWORD})
    assert r.status_code == 429  # даже верный пароль не принимается до окончания блокировки
    assert r.headers["Retry-After"] == "900"
    # блокировка касается только этого e-mail
    assert anon.post("/api/auth/login", json={"email": "smirnov@studio.local", "password": PASSWORD}).status_code == 200


def test_tampered_and_expired_token(app, anon, client):
    assert AuthClient(anon, client.token + "x").get("/api/projects").status_code == 401
    app.config["TOKEN_TTL"] = -1
    r = client.get("/api/projects")
    assert r.status_code == 401 and "истёк" in r.get_json()["error"]


def test_logout_revokes_token(client):
    assert client.post("/api/auth/logout").status_code == 204
    r = client.get("/api/projects")
    assert r.status_code == 401 and r.get_json()["error"] == "Сеанс завершён, войдите снова"


def test_deactivated_user_loses_access(app, client, editor):
    from app.db import execute
    with app.app_context():
        execute("UPDATE users SET is_active = false WHERE id = 5", returning=False)
    assert editor.get("/api/projects").status_code == 401


def test_editor_cannot_create_project(editor):
    r = editor.post("/api/projects", json={"title": "Чужой проект", "client_id": 1})
    assert r.status_code == 403
    assert r.get_json()["error"] == "Недостаточно прав для этого действия"


def test_producer_manages_only_own_projects(producer):
    assert producer.patch("/api/projects/1", json={"budget": 360000}).status_code == 200   # свой
    r = producer.patch("/api/projects/2", json={"budget": 1})                              # проект Лебедевой
    assert r.status_code == 403


def test_producer_creates_project_for_himself(producer):
    r = producer.post("/api/projects", json={"title": "Промо", "client_id": 1})
    assert r.status_code == 201 and r.get_json()["producer_id"] == 2


def test_admin_only_endpoints(producer, client):
    assert producer.delete("/api/projects/4").status_code == 403
    assert producer.post("/api/users", json={}).status_code == 403
    assert client.delete("/api/projects/4").status_code == 204
    assert client.get("/api/projects/4").status_code == 404


def test_admin_creates_user_who_can_login(client, anon):
    r = client.post("/api/users", json={"full_name": "Новиков Илья", "email": "novikov@studio.local",
                                        "role": "operator", "password": "secret-123"})
    assert r.status_code == 201 and "password" not in r.get_json()
    assert anon.post("/api/auth/login", json={"email": "novikov@studio.local", "password": "secret-123"}).status_code == 200
    dup = client.post("/api/users", json={"full_name": "X", "email": "NOVIKOV@studio.local", "password": "secret-123"})
    assert dup.status_code == 400 and "email" in dup.get_json()["details"]


def test_password_stored_as_hash(app):
    from app.db import query
    with app.app_context():
        row = query("SELECT password_hash FROM users WHERE id = 1", one=True)
    assert row["password_hash"].startswith("scrypt:") and PASSWORD not in row["password_hash"]


def test_security_headers(anon):
    r = anon.get("/")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert anon.get("/api/health").headers["Cache-Control"] == "no-store"


def test_body_must_be_json(client):
    r = client.post("/api/projects", data="title=x", content_type="application/x-www-form-urlencoded")
    assert r.status_code == 415


def test_too_large_body(client):
    r = client.post("/api/projects", json={"title": "x" * 70000, "client_id": 1})
    assert r.status_code == 413 and r.is_json


def test_sql_injection_in_search_is_harmless(client):
    r = client.get("/api/projects", query_string={"q": "'; DROP TABLE projects; --"})
    assert r.status_code == 200 and r.get_json() == []
    assert len(client.get("/api/projects").get_json()) == 4
