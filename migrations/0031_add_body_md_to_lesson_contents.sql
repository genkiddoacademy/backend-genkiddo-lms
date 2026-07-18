ALTER TABLE lesson_contents ADD COLUMN IF NOT EXISTS body_md TEXT;
ALTER TABLE lesson_contents ALTER COLUMN body DROP NOT NULL;
ALTER TABLE lesson_contents ALTER COLUMN body SET DEFAULT '[]'::jsonb;
