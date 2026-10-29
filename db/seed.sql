-- Тестовые данные для учебного стенда (вымышленные). Применяются после всех миграций:
--   python -m app.manage migrate --seed
-- Пароль всех демонстрационных учётных записей: studio2026 (в БД хранится только хеш).

INSERT INTO users (full_name, email, phone, role) VALUES
    ('Орлова Анна Сергеевна',      'orlova@studio.local',   '+79990000001', 'admin'),
    ('Кузнецов Дмитрий Игоревич',  'kuznetsov@studio.local','+79990000002', 'producer'),
    ('Белова Мария Андреевна',     'belova@studio.local',   '+79990000003', 'director'),
    ('Смирнов Павел Олегович',     'smirnov@studio.local',  '+79990000004', 'operator'),
    ('Волков Артём Денисович',     'volkov@studio.local',   '+79990000005', 'editor'),
    ('Лебедева Ксения Романовна',  'lebedeva@studio.local', '+79990000006', 'producer');

UPDATE users SET password_hash = v.hash FROM (VALUES
    ('orlova@studio.local', 'scrypt:32768:8:1$oX9vaJH7uvLi154g$87369e34497e07c559861fb6f0c896fbacc7004e263be5c826e4d0aa3b73d70bd2a27d40068696503c58a1b1d70df6773fb99b4c708dbee60f385a5a0eef3ec4'),
    ('kuznetsov@studio.local', 'scrypt:32768:8:1$jUCkkk3QN0hUbp8o$b63fbfb9d66de3f3ad65adabace65cab0e25e951c5539b321270322cbb64e83c42c6321f0c840f23b1bb827e70078962ba9166bf50c4f61ed76bc6b3d4d060cc'),
    ('belova@studio.local', 'scrypt:32768:8:1$DXnCjcJ4qNcbbwPl$95ad9a5df0d468c9944c84b281d03f01f60ec8a75669e4601a5b67e0d05885d19cd93e53c7d7b9943f717f08fe7a711d7859578716baa9e300b9b891e2331e8c'),
    ('smirnov@studio.local', 'scrypt:32768:8:1$AxBZPoCaezEFab53$46ab39c8b335bb8fdaece5950d8ca81f19074a55b17a6979e0470c3c1442d3f777a11bbeee3030a2b68bbdfdce9849953ca9a04feddb1d775314b6dde79a0f44'),
    ('volkov@studio.local', 'scrypt:32768:8:1$nYFMn6AqFp5J3NgV$fc863c18962b4f0ccc46f71a79971baf8747b32174550b6831488550d0d5a64fca627d8290de25dbdd8595e48b4a2208d3316e853e086bd9cf54c7677cb25f35'),
    ('lebedeva@studio.local', 'scrypt:32768:8:1$ROMwcN3qQxo2QnmN$a8bab852faec86515c7f37ac897f6797ebe67c4c71c79b33c7f37db63a6764f6bab275ce016257631e2ee17c0d37595968ff21d8248c7d268ce23af9e9f3d7e8')
) AS v(email, hash) WHERE users.email = v.email;

INSERT INTO clients (name, contact_person, phone, email) VALUES
    ('ООО «Северный кофе»',     'Иванов Олег',     '+79991110001', 'marketing@north-coffee.local'),
    ('Музыкальная группа «Ветер»', 'Петрова Алина', '+79991110002', NULL),
    ('АО «ТехноПром»',          'Сидоров Виктор',  NULL,           'pr@technoprom.local');

