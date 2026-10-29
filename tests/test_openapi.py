"""Спецификация OpenAPI корректна и описывает все маршруты API (ПР №11)."""
import re

from openapi_spec_validator import validate


def test_spec_is_valid_openapi(anon):
    spec = anon.get("/api/openapi.json").get_json()
    validate(spec)
    assert spec["info"]["version"] == "2.0.0"


def test_every_route_is_documented(app, anon):
    spec = anon.get("/api/openapi.json").get_json()
    documented = {(path, method.upper()) for path, ops in spec["paths"].items()
                  for method in ops if method != "parameters"}
    actual = set()
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith("/api/"):
            continue
        path = re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", rule.rule[len("/api"):])
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            actual.add((path, method))
    assert actual == documented


def test_swagger_ui_page(anon):
    r = anon.get("/api/docs")
    assert r.status_code == 200 and "swagger-ui-bundle.js" in r.get_data(as_text=True)
    assert "script-src 'self';" in r.headers["Content-Security-Policy"]
