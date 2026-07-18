-- Migration: Update classes default max_quota to 0
-- Created at: 2026-06-09

ALTER TABLE classes ALTER COLUMN max_quota SET DEFAULT 0;
UPDATE classes SET max_quota = 0 WHERE id IN (
    SELECT c.id FROM classes c 
    LEFT JOIN class_materi cc ON c.id = cc.class_id 
    WHERE cc.course_id IS NULL AND c.max_quota = 10
);
