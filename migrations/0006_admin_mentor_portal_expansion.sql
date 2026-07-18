-- Migration: 0006_admin_mentor_portal_expansion.sql
-- Description: Add admin payment verification fields and mentor assignment tables.

ALTER TABLE registrations ADD COLUMN IF NOT EXISTS manual_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE registrations ADD COLUMN IF NOT EXISTS verified_by UUID REFERENCES parents(id) ON DELETE SET NULL;
ALTER TABLE registrations ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE registrations ADD COLUMN IF NOT EXISTS midtrans_transaction_status TEXT;
ALTER TABLE registrations ADD COLUMN IF NOT EXISTS payment_type TEXT;

CREATE TABLE IF NOT EXISTS mentor_materials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mentor_id UUID REFERENCES mentors(id) ON DELETE CASCADE,
    course_id UUID REFERENCES courses(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT,
    file_url TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID REFERENCES classes(id) ON DELETE CASCADE,
    course_id UUID REFERENCES courses(id) ON DELETE SET NULL,
    mentor_id UUID REFERENCES mentors(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT,
    assignment_type TEXT DEFAULT 'task' CHECK (assignment_type IN ('task', 'quiz')),
    due_at TIMESTAMP WITH TIME ZONE,
    attachment_url TEXT,
    status TEXT DEFAULT 'published' CHECK (status IN ('draft', 'published', 'archived')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mentor_materials_mentor_id ON mentor_materials(mentor_id);
CREATE INDEX IF NOT EXISTS idx_mentor_materials_course_id ON mentor_materials(course_id);
CREATE INDEX IF NOT EXISTS idx_assignments_batch_id ON assignments(batch_id);
CREATE INDEX IF NOT EXISTS idx_assignments_mentor_id ON assignments(mentor_id);
