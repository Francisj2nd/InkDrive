#!/usr/bin/env python3
"""
Database migration script for InkDrive
Handles schema updates and data migrations
"""

import os
import sys
from sqlalchemy import text, inspect
from app import app, db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    try:
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception as e:
        logger.error(f"Error checking column {column_name} in {table_name}: {e}")
        return False

def add_missing_user_columns():
    """Add missing columns to users table"""
    migrations = [
        {
            'column': 'words_generated_this_month',
            'sql': 'ALTER TABLE users ADD COLUMN words_generated_this_month INTEGER DEFAULT 0'
        },
        {
            'column': 'downloads_this_month', 
            'sql': 'ALTER TABLE users ADD COLUMN downloads_this_month INTEGER DEFAULT 0'
        },
        {
            'column': 'last_quota_reset',
            'sql': 'ALTER TABLE users ADD COLUMN last_quota_reset TIMESTAMP'
        },
        {
            'column': 'theme_preference',
            'sql': "ALTER TABLE users ADD COLUMN theme_preference VARCHAR(10) DEFAULT 'auto'"
        },
        {
            'column': 'articles_generated',
            'sql': 'ALTER TABLE users ADD COLUMN articles_generated INTEGER DEFAULT 0'
        },
        {
            'column': 'subscription_tier',
            'sql': "ALTER TABLE users ADD COLUMN subscription_tier VARCHAR(20) DEFAULT 'free'"
        }
    ]
    
    applied_migrations = []
    
    for migration in migrations:
        column_name = migration['column']
        if not check_column_exists('users', column_name):
            try:
                db.session.execute(text(migration['sql']))
                db.session.commit()
                logger.info(f"✅ Added column: users.{column_name}")
                applied_migrations.append(column_name)
            except Exception as e:
                logger.error(f"❌ Failed to add column users.{column_name}: {e}")
                db.session.rollback()
        else:
            logger.info(f"⏭️  Column users.{column_name} already exists")
    
    return applied_migrations

def add_missing_article_columns():
    """Add missing columns to articles table"""
    migrations = [
        {
            'column': 'meta_description',
            'sql': 'ALTER TABLE articles ADD COLUMN meta_description VARCHAR(160)'
        },
        {
            'column': 'keywords',
            'sql': 'ALTER TABLE articles ADD COLUMN keywords TEXT'
        },
        {
            'column': 'rating',
            'sql': 'ALTER TABLE articles ADD COLUMN rating VARCHAR(10)'
        },
        {
            'column': 'is_favorite',
            'sql': 'ALTER TABLE articles ADD COLUMN is_favorite BOOLEAN DEFAULT FALSE'
        },
        {
            'column': 'download_count',
            'sql': 'ALTER TABLE articles ADD COLUMN download_count INTEGER DEFAULT 0'
        },
        {
            'column': 'public_id',
            'sql': 'ALTER TABLE articles ADD COLUMN public_id VARCHAR(20)'
        }
    ]
    
    applied_migrations = []
    
    for migration in migrations:
        column_name = migration['column']
        if not check_column_exists('articles', column_name):
            try:
                db.session.execute(text(migration['sql']))
                db.session.commit()
                logger.info(f"✅ Added column: articles.{column_name}")
                applied_migrations.append(column_name)
            except Exception as e:
                logger.error(f"❌ Failed to add column articles.{column_name}: {e}")
                db.session.rollback()
        else:
            logger.info(f"⏭️  Column articles.{column_name} already exists")
    
    return applied_migrations

def update_existing_data():
    """Update existing data with default values"""
    try:
        # Update users without quota reset date
        result = db.session.execute(text("""
            UPDATE users 
            SET last_quota_reset = CURRENT_TIMESTAMP 
            WHERE last_quota_reset IS NULL
        """))
        
        if result.rowcount > 0:
            logger.info(f"✅ Updated {result.rowcount} users with quota reset date")
        
        # Generate public_id for articles that don't have one
        result = db.session.execute(text("""
            UPDATE articles 
            SET public_id = SUBSTRING(MD5(RANDOM()::text), 1, 8)
            WHERE public_id IS NULL OR public_id = ''
        """))
        
        if result.rowcount > 0:
            logger.info(f"✅ Generated public_id for {result.rowcount} articles")
        
        db.session.commit()
        
    except Exception as e:
        logger.error(f"❌ Error updating existing data: {e}")
        db.session.rollback()

def create_missing_tables():
    """Create any missing tables"""
    try:
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        required_tables = ['users', 'articles', 'chat_sessions']
        missing_tables = [table for table in required_tables if table not in existing_tables]
        
        if missing_tables:
            logger.info(f"Creating missing tables: {missing_tables}")
            db.create_all()
            logger.info("✅ Created missing tables")
        else:
            logger.info("⏭️  All required tables exist")
            
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")
        raise

def run_migrations():
    """Run all necessary migrations"""
    logger.info("🚀 Starting database migrations...")
    
    try:
        with app.app_context():
            # Create missing tables first
            create_missing_tables()
            
            # Add missing columns
            user_migrations = add_missing_user_columns()
            article_migrations = add_missing_article_columns()
            
            # Update existing data
            update_existing_data()
            
            total_migrations = len(user_migrations) + len(article_migrations)
            
            if total_migrations > 0:
                logger.info(f"🎉 Successfully applied {total_migrations} migrations!")
            else:
                logger.info("✅ Database schema is up to date!")
                
            return True
            
    except Exception as e:
        logger.error(f"💥 Migration failed: {e}")
        return False

if __name__ == "__main__":
    if not os.getenv('DATABASE_URL'):
        logger.error("❌ DATABASE_URL environment variable not set!")
        sys.exit(1)
    
    success = run_migrations()
    sys.exit(0 if success else 1)
