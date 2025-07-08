-- Migration: Update PaymentMethod enum with manual payment methods
-- Date: 2025-07-08

-- Add new payment methods to the existing PaymentMethod enum
ALTER TYPE paymentmethod ADD VALUE IF NOT EXISTS 'manual_admin';
ALTER TYPE paymentmethod ADD VALUE IF NOT EXISTS 'manual_trial';
ALTER TYPE paymentmethod ADD VALUE IF NOT EXISTS 'auto_trial';
ALTER TYPE paymentmethod ADD VALUE IF NOT EXISTS 'manual_correction';

-- Note: PostgreSQL enum values cannot be removed once added
-- This migration is safe and will not affect existing data 