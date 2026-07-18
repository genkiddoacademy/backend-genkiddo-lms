-- Add dashboard_layout column to classes table
ALTER TABLE classes ADD COLUMN IF NOT EXISTS dashboard_layout JSONB;
