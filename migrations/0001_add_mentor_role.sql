-- Migration: 0001_add_mentor_role.sql
-- Description: Drop any old parent role check constraints to allow the 'mentor' role.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'parents_role_check' AND table_name = 'parents'
    ) THEN
        ALTER TABLE parents DROP CONSTRAINT parents_role_check;
    END IF;
END $$;
