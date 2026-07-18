CREATE TABLE IF NOT EXISTS discovery_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES students(id) ON DELETE SET NULL,
    parent_id UUID REFERENCES parents(id) ON DELETE SET NULL,
    program_name TEXT,
    course_name TEXT,
    session_number INTEGER NOT NULL CHECK (session_number > 0),
    session_title TEXT NOT NULL,
    session_date DATE NOT NULL,
    mentor_name TEXT,
    attendance_status TEXT NOT NULL DEFAULT 'present' CHECK (attendance_status IN ('present', 'excused', 'absent')),
    learning_summary TEXT NOT NULL,
    activities TEXT NOT NULL,
    project_result TEXT,
    material_score INTEGER NOT NULL CHECK (material_score BETWEEN 1 AND 5),
    logic_score INTEGER NOT NULL CHECK (logic_score BETWEEN 1 AND 5),
    practice_score INTEGER NOT NULL CHECK (practice_score BETWEEN 1 AND 5),
    creativity_score INTEGER NOT NULL CHECK (creativity_score BETWEEN 1 AND 5),
    focus_score INTEGER NOT NULL CHECK (focus_score BETWEEN 1 AND 5),
    digital_ethics_score INTEGER CHECK (digital_ethics_score BETWEEN 1 AND 5),
    communication_score INTEGER CHECK (communication_score BETWEEN 1 AND 5),
    strengths TEXT NOT NULL,
    improvements TEXT NOT NULL,
    parent_recommendation TEXT NOT NULL,
    next_session_plan TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_discovery_assessments_student_id
ON discovery_assessments(student_id);

CREATE INDEX IF NOT EXISTS idx_discovery_assessments_parent_id
ON discovery_assessments(parent_id);

CREATE INDEX IF NOT EXISTS idx_discovery_assessments_status
ON discovery_assessments(status);
