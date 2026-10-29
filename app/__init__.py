import os

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from . import db, observability, security
from .api import api
from .errors import register_error_handlers
from .pages import pages

__version__ = "2.0.0"


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        VERSION=__version__,
        DATABASE_URL=os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/studio"),
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-secret"),
        TOKEN_TTL=int(os.environ.get("TOKEN_TTL", 8 * 3600)),        # срок действия токена, с
        METRICS_TOKEN=os.environ.get("METRICS_TOKEN") or None,
        SLOW_REQUEST_MS=int(os.environ.get("SLOW_REQUEST_MS", 500)),  # NFR-01
        MAX_CONTENT_LENGTH=64 * 1024,                                 # защита от слишком больших тел запросов
        JSON_AS_ASCII=False,
    )
    if config:
        app.config.update(config)
    app.json.ensure_ascii = False
    if not app.config.get("TESTING") and app.config["SECRET_KEY"] in ("dev-only-secret", "change-me-secret") \
            and os.environ.get("APP_ENV") == "production":
        raise RuntimeError("SECRET_KEY не задан: укажите его в .env")

    observability.configure_logging(os.environ.get("LOG_LEVEL", "INFO"), os.environ.get("LOG_FORMAT", "text"))
    # за обратным прокси nginx: реальный IP клиента и схема берутся из X-Forwarded-*
    if int(os.environ.get("TRUSTED_PROXIES", 0)):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=int(os.environ["TRUSTED_PROXIES"]), x_proto=1)

    db.init_app(app)
    observability.init_app(app)
    security.init_app(app)
    app.register_blueprint(pages)
    app.register_blueprint(api, url_prefix="/api")
    register_error_handlers(app)
    return app
