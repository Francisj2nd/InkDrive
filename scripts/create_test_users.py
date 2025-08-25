import sqlite3
import os
from werkzeug.security import generate_password_hash

# Get the absolute path to the database file
db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'instance', 'inkdrive.db'))

def create_users():
    """Creates a regular user and a super admin user"""
    conn = None
    try:
        print(f"Connecting to database at: {db_path}")
        if not os.path.exists(db_path):
            print("Database file does not exist. Cannot create users.")
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create regular user
        print("Creating regular user...")
        cursor.execute("INSERT INTO users (email, name, password_hash, is_superadmin) VALUES (?, ?, ?, ?)",
                       ('testuser@example.com', 'Test User', generate_password_hash('password'), False))

        # Create super admin user
        print("Creating super admin user...")
        cursor.execute("INSERT INTO users (email, name, password_hash, is_superadmin) VALUES (?, ?, ?, ?)",
                       ('superadmin@example.com', 'Super Admin', generate_password_hash('password'), True))

        conn.commit()
        print("Successfully created users.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    create_users()
