#!/bin/sh
# Smoke-тест развёрнутого приложения (версия 2.0).
# Использование: ./deploy/smoke.sh [https://127.0.0.1:8443] [email] [пароль]
BASE="${1:-https://127.0.0.1:8443}"
EMAIL="${2:-${SMOKE_EMAIL:-orlova@studio.local}}"
PASSWORD="${3:-${SMOKE_PASSWORD:-studio2026}}"
CURL="curl -sk --max-time 10"
fail=0

check() {  # check <описание> <ожидаемый код> <curl-аргументы...>
    name="$1"; expected="$2"; shift 2
    code=$($CURL -o /dev/null -w "%{http_code}" "$@")
    if [ "$code" = "$expected" ]; then echo "OK   $name ($code)"; else echo "FAIL $name: ожидали $expected, получили $code"; fail=1; fi
}

check "health"                       200 "$BASE/api/health"
check "версия"                       200 "$BASE/api/openapi.json"
check "главная страница"             200 "$BASE/"
check "API без входа"                401 "$BASE/api/projects"
check "метрики снаружи закрыты"      404 "$BASE/api/metrics"

TOKEN=$($CURL -X POST -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" "$BASE/api/auth/login" \
    | sed -n 's/.*"token": *"\([^"]*\)".*/\1/p')
if [ -z "$TOKEN" ]; then echo "FAIL вход $EMAIL"; exit 1; fi
echo "OK   вход $EMAIL"
AUTH="Authorization: Bearer $TOKEN"
check "список проектов"              200 -H "$AUTH" "$BASE/api/projects"
check "несуществующий проект"        404 -H "$AUTH" "$BASE/api/projects/999999"
check "создание с ошибкой валидации" 400 -X POST -H "$AUTH" -H "Content-Type: application/json" -d '{"title":""}' "$BASE/api/projects"
check "отчёт о загрузке"             200 -H "$AUTH" "$BASE/api/reports/workload"

$CURL -s "$BASE/api/health"; echo
exit $fail
