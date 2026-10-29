#!/bin/sh
# Внешняя проверка стенда (cron каждые 5 минут):  */5 * * * * cd /opt/studio && ./deploy/monitor.sh
# Проверяет: health по HTTPS, состояние контейнеров, место на диске, свежесть резервной копии.
# При проблеме пишет в системный журнал (logger) и, если задан ALERT_WEBHOOK, отправляет оповещение.
cd "$(dirname "$0")/.."
HTTPS_PORT=$(sed -n 's/^HTTPS_PORT=//p' .env); HTTPS_PORT=${HTTPS_PORT:-8443}
ALERT_WEBHOOK=$(sed -n 's/^ALERT_WEBHOOK=//p' .env)
problems=""
add() { problems="${problems}${problems:+; }$1"; }

health=$(curl -sk --max-time 5 -w " %{http_code}" "https://127.0.0.1:$HTTPS_PORT/api/health")
code=${health##* }
body=$(printf "%s" "${health% *}" | tr -d "\n" | cut -c1-100)
[ "$code" = "200" ] || add "health $code: $body"

for svc in db app proxy; do
    id=$(docker compose ps -aq "$svc")
    st=$([ -n "$id" ] && docker inspect -f '{{.State.Status}}/{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$id")
    case "$st" in running/healthy) ;; *) add "контейнер $svc: ${st:-нет}";; esac
done

disk=$(df -P . | awk 'NR==2 {gsub("%","",$5); print $5}')
[ "$disk" -lt 85 ] || add "диск занят на ${disk}%"

if [ -f backups/last_success ]; then
    age=$(( ($(date +%s) - $(date -d "$(cat backups/last_success)" +%s)) / 3600 ))
    [ "$age" -le 26 ] || add "последней резервной копии ${age} ч"
else
    add "резервных копий нет"
fi

if [ -z "$problems" ]; then
    echo "$(date -Iseconds) OK ${health% *}"
    exit 0
fi
echo "$(date -Iseconds) ALERT $problems"
logger -t studio-monitor "ALERT $problems" 2>/dev/null || true
if [ -n "$ALERT_WEBHOOK" ]; then
    curl -s --max-time 5 -H "Content-Type: application/json" \
        -d "{\"text\":\"Видеостудия: $problems\"}" "$ALERT_WEBHOOK" > /dev/null || true
fi
exit 1
