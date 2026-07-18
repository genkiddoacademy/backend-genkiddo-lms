-- Migration: Add waitlisted status to enrollments
-- Date: 2026-06-09

-- 1. Add 'waitlisted' to the status check constraint
ALTER TABLE enrollments DROP CONSTRAINT IF EXISTS enrollments_status_check;
ALTER TABLE enrollments ADD CONSTRAINT enrollments_status_check CHECK (status IN ('active', 'completed', 'dropped', 'waitlisted'));

COMMENT ON COLUMN enrollments.status IS 'Status pendaftaran: active, completed, dropped, waitlisted (daftar tunggu)';
