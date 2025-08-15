"""
Migration script to add studio_type column to articles table
"""
import sqlite3
import os
from datetime import datetime

def run_migration():
    """Add studio_type column to articles table"""
    db_path = os.path.join('instance', 'inkdrive.db')
    
    if not os.path.exists(db_path):
        print("Database file not found. Please ensure the database exists.")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(articles)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'studio_type' not in columns:
            print("Adding studio_type column to articles table...")
            
            # Add the new column with default value
            cursor.execute("""
                ALTER TABLE articles 
                ADD COLUMN studio_type VARCHAR(50) DEFAULT 'ARTICLE'
            """)
            
            # Update existing records to have 'ARTICLE' as studio_type
            cursor.execute("""
                UPDATE articles 
                SET studio_type = 'ARTICLE' 
                WHERE studio_type IS NULL OR studio_type = ''
            """)
            
            conn.commit()
            print("✅ Successfully added studio_type column and updated existing records")
            
            # Verify the migration
            cursor.execute("SELECT COUNT(*) FROM articles WHERE studio_type = 'ARTICLE'")
            count = cursor.fetchone()[0]
            print(f"✅ Updated {count} existing articles with studio_type = 'ARTICLE'")
            
        else:
            print("✅ studio_type column already exists")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    print(f"Running migration at {datetime.now()}")
    success = run_migration()
    if success:
        print("Migration completed successfully!")
    else:
        print("Migration failed!")
