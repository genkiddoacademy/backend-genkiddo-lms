-- Create file_uploads table to track all uploads from BlockNote or other sources
CREATE TABLE IF NOT EXISTS file_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    mime_type TEXT,
    file_path TEXT NOT NULL,
    file_url TEXT NOT NULL,
    file_size BIGINT,
    owner_id UUID REFERENCES parents(id), -- Tracks which admin/mentor uploaded it
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster lookups
CREATE INDEX idx_file_uploads_owner ON file_uploads(owner_id);
CREATE INDEX idx_file_uploads_filename ON file_uploads(filename);
