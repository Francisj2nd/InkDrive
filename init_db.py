#!/usr/bin/env python3
"""
Database initialization script for production deployment
Run this script to create database tables on first deployment
"""

import os
import sys
from app import app, db
from migrations import run_migrations
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database():
    """Initialize the database with all tables and run migrations"""
    try:
        with app.app_context():
            logger.info("🚀 Initializing InkDrive database...")
            
            # Create all tables
            db.create_all()
            logger.info("✅ Database tables created successfully!")
            
            # Run migrations to ensure schema is up to date
            logger.info("🔄 Running database migrations...")
            migration_success = run_migrations()
            
            if not migration_success:
                logger.error("❌ Database migrations failed!")
                return False
            
            # Verify tables were created
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            logger.info(f"📋 Available tables: {', '.join(tables)}")
            
            if not tables:
                logger.error("⚠️  Warning: No tables were created!")
                return False
            
            # Verify critical columns exist
            required_columns = {
                'users': ['words_generated_this_month', 'downloads_this_month', 'last_quota_reset'],
                'articles': ['public_id', 'download_count']
            }
            
            for table, columns in required_columns.items():
                if table in tables:
                    table_columns = [col['name'] for col in inspector.get_columns(table)]
                    missing_columns = [col for col in columns if col not in table_columns]
                    if missing_columns:
                        logger.error(f"❌ Missing columns in {table}: {missing_columns}")
                        return False
                    else:
                        logger.info(f"✅ All required columns exist in {table}")
                        
            return True
            
    except Exception as e:
        logger.error(f"❌ Error initializing database: {e}")
        return False

if __name__ == "__main__":
    logger.info("🚀 Starting InkDrive database initialization...")
    
    # Check if DATABASE_URL is set
    if not os.getenv('DATABASE_URL'):
        logger.error("❌ DATABASE_URL environment variable not set!")
        sys.exit(1)
    
    success = init_database()
    
    if success:
        logger.info("🎉 Database initialization completed successfully!")
        sys.exit(0)
    else:
        logger.error("💥 Database initialization failed!")
        sys.exit(1)
