-- Migration: Add Multi-Node VPN Support
-- Description: Adds vpn_nodes and user_node_assignments tables for multi-node architecture
-- Date: 2025-01-09

-- Таблица серверных нод
CREATE TABLE IF NOT EXISTS vpn_nodes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    location VARCHAR(100),
    
    -- X3UI connection settings
    x3ui_url VARCHAR(255) NOT NULL,
    x3ui_username VARCHAR(100) NOT NULL,
    x3ui_password VARCHAR(255) NOT NULL,
    
    -- Node capacity and status
    max_users INTEGER DEFAULT 1000,
    current_users INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'active', -- active, inactive, maintenance
    
    -- Health monitoring
    last_health_check TIMESTAMP,
    health_status VARCHAR(50) DEFAULT 'unknown', -- healthy, unhealthy, unknown
    response_time_ms INTEGER,
    
    -- Configuration
    priority INTEGER DEFAULT 100, -- Higher = preferred
    weight FLOAT DEFAULT 1.0, -- Load balancing weight
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Привязка пользователей к нодам
CREATE TABLE IF NOT EXISTS user_node_assignments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    node_id INTEGER REFERENCES vpn_nodes(id) ON DELETE CASCADE,
    
    -- Assignment details
    assigned_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    
    -- X3UI specific details
    xui_inbound_id INTEGER,
    xui_client_email VARCHAR(255),
    
    -- Constraints
    UNIQUE(user_id, node_id, is_active)
);

-- Индексы для производительности
CREATE INDEX IF NOT EXISTS idx_vpn_nodes_status ON vpn_nodes(status, health_status);
CREATE INDEX IF NOT EXISTS idx_vpn_nodes_priority ON vpn_nodes(priority DESC, weight DESC);
CREATE INDEX IF NOT EXISTS idx_user_node_assignments_active ON user_node_assignments(user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_user_node_assignments_node ON user_node_assignments(node_id, is_active);

-- Добавляем текущий сервер как default node
INSERT INTO vpn_nodes (
    name, 
    description, 
    location,
    x3ui_url, 
    x3ui_username, 
    x3ui_password,
    priority,
    weight,
    status,
    health_status
) VALUES (
    'Primary-RU-1',
    'Main production server (existing)',
    'Russia',
    'http://5.35.69.133:2053',
    'admin',
    '2U9Zkb97JKNP3jN9',
    100,
    1.0,
    'active',
    'healthy'
) ON CONFLICT (name) DO NOTHING;

-- Мигрируем существующих пользователей на default node
INSERT INTO user_node_assignments (user_id, node_id, is_active, assigned_at)
SELECT 
    u.id,
    (SELECT id FROM vpn_nodes WHERE name = 'Primary-RU-1' LIMIT 1),
    true,
    NOW()
FROM users u
WHERE NOT EXISTS (
    SELECT 1 FROM user_node_assignments una 
    WHERE una.user_id = u.id AND una.is_active = true
);

-- Обновляем current_users для default node
UPDATE vpn_nodes 
SET current_users = (
    SELECT COUNT(*) 
    FROM user_node_assignments 
    WHERE node_id = vpn_nodes.id AND is_active = true
)
WHERE name = 'Primary-RU-1';

-- Комментарии для документации
COMMENT ON TABLE vpn_nodes IS 'VPN server nodes configuration and status';
COMMENT ON TABLE user_node_assignments IS 'User assignments to specific VPN nodes';
COMMENT ON COLUMN vpn_nodes.priority IS 'Higher values = preferred nodes for new users';
COMMENT ON COLUMN vpn_nodes.weight IS 'Load balancing weight (1.0 = normal, 0.5 = half capacity)';
COMMENT ON COLUMN vpn_nodes.health_status IS 'Current health: healthy, unhealthy, unknown'; 