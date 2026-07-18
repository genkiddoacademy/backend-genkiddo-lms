-- Migration: 0016_remove_max_quota_from_courses.sql
-- Description: Remove max_quota from courses table as capacity is managed at the batch/program level.

ALTER TABLE courses DROP COLUMN IF EXISTS max_quota;
