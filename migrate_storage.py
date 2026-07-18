import os
import psycopg2

def migrate():
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "genkiddo_db")
    db_user = os.getenv("DB_USER", "postgres")
    db_pass = os.getenv("DB_PASSWORD", "postgres")

    print(f"Connecting to database {db_name} at {db_host}:{db_port}...")
    try:
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_pass
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        # 1. Create final_reports if not exists
        print("Ensuring 'final_reports' table exists...")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS public.final_reports (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            student_id UUID REFERENCES public.students(id) ON DELETE CASCADE,
            course_id UUID REFERENCES public.courses(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            file_url TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # 2. Create certificates if not exists
        print("Ensuring 'certificates' table exists...")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS public.certificates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            student_id UUID REFERENCES public.students(id) ON DELETE CASCADE,
            course_id UUID REFERENCES public.courses(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            file_url TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # 3. Add file_url column to final_reports if not exists (in case table existed but lacked it)
        print("Ensuring 'file_url' column exists in 'final_reports'...")
        cur.execute("""
        ALTER TABLE public.final_reports ADD COLUMN IF NOT EXISTS file_url TEXT;
        """)
        
        # 4. Add file_url column to certificates if not exists (in case table existed but lacked it)
        print("Ensuring 'file_url' column exists in 'certificates'...")
        cur.execute("""
        ALTER TABLE public.certificates ADD COLUMN IF NOT EXISTS file_url TEXT;
        """)

        # 5. Grant permissions to tables
        print("Granting permissions to tables...")
        cur.execute("GRANT ALL ON TABLE public.final_reports TO anon;")
        cur.execute("GRANT ALL ON TABLE public.certificates TO anon;")
        
        print("Migration completed successfully!")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Migration error: {e}")

if __name__ == "__main__":
    migrate()
