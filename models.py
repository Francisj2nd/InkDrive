import logging
logger = logging.getLogger(__name__)
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
import json
import re
from bs4 import BeautifulSoup

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(255))
    
    # Google OAuth fields
    google_id = db.Column(db.String(100), unique=True, nullable=True, index=True)
    profile_picture = db.Column(db.String(255))
    
    # User preferences
    theme_preference = db.Column(db.String(20), default='light')  # 'light', 'dark', 'auto'
    
    # Account status
    is_verified = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    # Usage tracking - Fixed: Total words should never decrease
    articles_generated = db.Column(db.Integer, default=0)
    total_words_generated = db.Column(db.Integer, default=0)  # Cumulative total (never decreases)
    words_generated_this_month = db.Column(db.Integer, default=0)
    downloads_this_month = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime)
    last_quota_reset = db.Column(db.DateTime)
    
    # Relationships
    articles = db.relationship('Article', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    chat_sessions = db.relationship('ChatSession', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Set password hash"""
        if not password:
            raise ValueError("Password cannot be empty")
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        """Check password against hash"""
        if not self.password_hash or not password:
            return False
        try:
            return check_password_hash(self.password_hash, password)
        except ValueError as e:
            # Handle invalid hash format
            logger.error(f"Invalid password hash format for user {self.id}: {e}")
            return False
    
    def update_last_login(self):
        """Update last login timestamp"""
        try:
            self.last_login = datetime.now(timezone.utc)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e
    
    def to_dict(self):
        """Convert user to dictionary"""
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'theme_preference': self.theme_preference,
            'is_verified': self.is_verified,
            'articles_generated': self.articles_generated or 0,
            'total_words_generated': self.total_words_generated or 0,
            'words_generated_this_month': self.words_generated_this_month or 0,
            'downloads_this_month': self.downloads_this_month or 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

class Article(db.Model):
    __tablename__ = 'articles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Article content
    title = db.Column(db.String(500), nullable=False)
    content_html = db.Column(db.Text, nullable=False)
    content_raw = db.Column(db.Text, nullable=False)  # Raw markdown/text for refinements
    topic = db.Column(db.String(500))
    
    # Article metadata
    word_count = db.Column(db.Integer, default=0)
    is_refined = db.Column(db.Boolean, default=False)
    
    # Publishing
    is_public = db.Column(db.Boolean, default=False)
    public_id = db.Column(db.String(50), unique=True, nullable=True, index=True)
    published_at = db.Column(db.DateTime)
    
    # SEO fields
    meta_description = db.Column(db.Text)
    seo_keywords = db.Column(db.Text)
    
    # Analytics
    view_count = db.Column(db.Integer, default=0)
    download_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Link to chat session
    chat_session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id'), nullable=True)
    
    def publish(self):
        """Publish the article"""
        self.is_public = True
        self.published_at = datetime.now(timezone.utc)
        db.session.commit()
    
    def unpublish(self):
        """Unpublish the article"""
        self.is_public = False
        self.published_at = None
        db.session.commit()
    
    def increment_view(self):
        """Increment view count"""
        try:
            self.view_count = (self.view_count or 0) + 1
            db.session.commit()
        except Exception:
            db.session.rollback()
    
    def increment_download(self):
        """Increment download count"""
        try:
            self.download_count = (self.download_count or 0) + 1
            db.session.commit()
        except Exception:
            db.session.rollback()
    
    def get_excerpt(self, length=150):
        """Get article excerpt from content"""
        if not self.content_html:
            return ""
        
        # Remove HTML tags and get plain text
        soup = BeautifulSoup(self.content_html, 'html.parser')
        text = soup.get_text()
        
        # Clean up whitespace
        text = ' '.join(text.split())
        
        if len(text) <= length:
            return text
        
        # Find the last complete word within the length limit
        excerpt = text[:length]
        last_space = excerpt.rfind(' ')
        if last_space > 0:
            excerpt = excerpt[:last_space]
        
        return excerpt + "..."
    
    def get_first_image_url(self):
        """Extract the first image URL from content"""
        if not self.content_html:
            return None
        
        soup = BeautifulSoup(self.content_html, 'html.parser')
        img_tag = soup.find('img')
        
        if img_tag and img_tag.get('src'):
            return img_tag['src']
        
        return None
    
    def extract_seo_data(self):
        """Extract SEO keywords and meta description from content"""
        if not self.content_raw:
            return
        
        # Look for SEO Keywords and Meta Description in the raw content
        seo_keywords_match = re.search(r'SEO Keywords?:\s*(.+)', self.content_raw, re.IGNORECASE)
        meta_desc_match = re.search(r'Meta Description:\s*(.+)', self.content_raw, re.IGNORECASE)
        
        if seo_keywords_match:
            self.seo_keywords = seo_keywords_match.group(1).strip()
        
        if meta_desc_match:
            self.meta_description = meta_desc_match.group(1).strip()
    
    def to_dict(self):
        """Convert article to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'content_html': self.content_html,
            'content_raw': self.content_raw,
            'topic': self.topic,
            'word_count': self.word_count or 0,
            'is_refined': self.is_refined,
            'is_public': self.is_public,
            'public_id': self.public_id,
            'view_count': self.view_count or 0,
            'download_count': self.download_count or 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'excerpt': self.get_excerpt(),
            'first_image_url': self.get_first_image_url()
        }

class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    session_id = db.Column(db.String(100), nullable=False, index=True)  # Unique session identifier
    
    # Chat content
    title = db.Column(db.String(500), nullable=False)  # Topic/title of the chat
    messages = db.Column(db.Text)  # JSON string of messages
    raw_text = db.Column(db.Text)  # Latest raw text for refinements
    
    # Chat metadata
    has_refined = db.Column(db.Boolean, default=False)
    studio_type = db.Column(db.String(50), nullable=False, server_default='ARTICLE')
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    articles = db.relationship('Article', backref='chat_session', lazy='dynamic')
    
    def set_messages(self, messages_list):
        """Set messages as JSON string"""
        self.messages = json.dumps(messages_list) if messages_list else None
    
    def get_messages(self):
        """Get messages as Python list"""
        if not self.messages:
            return []
        try:
            return json.loads(self.messages)
        except (json.JSONDecodeError, TypeError):
            return []
    
    def to_dict(self):
        """Convert chat session to dictionary"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'title': self.title,
            'messages': self.get_messages(),
            'raw_text': self.raw_text,
            'has_refined': self.has_refined,
            'studio_type': self.studio_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
