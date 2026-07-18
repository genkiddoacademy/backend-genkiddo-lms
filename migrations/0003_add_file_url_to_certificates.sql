-- Migration: 0003_add_file_url_to_certificates.sql
-- Description: Add file_url column to certificates table.

ALTER TABLE certificates ADD COLUMN IF NOT EXISTS file_url TEXT;
