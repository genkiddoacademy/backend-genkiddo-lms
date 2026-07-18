ALTER TABLE classes ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0;
ALTER TABLE classes ADD COLUMN IF NOT EXISTS layout_variant TEXT NOT NULL DEFAULT 'medium' CHECK (layout_variant IN ('featured', 'small', 'medium'));
