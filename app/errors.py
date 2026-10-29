import logging

import psycopg2
from flask import jsonify, request
from werkzeug.exceptions import HTTPException

log = logging.getLogger("studio.errors")


class ValidationError(Exception):
    def __init__(self, errors):
        super().__init__("validation failed")
        self.errors = errors


class ApiError(Exception):
    """Ошибка с HTTP-кодом и сообщением для клиента (401, 403, 409, 412, 429...)."""

    def __init__(self, status, message, details=None, headers=None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.details = details
        self.headers = headers or {}


class NotFound(Exception):
    def __init__(self, message="Объект не найден"):
        super().__init__(message)
        self.message = message


def error_response(status, message, details=None):
    body = {"error": message}
    if details:
        body["details"] = details
    return jsonify(body), status


def register_error_handlers(app):
    @app.errorhandler(ValidationError)
    def _validation(e):
        return error_response(400, "Ошибка валидации", e.errors)

    @app.errorhandler(ApiError)
    def _api_error(e):
        body, status = error_response(e.status, e.message, e.details)
        return body, status, e.headers

    @app.errorhandler(NotFound)
    def _not_found(e):
        return error_response(404, e.message)

    @app.errorhandler(psycopg2.IntegrityError)
    def _integrity(e):
        # нарушение ограничения БД, не пойманное валидацией (например, гонка)
        log.warning("integrity error on %s %s: %s", request.method, request.path, e.pgcode)
        return error_response(409, "Конфликт данных: нарушено ограничение БД")

    @app.errorhandler(psycopg2.OperationalError)
    def _db_down(e):
        log.error("database unavailable: %s", e)
        return error_response(503, "База данных недоступна")

    @app.errorhandler(HTTPException)
    def _http(e):
        if request.path.startswith("/api/"):
            messages = {
                404: "Ресурс не найден",
                405: "Метод не поддерживается",
                413: "Слишком большой запрос",
                415: "Ожидается Content-Type: application/json",
            }
            return error_response(e.code, messages.get(e.code, e.name))
        return e

    @app.errorhandler(Exception)
    def _unexpected(e):
        log.exception("unhandled error on %s %s", request.method, request.path)
        return error_response(500, "Внутренняя ошибка сервера")
