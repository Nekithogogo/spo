#!/bin/sh
# Создаёт роль приложения с минимальными правами (только DML, без DDL).
# Выполняется контейнером postgres при первой инициализации тома.
# Пароль передаётся через переменную среды APP_DB_PASSWORD, в репозитории его нет.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE ROLE studio_app LOGIN PASSWORD '${APP_DB_PASSWORD}';
    GRANT CONNECT ON DATABASE "${POSTGRES_DB}" TO studio_app;
    GRANT USAGE ON SCHEMA public TO studio_app;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO studio_app;
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO studio_app;
    REVOKE CREATE ON SCHEMA public FROM PUBLIC;
EOSQL
