#!/bin/sh
# Резервная копия БД: pg_dump в формате custom, проверка читаемости, контрольная сумма, ротация.
# Использование: ./deploy/backup.sh        (cron: 0 3 * * *  cd /opt/studio && ./deploy/backup.sh)
set -eu
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
DIR="${BACKUP_DIR:-backups}"
KEEP="${BACKUP_KEEP:-14}"
mkdir -p "$DIR"
chmod 700 "$DIR"

STAMP=$(date +%Y%m%d_%H%M%S)
FILE="$DIR/studio_${STAMP}.dump"
START=$(date +%s)

docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$FILE.part"
docker compose exec -T db pg_restore --list < "$FILE.part" > /dev/null   # копия читается целиком
mv "$FILE.part" "$FILE"
chmod 600 "$FILE"
sha256sum "$FILE" > "$FILE.sha256"

# ротация: храним KEEP последних копий
ls -1t "$DIR"/studio_*.dump | tail -n +$((KEEP + 1)) | while read -r old; do rm -f "$old" "$old.sha256"; done

date -Iseconds > "$DIR/last_success"
echo "backup ok: $FILE ($(du -h "$FILE" | cut -f1), $(( $(date +%s) - START )) с), хранится копий: $(ls -1 "$DIR"/studio_*.dump | wc -l)"
