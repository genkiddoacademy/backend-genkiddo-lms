-- Migration: 0024_sync_and_default_quota.sql
-- Description: Sync junction tables and ensure max_quota defaults to 0.

-- 1. Create junction tables if missing
CREATE TABLE IF NOT EXISTS class_programs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_id UUID NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    program_id UUID NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(class_id, program_id)
);

-- 2. Sync relationships
INSERT INTO class_programs (class_id, program_id)
SELECT id, program_id FROM classes WHERE program_id IS NOT NULL ON CONFLICT DO NOTHING;

INSERT INTO class_materi (class_id, course_id)
SELECT id, course_id FROM classes WHERE course_id IS NOT NULL ON CONFLICT DO NOTHING;

-- 3. Set Defaults
ALTER TABLE classes ALTER COLUMN max_quota SET DEFAULT 0;
ALTER TABLE programs ALTER COLUMN max_quota SET DEFAULT 0;

-- 4. Fix historical bugged values
UPDATE classes SET max_quota = 0 WHERE max_quota = 10;
UPDATE programs SET max_quota = 0 WHERE max_quota = 10;

-- 5. Add missing program_id to enrollments (from migration 0022 that might have failed)
ALTER TABLE enrollments ADD COLUMN IF NOT EXISTS program_id UUID REFERENCES programs(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_enrollments_program_id ON enrollments(program_id);

-- Backfill data
UPDATE enrollments
SET program_id = cp.program_id
FROM class_programs cp
WHERE enrollments.class_id = cp.class_id AND enrollments.program_id IS NULL;
