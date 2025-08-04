#!/usr/bin/env python3
"""
Database initialization script for production deployment
Run this script to create database tables on first deployment
"""

import os
import sys
from app import app, db

def init_database():
    """Initialize the database with all tables"""
    try:
        with app.app_context():
            # Create all tables
            db.create_all()
            print("✅ Database tables created successfully!")
            
            # Verify tables were created
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            print(f"📋 Created tables: {', '.join(tables)}")
            
            if not tables:
                print("⚠️  Warning: No tables were created!")
                return False
                
            return True
            
    except Exception as e:
        print(f"❌ Error creating database tables: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Initializing InkDrive database...")
    
    # Check if DATABASE_URL is set
    if not os.getenv('DATABASE_URL'):
        print("❌ DATABASE_URL environment variable not set!")
        sys.exit(1)
    
    success = init_database()
    
    if success:
        print("🎉 Database initialization completed successfully!")
        sys.exit(0)
    else:
        print("💥 Database initialization failed!")
        sys.exit(1)
