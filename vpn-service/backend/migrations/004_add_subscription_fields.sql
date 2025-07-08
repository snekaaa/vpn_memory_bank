-- Миграция 004: Добавление полей подписки и поддержки Робокассы
-- Дата: 2025-01-17
-- Описание: Добавляет поля для отслеживания подписок пользователей и интеграции с Робокассой

-- Создаем enum для статусов подписки пользователя
CREATE TYPE user_subscription_status AS ENUM (
    'none',
    'active', 
    'expired',
    'suspended'
);

-- Добавляем поля подписки в таблицу users
ALTER TABLE users 
ADD COLUMN subscription_status user_subscription_status DEFAULT 'none',
ADD COLUMN subscription_end_date TIMESTAMP WITH TIME ZONE;

-- Добавляем индекс для быстрого поиска пользователей с активной подпиской
CREATE INDEX idx_users_subscription_status ON users(subscription_status);
CREATE INDEX idx_users_subscription_end_date ON users(subscription_end_date);

-- Расширяем enum paymentmethod для поддержки Робокассы
ALTER TYPE paymentmethod ADD VALUE 'robokassa';

-- Добавляем поля для Робокассы в таблицу payments
ALTER TABLE payments 
ADD COLUMN robokassa_invoice_id VARCHAR(255),
ADD COLUMN robokassa_signature VARCHAR(255),
ADD COLUMN robokassa_payment_method VARCHAR(100);

-- Добавляем индекс для robokassa_invoice_id
CREATE INDEX idx_payments_robokassa_invoice_id ON payments(robokassa_invoice_id);

-- Комментарии для документации
COMMENT ON COLUMN users.subscription_status IS 'Статус подписки пользователя';
COMMENT ON COLUMN users.subscription_end_date IS 'Дата окончания подписки';
COMMENT ON COLUMN payments.robokassa_invoice_id IS 'ID инвойса от Робокассы';
COMMENT ON COLUMN payments.robokassa_signature IS 'Подпись для проверки от Робокассы';
COMMENT ON COLUMN payments.robokassa_payment_method IS 'Метод оплаты в Робокассе';

-- Создаем функцию для автоматического обновления статуса подписки
CREATE OR REPLACE FUNCTION update_expired_subscriptions()
RETURNS void AS $$
BEGIN
    UPDATE users 
    SET subscription_status = 'expired'
    WHERE subscription_status = 'active' 
    AND subscription_end_date < NOW();
END;
$$ LANGUAGE plpgsql;

-- Создаем процедуру для периодического обновления статусов (можно вызывать из cron)
COMMENT ON FUNCTION update_expired_subscriptions() IS 'Функция для обновления истекших подписок';

-- Выводим результат миграции
SELECT 'Migration 004 completed successfully' AS result; 