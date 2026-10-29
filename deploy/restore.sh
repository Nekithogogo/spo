#!/bin/sh
# Восстановление БД из резервной копии с последующей проверкой.
# Использование: ./deploy/restore.sh backups/studio_YYYYmmdd_HHMMSS.dump [--yes]
set -eu
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
FILE="${1:?укажите файл резервной копии}"
[ -f "$FILE" ] || { echo "нет файла $FILE"; exit 1; }
if [ -f "$FILE.sha256" ]; then sha256sum -c "$FILE.sha256"; fi
if [ "${2:-}" != "--yes" ]; then
    printf "Текущая БД %s будет заменена копией %s. Продолжить? [y/N] " "$POSTGRES_DB" "$FILE"
    read -r answer; [ "$answer" = "y" ] || exit 1
fi
START=$(date +%s)
PSQL="docker compose exec -T db psql -v ON_ERROR_STOP=1 -U $POSTGRES_USER"

echo "1/5 остановка приложения"
docker compose stop app proxy

echo "2/5 пересоздание БД"
$PSQL -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$POSTGRES_DB' AND pid <> pg_backend_pid();" > /dev/null
$PSQL -d postgres -c "DROP DATABASE IF EXISTS \"$POSTGRES_DB\";" -c "CREATE DATABASE \"$POSTGRES_DB\";"
$PSQL -d postgres -c "REVOKE ALL ON DATABASE \"$POSTGRES_DB\" FROM PUBLIC; GRANT CONNECT ON DATABASE \"$POSTGRES_DB\" TO studio_app;"

echo "3/5 загрузка копии"
docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --exit-on-error < "$FILE"

echo "4/5 миграции (если копия старше текущей версии схемы)"
SEED_FLAG=--no-seed docker compose run --rm migrate

echo "5/5 запуск и проверка"
docker compose up -d app proxy
for i in $(seq 1 30); do
    [ "$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q app)")" = "healthy" ] && break
    sleep 2
done
for i in $(seq 1 30); do curl -sk --max-time 2 -o /dev/null "https://127.0.0.1:${HTTPS_PORT:-8443}/api/health" && break; sleep 1; done
SMOKE_EMAIL="${SMOKE_EMAIL:-}" SMOKE_PASSWORD="${SMOKE_PASSWORD:-}" ./deploy/smoke.sh "https://127.0.0.1:${HTTPS_PORT:-8443}" > /dev/null \
    && echo "smoke-тест пройден" || { echo "smoke-тест НЕ пройден"; exit 1; }
echo "restore ok за $(( $(date +%s) - START )) с"
