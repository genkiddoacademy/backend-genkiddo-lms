-- Migration: Add max_quota to programs
-- Description: Adds a max_quota column to the programs table to support global program capacity tracking.

ALTER TABLE programs ADD COLUMN IF NOT EXISTS max_quota INTEGER DEFAULT 0;
