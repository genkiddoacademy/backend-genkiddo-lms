-- Migration: 0008_system_flows_enhancements.sql
-- Description: Add fields for email verification on parents, and quota/details on classes (batches).

-- 1. Add email verification fields to parents
ALTER TABLE parents 
ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS verification_token TEXT;

-- 2. Add quota, duration, mentor, and status fields to classes (batches)
ALTER TABLE classes
ADD COLUMN IF NOT EXISTS max_quota INTEGER DEFAULT 10,
ADD COLUMN IF NOT EXISTS filled_quota INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS start_date DATE,
ADD COLUMN IF NOT EXISTS end_date DATE,
ADD COLUMN IF NOT EXISTS mentor_id UUID REFERENCES mentors(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS location TEXT,
ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'open' CHECK (status IN ('open', 'almost_full', 'full', 'closed', 'completed'));
