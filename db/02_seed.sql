-- Тестовые данные для учебного стенда (вымышленные).

INSERT INTO users (full_name, email, phone, role) VALUES
    ('Орлова Анна Сергеевна',      'orlova@studio.local',   '+79990000001', 'admin'),
    ('Кузнецов Дмитрий Игоревич',  'kuznetsov@studio.local','+79990000002', 'producer'),
    ('Белова Мария Андреевна',     'belova@studio.local',   '+79990000003', 'director'),
    ('Смирнов Павел Олегович',     'smirnov@studio.local',  '+79990000004', 'operator'),
    ('Волков Артём Денисович',     'volkov@studio.local',   '+79990000005', 'editor'),
    ('Лебедева Ксения Романовна',  'lebedeva@studio.local', '+79990000006', 'producer');

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
