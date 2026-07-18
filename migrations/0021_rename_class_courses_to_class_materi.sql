-- Rename class_courses → class_materi to avoid confusion
-- (course here actually means "materi", not "program")
ALTER TABLE IF EXISTS class_courses RENAME TO class_materi;

-- Update index name for consistency
DROP INDEX IF EXISTS idx_class_courses_class_course;
CREATE INDEX IF NOT EXISTS idx_class_materi_class_course ON class_materi(class_id, course_id);

-- Update sequence name if any
ALTER SEQUENCE IF EXISTS class_courses_id_seq RENAME TO class_materi_id_seq;
