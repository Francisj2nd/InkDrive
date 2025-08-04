from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import bcrypt
import json

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(128), nullable=True)  # Nullable for OAuth users
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    profile_picture = db.Column(db.String(200), nullable=True)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # User preferences
    theme_preference = db.Column(db.String(10), default='auto')  # 'light', 'dark', 'auto'
    articles_generated = db.Column(db.Integer, default=0)
    subscription_tier = db.Column(db.String(20), default='free')  # 'free', 'premium', 'enterprise'
    
    # Usage quotas
    words_generated_this_month = db.Column(db.Integer, default=0)
    downloads_this_month = db.Column(db.Integer, default=0)
    last_quota_reset = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    articles = db.relationship('Article', backref='author', lazy=True, cascade='all, delete-orphan')
    chat_sessions = db.relationship('ChatSession', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Hash and set password"""
        if password:
            self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def check_password(self, password):
        """Check if provided password matches hash"""
        if not self.password_hash:
            return False
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login = datetime.utcnow()
        db.session.commit()
    
    def to_dict(self):
        """Convert user to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'profile_picture': self.profile_picture,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'articles_generated': self.articles_generated,
            'subscription_tier': self.subscription_tier,
            'theme_preference': self.theme_preference,
            'words_generated_this_month': self.words_generated_this_month,
            'downloads_this_month': self.downloads_this_month
        }

class Article(db.Model):
    __tablename__ = 'articles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content_html = db.Column(db.Text, nullable=False)
    content_raw = db.Column(db.Text, nullable=False)  # Raw markdown/text
    topic = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_refined = db.Column(db.Boolean, default=False)
    word_count = db.Column(db.Integer, default=0)
    public_id = db.Column(db.String(20), unique=True, nullable=False, default=lambda: str(datetime.utcnow().timestamp())[:10])
    
    # SEO and metadata
    meta_description = db.Column(db.String(160), nullable=True)
    keywords = db.Column(db.Text, nullable=True)  # JSON array of keywords
    
    # User interactions
    rating = db.Column(db.String(10), nullable=True)  # 'up', 'down', null
    is_favorite = db.Column(db.Boolean, default=False)
    download_count = db.Column(db.Integer, default=0)
    
    def increment_download(self):
        """Increment download counter"""
        self.download_count += 1
        db.session.commit()
    
    def set_rating(self, rating):
        """Set article rating"""
        self.rating = rating if rating in ['up', 'down'] else None
        db.session.commit()
    
    def to_dict(self):
        """Convert article to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'topic': self.topic,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_refined': self.is_refined,
            'word_count': self.word_count,
            'rating': self.rating,
            'is_favorite': self.is_favorite,
            'download_count': self.download_count,
            'public_id': self.public_id
        }

class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_id = db.Column(db.String(100), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Session data
    messages = db.Column(db.Text, nullable=False)  # JSON array of messages
    raw_text = db.Column(db.Text, nullable=True)
    has_refined = db.Column(db.Boolean, default=False)
    
    def get_messages(self):
        """Get messages as Python list"""
        try:
            return json.loads(self.messages) if self.messages else []
        except json.JSONDecodeError:
            return []
    
    def set_messages(self, messages_list):
        """Set messages from Python list"""
        self.messages = json.dumps(messages_list)
    
    def to_dict(self):
        """Convert chat session to dictionary"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'title': self.title,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'messages': self.get_messages(),
            'has_refined': self.has_refined
        }
