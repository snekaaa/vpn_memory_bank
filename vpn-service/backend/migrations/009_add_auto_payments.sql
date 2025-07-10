-- Migration: Add auto payments support
-- Description: Adds support for recurring payments through Robokassa

-- 1. Add new fields to payments table
ALTER TABLE payments 
ADD COLUMN IF NOT EXISTS robokassa_recurring_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS is_recurring_enabled BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS recurring_period_days INTEGER,
ADD COLUMN IF NOT EXISTS next_payment_date TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS recurring_status VARCHAR(20) DEFAULT 'inactive',
ADD COLUMN IF NOT EXISTS is_recurring_setup BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS is_autopay_generated BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS autopay_attempt_number INTEGER,
ADD COLUMN IF NOT EXISTS autopay_parent_payment_id INTEGER REFERENCES payments(id);

-- 2. Create auto_payments table
CREATE TABLE IF NOT EXISTS auto_payments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subscription_id INTEGER REFERENCES subscriptions(id) ON DELETE SET NULL,
    payment_id INTEGER REFERENCES payments(id) ON DELETE SET NULL,
    robokassa_recurring_id VARCHAR(255) UNIQUE,
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'RUB',
    period_days INTEGER NOT NULL,
    next_payment_date TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(20) DEFAULT 'inactive' CHECK (status IN ('inactive', 'active', 'paused', 'cancelled', 'failed')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    attempts_count INTEGER DEFAULT 0,
    last_attempt_date TIMESTAMP WITH TIME ZONE,
    last_error_type VARCHAR(50),
    is_recurring_id_valid BOOLEAN DEFAULT TRUE
);

-- 3. Create payment_retry_attempts table
CREATE TABLE IF NOT EXISTS payment_retry_attempts (
    id SERIAL PRIMARY KEY,
    auto_payment_id INTEGER NOT NULL REFERENCES auto_payments(id) ON DELETE CASCADE,
    attempt_number INTEGER NOT NULL,
    error_type VARCHAR(50) NOT NULL,
    error_message TEXT,
    robokassa_response TEXT,
    scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
    attempted_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    result VARCHAR(20) CHECK (result IN ('success', 'failed', 'pending')),
    next_attempt_at TIMESTAMP WITH TIME ZONE,
    user_notified BOOLEAN DEFAULT FALSE,
    notification_sent_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Create user_notification_preferences table
CREATE TABLE IF NOT EXISTS user_notification_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notification_type VARCHAR(50) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    frequency VARCHAR(20) DEFAULT 'all',
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, notification_type)
);

-- 5. Add fields to subscriptions table for auto payment support
ALTER TABLE subscriptions
ADD COLUMN IF NOT EXISTS auto_payment_enabled BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS robokassa_recurring_id VARCHAR(255) UNIQUE,
ADD COLUMN IF NOT EXISTS recurring_setup_payment_id INTEGER REFERENCES payments(id),
ADD COLUMN IF NOT EXISTS next_billing_date TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS auto_payment_amount DECIMAL(10, 2),
ADD COLUMN IF NOT EXISTS auto_payment_status VARCHAR(20) DEFAULT 'inactive';

-- 6. Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_auto_payments_user_id ON auto_payments(user_id);
CREATE INDEX IF NOT EXISTS idx_auto_payments_subscription_id ON auto_payments(subscription_id);
CREATE INDEX IF NOT EXISTS idx_auto_payments_status ON auto_payments(status);
CREATE INDEX IF NOT EXISTS idx_auto_payments_next_payment_date ON auto_payments(next_payment_date);
CREATE INDEX IF NOT EXISTS idx_payment_retry_attempts_auto_payment_id ON payment_retry_attempts(auto_payment_id);
CREATE INDEX IF NOT EXISTS idx_payment_retry_attempts_scheduled_at ON payment_retry_attempts(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_subscriptions_next_billing_date ON subscriptions(next_billing_date);
CREATE INDEX IF NOT EXISTS idx_subscriptions_auto_payment_status ON subscriptions(auto_payment_status);

-- 7. Add trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_auto_payments_updated_at BEFORE UPDATE
    ON auto_payments FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_notification_preferences_updated_at BEFORE UPDATE
    ON user_notification_preferences FOR EACH ROW EXECUTE FUNCTION update_updated_at_column(); 