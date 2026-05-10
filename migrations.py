"""
Database migrations for InkDrive
"""
import logging
from datetime import datetime
from models import db
from sqlalchemy import text

logger = logging.getLogger(__name__)

def run_migrations():
    """Run all pending migrations"""
    try:
        # Check if we need to add missing fields to tables
        inspector = db.inspect(db.engine)
        
        # Check articles table columns
        articles_columns = [col['name'] for col in inspector.get_columns('articles')] if inspector.has_table('articles') else []
        users_columns = [col['name'] for col in inspector.get_columns('users')]
        
        migrations_needed = []

        # Check if articles table needs to be renamed
        if inspector.has_table('articles') and not inspector.has_table('generated_content'):
            migrations_needed.append('rename_articles_to_generated_content')
        
        # Check for missing articles fields
        if articles_columns and 'is_public' not in articles_columns:
            migrations_needed.append('add_is_public_field')
        if 'published_at' not in articles_columns:
            migrations_needed.append('add_published_at_field')
        if 'view_count' not in articles_columns:
            migrations_needed.append('add_view_count_field')
        if 'download_count' not in articles_columns:
            migrations_needed.append('add_download_count_field')
        if 'meta_description' not in articles_columns:
            migrations_needed.append('add_meta_description_field')
        if 'seo_keywords' not in articles_columns:
            migrations_needed.append('add_seo_keywords_field')
        if 'public_id' not in articles_columns:
            migrations_needed.append('add_public_id_field')
        
        # Check for missing users fields
        if 'updated_at' not in users_columns:
            migrations_needed.append('add_users_updated_at_field')
        if 'is_active' not in users_columns:
            migrations_needed.append('add_is_active_field')
        if 'total_words_generated' not in users_columns:
            migrations_needed.append('add_total_words_generated_field')
        if 'is_superadmin' not in users_columns:
            migrations_needed.append('add_is_superadmin_field')

        # Check for missing generated_content fields (auto-publish)
        gc_columns = (
            [col['name'] for col in inspector.get_columns('generated_content')]
            if inspector.has_table('generated_content') else []
        )
        if gc_columns and 'is_auto_published' not in gc_columns:
            migrations_needed.append('add_is_auto_published_field')
        if gc_columns and 'category' not in gc_columns:
            migrations_needed.append('add_category_field')

        # Ensure auto_publish_config table exists (handled by db.create_all, but double-check)
        if not inspector.has_table('auto_publish_config'):
            migrations_needed.append('create_auto_publish_config_table')

        # Run migrations
        for migration in migrations_needed:
            logger.info(f"Running migration: {migration}")
            if migration == 'rename_articles_to_generated_content':
                rename_articles_to_generated_content()
            elif migration == 'add_is_public_field':
                add_is_public_field()
            elif migration == 'add_published_at_field':
                add_published_at_field()
            elif migration == 'add_view_count_field':
                add_view_count_field()
            elif migration == 'add_download_count_field':
                add_download_count_field()
            elif migration == 'add_meta_description_field':
                add_meta_description_field()
            elif migration == 'add_seo_keywords_field':
                add_seo_keywords_field()
            elif migration == 'add_public_id_field':
                add_public_id_field()
            elif migration == 'add_users_updated_at_field':
                add_users_updated_at_field()
            elif migration == 'add_is_active_field':
                add_is_active_field()
            elif migration == 'add_total_words_generated_field':
                add_total_words_generated_field()
            elif migration == 'add_is_superadmin_field':
                add_is_superadmin_field()
            elif migration == 'add_is_auto_published_field':
                add_is_auto_published_field()
            elif migration == 'add_category_field':
                add_category_field()
            elif migration == 'create_auto_publish_config_table':
                create_auto_publish_config_table()
        
        if migrations_needed:
            logger.info(f"Completed {len(migrations_needed)} migrations")
        else:
            logger.info("No migrations needed")
            
        return True
            
    except Exception as e:
        logger.error(f"Migration error: {e}")
        db.session.rollback()
        return False

def add_is_public_field():
    """Add is_public field to articles table"""
    try:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE articles ADD COLUMN is_public BOOLEAN DEFAULT FALSE'))
            conn.commit()
        logger.info("Added is_public field to articles table")
    except Exception as e:
        logger.error(f"Error adding is_public field: {e}")
        raise

def add_published_at_field():
    """Add published_at field to articles table"""
    try:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE articles ADD COLUMN published_at TIMESTAMP'))
            conn.commit()
        logger.info("Added published_at field to articles table")
    except Exception as e:
        logger.error(f"Error adding published_at field: {e}")
        raise

