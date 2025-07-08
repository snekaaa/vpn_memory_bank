-- Миграция 003: Добавление полей Reality mode в таблицу vpn_nodes
-- Дата: 2025-01-17
-- Описание: Добавляет поля для поддержки VLESS Reality режима

-- Проверяем существует ли таблица vpn_nodes
DO $$ 
BEGIN
    -- Добавляем колонку mode если она не существует
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'vpn_nodes' AND column_name = 'mode'
    ) THEN
        ALTER TABLE vpn_nodes ADD COLUMN mode VARCHAR(7) NOT NULL DEFAULT 'reality';
        RAISE NOTICE 'Добавлена колонка mode';
    ELSE
        RAISE NOTICE 'Колонка mode уже существует';
    END IF;

    -- Добавляем колонку public_key если она не существует
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'vpn_nodes' AND column_name = 'public_key'
    ) THEN
        ALTER TABLE vpn_nodes ADD COLUMN public_key TEXT;
        RAISE NOTICE 'Добавлена колонка public_key';
    ELSE
        RAISE NOTICE 'Колонка public_key уже существует';
    END IF;

    -- Добавляем колонку short_id если она не существует
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'vpn_nodes' AND column_name = 'short_id'
    ) THEN
        ALTER TABLE vpn_nodes ADD COLUMN short_id VARCHAR(32);
        RAISE NOTICE 'Добавлена колонка short_id';
    ELSE
        RAISE NOTICE 'Колонка short_id уже существует';
    END IF;

    -- Добавляем колонку sni_mask если она не существует
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'vpn_nodes' AND column_name = 'sni_mask'
    ) THEN
        ALTER TABLE vpn_nodes ADD COLUMN sni_mask VARCHAR(255);
        RAISE NOTICE 'Добавлена колонка sni_mask';
    ELSE
        RAISE NOTICE 'Колонка sni_mask уже существует';
    END IF;

END $$;

-- Создаем индекс для mode для быстрого поиска по типу ноды
CREATE INDEX IF NOT EXISTS ix_vpn_nodes_mode ON vpn_nodes(mode);

-- Обновляем существующие ноды с дефолтными значениями Reality mode
UPDATE vpn_nodes 
SET 
    mode = 'reality',
    public_key = 'default_public_key_' || id::text,
    short_id = LEFT(MD5(random()::text), 8),
    sni_mask = 'apple.com'
WHERE mode IS NULL OR mode = '';

COMMIT; 