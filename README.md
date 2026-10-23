# Видеостудия/продакшн — управление проектами

Учебная информационная система для видеостудии: учёт проектов (заказов на видеопроизводство), заказчиков, съёмочной группы, задач по этапам производства и оборудования.

Монолитное веб-приложение: **Python 3 + Flask**, **PostgreSQL 16**, HTML-шаблоны Jinja2 и JavaScript (fetch API). Развёртывание: **Docker Compose** + gunicorn.

## Возможности первой версии (MVP)

- список проектов с фильтром по статусу и прогрессом задач;
- создание проекта с проверкой данных на сервере;
- карточка проекта: заказчик, продюсер, бюджет, сроки, съёмочная группа;
- задачи по этапам «Препродакшн → Съёмка → Постпродакшн → Согласование», добавление задачи и смена её статуса;
- REST API в формате JSON, справочники заказчиков, сотрудников и оборудования.

## Структура репозитория

```
app/                 приложение Flask
  __init__.py        фабрика приложения, конфигурация из переменных среды
  db.py              подключение к PostgreSQL
  services.py        бизнес-операции и валидация
  api.py             REST-маршруты /api/...
  pages.py           HTML-страницы
  errors.py          единая обработка ошибок (400/404/409/503/500)
  templates/, static/ интерфейс
db/
  01_schema.sql      схема БД (таблицы, ограничения, индексы)
  02_seed.sql        тестовые данные
  03_app_role.sh     роль приложения с минимальными правами (Docker)
  04_checks.sql      проверочные запросы и проверка ограничений
deploy/smoke.sh      smoke-тест развёрнутой версии
tests/               автотесты API (pytest, реальная БД)
docs/                диаграммы, скриншоты, отчёты по практическим работам
Dockerfile, docker-compose.yml, gunicorn.conf.py, .env.example
```

## Локальный запуск (среда разработки)

Нужны Python 3.11+ и PostgreSQL 16.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

createdb studio
psql -d studio -f db/01_schema.sql
psql -d studio -f db/02_seed.sql

export DATABASE_URL=postgresql://postgres:ПАРОЛЬ@localhost:5432/studio   # Windows: set DATABASE_URL=...
flask --app wsgi run                 # http://127.0.0.1:5000
```

Тесты (используют отдельную БД, которая пересоздаётся перед каждым тестом):

```bash
createdb studio_test
export TEST_DATABASE_URL=postgresql://postgres:ПАРОЛЬ@localhost:5432/studio_test
pytest -q
```

## Тестовое окружение (Docker)

```bash
cp .env.example .env                 # задать свои пароли
docker compose up -d --build
./deploy/smoke.sh                    # http://127.0.0.1:8080
docker compose logs -f app           # журнал приложения
```

Порт БД наружу не публикуется, приложение слушает только `127.0.0.1:8080`, работает от непривилегированного пользователя и подключается к БД ролью `studio_app` без прав на изменение схемы.

## REST API (MVP)

| Метод | Путь | Назначение | Коды |
|---|---|---|---|
| GET | `/api/health` | состояние приложения и БД | 200, 503 |
| GET | `/api/projects?status=` | список проектов | 200, 400 |
| POST | `/api/projects` | создать проект | 201, 400 |
| GET | `/api/projects/{id}` | карточка проекта с задачами | 200, 404 |
| GET | `/api/projects/{id}/tasks` | задачи проекта | 200, 404 |
| POST | `/api/projects/{id}/tasks` | добавить задачу | 201, 400, 404 |
| PATCH | `/api/tasks/{id}` | сменить статус задачи | 200, 400, 404 |
| GET | `/api/clients`, `/api/users?role=`, `/api/equipment` | справочники | 200 |

## Отчёты

Отчёты по практическим работам лежат в `docs/reports/`.
