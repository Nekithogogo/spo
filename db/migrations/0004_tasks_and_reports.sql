-- Миграция 0004 (версия 2.0, ПР №10): редактирование задач, индексы под отчёты и фильтры.

ALTER TABLE tasks
    ADD COLUMN description  TEXT,
    ADD COLUMN updated_at   TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE TRIGGER tasks_updated_at
    BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE project_members
    ADD CONSTRAINT members_role_not_blank_chk CHECK (length(trim(role_in_project)) > 0);

-- Отчёт о загрузке (FR-12) считает только открытые задачи: частичный индекс меньше полного
DROP INDEX idx_tasks_assignee;
CREATE INDEX idx_tasks_assignee_open ON tasks (assignee_id) WHERE status <> 'done';
-- Прогресс проекта: count(*) FILTER (status = 'done') по project_id
DROP INDEX idx_tasks_project;
CREATE INDEX idx_tasks_project_status ON tasks (project_id, status);
-- Сортировка списка проектов по дедлайну и поиск по подстроке названия (ILIKE '%...%')
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_projects_deadline ON projects (deadline NULLS LAST, id);
CREATE INDEX idx_projects_title_trgm ON projects USING gin (title gin_trgm_ops);

-- Представление для отчёта о загрузке сотрудников (FR-12)
CREATE VIEW v_user_workload AS
SELECT u.id AS user_id, u.full_name, u.role,
       count(t.id) FILTER (WHERE t.status <> 'done')                                   AS open_tasks,
       count(t.id) FILTER (WHERE t.status = 'in_progress')                             AS in_progress,
       count(t.id) FILTER (WHERE t.status <> 'done' AND t.due_date < current_date)     AS overdue,
       count(DISTINCT t.project_id) FILTER (WHERE t.status <> 'done')                  AS projects
FROM users u
LEFT JOIN tasks t ON t.assignee_id = u.id
WHERE u.is_active
GROUP BY u.id;
