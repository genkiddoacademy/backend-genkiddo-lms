-- 1. Create class_courses junction table to support multiple courses per program/class
CREATE TABLE IF NOT EXISTS class_courses (
    class_id UUID NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    PRIMARY KEY (class_id, course_id)
);

-- Migrate existing course_id relationship from classes to class_courses
INSERT INTO class_courses (class_id, course_id)
SELECT id, course_id FROM classes 
WHERE course_id IS NOT NULL
ON CONFLICT DO NOTHING;

-- 2. Add class_id and expires_at to enrollments
ALTER TABLE enrollments ADD COLUMN IF NOT EXISTS class_id UUID REFERENCES classes(id) ON DELETE SET NULL;
ALTER TABLE enrollments ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;

-- Backfill class_id in enrollments table based on registrations if possible
DO $$
BEGIN
    UPDATE enrollments e
    SET class_id = r.class_id
    FROM registrations r
    WHERE e.student_id = r.student_id AND r.class_id IS NOT NULL AND e.class_id IS NULL;
END $$;

-- 3. Create assignment_submissions table to support Task / Project submissions
CREATE TABLE IF NOT EXISTS assignment_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id UUID NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    submission_url TEXT NOT NULL,
    notes TEXT,
    grade NUMERIC,
    feedback TEXT,
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    graded_at TIMESTAMP WITH TIME ZONE,
    graded_by UUID REFERENCES parents(id) ON DELETE SET NULL,
    UNIQUE (assignment_id, student_id)
);

-- Add index on assignment_submissions
CREATE INDEX IF NOT EXISTS idx_assignment_submissions_assignment_id ON assignment_submissions(assignment_id);
CREATE INDEX IF NOT EXISTS idx_assignment_submissions_student_id ON assignment_submissions(student_id);