def add_view_count_field():
    """Add view_count field to articles table"""
    try:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE articles ADD COLUMN view_count INTEGER DEFAULT 0'))
            conn.commit()
        logger.info("Added view_count field to articles table")
    except Exception as e:
        logger.error(f"Error adding view_count field: {e}")
        raise

def add_download_count_field():
    """Add download_count field to articles table"""
    try:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE articles ADD COLUMN download_count INTEGER DEFAULT 0'))
            conn.commit()
        logger.info("Added download_count field to articles table")
    except Exception as e:
        logger.error(f"Error adding download_count field: {e}")
        raise

def add_meta_description_field():
    """Add meta_description field to articles table"""
    try:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE articles ADD COLUMN meta_description TEXT'))
            conn.commit()
        logger.info("Added meta_description field to articles table")
    except Exception as e:
        logger.error(f"Error adding meta_description field: {e}")
        raise

def add_seo_keywords_field():
    """Add seo_keywords field to articles table"""
    try:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE articles ADD COLUMN seo_keywords TEXT'))
            conn.commit()
        logger.info("Added seo_keywords field to articles table")
    except Exception as e:
        logger.error(f"Error adding seo_keywords field: {e}")
        raise

def add_public_id_field():
    """Add public_id field to articles table"""
    try:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE articles ADD COLUMN public_id VARCHAR(50)'))
            conn.commit()
        logger.info("Added public_id field to articles table")
    except Exception as e:
        logger.error(f"Error adding public_id field: {e}")
        raise

def add_users_updated_at_field():
    """Add updated_at field to users table"""
    try:
        with db.engine.connect() as conn:
            # Add the column with a default value of current timestamp
            conn.execute(text('ALTER TABLE users ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'))
            conn.commit()
        logger.info("Added updated_at field to users table")
    except Exception as e:
        logger.error(f"Error adding updated_at field: {e}")
        raise

def add_is_active_field():
    """Add is_active field to users table"""
    try:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE'))
            conn.commit()
        logger.info("Added is_active field to users table")
    except Exception as e:
        logger.error(f"Error adding is_active field: {e}")
        raise

def add_total_words_generated_field():
    """Add total_words_generated field to users table"""
    try:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE users ADD COLUMN total_words_generated INTEGER DEFAULT 0'))
            conn.commit()
        logger.info("Added total_words_generated field to users table")
    except Exception as e:
        logger.error(f"Error adding total_words_generated field: {e}")
        raise

def add_is_superadmin_field():
    """Add is_superadmin field to users table"""
    try:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE users ADD COLUMN is_superadmin BOOLEAN DEFAULT FALSE'))
            conn.commit()
        logger.info("Added is_superadmin field to users table")
    except Exception as e:
        logger.error(f"Error adding is_superadmin field: {e}")
        raise

def rename_articles_to_generated_content():
    """Rename the articles table to generated_content"""
    try:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE articles RENAME TO generated_content'))
            conn.commit()
        logger.info("Renamed table 'articles' to 'generated_content'")
    except Exception as e:
        logger.error(f"Error renaming articles table: {e}")
        raise


def add_is_auto_published_field():
    """Add is_auto_published flag to generated_content."""
    try:
        with db.engine.connect() as conn:
            conn.execute(text(
                'ALTER TABLE generated_content ADD COLUMN is_auto_published BOOLEAN DEFAULT FALSE'
            ))
            conn.commit()
        logger.info("Added is_auto_published field to generated_content")
    except Exception as e:
        logger.error(f"Error adding is_auto_published field: {e}")
        raise


def add_category_field():
    """Add category column to generated_content."""
    try:
        with db.engine.connect() as conn:
            conn.execute(text(
                'ALTER TABLE generated_content ADD COLUMN category VARCHAR(100)'
            ))
            conn.commit()
        logger.info("Added category field to generated_content")
    except Exception as e:
        logger.error(f"Error adding category field: {e}")
        raise


def create_auto_publish_config_table():
    """Create auto_publish_config table if it doesn't exist yet."""
    try:
        with db.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS auto_publish_config (
                    id SERIAL PRIMARY KEY,
                    is_enabled BOOLEAN DEFAULT FALSE,
                    frequency_hours INTEGER DEFAULT 6,
                    articles_per_run INTEGER DEFAULT 3,
                    word_count INTEGER DEFAULT 800,
                    tone VARCHAR(50) DEFAULT 'Professional',
                    categories TEXT DEFAULT '[]',
                    last_run_at TIMESTAMP,
                    last_run_status VARCHAR(500),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
        logger.info("Created auto_publish_config table")
    except Exception as e:
        logger.error(f"Error creating auto_publish_config table: {e}")
        raise
