import psycopg2
from app.core.config import settings
import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env

def init_db():
    print("Initializing Database...")
    
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("DATABASE_URL not found in .env. Please configure it.")
        return

    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()

        print(f"Connected to {db_url}")

        # 1. Create Roles & Schema Extensions
        print("Creating roles & extensions...")
        cur.execute("CREATE SCHEMA IF NOT EXISTS extensions;")
        cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\" SCHEMA extensions;")
        cur.execute("DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon NOLOGIN; END IF; END $$;")
        cur.execute("GRANT USAGE ON SCHEMA public TO anon;")
        cur.execute("GRANT ALL ON SCHEMA public TO anon;")
        # Fix: Conditional grants, using 1=1 as dummy for non-existent roles
        cur.execute("GRANT ALL ON SCHEMA public TO authenticated;" if os.getenv("DB_AUTH_ROLE") else "SELECT 1;")
        cur.execute("GRANT ALL ON SCHEMA public TO service_role;" if os.getenv("DB_SERVICE_ROLE") else "SELECT 1;")
        
        # 2. Create Tables
        print("Creating tables...")

        # 2. Create Tables
        print("Creating tables...")
        
        tables = [
            """
            CREATE TABLE IF NOT EXISTS admins (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                whatsapp_number TEXT,
                role TEXT DEFAULT 'staff',
                is_active BOOLEAN DEFAULT TRUE,
                is_notified BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS parents (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                whatsapp_number TEXT,
                city TEXT,
                source TEXT,
                password_hash TEXT,
                role TEXT DEFAULT 'parent',
                is_verified BOOLEAN DEFAULT FALSE,
                verification_token TEXT,
                reset_token TEXT,
                reset_expires_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS programs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                title TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                description TEXT,
                image_url TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                max_quota INTEGER DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS classes (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                program_id UUID REFERENCES programs(id) ON DELETE SET NULL,
                name TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                subtitle TEXT,
                base_price NUMERIC NOT NULL,
                category TEXT,
                items TEXT[],
                is_active BOOLEAN DEFAULT TRUE,
                max_quota INTEGER DEFAULT 0,
                filled_quota INTEGER DEFAULT 0,
                start_date DATE,
                end_date DATE,
                mentor_id UUID,
                location TEXT,
                status TEXT DEFAULT 'open' CHECK (status IN ('open', 'almost_full', 'full', 'closed', 'completed')),
                dashboard_layout JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS courses (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                title TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                description TEXT,
                short_desc TEXT,
                thumbnail TEXT,
                level TEXT CHECK (level IN ('beginner', 'intermediate', 'advanced')),
                category TEXT,
                teacher_id UUID REFERENCES admins(id),
                status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                is_featured BOOLEAN DEFAULT FALSE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS chapters (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT,
                sort_order INTEGER DEFAULT 0 NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS quizzes (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                lesson_id UUID,
                title TEXT NOT NULL,
                max_attempts INTEGER,
                duration INTEGER,
                passing_percentage NUMERIC DEFAULT 0,
                total_marks NUMERIC DEFAULT 0,
                shuffle_questions BOOLEAN DEFAULT FALSE,
                limit_questions_to INTEGER,
                enable_negative_marking BOOLEAN DEFAULT FALSE,
                marks_to_cut NUMERIC DEFAULT 0,
                show_answers BOOLEAN DEFAULT FALSE,
                show_submission_history BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS lessons (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                chapter_id UUID REFERENCES chapters(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                content_type TEXT DEFAULT 'rich_text' CHECK (content_type IN ('rich_text', 'quiz')),
                sort_order INTEGER DEFAULT 0 NOT NULL,
                duration_min INTEGER DEFAULT 0,
                is_free BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                quiz_id UUID REFERENCES quizzes(id) ON DELETE SET NULL
            );
            """,
            """
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='quizzes' AND column_name='lesson_id') THEN
                    -- already defined above in CREATE TABLE
                ELSE
                    ALTER TABLE quizzes DROP CONSTRAINT IF EXISTS quizzes_lesson_id_fkey;
                    ALTER TABLE quizzes ADD CONSTRAINT quizzes_lesson_id_fkey FOREIGN KEY (lesson_id) REFERENCES lessons(id) ON DELETE CASCADE;
                    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='quizzes_lesson_id_key') THEN
                        ALTER TABLE quizzes ADD CONSTRAINT quizzes_lesson_id_key UNIQUE (lesson_id);
                    END IF;
                END IF;
            END $$;
            """,
            """
            CREATE TABLE IF NOT EXISTS questions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                quiz_id UUID NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
                question JSONB NOT NULL,
                type TEXT NOT NULL DEFAULT 'Choices' CHECK (type IN ('Choices', 'User Input', 'Open Ended')),
                marks NUMERIC DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                multiple BOOLEAN DEFAULT FALSE,
                option_1 TEXT, option_2 TEXT, option_3 TEXT, option_4 TEXT,
                is_correct_1 BOOLEAN DEFAULT FALSE, is_correct_2 BOOLEAN DEFAULT FALSE, 
                is_correct_3 BOOLEAN DEFAULT FALSE, is_correct_4 BOOLEAN DEFAULT FALSE,
                explanation_1 TEXT, explanation_2 TEXT, explanation_3 TEXT, explanation_4 TEXT,
                possibility_1 TEXT, possibility_2 TEXT, possibility_3 TEXT, possibility_4 TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS lesson_contents (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                lesson_id UUID REFERENCES lessons(id) ON DELETE CASCADE UNIQUE,
                body JSONB DEFAULT '{}'::JSONB NOT NULL,
                plain_text TEXT,
                version INTEGER DEFAULT 1,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS students (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                parent_id UUID REFERENCES parents(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                username TEXT,
                password_hash TEXT,
                age INTEGER NOT NULL,
                gender TEXT NOT NULL,
                coding_experience TEXT,
                interests TEXT[],
                school_origin TEXT,
                last_active_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (parent_id, name)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS enrollments (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                class_id UUID REFERENCES classes(id) ON DELETE SET NULL,
                program_id UUID REFERENCES programs(id) ON DELETE SET NULL,
                status TEXT DEFAULT 'active' CHECK (status IN ('active', 'completed', 'dropped', 'waitlisted')),
                progress_pct NUMERIC DEFAULT 0,
                enrolled_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP WITH TIME ZONE,
                expires_at TIMESTAMP WITH TIME ZONE,
                UNIQUE (student_id, course_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS lesson_progress (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                lesson_id UUID NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
                status TEXT DEFAULT 'not_started' CHECK (status IN ('not_started', 'in_progress', 'completed')),
                score NUMERIC,
                completed_at TIMESTAMP WITH TIME ZONE,
                UNIQUE (student_id, lesson_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS quiz_submissions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                quiz_id UUID NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
                student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                score NUMERIC DEFAULT 0,
                score_out_of NUMERIC DEFAULT 0,
                percentage NUMERIC DEFAULT 0,
                is_open_ended BOOLEAN DEFAULT FALSE,
                result JSONB DEFAULT '[]'::JSONB,
                attempt_number INTEGER DEFAULT 1,
                started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                submitted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (student_id, quiz_id, attempt_number)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS promo_codes (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                code TEXT UNIQUE NOT NULL,
                discount_type TEXT NOT NULL,
                discount_value NUMERIC NOT NULL,
                applicable_class_ids UUID[],
                max_usage INTEGER,
                used_count INTEGER DEFAULT 0,
                min_amount NUMERIC DEFAULT 0,
                min_children INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                expires_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                label TEXT,
                description TEXT
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS registrations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                student_id UUID REFERENCES students(id) ON DELETE CASCADE,
                class_id UUID REFERENCES classes(id),
                promo_code_id UUID REFERENCES promo_codes(id),
                expectation TEXT,
                status TEXT DEFAULT 'pending',
                amount NUMERIC,
                final_amount NUMERIC,
                service_fee NUMERIC DEFAULT 0,
                midtrans_order_id TEXT UNIQUE,
                qris_payload TEXT,
                payment_method TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
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
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS mentors (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                parent_id UUID NOT NULL REFERENCES parents(id) ON DELETE CASCADE,
                bio TEXT,
                expertise TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS schedules (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                enrollment_id UUID REFERENCES enrollments(id) ON DELETE CASCADE,
                course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
                mentor_id UUID REFERENCES mentors(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                class_type TEXT NOT NULL CHECK (class_type IN ('online', 'offline', 'hybrid')),
                start_time TIMESTAMP WITH TIME ZONE NOT NULL,
                end_time TIMESTAMP WITH TIME ZONE NOT NULL,
                location TEXT,
                zoom_meeting_id TEXT,
                zoom_join_url TEXT,
                zoom_start_url TEXT,
                status TEXT DEFAULT 'upcoming' CHECK (status IN ('upcoming', 'ongoing', 'done', 'cancelled')),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS attendances (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                schedule_id UUID REFERENCES schedules(id) ON DELETE CASCADE,
                student_id UUID REFERENCES students(id) ON DELETE CASCADE,
                status TEXT NOT NULL CHECK (status IN ('present', 'absent', 'permission', 'late')),
                notes TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (schedule_id, student_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS session_reports (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                schedule_id UUID REFERENCES schedules(id) ON DELETE CASCADE,
                student_id UUID REFERENCES students(id) ON DELETE CASCADE,
                mentor_id UUID REFERENCES mentors(id) ON DELETE CASCADE,
                material_summary TEXT NOT NULL,
                understanding_score INTEGER CHECK (understanding_score BETWEEN 1 AND 10),
                logic_score INTEGER CHECK (logic_score BETWEEN 1 AND 10),
                creativity_score INTEGER CHECK (creativity_score BETWEEN 1 AND 10),
                independence_score INTEGER CHECK (independence_score BETWEEN 1 AND 10),
                digital_ethics_score INTEGER CHECK (digital_ethics_score BETWEEN 1 AND 10),
                mentor_notes TEXT NOT NULL,
                recommendation TEXT,
                status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'submitted')),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (schedule_id, student_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS final_reports (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                enrollment_id UUID REFERENCES enrollments(id) ON DELETE CASCADE,
                student_id UUID REFERENCES students(id) ON DELETE CASCADE,
                mentor_id UUID REFERENCES mentors(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                strengths TEXT NOT NULL,
                improvements TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                file_url TEXT,
                status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'submitted', 'revision_requested', 'approved', 'published')),
                reviewed_by UUID REFERENCES parents(id) ON DELETE SET NULL,
                reviewed_at TIMESTAMP WITH TIME ZONE,
                published_at TIMESTAMP WITH TIME ZONE,
                revision_notes TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (enrollment_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS certificates (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                enrollment_id UUID REFERENCES enrollments(id) ON DELETE CASCADE,
                student_id UUID REFERENCES students(id) ON DELETE CASCADE,
                certificate_number TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                file_url TEXT,
                status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'issued', 'revoked')),
                approved_by UUID REFERENCES parents(id) ON DELETE SET NULL,
                approved_at TIMESTAMP WITH TIME ZONE,
                issued_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (enrollment_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS notification_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES parents(id) ON DELETE CASCADE,
                channel TEXT NOT NULL CHECK (channel IN ('email', 'whatsapp')),
                event_type TEXT NOT NULL,
                recipient TEXT NOT NULL,
                status TEXT DEFAULT 'pending' CHECK (status IN ('sent', 'failed', 'pending')),
                payload JSONB DEFAULT '{}'::JSONB NOT NULL,
                sent_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS certificate_templates (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT NOT NULL,
                background_url TEXT NOT NULL,
                layout_json JSONB DEFAULT '{}'::JSONB NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_by UUID REFERENCES parents(id) ON DELETE SET NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS mentor_materials (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                mentor_id UUID REFERENCES mentors(id) ON DELETE CASCADE,
                course_id UUID REFERENCES courses(id) ON DELETE SET NULL,
                title TEXT NOT NULL,
                description TEXT,
                file_url TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
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
            """,
            """
            CREATE TABLE IF NOT EXISTS class_materi (
                class_id UUID NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
                course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                PRIMARY KEY (class_id, course_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS program_courses (
                program_id UUID NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
                course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                PRIMARY KEY (program_id, course_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS course_mentors (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                program_id UUID NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
                mentor_id UUID NOT NULL REFERENCES mentors(id) ON DELETE CASCADE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(program_id, mentor_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS assignment_submissions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                assignment_id UUID NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
                student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                submission_url TEXT NOT NULL,
                notes TEXT,
                grade NUMERIC,
                feedback TEXT,
                submitted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                graded_at TIMESTAMP WITH TIME ZONE,
                graded_by UUID REFERENCES parents(id) ON DELETE SET NULL,
                UNIQUE (assignment_id, student_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS shortlinks (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                code TEXT UNIQUE NOT NULL,
                original_url TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                clicks INTEGER DEFAULT 0,
                expires_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS catalog_layout (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                type VARCHAR(50) NOT NULL,
                batch_id UUID REFERENCES classes(id) ON DELETE CASCADE,
                h1 TEXT,
                h2 TEXT,
                paragraph TEXT,
                align VARCHAR(20) DEFAULT 'center',
                color VARCHAR(50) DEFAULT '#F86300',
                order_index INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS class_programs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                class_id UUID NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
                program_id UUID NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(class_id, program_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS payment_groups (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                parent_id UUID NOT NULL REFERENCES parents(id) ON DELETE CASCADE,
                total_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
                service_fee DOUBLE PRECISION DEFAULT 0,
                final_total DOUBLE PRECISION DEFAULT 0,
                midtrans_order_id VARCHAR(255),
                midtrans_payload JSONB,
                status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'paid', 'failed', 'expired')),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS file_uploads (
                id UUID PRIMARY KEY DEFAULT extensions.uuid_generate_v4(),
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                mime_type TEXT,
                file_path TEXT NOT NULL,
                file_url TEXT NOT NULL,
                file_size BIGINT,
                owner_id UUID REFERENCES parents(id),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        ]

        for sql in tables:
            cur.execute(sql)

        # Add payment_group_id FK column before indices (for idx_registrations_payment_group_id)
        cur.execute("ALTER TABLE registrations ADD COLUMN IF NOT EXISTS payment_group_id UUID REFERENCES payment_groups(id);")

        # Create Recommended Indices
        print("Creating recommended indices...")
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_mentors_parent_id ON mentors(parent_id);",
            "CREATE INDEX IF NOT EXISTS idx_schedules_enrollment_id ON schedules(enrollment_id);",
            "CREATE INDEX IF NOT EXISTS idx_schedules_mentor_id ON schedules(mentor_id);",
            "CREATE INDEX IF NOT EXISTS idx_schedules_course_id ON schedules(course_id);",
            "CREATE INDEX IF NOT EXISTS idx_schedules_start_time ON schedules(start_time);",
            "CREATE INDEX IF NOT EXISTS idx_attendances_schedule_id ON attendances(schedule_id);",
            "CREATE INDEX IF NOT EXISTS idx_attendances_student_id ON attendances(student_id);",
            "CREATE INDEX IF NOT EXISTS idx_session_reports_schedule_id ON session_reports(schedule_id);",
            "CREATE INDEX IF NOT EXISTS idx_session_reports_student_id ON session_reports(student_id);",
            "CREATE INDEX IF NOT EXISTS idx_session_reports_mentor_id ON session_reports(mentor_id);",
            "CREATE INDEX IF NOT EXISTS idx_final_reports_enrollment_id ON final_reports(enrollment_id);",
            "CREATE INDEX IF NOT EXISTS idx_final_reports_student_id ON final_reports(student_id);",
            "CREATE INDEX IF NOT EXISTS idx_final_reports_mentor_id ON final_reports(mentor_id);",
            "CREATE INDEX IF NOT EXISTS idx_certificates_enrollment_id ON certificates(enrollment_id);",
            "CREATE INDEX IF NOT EXISTS idx_certificates_student_id ON certificates(student_id);",
            "CREATE INDEX IF NOT EXISTS idx_certificates_number ON certificates(certificate_number);",
            "CREATE INDEX IF NOT EXISTS idx_notification_logs_user_id ON notification_logs(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_notification_logs_created_at ON notification_logs(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_cert_templates_active ON certificate_templates(is_active);",
            "CREATE INDEX IF NOT EXISTS idx_mentor_materials_mentor_id ON mentor_materials(mentor_id);",
            "CREATE INDEX IF NOT EXISTS idx_mentor_materials_course_id ON mentor_materials(course_id);",
            "CREATE INDEX IF NOT EXISTS idx_assignments_batch_id ON assignments(batch_id);",
            "CREATE INDEX IF NOT EXISTS idx_assignments_mentor_id ON assignments(mentor_id);",
            "CREATE INDEX IF NOT EXISTS idx_assignment_submissions_assignment_id ON assignment_submissions(assignment_id);",
            "CREATE INDEX IF NOT EXISTS idx_assignment_submissions_student_id ON assignment_submissions(student_id);",
            "CREATE INDEX IF NOT EXISTS idx_shortlinks_code ON shortlinks(code);",
            "CREATE INDEX IF NOT EXISTS idx_course_mentors_program_id ON course_mentors(program_id);",
            "CREATE INDEX IF NOT EXISTS idx_course_mentors_mentor_id ON course_mentors(mentor_id);",
            "CREATE INDEX IF NOT EXISTS idx_payment_groups_parent_id ON payment_groups(parent_id);",
            "CREATE INDEX IF NOT EXISTS idx_payment_groups_status ON payment_groups(status);",
            "CREATE INDEX IF NOT EXISTS idx_registrations_payment_group_id ON registrations(payment_group_id);",
            "CREATE INDEX IF NOT EXISTS idx_file_uploads_owner ON file_uploads(owner_id);"
        ]
        for idx_sql in indices:
            cur.execute(idx_sql)

        # Fix potential primary key naming collision due to historical tables renaming
        cur.execute("""
        DO $$
        BEGIN
            -- 1. Rename classes_pkey on courses to courses_pkey if it exists
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'classes_pkey' AND table_name = 'courses'
            ) THEN
                ALTER TABLE courses RENAME CONSTRAINT classes_pkey TO courses_pkey;
            END IF;
            
            -- 2. Add primary key constraint on classes(id) if it doesn't exist
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'classes_pkey' AND table_name = 'classes'
            ) THEN
                -- Check if index classes_pkey exists and drop it first to prevent name clash
                IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'classes_pkey') THEN
                    DROP INDEX classes_pkey;
                END IF;
                ALTER TABLE classes ADD CONSTRAINT classes_pkey PRIMARY KEY (id);
            END IF;
        END $$;
        """)

        # 4. Patch existing tables
        print("Patching tables...")
        cur.execute("ALTER TABLE registrations ADD COLUMN IF NOT EXISTS midtrans_order_id TEXT;")
        cur.execute("ALTER TABLE registrations ADD COLUMN IF NOT EXISTS payment_reference TEXT;")
        cur.execute("ALTER TABLE registrations ADD COLUMN IF NOT EXISTS payment_method TEXT;")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_registrations_midtrans_order_id ON registrations(midtrans_order_id);")
        cur.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS username TEXT;")
        cur.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS password_hash TEXT;")
        cur.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS gender TEXT;")
        cur.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMP WITH TIME ZONE;")
        cur.execute("ALTER TABLE programs ADD COLUMN IF NOT EXISTS max_quota INTEGER DEFAULT 0;")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_students_username_unique ON students(username) WHERE username IS NOT NULL;")
        cur.execute("ALTER TABLE certificates ADD COLUMN IF NOT EXISTS file_url TEXT;")
        
        # Safe rename course_id to class_id (revert previous incorrect change)
        cur.execute("""
        DO $$ 
        BEGIN 
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='registrations' AND column_name='course_id') THEN
                ALTER TABLE registrations RENAME COLUMN course_id TO class_id;
            END IF;
        END $$;
        """)

        # Drop old registrations_course_id_fkey constraint and ensure registrations_class_id_fkey constraint points to classes
        cur.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'registrations_course_id_fkey' AND table_name = 'registrations'
            ) THEN
                ALTER TABLE registrations DROP CONSTRAINT registrations_course_id_fkey;
            END IF;
            
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'registrations_class_id_fkey' AND table_name = 'registrations'
            ) THEN
                ALTER TABLE registrations DROP CONSTRAINT registrations_class_id_fkey;
            END IF;
            
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'registrations_class_id_fkey' AND table_name = 'registrations'
            ) THEN
                ALTER TABLE registrations ADD CONSTRAINT registrations_class_id_fkey FOREIGN KEY (class_id) REFERENCES classes(id);
            END IF;
        END $$;
        """)

        # Add missing columns to courses if they don't exist
        course_cols = [
            ("name", "TEXT NOT NULL DEFAULT ''"),
            ("description", "TEXT"),
            ("level", "TEXT"),
            ("category", "TEXT"),
            ("status", "TEXT DEFAULT 'draft'"),
            ("is_published", "BOOLEAN DEFAULT FALSE"),
            ("sort_order", "INTEGER DEFAULT 0"),
            ("image_url", "TEXT")
        ]
        for col, definition in course_cols:
            cur.execute(f"ALTER TABLE courses ADD COLUMN IF NOT EXISTS {col} {definition};")

        # Patch classes to add course_id
        cur.execute("ALTER TABLE classes ADD COLUMN IF NOT EXISTS course_id UUID REFERENCES courses(id) ON DELETE SET NULL;")
        cur.execute("ALTER TABLE classes ADD COLUMN IF NOT EXISTS image_url TEXT;")
        cur.execute("ALTER TABLE classes ADD COLUMN IF NOT EXISTS dashboard_layout JSONB;")


        cur.execute("ALTER TABLE program_courses ADD COLUMN IF NOT EXISTS sort_order INTEGER DEFAULT 0;")
        
        # Patch enrollments to add class_id and expires_at
        cur.execute("ALTER TABLE enrollments ADD COLUMN IF NOT EXISTS class_id UUID REFERENCES classes(id) ON DELETE SET NULL;")
        cur.execute("ALTER TABLE enrollments ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;")

        cur.execute("ALTER TABLE parents ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;")
        cur.execute("ALTER TABLE parents ADD COLUMN IF NOT EXISTS verification_token TEXT;")
        cur.execute("ALTER TABLE parents ADD COLUMN IF NOT EXISTS reset_token TEXT;")
        cur.execute("ALTER TABLE parents ADD COLUMN IF NOT EXISTS reset_expires_at TIMESTAMP WITH TIME ZONE;")
        cur.execute("ALTER TABLE programs ADD COLUMN IF NOT EXISTS max_quota INTEGER DEFAULT 0;")
        cur.execute("ALTER TABLE classes ADD COLUMN IF NOT EXISTS max_quota INTEGER DEFAULT 0;")
        cur.execute("ALTER TABLE classes ADD COLUMN IF NOT EXISTS start_date DATE;")
        cur.execute("ALTER TABLE classes ADD COLUMN IF NOT EXISTS end_date DATE;")
        cur.execute("ALTER TABLE classes ADD COLUMN IF NOT EXISTS mentor_id UUID REFERENCES mentors(id) ON DELETE SET NULL;")
        cur.execute("ALTER TABLE classes ADD COLUMN IF NOT EXISTS location TEXT;")
        cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'classes' AND column_name = 'status'
            ) THEN
                ALTER TABLE classes ADD COLUMN status TEXT DEFAULT 'open' CHECK (status IN ('open', 'almost_full', 'full', 'closed', 'completed'));
            END IF;
        END $$;
        """)
        cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'students' AND column_name = 'status'
            ) THEN
                ALTER TABLE students ADD COLUMN status TEXT DEFAULT 'preview' CHECK (status IN ('preview', 'active', 'suspended', 'archived'));
            END IF;
        END $$;
        """)

        cur.execute("""
        CREATE OR REPLACE FUNCTION update_class_quota_trigger()
        RETURNS TRIGGER AS $$
        DECLARE
            v_max_quota INTEGER;
            v_filled_quota INTEGER;
            v_class_id UUID;
            v_old_active BOOLEAN;
            v_new_active BOOLEAN;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                v_class_id := NEW.class_id;
                v_old_active := FALSE;
                v_new_active := NEW.status IN ('pending', 'paid', 'active', 'completed');
            ELSIF TG_OP = 'UPDATE' THEN
                v_class_id := NEW.class_id;
                v_old_active := OLD.status IN ('pending', 'paid', 'active', 'completed');
                v_new_active := NEW.status IN ('pending', 'paid', 'active', 'completed');
            ELSIF TG_OP = 'DELETE' THEN
                v_class_id := OLD.class_id;
                v_old_active := OLD.status IN ('pending', 'paid', 'active', 'completed');
                v_new_active := FALSE;
            END IF;

            IF v_class_id IS NOT NULL THEN
                SELECT max_quota, filled_quota INTO v_max_quota, v_filled_quota 
                FROM classes WHERE id = v_class_id;
                
                IF v_max_quota IS NULL THEN
                    v_max_quota := 0;
                END IF;
                IF v_filled_quota IS NULL THEN
                    v_filled_quota := 0;
                END IF;

                IF v_new_active AND NOT v_old_active THEN
                    v_filled_quota := v_filled_quota + 1;
                ELSIF NOT v_new_active AND v_old_active THEN
                    v_filled_quota := GREATEST(0, v_filled_quota - 1);
                END IF;

                UPDATE classes 
                SET 
                    filled_quota = v_filled_quota,
                    status = CASE 
                        WHEN v_filled_quota >= v_max_quota THEN 'full'
                        WHEN v_filled_quota >= FLOOR(v_max_quota * 0.8) THEN 'almost_full'
                        ELSE 'open'
                    END
                WHERE id = v_class_id;
            END IF;
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """)

        cur.execute("DROP TRIGGER IF EXISTS trg_update_class_quota ON registrations;")
        cur.execute("""
        CREATE TRIGGER trg_update_class_quota
        AFTER INSERT OR UPDATE OR DELETE ON registrations
        FOR EACH ROW
        EXECUTE FUNCTION update_class_quota_trigger();
        """)

        # 5. Create Admin User
        print("Ensuring admin user exists...")
        import bcrypt
        admin_email = os.getenv("ADMIN_EMAIL", "admin@genkiddo.id")
        admin_pass = os.getenv("ADMIN_PASSWORD", "admin123")
        
        cur.execute("SELECT id FROM parents WHERE email = %s", (admin_email,))
        if not cur.fetchone():
            hashed = bcrypt.hashpw(admin_pass.encode(), bcrypt.gensalt()).decode()
            cur.execute(
                "INSERT INTO parents (email, name, password_hash, role) VALUES (%s, %s, %s, %s)",
                (admin_email, "Admin Genkiddo", hashed, "admin")
            )
            print(f"Admin user {admin_email} created.")
        else:
            print(f"Admin user {admin_email} already exists.")

        # 6. Seed Classes
        classes_data = [
            {
                "name": "GenLive",
                "display_name": "GenLive",
                "subtitle": "Kelas online",
                "base_price": 295000,
                "category": "Online",
                "items": [
                    "Kelas online, maksimal tiga anak satu kelas",
                    "1 minggu sekali 90 menit per pertemuan",
                    "Ada 3 level disesuaikan dengan usia dan kemampuan",
                    "Periode 1 bulan"
                ]
            },
            {
                "name": "GenSquad",
                "display_name": "GenSquad",
                "subtitle": "Kelas offline tatap muka",
                "base_price": 315000,
                "category": "Offline",
                "items": [
                    "Kelas offline tatap muka, tiga anak per grup",
                    "1 minggu sekali 90 menit per pertemuan",
                    "Ada 3 level disesuaikan dengan usia dan kemampuan",
                    "Periode 1 bulan"
                ]
            },
            {
                "name": "GenConnect",
                "display_name": "GenConnect",
                "subtitle": "Online Zoom/Gmeet 1 on 1",
                "base_price": 400000,
                "category": "Online",
                "items": [
                    "Online Zoom/Gmeet 1 on 1 bersama tutor",
                    "1 minggu sekali 90 menit per pertemuan",
                    "Ada 3 level disesuaikan dengan usia dan kemampuan",
                    "Periode 1 bulan"
                ]
            },
            {
                "name": "GenHome",
                "display_name": "GenHome",
                "subtitle": "Offline 1 on 1",
                "base_price": 420000,
                "category": "Offline",
                "items": [
                    "Offline 1 on 1 dengan tutor langsung",
                    "1 minggu sekali 90 menit per pertemuan",
                    "Ada 3 level disesuaikan dengan usia dan kemampuan",
                    "Periode 1 bulan"
                ]
            }
        ]
        
        print("Ensuring classes exist...")
        for cls in classes_data:
            cur.execute("SELECT id FROM classes WHERE name = %s", (cls["name"],))
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO classes (name, display_name, subtitle, base_price, category, items) VALUES (%s, %s, %s, %s, %s, %s)",
                    (cls["name"], cls["display_name"], cls["subtitle"], cls["base_price"], cls["category"], cls["items"])
                )
                print(f"Class {cls['name']} created.")

        # 7. Seed Default Course
        print("Ensuring default course 'Scratch dasar' exists and is active...")
        cur.execute("SELECT id FROM courses WHERE slug = 'scratch-dasar';")
        course_row = cur.fetchone()
        if not course_row:
            cur.execute(
                "INSERT INTO courses (title, slug, description, short_desc, level, category, status, is_active) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;",
                ("Scratch dasar", "scratch-dasar", "Belajar pemrograman Scratch tingkat dasar untuk anak-anak.", "Belajar Scratch dasar", "beginner", "Coding", "published", True)
            )
            course_id = cur.fetchone()[0]
            print(f"Course 'Scratch dasar' created with ID: {course_id}")
        else:
            course_id = course_row[0]
            cur.execute("UPDATE courses SET status = 'published', is_active = True WHERE id = %s", (course_id,))
            print(f"Course 'Scratch dasar' (ID: {course_id}) set to published & active.")

        # Link classes without course_id to default Scratch dasar course
        cur.execute("UPDATE classes SET course_id = %s WHERE course_id IS NULL;", (course_id,))
        print("Linked classes without course_id to default Scratch dasar course.")

        # Seed class_materi junction from existing classes
        cur.execute("INSERT INTO class_materi (class_id, course_id) SELECT id, course_id FROM classes WHERE course_id IS NOT NULL ON CONFLICT DO NOTHING;")
        print("Seeded class_materi from classes.")

        # Backfill class_id in enrollments table based on registrations
        cur.execute("""
        UPDATE enrollments e
        SET class_id = r.class_id
        FROM registrations r
        WHERE e.student_id = r.student_id AND r.class_id IS NOT NULL AND e.class_id IS NULL;
        """)
        print("Backfilled class_id in enrollments.")

        # 8. Seed Students and Enrollments for Parents
        print("Ensuring students and enrollments exist for parents...")
        cur.execute("SELECT id, email, name FROM parents WHERE role = 'parent';")
        parents = cur.fetchall()
        for parent_id, parent_email, parent_name in parents:
            cur.execute("SELECT id FROM students WHERE parent_id = %s", (parent_id,))
            student_row = cur.fetchone()
            if not student_row:
                student_name = f"Anak {parent_name}"
                cur.execute(
                    "INSERT INTO students (parent_id, name, age, gender, coding_experience, interests) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;",
                    (parent_id, student_name, 10, "Laki-laki", "None", ["Membuat Game Sederhana"])
                )
                student_id = cur.fetchone()[0]
                print(f"Student '{student_name}' created for parent {parent_email}.")
            else:
                student_id = student_row[0]
            
            # Enroll the student in the default course
            cur.execute("SELECT id FROM enrollments WHERE student_id = %s AND course_id = %s", (student_id, course_id))
            if not cur.fetchone():
                # Get class_id associated with this course if exists
                cur.execute("SELECT id FROM classes WHERE course_id = %s LIMIT 1;", (course_id,))
                class_row = cur.fetchone()
                assoc_class_id = class_row[0] if class_row else None
                
                cur.execute(
                    "INSERT INTO enrollments (student_id, course_id, class_id, status) VALUES (%s, %s, %s, 'active')",
                    (student_id, course_id, assoc_class_id)
                )
                print(f"Enrolled student (ID: {student_id}) in course (ID: {course_id}) under class (ID: {assoc_class_id}).")

        # 9. Seed Sample Mentor
        print("Ensuring sample mentor exists...")
        mentor_email = "mentor@genkiddo.id"
        mentor_pass = "mentor123"
        cur.execute("SELECT id FROM parents WHERE email = %s", (mentor_email,))
        mentor_parent_row = cur.fetchone()
        if not mentor_parent_row:
            import bcrypt
            hashed = bcrypt.hashpw(mentor_pass.encode(), bcrypt.gensalt()).decode()
            cur.execute(
                "INSERT INTO parents (email, name, password_hash, role, city) VALUES (%s, %s, %s, %s, %s) RETURNING id;",
                (mentor_email, "Mentor Genkiddo", hashed, "mentor", "Jakarta")
            )
            mentor_parent_id = cur.fetchone()[0]
            print(f"Mentor parent account {mentor_email} created.")
        else:
            mentor_parent_id = mentor_parent_row[0]
            
        cur.execute("SELECT id FROM mentors WHERE parent_id = %s", (mentor_parent_id,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO mentors (parent_id, bio, expertise, is_active) VALUES (%s, %s, %s, %s);",
                (mentor_parent_id, "Mentor berpengalaman di bidang Scratch dan game development untuk anak-anak.", "Scratch, Python, Web Development", True)
            )
            print(f"Mentor profile created for {mentor_email}.")

        # 10. Seed Catalog Layout
        print("Ensuring catalog layout is seeded...")
        cur.execute("SELECT COUNT(*) FROM catalog_layout;")
        if cur.fetchone()[0] == 0:
            cur.execute("SELECT id, name FROM classes;")
            class_map = {row[1]: row[0] for row in cur.fetchall()}
            
            layout_data = [
                {
                    "type": "section",
                    "batch_id": None,
                    "h1": "GenPrivate",
                    "h2": "Pembelajaran Personal",
                    "paragraph": None,
                    "align": "center",
                    "color": "#F86300",
                    "order_index": 0
                }
            ]
            
            if "GenConnect" in class_map:
                layout_data.append({
                    "type": "batch",
                    "batch_id": class_map["GenConnect"],
                    "h1": None, "h2": None, "paragraph": None, "align": "center", "color": "#F86300",
                    "order_index": 1
                })
            
            if "GenHome" in class_map:
                layout_data.append({
                    "type": "batch",
                    "batch_id": class_map["GenHome"],
                    "h1": None, "h2": None, "paragraph": None, "align": "center", "color": "#F86300",
                    "order_index": 2
                })
                
            layout_data.append({
                "type": "section",
                "batch_id": None,
                "h1": "GenClass",
                "h2": "Pembelajaran Kelompok",
                "paragraph": None,
                "align": "center",
                "color": "#F86300",
                "order_index": 3
            })
            
            if "GenLive" in class_map:
                layout_data.append({
                    "type": "batch",
                    "batch_id": class_map["GenLive"],
                    "h1": None, "h2": None, "paragraph": None, "align": "center", "color": "#F86300",
                    "order_index": 4
                })
                
            if "GenSquad" in class_map:
                layout_data.append({
                    "type": "batch",
                    "batch_id": class_map["GenSquad"],
                    "h1": None, "h2": None, "paragraph": None, "align": "center", "color": "#F86300",
                    "order_index": 5
                })
                
            for item in layout_data:
                cur.execute(
                    """
                    INSERT INTO catalog_layout (type, batch_id, h1, h2, paragraph, align, color, order_index)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (item["type"], item["batch_id"], item["h1"], item["h2"], item["paragraph"], item["align"], item["color"], item["order_index"])
                )
            print("Seeded catalog_layout table with default layout.")

        # 3. Grant Permissions
        print("Granting permissions...")
        cur.execute("GRANT ALL ON ALL TABLES IN SCHEMA public TO anon;")
        cur.execute("GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon;")

        print("Database initialization complete!")
        
        cur.close()
        conn.close()

    except Exception as e:
        print(f"Error initializing database: {e}")

if __name__ == "__main__":
    init_db()
