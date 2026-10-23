-- Проверочные запросы к БД (ПР №4, раздел 5).
-- Запуск: psql -d studio -f db/04_checks.sql
\echo '=== 1. Проекты с заказчиком и продюсером ==='
SELECT p.id, p.title, c.name AS client, u.full_name AS producer, p.status, p.deadline
FROM projects p
JOIN clients c ON c.id = p.client_id
LEFT JOIN users u ON u.id = p.producer_id
ORDER BY p.deadline;

\echo '=== 2. Прогресс задач по проектам ==='
SELECT p.title,
       count(t.id)                                   AS total,
       count(t.id) FILTER (WHERE t.status = 'done')  AS done,
       round(100.0 * count(t.id) FILTER (WHERE t.status = 'done') / NULLIF(count(t.id), 0)) AS pct
FROM projects p
LEFT JOIN tasks t ON t.project_id = p.id
GROUP BY p.id
ORDER BY p.id;

\echo '=== 3. Нагрузка сотрудников: открытые задачи ==='
SELECT u.full_name, u.role, count(t.id) AS open_tasks
FROM users u
LEFT JOIN tasks t ON t.assignee_id = u.id AND t.status <> 'done'
GROUP BY u.id
ORDER BY open_tasks DESC, u.full_name;

\echo '=== 4. Занятость оборудования 25.10.2026 ==='
SELECT e.inventory_number, e.name, p.title, b.starts_at, b.ends_at
FROM equipment_bookings b
JOIN equipment e ON e.id = b.equipment_id
JOIN projects p ON p.id = b.project_id
WHERE tstzrange(b.starts_at, b.ends_at) && tstzrange('2026-10-25 00:00+03', '2026-10-26 00:00+03');

\echo '=== 5. Проверка ограничений (каждая команда должна завершиться ошибкой) ==='
\set ON_ERROR_STOP off
-- 5.1 недопустимый статус проекта (CHECK)
INSERT INTO projects (title, client_id, status) VALUES ('Тест', 1, 'unknown');
-- 5.2 несуществующий заказчик (FK)
INSERT INTO projects (title, client_id) VALUES ('Тест', 999);
-- 5.3 дедлайн раньше старта (CHECK)
INSERT INTO projects (title, client_id, start_date, deadline) VALUES ('Тест', 1, '2026-12-01', '2026-11-01');
-- 5.4 повтор e-mail сотрудника (UNIQUE)
INSERT INTO users (full_name, email) VALUES ('Дубликат', 'orlova@studio.local');
-- 5.5 пересечение брони камеры CAM-001 (EXCLUDE)
INSERT INTO equipment_bookings (equipment_id, project_id, starts_at, ends_at)
VALUES (1, 2, '2026-10-25 18:00+03', '2026-10-25 22:00+03');
-- 5.6 удаление заказчика, у которого есть проекты (ON DELETE RESTRICT)
DELETE FROM clients WHERE id = 1;
-- 5.7 отрицательный бюджет (CHECK)
UPDATE projects SET budget = -1 WHERE id = 1;
\set ON_ERROR_STOP on

\echo '=== 6. Каскадное удаление: задачи удаляются вместе с проектом ==='
BEGIN;
SELECT count(*) AS tasks_before FROM tasks WHERE project_id = 2;
DELETE FROM projects WHERE id = 2;
SELECT count(*) AS tasks_of_deleted_project FROM tasks WHERE project_id = 2;
ROLLBACK;
