-- Миграция: Добавление системы управления платежными провайдерами
-- Дата: 2025-01-07
-- Описание: Создание таблицы payment_providers и интеграция с существующими платежами

-- Создание типов для enum'ов
CREATE TYPE payment_provider_type AS ENUM (
    'robokassa',
    'yookassa',
    'coingate',
    'paypal',
    'stripe',
    'sberbank',
    'tinkoff'
);

CREATE TYPE payment_provider_status AS ENUM (
    'active',
    'inactive',
    'testing',
    'error',
    'maintenance'
);

-- Создание таблицы payment_providers
CREATE TABLE payment_providers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    provider_type payment_provider_type NOT NULL,
    
    -- Статус и режим работы
    status payment_provider_status DEFAULT 'inactive',
    is_active BOOLEAN DEFAULT FALSE,
    is_test_mode BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    
    -- Конфигурация (JSON с настройками для каждого типа провайдера)
    config JSONB NOT NULL DEFAULT '{}',
    
    -- Описание и метаданные
    description TEXT,
    webhook_url VARCHAR(500),
    
    -- Приоритет (для сортировки)
    priority INTEGER DEFAULT 100,
    
    -- Ограничения по сумме
    min_amount DECIMAL(10,2) DEFAULT 0.0,
    max_amount DECIMAL(10,2),
    
    -- Комиссия
    commission_percent DECIMAL(5,2) DEFAULT 0.0,
    commission_fixed DECIMAL(10,2) DEFAULT 0.0,
    
    -- Статистика
    total_payments INTEGER DEFAULT 0,
    successful_payments INTEGER DEFAULT 0,
    failed_payments INTEGER DEFAULT 0,
    total_amount DECIMAL(15,2) DEFAULT 0.0,
    
    -- Статус последнего тестирования
    last_test_at TIMESTAMP WITH TIME ZONE,
    last_test_status VARCHAR(50),
    last_test_message TEXT,
    
    -- Временные метки
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Создание индексов
CREATE INDEX idx_payment_providers_provider_type ON payment_providers(provider_type);
CREATE INDEX idx_payment_providers_status ON payment_providers(status);
CREATE INDEX idx_payment_providers_is_active ON payment_providers(is_active);
CREATE INDEX idx_payment_providers_priority ON payment_providers(priority);

-- Триггер для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_payment_providers_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_payment_providers_updated_at
    BEFORE UPDATE ON payment_providers
    FOR EACH ROW
    EXECUTE FUNCTION update_payment_providers_updated_at();

-- Добавление поля provider_id в таблицу payments
ALTER TABLE payments ADD COLUMN provider_id INTEGER;
ALTER TABLE payments ADD CONSTRAINT fk_payments_provider_id 
    FOREIGN KEY (provider_id) REFERENCES payment_providers(id) ON DELETE SET NULL;

-- Создание индекса для provider_id
CREATE INDEX idx_payments_provider_id ON payments(provider_id);

-- Создание записи для существующей Робокассы (миграция данных)
INSERT INTO payment_providers (
    name,
    provider_type,
    status,
    is_active,
    is_test_mode,
    is_default,
    config,
    description,
    priority,
    created_at,
    updated_at
) VALUES (
    'Основная Робокасса',
    'robokassa',
    'active',
    TRUE,
    TRUE,  -- Предполагаем что работает в тестовом режиме
    TRUE,  -- Делаем провайдером по умолчанию
    '{"shop_id": "", "password1": "", "password2": "", "base_url": "https://auth.robokassa.ru/Merchant/Index.aspx"}',
    'Основной провайдер Робокасса для обработки платежей',
    100,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

-- Получение ID созданного провайдера Робокассы
DO $$
DECLARE
    robokassa_provider_id INTEGER;
BEGIN
    -- Получаем ID провайдера Робокассы
    SELECT id INTO robokassa_provider_id 
    FROM payment_providers 
    WHERE provider_type = 'robokassa' AND name = 'Основная Робокасса';
    
    -- Обновляем существующие платежи Робокассы
    UPDATE payments 
    SET provider_id = robokassa_provider_id 
    WHERE payment_method = 'robokassa' OR robokassa_invoice_id IS NOT NULL;
    
    -- Обновляем статистику провайдера
    UPDATE payment_providers 
    SET 
        total_payments = (
            SELECT COUNT(*) 
            FROM payments 
            WHERE provider_id = robokassa_provider_id
        ),
        successful_payments = (
            SELECT COUNT(*) 
            FROM payments 
            WHERE provider_id = robokassa_provider_id AND status = 'SUCCEEDED'
        ),
        failed_payments = (
            SELECT COUNT(*) 
            FROM payments 
            WHERE provider_id = robokassa_provider_id AND status = 'FAILED'
        ),
        total_amount = (
            SELECT COALESCE(SUM(amount), 0) 
            FROM payments 
            WHERE provider_id = robokassa_provider_id AND status = 'SUCCEEDED'
        )
    WHERE id = robokassa_provider_id;
END $$;

-- Создание дополнительных ограничений
ALTER TABLE payment_providers ADD CONSTRAINT chk_payment_providers_amounts 
    CHECK (min_amount >= 0 AND (max_amount IS NULL OR max_amount >= min_amount));

ALTER TABLE payment_providers ADD CONSTRAINT chk_payment_providers_commission 
    CHECK (commission_percent >= 0 AND commission_percent <= 100);

ALTER TABLE payment_providers ADD CONSTRAINT chk_payment_providers_stats 
    CHECK (total_payments >= 0 AND successful_payments >= 0 AND failed_payments >= 0 AND total_amount >= 0);

-- Комментарии к таблице и колонкам
COMMENT ON TABLE payment_providers IS 'Таблица платежных провайдеров для системы управления платежными системами';
COMMENT ON COLUMN payment_providers.config IS 'JSON конфигурация с настройками для каждого типа провайдера';
COMMENT ON COLUMN payment_providers.webhook_url IS 'URL для получения webhook уведомлений от провайдера';
COMMENT ON COLUMN payment_providers.priority IS 'Приоритет провайдера для сортировки (меньше = выше приоритет)';
COMMENT ON COLUMN payment_providers.is_default IS 'Является ли провайдер основным для нового типа платежей';
COMMENT ON COLUMN payment_providers.last_test_status IS 'Статус последнего тестирования (success, error, timeout)'; 