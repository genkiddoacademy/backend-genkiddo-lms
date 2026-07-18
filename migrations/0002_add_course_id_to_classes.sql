-- Migration: 0002_add_course_id_to_classes.sql
-- Description: Add course_id column to classes table for dynamic course linkages.

ALTER TABLE classes ADD COLUMN IF NOT EXISTS course_id UUID REFERENCES courses(id) ON DELETE SET NULL;
