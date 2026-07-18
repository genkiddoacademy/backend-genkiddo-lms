-- Migration 0022: Add program_id to enrollments for explicit program-level enrollment tracking
-- This enables 1-student-1-program enforcement even when courses are shared across programs.

ALTER TABLE enrollments ADD COLUMN IF NOT EXISTS program_id UUID REFERENCES programs(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_enrollments_program_id ON enrollments(program_id);

-- Backfill: try to infer program_id from existing active enrollments via class_programs + program_courses
UPDATE enrollments e
SET program_id = sub.program_id
FROM (
    SELECT DISTINCT ON (enr.id)
        enr.id AS enrollment_id,
        cp.program_id
    FROM enrollments enr
    JOIN class_programs cp ON cp.class_id = enr.class_id
    JOIN program_courses pc ON pc.program_id = cp.program_id AND pc.course_id = enr.course_id
    WHERE enr.program_id IS NULL AND enr.status = 'active'
) sub
WHERE e.id = sub.enrollment_id;
