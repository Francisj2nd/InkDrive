#!/usr/bin/env python3
"""
Script to fix missing database columns
Run this to add any missing columns to existing tables
"""

import os
import sys
from app import app, db
import logging
from sqlalchemy import text, inspect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_missing_columns():
    """Add any missing columns to existing tables"""
    try:
        with app.app_context():
            logger.info("🔧 Checking for missing database columns...")
            
            inspector = inspect(db.engine)
            
            # Check users table
            users_columns = [col['name'] for col in inspector.get_columns('users')]
            logger.info(f"Current users columns: {users_columns}")
            
            # Add missing updated_at column to users table
            if 'updated_at' not in users_columns:
                logger.info("Adding missing updated_at column to users table...")
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE users ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'))
                    conn.commit()
                logger.info("✅ Added updated_at column to users table")
            
            # Check articles table
            articles_columns = [col['name'] for col in inspector.get_columns('articles')]
            logger.info(f"Current articles columns: {articles_columns}")
            
            # Add any other missing columns as needed
            missing_articles_columns = []
            required_articles_columns = {
                'is_public': 'BOOLEAN DEFAULT FALSE',
                'published_at': 'TIMESTAMP',
                'view_count': 'INTEGER DEFAULT 0',
                'download_count': 'INTEGER DEFAULT 0',
                'meta_description': 'TEXT',
                'seo_keywords': 'TEXT',
                'public_id': 'VARCHAR(50)'
            }
            
            for col_name, col_def in required_articles_columns.items():
                if col_name not in articles_columns:
                    missing_articles_columns.append((col_name, col_def))
            
            if missing_articles_columns:
                logger.info(f"Adding {len(missing_articles_columns)} missing columns to articles table...")
                with db.engine.connect() as conn:
                    for col_name, col_def in missing_articles_columns:
                        conn.execute(text(f'ALTER TABLE articles ADD COLUMN {col_name} {col_def}'))
                        logger.info(f"✅ Added {col_name} column to articles table")
                    conn.commit()
            
            # Check users table for other missing columns
            missing_users_columns = []
            required_users_columns = {
                'is_active': 'BOOLEAN DEFAULT TRUE',
                'total_words_generated': 'INTEGER DEFAULT 0'
            }
            
            for col_name, col_def in required_users_columns.items():
                if col_name not in users_columns:
                    missing_users_columns.append((col_name, col_def))
            
            if missing_users_columns:
                logger.info(f"Adding {len(missing_users_columns)} missing columns to users table...")
                with db.engine.connect() as conn:
                    for col_name, col_def in missing_users_columns:
                        conn.execute(text(f'ALTER TABLE users ADD COLUMN {col_name} {col_def}'))
                        logger.info(f"✅ Added {col_name} column to users table")
                    conn.commit()
            
            logger.info("🎉 Database column fixes completed successfully!")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error fixing database columns: {e}")
        return False

if __name__ == "__main__":
    logger.info("🚀 Starting database column fix...")
    
    # Check if DATABASE_URL is set
    if not os.getenv('DATABASE_URL'):
        logger.error("❌ DATABASE_URL environment variable not set!")
        sys.exit(1)
    
    success = fix_missing_columns()
    
    if success:
        logger.info("🎉 Database column fixes completed successfully!")
        sys.exit(0)
    else:
        logger.error("💥 Database column fixes failed!")
        sys.exit(1)
