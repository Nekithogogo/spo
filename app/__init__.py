import logging
import os

from flask import Flask

from . import db
from .api import api
from .errors import register_error_handlers
from .pages import pages


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        DATABASE_URL=os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/studio"),
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-secret"),
        JSON_AS_ASCII=False,
    )
    if config:
        app.config.update(config)
    app.json.ensure_ascii = False

    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    db.init_app(app)
    app.register_blueprint(pages)
    app.register_blueprint(api, url_prefix="/api")
    register_error_handlers(app)
    return app
