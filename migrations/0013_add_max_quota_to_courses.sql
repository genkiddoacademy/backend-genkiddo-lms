-- Migration: 0013_add_max_quota_to_courses.sql
-- Description: Add max_quota to individual courses so batch capacity is aggregated dynamically.

ALTER TABLE courses ADD COLUMN IF NOT EXISTS max_quota INTEGER DEFAULT 10;
