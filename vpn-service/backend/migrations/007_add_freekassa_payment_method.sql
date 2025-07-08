-- Migration: Add FreeKassa payment method to PaymentMethod enum
-- This migration adds support for FreeKassa payment method

-- Add FreeKassa value to paymentmethod enum
ALTER TYPE paymentmethod ADD VALUE 'freekassa';
 
-- Commit the change
COMMIT; 