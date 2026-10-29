"""Спецификация OpenAPI 3.0 (файл app/openapi.yaml) и страница Swagger UI."""
from functools import lru_cache
from pathlib import Path

import yaml
from flask import current_app

SPEC_FILE = Path(__file__).resolve().parent / "openapi.yaml"
SWAGGER_UI = "/static/vendor/swagger-ui"  # swagger-ui-dist 5.17.14, хранится локально: без внешних CDN


@lru_cache(maxsize=1)
def _load():
    return yaml.safe_load(SPEC_FILE.read_text(encoding="utf-8"))


def spec():
    data = dict(_load())
    data["info"] = {**data["info"], "version": current_app.config["VERSION"]}
    return data


def spec_yaml():
    return SPEC_FILE.read_text(encoding="utf-8")


def swagger_page():
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>API · Видеостудия</title>
<link rel="stylesheet" href="{SWAGGER_UI}/swagger-ui.css"></head>
<body><div id="swagger"></div>
<script src="{SWAGGER_UI}/swagger-ui-bundle.js"></script>
<script src="/static/js/swagger-init.js"></script>
</body></html>"""
