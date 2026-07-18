import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import psycopg2
from app.core.config import settings

def main():
    print("Connecting to database...")
    conn = psycopg2.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            # 1. Create programs table
            print("Creating programs table...")
            cur.execute("""
            CREATE TABLE IF NOT EXISTS programs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                title TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                description TEXT,
                image_url TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 2. Create program_courses junction table
            print("Creating program_courses table...")
            cur.execute("""
            CREATE TABLE IF NOT EXISTS program_courses (
                program_id UUID NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
                course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                PRIMARY KEY (program_id, course_id)
            );
            """)

            # 3. Add program_id to classes table
            print("Adding program_id to classes table...")
            cur.execute("""
            ALTER TABLE classes ADD COLUMN IF NOT EXISTS program_id UUID REFERENCES programs(id) ON DELETE SET NULL;
            """)
            print("Migration completed successfully!")
    except Exception as e:
        print("Migration failed:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
