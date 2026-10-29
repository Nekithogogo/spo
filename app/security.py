"""Заголовки безопасности HTTP-ответов (ПР №12)."""
from flask import request

CSP = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
# Swagger UI задаёт часть стилей встроенными атрибутами, поэтому только для /api/docs разрешён 'unsafe-inline' в style-src
CSP_DOCS = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'"


def _headers(response):
    h = response.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Referrer-Policy", "no-referrer")
    h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    h.setdefault("Content-Security-Policy", CSP_DOCS if request.path == "/api/docs" else CSP)
    if request.path.startswith("/api/"):
        h.setdefault("Cache-Control", "no-store")  # ответы API с персональными данными не кэшируются
    return response


def init_app(app):
    app.after_request(_headers)
