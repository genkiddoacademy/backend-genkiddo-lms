-- Migration: 0017_add_last_active_at_to_students.sql
-- Description: Add last_active_at column to students table to track online status.

ALTER TABLE students ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMP WITH TIME ZONE;
