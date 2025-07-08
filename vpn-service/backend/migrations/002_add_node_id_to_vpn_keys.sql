-- Migration: Add node_id to vpn_keys
-- Description: Adds node_id column to vpn_keys table for multi-node support
-- Date: 2025-01-09

-- Добавляем колонку node_id в таблицу vpn_keys
ALTER TABLE vpn_keys ADD COLUMN IF NOT EXISTS node_id INTEGER;

-- Добавляем foreign key constraint
ALTER TABLE vpn_keys ADD CONSTRAINT fk_vpn_keys_node
    FOREIGN KEY (node_id) REFERENCES vpn_nodes(id) ON DELETE SET NULL;

-- Создаем индекс для быстрого поиска по node_id
CREATE INDEX IF NOT EXISTS idx_vpn_keys_node_id ON vpn_keys(node_id);

-- Обновляем существующие ключи, привязываем их к default node
UPDATE vpn_keys
SET node_id = (SELECT id FROM vpn_nodes WHERE name = 'Primary-RU-1' LIMIT 1)
WHERE node_id IS NULL;

-- Комментарий для документации
COMMENT ON COLUMN vpn_keys.node_id IS 'ID ноды, на которой создан VPN ключ'; 