import sqlite3
import os

# Get the absolute path to the database file
db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'instance', 'inkdrive.db'))

def drop_column():
    """Drops the view_count column from the articles table"""
    conn = None
    try:
        print(f"Connecting to database at: {db_path}")
        if not os.path.exists(db_path):
            print("Database file does not exist. No migration needed.")
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get table info to check for the column
        cursor.execute("PRAGMA table_info(articles)")
        columns = [row[1] for row in cursor.fetchall()]

        # Add column if it doesn't exist
        if 'view_count' in columns:
            print("Dropping column: view_count")
            cursor.execute('ALTER TABLE articles DROP COLUMN view_count')
        else:
            print("Column view_count already exists.")

        conn.commit()
        print("Successfully dropped column.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    drop_column()
