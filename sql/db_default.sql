-- Создание таблиц
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name TEXT,
    email TEXT,
    role TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users_audit (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changed_by TEXT,
    field_changed TEXT,
    old_value TEXT,
    new_value TEXT
);

-- Установка pg_cron
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Функция логирования изменений
CREATE OR REPLACE FUNCTION log_user_changed()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;

    IF OLD.name IS DISTINCT FROM NEW.name THEN
        INSERT INTO users_audit (user_id, changed_by, field_changed, old_value, new_value)
        VALUES (OLD.id, current_user, 'name', OLD.name, NEW.name);
    END IF;

    IF OLD.email IS DISTINCT FROM NEW.email THEN
        INSERT INTO users_audit (user_id, changed_by, field_changed, old_value, new_value)
        VALUES (OLD.id, current_user, 'email', OLD.email, NEW.email);
    END IF;

    IF OLD.role IS DISTINCT FROM NEW.role THEN
        INSERT INTO users_audit (user_id, changed_by, field_changed, old_value, new_value)
        VALUES (OLD.id, current_user, 'role', OLD.role, NEW.role);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Создание триггера
DROP TRIGGER IF EXISTS trg_log_user_changes ON users;
CREATE TRIGGER trg_log_user_changes
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION log_user_changed();

-- Функция экспорта в CSV
CREATE OR REPLACE FUNCTION export_yesterday_audit()
RETURNS void AS $$
DECLARE
    file_path TEXT;
BEGIN
    file_path := '/tmp/users_audit_export_' || to_char(CURRENT_DATE - INTERVAL '1 day', 'YYYY-MM-DD') || '.csv';
    EXECUTE format(
        'COPY (SELECT * FROM users_audit WHERE changed_at >= CURRENT_DATE - INTERVAL ''1 day'' AND changed_at < CURRENT_DATE) TO %L WITH CSV HEADER',
        file_path
    );
END;
$$ LANGUAGE plpgsql;

-- Настройка pg_cron на 3:00 ночи
SELECT cron.schedule(
    'export-audit-nightly',
    '0 3 * * *',
    'SELECT export_yesterday_audit()'
);
