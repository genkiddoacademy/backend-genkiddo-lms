-- Migration: 0018_multi_course_batches.sql
-- Description: Support multiple programs per batch and dynamic quota.

CREATE TABLE IF NOT EXISTS class_programs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_id UUID NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    program_id UUID NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(class_id, program_id)
);

-- Backfill data from classes.program_id to class_programs
INSERT INTO class_programs (class_id, program_id)
SELECT id, program_id FROM classes WHERE program_id IS NOT NULL
ON CONFLICT DO NOTHING;

-- Note: We keep classes.program_id for now to avoid breaking existing queries immediately, 
-- but we will phase it out in the logic.
