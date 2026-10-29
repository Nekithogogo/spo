# Подготовка сервера и выпуск версии

Целевая платформа: виртуальный сервер (VPS) **Ubuntu 24.04 LTS**, 2 vCPU, 2 ГБ RAM, 20 ГБ SSD,
приложение запускается в контейнерах Docker Compose. Учебный стенд повторяет ту же схему на локальной машине
(порты 8080/8443 на 127.0.0.1 и самоподписанный сертификат).

## 1. Базовая настройка ОС (под root, один раз)

```bash
apt update && apt full-upgrade -y
apt install -y ca-certificates curl git ufw fail2ban unattended-upgrades
dpkg-reconfigure -f noninteractive unattended-upgrades     # автоматические обновления безопасности
timedatectl set-timezone Europe/Moscow

# пользователь для выпуска версий; вход только по ключу
adduser --disabled-password --gecos "" deploy
mkdir -p /home/deploy/.ssh && cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh && chmod 700 /home/deploy/.ssh && chmod 600 /home/deploy/.ssh/authorized_keys

# SSH: без пароля и без входа под root
sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication no/; s/^#\?PermitRootLogin .*/PermitRootLogin no/' /etc/ssh/sshd_config
systemctl restart ssh

# брандмауэр: только SSH, HTTP и HTTPS
ufw default deny incoming && ufw default allow outgoing
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp
ufw --force enable
systemctl enable --now fail2ban                             # блокировка перебора паролей SSH
```

## 2. Docker

```bash
curl -fsSL https://get.docker.com | sh
usermod -aG docker deploy
cat > /etc/docker/daemon.json <<'JSON'
{ "log-driver": "json-file", "log-opts": { "max-size": "10m", "max-file": "5" }, "live-restore": true }
JSON
systemctl restart docker
```

Важно: Docker публикует порты в обход правил ufw, поэтому в `docker-compose.yml` наружу открыт только
прокси (80/443), а порты БД и приложения не публикуются вообще.

## 3. Код, конфигурация, сертификат (под deploy)

```bash
sudo mkdir -p /opt/studio && sudo chown deploy: /opt/studio
git clone https://github.com/Nekithogogo/spo.git /opt/studio && cd /opt/studio
cp .env.example .env && chmod 600 .env
# в .env: свои пароли и SECRET_KEY (openssl rand -hex 32), HTTP_BIND=0.0.0.0, HTTP_PORT=80, HTTPS_PORT=443,
#         SEED_FLAG=--no-seed (рабочая БД без демонстрационных данных)
```

Сертификат Let's Encrypt для домена (порт 80 должен быть свободен на время выпуска сертификата):

```bash
sudo apt install -y certbot
sudo certbot certonly --standalone -d studio.example.ru
mkdir -p deploy/nginx/certs
sudo cp /etc/letsencrypt/live/studio.example.ru/{fullchain,privkey}.pem deploy/nginx/certs/
# продление: certbot renew --deploy-hook "cp ... && docker compose -f /opt/studio/docker-compose.yml restart proxy"
```

Без домена (учебный стенд): `./deploy/gen-cert.sh <имя или IP>` создаёт самоподписанный сертификат.

## 4. Первый запуск и учётная запись администратора

```bash
docker compose up -d --build
docker compose run --rm -T migrate python -m app.manage set-password admin@studio.local   # пароль из stdin
./deploy/smoke.sh https://127.0.0.1
```

## 5. Регулярные задачи (crontab -e под deploy)

```
0 3 * * *   cd /opt/studio && ./deploy/backup.sh  >> /var/log/studio/backup.log 2>&1
*/5 * * * * cd /opt/studio && ./deploy/monitor.sh >> /var/log/studio/monitor.log 2>&1
```

Копии из `backups/` раз в сутки переносятся за пределы сервера (`rsync`/объектное хранилище), иначе
потеря диска уничтожит и БД, и её резервные копии.

## 6. Выпуск новой версии

```bash
cd /opt/studio
./deploy/release.sh 2.0.0       # backup → сборка → миграции → замена app → smoke; при ошибке откат
docker compose ps               # все сервисы healthy
```

Мониторинг: `docker compose --profile monitoring up -d`, интерфейс Prometheus открывается через
SSH-туннель: `ssh -L 9090:127.0.0.1:9090 deploy@сервер`, затем http://127.0.0.1:9090/alerts.
