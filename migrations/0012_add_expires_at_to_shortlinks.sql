-- Add expires_at column to shortlinks table
ALTER TABLE shortlinks ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE DEFAULT NULL;
