#!/bin/sh
# Выпуск новой версии: резервная копия -> сборка образа -> миграции -> замена приложения -> smoke-тест.
# При неудаче приложение возвращается на предыдущую версию образа.
# Использование: ./deploy/release.sh 2.0.0      (тег в git: v2.0.0; SKIP_GIT=1 — собрать из текущей копии)
set -eu
cd "$(dirname "$0")/.."
NEW="${1:?укажите версию, например 2.0.0}"
PREV=$(cat deploy/.release 2>/dev/null || echo "")
HTTPS_PORT=$(sed -n 's/^HTTPS_PORT=//p' .env); HTTPS_PORT=${HTTPS_PORT:-8443}
log() { echo "[release $(date +%H:%M:%S)] $*"; }

rollback() {
    log "ОШИБКА: $1"
    if [ -n "$PREV" ]; then
        log "откат приложения на версию $PREV"
        APP_VERSION="$PREV" docker compose up -d --no-deps app
    fi
    log "миграции 0002+ только добавляют объекты, предыдущая версия работает с новой схемой;"
    log "если нужно вернуть и данные: ./deploy/restore.sh <последняя копия из backups/>"
    exit 1
}

if [ "${SKIP_GIT:-0}" != "1" ]; then
    log "получение тега v$NEW"
    git fetch --tags origin
    git checkout --quiet "v$NEW"
fi

log "резервная копия перед выпуском"
./deploy/backup.sh

log "сборка образа studio-app:$NEW"
APP_VERSION="$NEW" docker compose build migrate

log "миграции схемы"
APP_VERSION="$NEW" SEED_FLAG=--no-seed docker compose run --rm migrate || rollback "миграции не применены (транзакция откачена)"

log "замена приложения"
APP_VERSION="$NEW" docker compose up -d --no-deps app
for i in $(seq 1 30); do
    status=$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q app)")
    [ "$status" = "healthy" ] && break
    sleep 2
done
[ "$status" = "healthy" ] || rollback "приложение не прошло health-check"
docker compose up -d proxy
for i in $(seq 1 30); do
    curl -sk --max-time 2 -o /dev/null "https://127.0.0.1:$HTTPS_PORT/api/health" && break
    sleep 1
done

log "smoke-тест"
# учётная запись для проверки: SMOKE_EMAIL / SMOKE_PASSWORD из .env
SMOKE_EMAIL=$(sed -n 's/^SMOKE_EMAIL=//p' .env) SMOKE_PASSWORD=$(sed -n 's/^SMOKE_PASSWORD=//p' .env) \
    ./deploy/smoke.sh "https://127.0.0.1:$HTTPS_PORT" || rollback "smoke-тест не пройден"

echo "$NEW" > deploy/.release
log "версия $NEW выпущена (предыдущая: ${PREV:-нет})"
