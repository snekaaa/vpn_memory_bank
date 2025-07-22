-- Migration: Add App Settings Table
-- Description: Creates app_settings table for centralized application configuration
-- Date: 2025-01-XX
-- Version: 011

-- Create app_settings table with singleton pattern
CREATE TABLE IF NOT EXISTS app_settings (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Site Configuration
    site_name VARCHAR(255) NOT NULL DEFAULT 'VPN Service',
    site_domain VARCHAR(255),
    site_description TEXT,
    
    -- User/Trial Settings
    trial_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    trial_days INTEGER NOT NULL DEFAULT 7 CHECK (trial_days >= 0),
    trial_max_per_user INTEGER NOT NULL DEFAULT 1 CHECK (trial_max_per_user >= 0),
    
    -- Security Settings  
    token_expire_minutes INTEGER NOT NULL DEFAULT 30 CHECK (token_expire_minutes > 0),
    admin_telegram_ids TEXT NOT NULL DEFAULT '[]',  -- JSON array
    admin_usernames TEXT NOT NULL DEFAULT '[]',     -- JSON array  
    
    -- Bot Settings
    telegram_bot_token VARCHAR(255),
    bot_welcome_message TEXT,
    bot_help_message TEXT,
    bot_apps_message TEXT DEFAULT 'Скачайте приложения для вашего устройства:'
);

-- Create trigger function for automatic updated_at
CREATE OR REPLACE FUNCTION update_app_settings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for automatic updated_at update
DROP TRIGGER IF EXISTS update_app_settings_updated_at_trigger ON app_settings;
CREATE TRIGGER update_app_settings_updated_at_trigger
    BEFORE UPDATE ON app_settings 
    FOR EACH ROW 
    EXECUTE FUNCTION update_app_settings_updated_at();

-- Insert default settings with current ENV values if table is empty
INSERT INTO app_settings (
    id, 
    site_name, 
    trial_days, 
    admin_telegram_ids, 
    admin_usernames, 
    telegram_bot_token
) 
SELECT 
    1,
    'VPN Service',
    7,
    '["352313872"]',
    '["av_nosov", "seo2seo"]',
    '8019787780:AAGy5cBWpQ09yvtDE3sp0AMY7kZyRYbSJqU'
WHERE NOT EXISTS (SELECT 1 FROM app_settings WHERE id = 1);

-- Verify the migration
SELECT 'App settings table created successfully' AS migration_status; 