import sqlite3
import os

# Get the absolute path to the database file
db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'instance', 'inkdrive.db'))

def add_column():
    """Adds the is_superadmin column to the users table"""
    conn = None
    try:
        print(f"Connecting to database at: {db_path}")
        if not os.path.exists(db_path):
            print("Database file does not exist. No migration needed.")
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get table info to check for the column
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]

        # Add column if it doesn't exist
        if 'is_superadmin' not in columns:
            print("Adding column: is_superadmin")
            cursor.execute('ALTER TABLE users ADD COLUMN is_superadmin BOOLEAN DEFAULT FALSE')
        else:
            print("Column is_superadmin already exists.")

        conn.commit()
        print("Successfully added column.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    add_column()
