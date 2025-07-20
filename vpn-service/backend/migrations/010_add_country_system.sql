-- Migration 010: Add Country System to VPN Service
-- Adds countries table, user server assignments, and server switch logging
-- Version: 1.0
-- Date: 2025-01-09

BEGIN;

-- Create countries table
CREATE TABLE IF NOT EXISTS countries (
    id SERIAL PRIMARY KEY,
    code VARCHAR(2) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    name_en VARCHAR(100),
    flag_emoji VARCHAR(10) NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,
    priority INTEGER DEFAULT 100 NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for countries
CREATE INDEX IF NOT EXISTS idx_countries_code ON countries(code);
CREATE INDEX IF NOT EXISTS idx_countries_is_active ON countries(is_active);
CREATE INDEX IF NOT EXISTS idx_countries_priority ON countries(priority);

-- Add country_id to vpn_nodes table
ALTER TABLE vpn_nodes 
ADD COLUMN IF NOT EXISTS country_id INTEGER REFERENCES countries(id);

-- Create index for vpn_nodes.country_id
CREATE INDEX IF NOT EXISTS idx_vpn_nodes_country_id ON vpn_nodes(country_id);

-- Create user_server_assignments table
CREATE TABLE IF NOT EXISTS user_server_assignments (
    user_id BIGINT PRIMARY KEY,
    node_id INTEGER NOT NULL REFERENCES vpn_nodes(id),
    country_id INTEGER NOT NULL REFERENCES countries(id),
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_switch_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for user_server_assignments
CREATE INDEX IF NOT EXISTS idx_user_server_assignments_user_id ON user_server_assignments(user_id);
CREATE INDEX IF NOT EXISTS idx_user_server_assignments_country_id ON user_server_assignments(country_id);
CREATE INDEX IF NOT EXISTS idx_user_server_assignments_node_id ON user_server_assignments(node_id);

-- Create server_switch_log table
CREATE TABLE IF NOT EXISTS server_switch_log (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    from_node_id INTEGER REFERENCES vpn_nodes(id),
    to_node_id INTEGER NOT NULL REFERENCES vpn_nodes(id),
    country_code VARCHAR(2) NOT NULL,
    success BOOLEAN DEFAULT false NOT NULL,
    error_message TEXT,
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for server_switch_log
CREATE INDEX IF NOT EXISTS idx_server_switch_log_user_id ON server_switch_log(user_id);
CREATE INDEX IF NOT EXISTS idx_server_switch_log_created_at ON server_switch_log(created_at);
CREATE INDEX IF NOT EXISTS idx_server_switch_log_country_code ON server_switch_log(country_code);
CREATE INDEX IF NOT EXISTS idx_server_switch_log_success ON server_switch_log(success);

-- Insert initial countries data
INSERT INTO countries (code, name, name_en, flag_emoji, is_active, priority) VALUES
    ('RU', 'Россия', 'Russia', '🇷🇺', true, 100),
    ('NL', 'Нидерланды', 'Netherlands', '🇳🇱', true, 90),
    ('DE', 'Германия', 'Germany', '🇩🇪', true, 80),
    ('US', 'США', 'United States', '🇺🇸', false, 70),
    ('FR', 'Франция', 'France', '🇫🇷', false, 60),
    ('UK', 'Великобритания', 'United Kingdom', '🇬🇧', false, 50)
ON CONFLICT (code) DO NOTHING;

-- Update existing nodes with country mappings based on location
-- This maps existing location strings to country IDs
UPDATE vpn_nodes 
SET country_id = (
    CASE 
        WHEN location = 'Россия' THEN (SELECT id FROM countries WHERE code = 'RU')
        WHEN location = 'Нидерланды' THEN (SELECT id FROM countries WHERE code = 'NL')
        WHEN location = 'Германия' THEN (SELECT id FROM countries WHERE code = 'DE')
        -- Auto-detected nodes will need manual assignment
        ELSE NULL
    END
)
WHERE country_id IS NULL;

COMMIT;

-- Verify migration results
SELECT 'Countries created:' as info, count(*) as count FROM countries;
SELECT 'Nodes with countries:' as info, count(*) as count FROM vpn_nodes WHERE country_id IS NOT NULL;
SELECT 'Nodes without countries (need manual assignment):' as info, count(*) as count FROM vpn_nodes WHERE country_id IS NULL; 