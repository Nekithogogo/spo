#!/bin/sh
# Smoke-тест развёрнутого приложения. Использование: ./deploy/smoke.sh [http://127.0.0.1:8080]
BASE="${1:-http://127.0.0.1:8080}"
fail=0

check() {  # check <описание> <ожидаемый код> <curl-аргументы...>
    name="$1"; expected="$2"; shift 2
    code=$(curl -s -o /dev/null -w "%{http_code}" "$@")
    if [ "$code" = "$expected" ]; then echo "OK   $name ($code)"; else echo "FAIL $name: ожидали $expected, получили $code"; fail=1; fi
}

check "health"                       200 "$BASE/api/health"
check "главная страница"             200 "$BASE/"
check "список проектов"              200 "$BASE/api/projects"
check "карточка проекта"             200 "$BASE/api/projects/1"
check "несуществующий проект"        404 "$BASE/api/projects/999999"
check "создание с ошибкой валидации" 400 -X POST -H "Content-Type: application/json" -d '{"title":""}' "$BASE/api/projects"

exit $fail
