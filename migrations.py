"""
Database migrations for InkDrive
"""
import logging
from datetime import datetime
from models import db, Article

logger = logging.getLogger(__name__)

def run_migrations():
    """Run all pending migrations"""
    try:
        # Check if we need to add publishing fields to articles table
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('articles')]
        
        migrations_needed = []
        
        # Check for missing publishing fields
        if 'is_public' not in columns:
            migrations_needed.append('add_is_public_field')
        if 'published_at' not in columns:
            migrations_needed.append('add_published_at_field')
        if 'view_count' not in columns:
            migrations_needed.append('add_view_count_field')
        
        # Run migrations
        for migration in migrations_needed:
            logger.info(f"Running migration: {migration}")
            if migration == 'add_is_public_field':
                add_is_public_field()
            elif migration == 'add_published_at_field':
                add_published_at_field()
            elif migration == 'add_view_count_field':
                add_view_count_field()
        
        if migrations_needed:
            logger.info(f"Completed {len(migrations_needed)} migrations")
        else:
            logger.info("No migrations needed")
            
    except Exception as e:
        logger.error(f"Migration error: {e}")
        db.session.rollback()
        raise

def add_is_public_field():
    """Add is_public field to articles table"""
    try:
        db.engine.execute('ALTER TABLE articles ADD COLUMN is_public BOOLEAN DEFAULT FALSE')
        db.session.commit()
        logger.info("Added is_public field to articles table")
    except Exception as e:
        logger.error(f"Error adding is_public field: {e}")
        db.session.rollback()
        raise

def add_published_at_field():
    """Add published_at field to articles table"""
    try:
        db.engine.execute('ALTER TABLE articles ADD COLUMN published_at DATETIME')
        db.session.commit()
        logger.info("Added published_at field to articles table")
    except Exception as e:
        logger.error(f"Error adding published_at field: {e}")
        db.session.rollback()
        raise

def add_view_count_field():
    """Add view_count field to articles table"""
    try:
        db.engine.execute('ALTER TABLE articles ADD COLUMN view_count INTEGER DEFAULT 0')
        db.session.commit()
        logger.info("Added view_count field to articles table")
    except Exception as e:
        logger.error(f"Error adding view_count field: {e}")
        db.session.rollback()
        raise
