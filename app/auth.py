"""Аутентификация по токену (Authorization: Bearer) и проверка ролей (FR-11).

Токен подписан SECRET_KEY (itsdangerous) и содержит id сотрудника и token_version.
Срок жизни ограничен TOKEN_TTL; выход из системы увеличивает token_version, и все
выданные ранее токены этого сотрудника перестают приниматься.
"""
from functools import wraps

from flask import current_app, g, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash

from .db import execute, query
from .errors import ApiError, ValidationError

MANAGERS = ("admin", "producer")
MAX_FAILS_PER_EMAIL = 5
MAX_FAILS_PER_IP = 20
LOCK_MINUTES = 15
# сравниваем пароль с фиктивным хешем, чтобы время ответа не выдавало, существует ли e-mail
_DUMMY_HASH = "scrypt:32768:8:1$dummysaltdummysa$" + "0" * 128


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="studio-api-token")


def issue_token(user):
    return _serializer().dumps({"uid": user["id"], "v": user["token_version"]})


def _client_ip():
    return request.remote_addr or "unknown"


def _too_many_failures(email, ip):
    row = query(
        """SELECT count(*) FILTER (WHERE lower(email) = lower(%s)) AS by_email,
                  count(*) FILTER (WHERE ip = %s) AS by_ip
           FROM login_attempts
           WHERE NOT success AND created_at > now() - make_interval(mins => %s)""",
        (email, ip, LOCK_MINUTES),
        one=True,
    )
    return row["by_email"] >= MAX_FAILS_PER_EMAIL or row["by_ip"] >= MAX_FAILS_PER_IP


def login(data):
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    errors = {}
    if not email:
        errors["email"] = "Укажите e-mail"
    if not password:
        errors["password"] = "Укажите пароль"
    if errors:
        raise ValidationError(errors)

    ip = _client_ip()
    if _too_many_failures(email, ip):
        raise ApiError(429, f"Слишком много неудачных попыток входа. Повторите через {LOCK_MINUTES} минут",
                       headers={"Retry-After": str(LOCK_MINUTES * 60)})

    user = query(
        "SELECT id, full_name, email, role, is_active, password_hash, token_version FROM users WHERE lower(email) = %s",
        (email,),
        one=True,
    )
    ok = check_password_hash(user["password_hash"] if user and user["password_hash"] else _DUMMY_HASH, password)
    ok = ok and user is not None and user["is_active"]
    execute("INSERT INTO login_attempts (email, ip, success) VALUES (%s, %s, %s)", (email, ip, ok), returning=False)
    if not ok:
        current_app.logger.warning("login failed for %s from %s", email, ip)
        raise ApiError(401, "Неверный e-mail или пароль")

    execute("UPDATE users SET last_login_at = now() WHERE id = %s", (user["id"],), returning=False)
    return {
        "token": issue_token(user),
        "token_type": "Bearer",
        "expires_in": current_app.config["TOKEN_TTL"],
        "user": public_user(user),
    }


def logout(user):
    execute("UPDATE users SET token_version = token_version + 1 WHERE id = %s", (user["id"],), returning=False)


def public_user(user):
    return {k: user[k] for k in ("id", "full_name", "email", "role")}


def load_current_user():
    """Разбирает заголовок Authorization; при ошибке — 401."""
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise ApiError(401, "Требуется вход в систему", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = _serializer().loads(token, max_age=current_app.config["TOKEN_TTL"])
    except SignatureExpired:
        raise ApiError(401, "Срок действия входа истёк, войдите снова", headers={"WWW-Authenticate": "Bearer"})
    except BadSignature:
        raise ApiError(401, "Недействительный токен", headers={"WWW-Authenticate": "Bearer"})
    user = query(
        "SELECT id, full_name, email, role, is_active, token_version FROM users WHERE id = %s",
        (payload.get("uid"),),
        one=True,
    )
    if user is None or not user["is_active"] or user["token_version"] != payload.get("v"):
        raise ApiError(401, "Сеанс завершён, войдите снова", headers={"WWW-Authenticate": "Bearer"})
    g.user = user
    return user


def current_user():
    return g.get("user")


def require_roles(*roles):
    """Декоратор маршрута: доступ только перечисленным ролям."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user["role"] not in roles:
                raise ApiError(403, "Недостаточно прав для этого действия")
            return view(*args, **kwargs)
        return wrapper
    return decorator


def ensure_can_manage(project):
    """Изменять проект может администратор или продюсер этого проекта."""
    user = current_user()
    if user["role"] == "admin":
        return
    if user["role"] == "producer" and project["producer_id"] == user["id"]:
        return
    raise ApiError(403, "Изменять проект может только его продюсер или администратор")
