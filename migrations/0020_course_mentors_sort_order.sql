-- Migration: Course Mentors & Material Sort Order
-- Adds multi-mentor support for courses (programs) and sort_order for material bundling

CREATE TABLE IF NOT EXISTS course_mentors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_id UUID NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
    mentor_id UUID NOT NULL REFERENCES mentors(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(program_id, mentor_id)
);

-- Add sort_order to program_courses for DnD ordering
ALTER TABLE program_courses ADD COLUMN IF NOT EXISTS sort_order INTEGER DEFAULT 0;

-- Index for course_mentors
CREATE INDEX IF NOT EXISTS idx_course_mentors_program_id ON course_mentors(program_id);
CREATE INDEX IF NOT EXISTS idx_course_mentors_mentor_id ON course_mentors(mentor_id);
