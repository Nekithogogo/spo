# Видеостудия/продакшн — управление проектами

Учебная информационная система для видеостудии: учёт проектов (заказов на видеопроизводство), заказчиков, съёмочной группы, задач по этапам производства и оборудования.

Монолитное веб-приложение: **Python 3 + Flask**, **PostgreSQL 16**, HTML-шаблоны Jinja2 и JavaScript (fetch API). Развёртывание: **Docker Compose** + gunicorn.

## Возможности (версия 2.0)

- вход по e-mail и паролю, роли: администратор, продюсер, режиссёр, оператор, монтажёр;
- список проектов с фильтром по статусу, поиском и постраничным выводом;
- создание и редактирование проекта, перевод по этапам «Новый → Препродакшн → Съёмка → Постпродакшн → Согласование → Сдан» с историей;
- задачи по этапам: добавление, редактирование, смена статуса исполнителем, удаление;
- съёмочная группа проекта и бронирование оборудования без пересечений по времени;
- отчёт о загрузке сотрудников;
- REST API 2.0 (31 операция) со спецификацией OpenAPI и Swagger UI;
- миграции БД, HTTPS через nginx, метрики Prometheus, резервное копирование и восстановление.

История изменений: [CHANGELOG.md](CHANGELOG.md).

## Структура репозитория

```
app/                   приложение Flask
  __init__.py          фабрика приложения, конфигурация из переменных среды
  auth.py              вход, токены, роли
  api.py               REST-маршруты /api/...
  services.py          бизнес-операции и валидация
  manage.py            миграции БД и служебные команды
  observability.py     журнал JSON, метрики, health-check
  security.py          заголовки безопасности
  openapi.yaml         спецификация API
  db.py, errors.py, pages.py, templates/, static/
db/
  migrations/          0001_initial … 0004_tasks_and_reports
  seed.sql             демонстрационные данные (пароль studio2026)
  03_app_role.sh       роль приложения с минимальными правами (Docker)
  04_checks.sql        проверочные запросы и проверка ограничений
deploy/                nginx, сертификат, release/backup/restore/monitor/smoke, SERVER.md
monitoring/            конфигурация и правила оповещений Prometheus
tests/                 65 автотестов (pytest, реальная БД)
docs/                  диаграммы, скриншоты, отчёты по практическим работам
```

## Локальный запуск (среда разработки)

Нужны Python 3.11+ и PostgreSQL 16.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

createdb studio
export DATABASE_URL=postgresql://postgres:ПАРОЛЬ@localhost:5432/studio   # Windows: set DATABASE_URL=...
python -m app.manage migrate --seed  # миграции + демонстрационные данные
python -m app.manage status          # какие миграции применены
flask --app wsgi run                 # http://127.0.0.1:5000, вход: kuznetsov@studio.local / studio2026
```

Тесты (отдельная БД, пересоздаётся перед каждым тестом):

```bash
createdb studio_test
export TEST_DATABASE_URL=postgresql://postgres:ПАРОЛЬ@localhost:5432/studio_test
pytest -q
```

## Тестовое окружение (Docker)

```bash
cp .env.example .env                 # задать свои пароли
./deploy/gen-cert.sh                 # самоподписанный сертификат для HTTPS
docker compose up -d --build         # db → migrate → app → proxy
./deploy/smoke.sh                    # https://127.0.0.1:8443
docker compose --profile monitoring up -d   # Prometheus: http://127.0.0.1:9090
```

Выпуск версии: `./deploy/release.sh 2.0.0`, резервная копия: `./deploy/backup.sh`,
восстановление: `./deploy/restore.sh backups/<файл>.dump`, проверка стенда: `./deploy/monitor.sh`.
Подготовка рабочего сервера описана в [deploy/SERVER.md](deploy/SERVER.md).

## REST API

Документация: `/api/docs` (Swagger UI), спецификация `/api/openapi.json`. Все ресурсы, кроме health и
документации, требуют заголовок `Authorization: Bearer <токен>` из `POST /api/auth/login`.

## Отчёты

Отчёты по практическим работам лежат в `docs/reports/` (исходники `prNN.md`, сборка в Word: `python docs/reports/build.py`).
