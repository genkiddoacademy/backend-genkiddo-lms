-- Create shortlinks table for click-tracking URL redirections
CREATE TABLE IF NOT EXISTS shortlinks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT UNIQUE NOT NULL,
    original_url TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    clicks INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast code resolution
CREATE INDEX IF NOT EXISTS idx_shortlinks_code ON shortlinks(code);
