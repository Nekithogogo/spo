-- ИС «Видеостудия/продакшн — управление проектами»
-- Физическая схема БД (ПР №4). СУБД: PostgreSQL 16.

CREATE EXTENSION IF NOT EXISTS btree_gist;  -- нужен для запрета пересечения броней оборудования

-- Сотрудники студии
CREATE TABLE users (
    id          SERIAL PRIMARY KEY,
    full_name   VARCHAR(150) NOT NULL,
    email       VARCHAR(150) NOT NULL UNIQUE,
    phone       VARCHAR(20),
    role        VARCHAR(20)  NOT NULL DEFAULT 'editor'
                CHECK (role IN ('admin', 'producer', 'director', 'operator', 'editor')),
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Заказчики
CREATE TABLE clients (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    contact_person  VARCHAR(150),
    phone           VARCHAR(20),
    email           VARCHAR(150),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT clients_contact_chk CHECK (phone IS NOT NULL OR email IS NOT NULL)
);

-- Проекты (заказы на видеопроизводство)
CREATE TABLE projects (
    id            SERIAL PRIMARY KEY,
    title         VARCHAR(200)  NOT NULL,
    client_id     INTEGER       NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    producer_id   INTEGER       REFERENCES users(id) ON DELETE SET NULL,
    project_type  VARCHAR(30)   NOT NULL DEFAULT 'commercial'
                  CHECK (project_type IN ('commercial', 'music_video', 'corporate', 'event', 'documentary', 'other')),
    status        VARCHAR(20)   NOT NULL DEFAULT 'new'
                  CHECK (status IN ('new', 'preproduction', 'shooting', 'postproduction', 'review', 'done', 'cancelled')),
    budget        NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (budget >= 0),
    start_date    DATE,
    deadline      DATE,
    description   TEXT,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT projects_dates_chk CHECK (deadline IS NULL OR start_date IS NULL OR deadline >= start_date)
);

-- Состав съёмочной группы проекта (N:M users <-> projects)
CREATE TABLE project_members (
    project_id       INTEGER     NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id          INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_in_project  VARCHAR(50) NOT NULL,
    PRIMARY KEY (project_id, user_id)
);

-- Задачи по этапам производства
CREATE TABLE tasks (
    id           SERIAL PRIMARY KEY,
    project_id   INTEGER      NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title        VARCHAR(200) NOT NULL,
    stage        VARCHAR(20)  NOT NULL DEFAULT 'preproduction'
                 CHECK (stage IN ('preproduction', 'shooting', 'postproduction', 'review')),
    status       VARCHAR(20)  NOT NULL DEFAULT 'todo'
                 CHECK (status IN ('todo', 'in_progress', 'done')),
    assignee_id  INTEGER      REFERENCES users(id) ON DELETE SET NULL,
    due_date     DATE,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Оборудование студии
CREATE TABLE equipment (
    id                SERIAL PRIMARY KEY,
    name              VARCHAR(150) NOT NULL,
    category          VARCHAR(20)  NOT NULL
                      CHECK (category IN ('camera', 'lens', 'light', 'sound', 'grip', 'other')),
    inventory_number  VARCHAR(30)  NOT NULL UNIQUE,
    is_available      BOOLEAN      NOT NULL DEFAULT TRUE
);

-- Бронирование оборудования под проект (N:M equipment <-> projects с интервалом времени)
CREATE TABLE equipment_bookings (
    id            SERIAL PRIMARY KEY,
    equipment_id  INTEGER     NOT NULL REFERENCES equipment(id) ON DELETE RESTRICT,
    project_id    INTEGER     NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    starts_at     TIMESTAMPTZ NOT NULL,
    ends_at       TIMESTAMPTZ NOT NULL,
    CONSTRAINT bookings_period_chk CHECK (ends_at > starts_at),
    -- одна и та же единица оборудования не может быть занята в пересекающиеся интервалы
    CONSTRAINT bookings_no_overlap EXCLUDE USING gist (
        equipment_id WITH =,
        tstzrange(starts_at, ends_at) WITH &&
    )
);

-- Индексы под частые выборки (внешние ключи и фильтры списков)
CREATE INDEX idx_projects_status     ON projects(status);
CREATE INDEX idx_projects_client     ON projects(client_id);
CREATE INDEX idx_projects_producer   ON projects(producer_id);
CREATE INDEX idx_tasks_project       ON tasks(project_id);
CREATE INDEX idx_tasks_assignee      ON tasks(assignee_id);
CREATE INDEX idx_members_user        ON project_members(user_id);
CREATE INDEX idx_bookings_project    ON equipment_bookings(project_id);

-- Автоматическое обновление updated_at у проекта
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
