CREATE TABLE IF NOT EXISTS achievements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    icon VARCHAR(100) NOT NULL DEFAULT 'solar:star-bold',
    color VARCHAR(20) NOT NULL DEFAULT '#FFD700',
    category VARCHAR(50) NOT NULL DEFAULT 'lesson', -- lesson, streak, quiz, assignment
    condition_type VARCHAR(50) NOT NULL, -- 'lesson_count', 'streak_days', 'quiz_score', 'complete_course'
    condition_value INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS student_achievements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    achievement_id UUID NOT NULL REFERENCES achievements(id) ON DELETE CASCADE,
    earned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(student_id, achievement_id)
);
