-- Migration 006: Add FreeKassa Support
-- Date: 2025-01-07
-- Description: Add FreeKassa to payment providers and required fields for admin panel

-- Add freekassa to payment_provider_type enum
ALTER TYPE payment_provider_type ADD VALUE 'freekassa';

-- Add missing fields required for payment provider admin panel
ALTER TABLE payment_providers 
ADD COLUMN min_amount DECIMAL(10,2) DEFAULT 1.00,
ADD COLUMN max_amount DECIMAL(10,2) DEFAULT 100000.00,
ADD COLUMN commission_percent DECIMAL(5,2) DEFAULT 0.00,
ADD COLUMN commission_fixed DECIMAL(10,2) DEFAULT 0.00;

-- Add FreeKassa-specific fields
ALTER TABLE payment_providers
ADD COLUMN success_url VARCHAR(500),
ADD COLUMN failure_url VARCHAR(500),
ADD COLUMN notification_url VARCHAR(500),
ADD COLUMN notification_method VARCHAR(10) DEFAULT 'POST' CHECK (notification_method IN ('GET', 'POST'));

-- Update existing records to have default values
UPDATE payment_providers 
SET min_amount = 1.00, 
    max_amount = 100000.00, 
    commission_percent = 0.00, 
    commission_fixed = 0.00
WHERE min_amount IS NULL;

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_payment_providers_type_status ON payment_providers(provider_type, status);
CREATE INDEX IF NOT EXISTS idx_payment_providers_active ON payment_providers(is_active, is_default);

-- Add comment for documentation
COMMENT ON COLUMN payment_providers.min_amount IS 'Minimum payment amount for this provider';
COMMENT ON COLUMN payment_providers.max_amount IS 'Maximum payment amount for this provider';
COMMENT ON COLUMN payment_providers.commission_percent IS 'Commission percentage (0-100)';
COMMENT ON COLUMN payment_providers.commission_fixed IS 'Fixed commission amount';
COMMENT ON COLUMN payment_providers.success_url IS 'URL to redirect after successful payment';
COMMENT ON COLUMN payment_providers.failure_url IS 'URL to redirect after failed payment';
COMMENT ON COLUMN payment_providers.notification_url IS 'URL for webhook notifications';
COMMENT ON COLUMN payment_providers.notification_method IS 'HTTP method for webhook notifications'; 