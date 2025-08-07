#!/usr/bin/env python3
"""
Script to fix database schema issues on Render
Run this script to add missing columns to the database
"""

import os
import sys
import logging

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db
from migrations import run_migrations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_database_schema():
    """Fix database schema by running migrations"""
    try:
        with app.app_context():
            logger.info("Starting database schema fix...")
            
            # Create all tables first (in case they don't exist)
            db.create_all()
            logger.info("Created/verified all tables")
            
            # Run migrations to add missing columns
            run_migrations()
            logger.info("Migrations completed successfully")
            
            logger.info("Database schema fix completed!")
            
    except Exception as e:
        logger.error(f"Error fixing database schema: {e}")
        raise

if __name__ == "__main__":
    fix_database_schema()
