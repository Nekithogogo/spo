#!/bin/sh
# Самоподписанный сертификат для тестового стенда (на сервере с доменом — Let's Encrypt, см. deploy/SERVER.md).
# Использование: ./deploy/gen-cert.sh [имя_хоста]
set -e
HOST="${1:-localhost}"
DIR="$(dirname "$0")/nginx/certs"
mkdir -p "$DIR"
if [ -f "$DIR/fullchain.pem" ]; then echo "сертификат уже есть: $DIR"; exit 0; fi
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
    -subj "/CN=$HOST" -addext "subjectAltName=DNS:$HOST,DNS:localhost,IP:127.0.0.1" \
    -keyout "$DIR/privkey.pem" -out "$DIR/fullchain.pem"
chmod 644 "$DIR/privkey.pem"   # читает процесс nginx в контейнере; каталог закрыт правами на хосте
echo "создан самоподписанный сертификат для $HOST в $DIR"
