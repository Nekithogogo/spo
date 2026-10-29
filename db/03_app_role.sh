#!/bin/sh
# Создаёт роль приложения с минимальными правами (только DML, без DDL).
# Выполняется контейнером postgres при первой инициализации тома. Таблицы создают миграции
# (python -m app.manage migrate), они же выдают роли права на новые таблицы.
# Пароль передаётся через переменную среды APP_DB_PASSWORD, в репозитории его нет.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE ROLE studio_app LOGIN PASSWORD '${APP_DB_PASSWORD}' CONNECTION LIMIT 20;
    GRANT CONNECT ON DATABASE "${POSTGRES_DB}" TO studio_app;
    GRANT USAGE ON SCHEMA public TO studio_app;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO studio_app;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO studio_app;
    REVOKE CREATE ON SCHEMA public FROM PUBLIC;
    REVOKE ALL ON DATABASE "${POSTGRES_DB}" FROM PUBLIC;
EOSQL
