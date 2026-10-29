-- Миграция 0002 (версия 2.0, ПР №10): учётные записи и вход в систему (FR-11).
-- Пароль хранится только в виде хеша (scrypt, соль внутри хеша).
-- token_version увеличивается при выходе из системы: все ранее выданные токены перестают действовать.

ALTER TABLE users
    ADD COLUMN password_hash  VARCHAR(255),
    ADD COLUMN token_version  INTEGER     NOT NULL DEFAULT 0,
    ADD COLUMN last_login_at  TIMESTAMPTZ;

-- Миграция данных: e-mail приводится к нижнему регистру, уникальность становится регистронезависимой
UPDATE users SET email = lower(trim(email)) WHERE email <> lower(trim(email));
ALTER TABLE users DROP CONSTRAINT users_email_key;
CREATE UNIQUE INDEX users_email_lower_uq ON users (lower(email));
ALTER TABLE users ADD CONSTRAINT users_email_format_chk CHECK (email ~ '^[^@\s]+@[^@\s]+$');

-- Журнал попыток входа: защита от перебора паролей и аудит
CREATE TABLE login_attempts (
    id          BIGSERIAL   PRIMARY KEY,
    email       VARCHAR(150) NOT NULL,
    ip          VARCHAR(45),
    success     BOOLEAN     NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_login_attempts_email_time ON login_attempts (lower(email), created_at DESC);
CREATE INDEX idx_login_attempts_ip_time    ON login_attempts (ip, created_at DESC);
