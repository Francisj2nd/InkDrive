import sqlite3
import os

# Get the absolute path to the database file
db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'instance', 'inkdrive.db'))

def drop_columns():
    """Drops publishing-related columns from the articles table"""
    conn = None
    try:
        print(f"Connecting to database at: {db_path}")
        if not os.path.exists(db_path):
            print("Database file does not exist. No migration needed.")
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get table info to check for columns
        cursor.execute("PRAGMA table_info(articles)")
        columns = [row[1] for row in cursor.fetchall()]

        # Drop index if it exists
        cursor.execute("PRAGMA index_list(articles)")
        indexes = [row[1] for row in cursor.fetchall()]
        if 'ix_articles_public_id' in indexes:
            print("Dropping index: ix_articles_public_id")
            cursor.execute('DROP INDEX ix_articles_public_id')
        else:
            print("Index ix_articles_public_id does not exist.")

        # Drop columns if they exist
        if 'is_public' in columns:
            print("Dropping column: is_public")
            cursor.execute('ALTER TABLE articles DROP COLUMN is_public')
        else:
            print("Column is_public does not exist.")

        if 'public_id' in columns:
            print("Dropping column: public_id")
            cursor.execute('ALTER TABLE articles DROP COLUMN public_id')
        else:
            print("Column public_id does not exist.")

        if 'published_at' in columns:
            print("Dropping column: published_at")
            cursor.execute('ALTER TABLE articles DROP COLUMN published_at')
        else:
            print("Column published_at does not exist.")

        conn.commit()
        print("Successfully dropped columns.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    drop_columns()