INSERT INTO projects (title, client_id, producer_id, project_type, status, budget, start_date, deadline, description) VALUES
    ('Рекламный ролик «Утро с кофе»', 1, 2, 'commercial',  'shooting',       350000, '2026-10-01', '2026-11-15', '30-секундный ролик для ТВ и соцсетей'),
    ('Клип «Ветер перемен»',          2, 6, 'music_video', 'preproduction',  220000, '2026-10-20', '2026-12-10', 'Клип на новый сингл, натурные съёмки'),
    ('Корпоративный фильм к 25-летию',3, 2, 'corporate',   'postproduction', 480000, '2026-09-01', '2026-11-01', 'Интервью с сотрудниками и съёмка производства'),
    ('Тизер выставки «ТехноПром-2027»',3, 6, 'event',      'new',            90000,  NULL,         '2027-01-20', NULL);

INSERT INTO project_members (project_id, user_id, role_in_project) VALUES
    (1, 2, 'Продюсер'), (1, 3, 'Режиссёр'), (1, 4, 'Оператор-постановщик'), (1, 5, 'Монтажёр'),
    (2, 6, 'Продюсер'), (2, 3, 'Режиссёр'),
    (3, 2, 'Продюсер'), (3, 4, 'Оператор'), (3, 5, 'Монтажёр и цветокоррекция');

INSERT INTO tasks (project_id, title, stage, status, assignee_id, due_date) VALUES
    (1, 'Согласовать сценарий с заказчиком', 'preproduction',  'done',        3, '2026-10-05'),
    (1, 'Подобрать локацию (кофейня)',       'preproduction',  'done',        2, '2026-10-08'),
    (1, 'Съёмочный день №1',                 'shooting',       'in_progress', 4, '2026-10-25'),
    (1, 'Черновой монтаж',                   'postproduction', 'todo',        5, '2026-11-05'),
    (2, 'Написать режиссёрский сценарий',    'preproduction',  'in_progress', 3, '2026-10-30'),
    (2, 'Кастинг массовки',                  'preproduction',  'todo',        6, '2026-11-05'),
    (3, 'Монтаж интервью',                   'postproduction', 'in_progress', 5, '2026-10-25'),
    (3, 'Цветокоррекция',                    'postproduction', 'todo',        5, '2026-10-28'),
    (3, 'Показ заказчику',                   'review',         'todo',        2, '2026-10-30');

INSERT INTO equipment (name, category, inventory_number) VALUES
    ('Sony FX6',                 'camera', 'CAM-001'),
    ('Blackmagic Pocket 6K Pro', 'camera', 'CAM-002'),
    ('Объектив Sigma 24-70 f/2.8','lens',  'LNS-001'),
    ('Aputure 600d Pro',         'light',  'LGT-001'),
    ('Петличная система Rode Wireless PRO', 'sound', 'SND-001'),
    ('Слайдер Edelkrone',        'grip',   'GRP-001');

INSERT INTO equipment_bookings (equipment_id, project_id, starts_at, ends_at) VALUES
    (1, 1, '2026-10-25 08:00+03', '2026-10-25 20:00+03'),
    (4, 1, '2026-10-25 08:00+03', '2026-10-25 20:00+03'),
    (5, 3, '2026-09-10 09:00+03', '2026-09-12 19:00+03');

-- История статусов: стартовые записи для демонстрационных проектов
INSERT INTO project_status_history (project_id, old_status, new_status, changed_by, changed_at) VALUES
    (1, NULL, 'new', 2, '2026-09-25 10:00+03'), (1, 'new', 'preproduction', 2, '2026-10-01 10:00+03'),
    (1, 'preproduction', 'shooting', 2, '2026-10-20 09:00+03'),
    (2, NULL, 'new', 6, '2026-10-15 12:00+03'), (2, 'new', 'preproduction', 6, '2026-10-20 12:00+03'),
    (3, NULL, 'new', 2, '2026-08-25 11:00+03'), (3, 'new', 'preproduction', 2, '2026-09-01 11:00+03'),
    (3, 'preproduction', 'shooting', 2, '2026-09-10 09:00+03'), (3, 'shooting', 'postproduction', 2, '2026-09-20 18:00+03'),
    (4, NULL, 'new', 6, '2026-10-22 15:00+03');
