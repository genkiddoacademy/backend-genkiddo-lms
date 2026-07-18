-- Description: Add service_fee to registrations table to support service fees on QRIS and Bank Transfer (Virtual Account) payments.
ALTER TABLE registrations ADD COLUMN IF NOT EXISTS service_fee NUMERIC DEFAULT 0;
