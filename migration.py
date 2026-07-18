import psycopg2
from dotenv import load_dotenv
import os
import sys

# Load local environment variables
load_dotenv()

# Add backend-fastapi directory to path to load config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.core.config import settings

def run_migrations():
    print("Running database migrations...")
    database_url = os.getenv("DATABASE_URL", "").strip()
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "genkiddo_db")
    db_user = os.getenv("DB_USER", "postgres")
    db_pass = os.getenv("DB_PASSWORD", "postgres")

    if database_url:
        print("Connecting to database using DATABASE_URL...")
    else:
        print(f"Connecting to database {db_name} at {db_host}...")
    
    try:
        conn_kwargs = {"dsn": database_url} if database_url else {
            "host": db_host,
            "port": db_port,
            "database": db_name,
            "user": db_user,
            "password": db_pass,
        }
        conn = psycopg2.connect(**conn_kwargs)
        conn.autocommit = False
        cur = conn.cursor()

        # Create schema_migrations table to track applied migrations
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()

        # Find all migrations in the migrations folder
        migrations_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")
        if not os.path.exists(migrations_dir):
            print(f"Migrations directory not found at {migrations_dir}")
            return

        migration_files = sorted([f for f in os.listdir(migrations_dir) if f.endswith(".sql")])
        print(f"Found {len(migration_files)} migration file(s).")

        applied_count = 0
        for filename in migration_files:
            # Check if this migration was already applied
            cur.execute("SELECT 1 FROM schema_migrations WHERE version = %s;", (filename,))
            if cur.fetchone():
                continue

            print(f"Applying migration: {filename}...")
            file_path = os.path.join(migrations_dir, filename)
            with open(file_path, "r") as sql_file:
                sql_content = sql_file.read()

            try:
                if sql_content.strip():
                    cur.execute(sql_content)
                
                # Register the migration as applied
                cur.execute("INSERT INTO schema_migrations (version) VALUES (%s);", (filename,))
                conn.commit()
                print(f"Successfully applied {filename}.")
                applied_count += 1
            except Exception as e:
                conn.rollback()
                print(f"ERROR: Failed to apply migration {filename}. Transaction rolled back.")
                print(f"Detail: {e}")
                raise e

        if applied_count == 0:
            print("All migrations are already up-to-date!")
        else:
            print(f"Successfully applied {applied_count} migrations.")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"Database migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_migrations()
