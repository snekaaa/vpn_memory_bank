-- Миграция 005: Упрощение архитектуры подписок
-- Убираем зависимость от таблицы subscriptions

-- 1. Переименовываем subscription_end_date в valid_until для ясности
ALTER TABLE users RENAME COLUMN subscription_end_date TO valid_until;

-- 2. Обновляем комментарии
COMMENT ON COLUMN users.valid_until IS 'Дата окончания действия аккаунта пользователя';
COMMENT ON COLUMN users.subscription_status IS 'Статус аккаунта: active, expired, none';

-- 3. Убираем foreign key constraints от vpn_keys и payments к subscriptions
-- (будем делать это позже, когда обновим код)

-- 4. Обновляем индексы
DROP INDEX IF EXISTS idx_users_subscription_end_date;
CREATE INDEX idx_users_valid_until ON users(valid_until);

-- 5. Добавляем функцию для проверки действительности аккаунта
CREATE OR REPLACE FUNCTION user_has_valid_subscription(user_id_param INTEGER)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM users 
        WHERE id = user_id_param 
        AND subscription_status = 'active' 
        AND valid_until > NOW()
    );
END;
$$ LANGUAGE plpgsql; 