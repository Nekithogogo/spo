-- Миграция 0003 (версия 2.0, ПР №10): история смены статусов проекта (FR-08, FR-13).

CREATE TABLE project_status_history (
    id          BIGSERIAL   PRIMARY KEY,
    project_id  INTEGER     NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    old_status  VARCHAR(20),
    new_status  VARCHAR(20) NOT NULL,
    changed_by  INTEGER     REFERENCES users(id) ON DELETE SET NULL,
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    comment     VARCHAR(500),
    CONSTRAINT history_status_changed_chk CHECK (old_status IS DISTINCT FROM new_status)
);
CREATE INDEX idx_history_project_time ON project_status_history (project_id, changed_at DESC);

-- Начальная запись истории для уже существующих проектов (миграция данных)
INSERT INTO project_status_history (project_id, old_status, new_status, changed_by, changed_at, comment)
SELECT id, NULL, status, producer_id, created_at, 'Перенесено при обновлении до версии 2.0'
FROM projects;
