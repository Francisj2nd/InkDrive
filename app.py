import os
import io
import re
import uuid
import requests
import markdown
import secrets
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash, session, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from bs4 import BeautifulSoup
from docx import Document
from docx.shared import Inches
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from datetime import datetime, timedelta
import json
import logging
from sqlalchemy.exc import OperationalError, DatabaseError
import time

# Import our models and forms
from models import db, User, Article, ChatSession
from forms import LoginForm, RegisterForm, ProfileForm, ChangePasswordForm

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. INITIALIZATION & HELPERS ---
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///inkdrive.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'connect_args': {
        'connect_timeout': 10,
        'sslmode': 'require' if 'postgresql' in os.getenv('DATABASE_URL', '') else None
    }
}

# Fix for Render PostgreSQL URLs
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)

# Google OAuth Configuration
app.config['GOOGLE_CLIENT_ID'] = os.getenv('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.getenv('GOOGLE_CLIENT_SECRET')

# Load environment variables from Render
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash-lite")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

# Usage limits for free plan
MONTHLY_WORD_LIMIT = 30000
MONTHLY_DOWNLOAD_LIMIT = 10

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth_login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {e}")
        return None

# Database connection retry decorator
def retry_db_operation(max_retries=3, delay=1):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (OperationalError, DatabaseError) as e:
                    logger.warning(f"Database operation failed (attempt {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        time.sleep(delay * (2 ** attempt))  # Exponential backoff
                        continue
                    else:
                        logger.error(f"Database operation failed after {max_retries} attempts: {e}")
                        raise
                except Exception as e:
                    logger.error(f"Unexpected error in database operation: {e}")
                    raise
            return None
        return wrapper
    return decorator

# Validation check - log missing variables but don't fail
missing_vars = []
if not GCP_PROJECT_ID: missing_vars.append("GCP_PROJECT_ID")
if not UNSPLASH_ACCESS_KEY: missing_vars.append("UNSPLASH_ACCESS_KEY")
if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"): missing_vars.append("GOOGLE_APPLICATION_CREDENTIALS")

if missing_vars:
    logger.warning(f"Missing environment variables: {', '.join(missing_vars)}")

# --- Initialize genai client with Vertex AI ---
CLIENT = None
try:
    if GCP_PROJECT_ID and os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        genai.configure()
        CLIENT = genai.GenerativeModel(model_name=MODEL_NAME)
        logger.info("Google AI Client Initialized Successfully via Vertex AI.")
    else:
        logger.warning("Google AI client not initialized - missing credentials")
except Exception as e:
    logger.error(f"Failed to initialize Google AI client: {e}")

# Helper functions
def construct_initial_prompt(topic):
    article_requirements = """
**Article Requirements:**
1. Focus and Depth: Focus entirely on the topic. Educate the reader in-depth.
2. Length: Aim for over 1000 words.
3. Structure: Use clear sections with H2 and H3 subheadings using Markdown.
4. Placeholders: Include 3 relevant image placeholders. For each, provide a suggested title and a full, SEO-optimized alt text. Format them exactly like this: `[Image Placeholder: Title, Alt Text]`
5. SEO Elements: At the very end of the article, provide "SEO Keywords:" and "Meta Description:".
6. Quality: The content must be original, human-readable, and valuable.
"""
    return f"""I want you to generate a high-quality, SEO-optimized thought-leadership article on the topic of: "{topic}"

{article_requirements}
"""

def get_image_url(query):
    if not UNSPLASH_ACCESS_KEY or "YOUR_KEY" in UNSPLASH_ACCESS_KEY:
        return None
    api_url = "https://api.unsplash.com/search/photos"
    params = {"query": query, "per_page": 1, "client_id": UNSPLASH_ACCESS_KEY}
    try:
        response = requests.get(api_url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data["results"]:
            photo = data["results"][0]
            return {"url": photo["urls"]["regular"], "attribution": f"Photo by {photo['user']['name']} on Unsplash"}
        return None
    except requests.RequestException as e:
        logger.error(f"Error fetching image: {e}")
        return None

def format_article_content(raw_markdown_text):
    """Format article content with images"""
    hybrid_content = raw_markdown_text
    placeholder_regex = re.compile(r"\[Image Placeholder: (.*?),\s*(.*?)\]")

    for match in placeholder_regex.finditer(raw_markdown_text):
        original_placeholder = match.group(0)
        title = match.group(1).strip()
        alt_text = match.group(2).strip()
        image_data = get_image_url(alt_text)

        if image_data:
            new_image_tag = (
                f'<div class="real-image-container">'
                f'<p class="image-title">{title}</p>'
                f'<img src="{image_data["url"]}" alt="">'
                f'<p class="alt-text-display"><strong>Alt Text:</strong> {alt_text}</p>'
                f'<p class="attribution">{image_data["attribution"]}</p>'
                f'</div>'
            )
            hybrid_content = hybrid_content.replace(original_placeholder, new_image_tag, 1)
        else:
            hybrid_content = hybrid_content.replace(original_placeholder, f'<p>[Image Placeholder: {title} - Could not fetch image]</p>', 1)

    final_html = markdown.markdown(hybrid_content, extensions=['fenced_code', 'tables'])
    return final_html

@retry_db_operation(max_retries=3)
def save_article_to_db(user_id, topic, content_html, content_raw, is_refined=False, article_id=None):
    """Save article to database with retry logic"""
    try:
        # Extract word count (rough estimate)
        word_count = len(content_raw.split())
        
        if article_id:
            # Update existing article
            article = Article.query.filter_by(id=article_id, user_id=user_id).first()
            if article:
                article.content_html = content_html
                article.content_raw = content_raw
                article.is_refined = is_refined
                article.word_count = word_count
                article.updated_at = datetime.utcnow()
            else:
                # Article not found or doesn't belong to user
                return None
        else:
            # Create new article
            article = Article(
                user_id=user_id,
                title=topic[:200],  # Truncate if too long
                content_html=content_html,
                content_raw=content_raw,
                topic=topic,
                is_refined=is_refined,
                word_count=word_count,
                public_id=str(uuid.uuid4())[:8]  # Generate a short public ID for sharing
            )
            
            db.session.add(article)
            
            # Update user's article count and monthly word count
            user = User.query.get(user_id)
            if user:
                user.articles_generated = (user.articles_generated or 0) + 1
                
                # Check if we need to reset monthly quotas
                if user.last_quota_reset is None or (datetime.utcnow() - user.last_quota_reset) > timedelta(days=30):
                    user.words_generated_this_month = word_count
                    user.downloads_this_month = 0
                    user.last_quota_reset = datetime.utcnow()
                else:
                    user.words_generated_this_month = (user.words_generated_this_month or 0) + word_count
        
        db.session.commit()
        return article.id
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving article: {e}")
        return None

@retry_db_operation(max_retries=2)
def check_monthly_word_quota(user):
    """Check if user has exceeded monthly word quota"""
    try:
        # Reset quota if it's been more than 30 days
        if user.last_quota_reset is None or (datetime.utcnow() - user.last_quota_reset) > timedelta(days=30):
            user.words_generated_this_month = 0
            user.downloads_this_month = 0
            user.last_quota_reset = datetime.utcnow()
            db.session.commit()
            return True
        
        words_generated = user.words_generated_this_month or 0
        return words_generated < MONTHLY_WORD_LIMIT
    except Exception as e:
        logger.error(f"Error checking word quota for user {user.id}: {e}")
        return True  # Allow operation if check fails

@retry_db_operation(max_retries=2)
def check_monthly_download_quota(user):
    """Check if user has exceeded monthly download quota"""
    try:
        # Reset quota if it's been more than 30 days
        if user.last_quota_reset is None or (datetime.utcnow() - user.last_quota_reset) > timedelta(days=30):
            user.words_generated_this_month = 0
            user.downloads_this_month = 0
            user.last_quota_reset = datetime.utcnow()
            db.session.commit()
            return True
        
        downloads_this_month = user.downloads_this_month or 0
        return downloads_this_month < MONTHLY_DOWNLOAD_LIMIT
    except Exception as e:
        logger.error(f"Error checking download quota for user {user.id}: {e}")
        return True  # Allow operation if check fails

# --- 2. AUTHENTICATION ROUTES ---

@app.route('/auth/login', methods=['GET', 'POST'])
def auth_login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = User.query.filter_by(email=form.email.data.lower()).first()
            
            if user and user.check_password(form.password.data):
                login_user(user, remember=form.remember_me.data)
                
                # Safely update last login with error handling
                try:
                    user.update_last_login()
                except Exception as e:
                    logger.warning(f"Failed to update last login for user {user.id}: {e}")
                
                flash('Welcome back!', 'success')
                
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('index'))
            else:
                flash('Invalid email or password.', 'error')
        except (OperationalError, DatabaseError) as e:
            logger.error(f"Database error during login: {e}")
            flash('Database connection issue. Please try again in a moment.', 'error')
        except Exception as e:
            logger.error(f"Login error: {e}")
            flash('An error occurred during login. Please try again.', 'error')
    
    return render_template('auth/login.html', form=form)

@app.route('/auth/register', methods=['GET', 'POST'])
def auth_register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        try:
            # Check if user already exists
            existing_user = User.query.filter_by(email=form.email.data.lower()).first()
            if existing_user:
                flash('Email address already registered.', 'error')
                return render_template('auth/register.html', form=form)
            
            # Create new user with safe defaults
            user = User(
                email=form.email.data.lower(),
                name=form.name.data,
                is_verified=True,  # Auto-verify for now
                words_generated_this_month=0,
                downloads_this_month=0,
                articles_generated=0,
                last_quota_reset=datetime.utcnow()
            )
            user.set_password(form.password.data)
            
            db.session.add(user)
            db.session.commit()
            
            login_user(user)
            flash('Registration successful! Welcome to InkDrive!', 'success')
            return redirect(url_for('index'))
            
        except (OperationalError, DatabaseError) as e:
            db.session.rollback()
            logger.error(f"Database error during registration: {e}")
            flash('Database connection issue. Please try again in a moment.', 'error')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Registration error: {e}")
            flash('Registration failed. Please try again.', 'error')
    
    return render_template('auth/register.html', form=form)

@app.route('/auth/google')
def auth_google():
    """Initiate Google OAuth flow"""
    if not app.config.get('GOOGLE_CLIENT_ID'):
        flash('Google authentication is not configured.', 'error')
        return redirect(url_for('auth_login'))
    
    return render_template('auth/google_auth.html')

@app.route('/auth/google/callback', methods=['POST'])
def auth_google_callback():
    """Handle Google OAuth callback"""
    try:
        token = request.json.get('credential')
        if not token:
            return jsonify({'error': 'No credential provided'}), 400
        
        # Verify the token
        idinfo = id_token.verify_oauth2_token(
            token, 
            google_requests.Request(), 
            app.config['GOOGLE_CLIENT_ID']
        )
        
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            return jsonify({'error': 'Invalid token issuer'}), 400
        
        google_id = idinfo['sub']
        email = idinfo['email']
        name = idinfo['name']
        picture = idinfo.get('picture')
        
        # Check if user exists
        user = User.query.filter_by(google_id=google_id).first()
        if not user:
            user = User.query.filter_by(email=email.lower()).first()
            if user:
                # Link Google account to existing user
                user.google_id = google_id
                user.profile_picture = picture
            else:
                # Create new user with safe defaults
                user = User(
                    email=email.lower(),
                    name=name,
                    google_id=google_id,
                    profile_picture=picture,
                    is_verified=True,
                    words_generated_this_month=0,
                    downloads_this_month=0,
                    articles_generated=0,
                    last_quota_reset=datetime.utcnow()
                )
                db.session.add(user)
        else:
            # Update existing Google user info
            user.name = name
            user.profile_picture = picture
        
        db.session.commit()
        login_user(user)
        
        # Safely update last login
        try:
            user.update_last_login()
        except Exception as e:
            logger.warning(f"Failed to update last login for Google user {user.id}: {e}")
        
        return jsonify({'success': True, 'redirect': url_for('index')})
        
    except ValueError as e:
        logger.error(f"Google auth token error: {e}")
        return jsonify({'error': 'Invalid token'}), 400
    except (OperationalError, DatabaseError) as e:
        db.session.rollback()
        logger.error(f"Database error during Google auth: {e}")
        return jsonify({'error': 'Database connection issue. Please try again.'}), 500
    except Exception as e:
        db.session.rollback()
        logger.error(f"Google auth error: {e}")
        return jsonify({'error': 'Authentication failed'}), 500

@app.route('/auth/logout')
@login_required
def auth_logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# --- 3. PROFILE & DASHBOARD ROUTES ---

@app.route('/profile')
@app.route('/profile/dashboard')
@login_required
def profile_dashboard():
    """User profile dashboard"""
    try:
        # Get user's recent articles with error handling
        recent_articles = []
        total_articles = 0
        total_words = 0
        total_downloads = 0
        
        try:
            recent_articles = Article.query.filter_by(user_id=current_user.id)\
                                         .order_by(Article.created_at.desc())\
                                         .limit(10).all()
            
            # Calculate stats
            total_articles = Article.query.filter_by(user_id=current_user.id).count()
            total_words = db.session.query(db.func.sum(Article.word_count))\
                                   .filter_by(user_id=current_user.id).scalar() or 0
            total_downloads = db.session.query(db.func.sum(Article.download_count))\
                                        .filter_by(user_id=current_user.id).scalar() or 0
        except (OperationalError, DatabaseError) as e:
            logger.error(f"Database error loading dashboard data: {e}")
            flash('Some dashboard data may not be available due to connection issues.', 'warning')
        
        # Check if we need to reset monthly quotas with error handling
        try:
            if current_user.last_quota_reset is None or (datetime.utcnow() - current_user.last_quota_reset) > timedelta(days=30):
                current_user.words_generated_this_month = 0
                current_user.downloads_this_month = 0
                current_user.last_quota_reset = datetime.utcnow()
                db.session.commit()
        except Exception as e:
            logger.warning(f"Failed to reset quotas for user {current_user.id}: {e}")
        
        stats = {
            'total_articles': total_articles,
            'total_words': total_words,
            'total_downloads': total_downloads,
            'words_this_month': getattr(current_user, 'words_generated_this_month', 0) or 0,
            'downloads_this_month': getattr(current_user, 'downloads_this_month', 0) or 0,
            'word_limit': MONTHLY_WORD_LIMIT,
            'download_limit': MONTHLY_DOWNLOAD_LIMIT,
            'member_since': current_user.created_at.strftime('%B %Y') if current_user.created_at else 'Unknown'
        }
        
        return render_template('profile/dashboard.html', 
                             user=current_user, 
                             recent_articles=recent_articles,
                             stats=stats)
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        flash('Error loading dashboard.', 'error')
        return redirect(url_for('index'))

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def profile_edit():
    """Edit user profile"""
    form = ProfileForm(obj=current_user)
    
    if form.validate_on_submit():
        try:
            current_user.name = form.name.data
            current_user.theme_preference = form.theme_preference.data
            
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile_dashboard'))
        except (OperationalError, DatabaseError) as e:
            db.session.rollback()
            logger.error(f"Database error updating profile: {e}")
            flash('Database connection issue. Please try again.', 'error')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Profile update error: {e}")
            flash('Failed to update profile.', 'error')
    
    return render_template('profile/edit.html', form=form)

@app.route('/profile/change-password', methods=['GET', 'POST'])
@login_required
def profile_change_password():
    """Change user password"""
    if current_user.google_id and not current_user.password_hash:
        flash('Google account users cannot change password here.', 'info')
        return redirect(url_for('profile_dashboard'))
    
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        try:
            if not current_user.check_password(form.current_password.data):
                flash('Current password is incorrect.', 'error')
                return render_template('profile/change_password.html', form=form)
            
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('profile_dashboard'))
        except (OperationalError, DatabaseError) as e:
            db.session.rollback()
            logger.error(f"Database error changing password: {e}")
            flash('Database connection issue. Please try again.', 'error')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Password change error: {e}")
            flash('Failed to change password.', 'error')
    
    return render_template('profile/change_password.html', form=form)

@app.route('/profile/delete-account', methods=['POST'])
@login_required
def profile_delete_account():
    """Delete user account"""
    try:
        # Delete all user's articles
        Article.query.filter_by(user_id=current_user.id).delete()
        
        # Delete all user's chat sessions
        ChatSession.query.filter_by(user_id=current_user.id).delete()
        
        # Delete the user
        db.session.delete(current_user)
        db.session.commit()
        
        logout_user()
        flash('Your account has been deleted successfully.', 'success')
        return redirect(url_for('index'))
    except (OperationalError, DatabaseError) as e:
        db.session.rollback()
        logger.error(f"Database error deleting account: {e}")
        flash('Database connection issue. Please try again.', 'error')
        return redirect(url_for('profile_edit'))
    except Exception as e:
        db.session.rollback()
        logger.error(f"Account deletion error: {e}")
        flash('Failed to delete account. Please try again.', 'error')
        return redirect(url_for('profile_edit'))

@app.route('/profile/articles')
@login_required
def profile_articles():
    """View all user articles"""
    try:
        page = request.args.get('page', 1, type=int)
        articles = Article.query.filter_by(user_id=current_user.id)\
                               .order_by(Article.created_at.desc())\
                               .paginate(page=page, per_page=20, error_out=False)
        
        return render_template('profile/articles.html', articles=articles)
    except (OperationalError, DatabaseError) as e:
        logger.error(f"Database error loading articles: {e}")
        flash('Database connection issue loading articles.', 'error')
        return redirect(url_for('profile_dashboard'))
    except Exception as e:
        logger.error(f"Articles page error: {e}")
        flash('Error loading articles.', 'error')
        return redirect(url_for('profile_dashboard'))

@app.route('/article/view/<int:article_id>')
@login_required
def article_view(article_id):
    """View a specific article"""
    try:
        article = Article.query.filter_by(id=article_id, user_id=current_user.id).first_or_404()
        return render_template('article/view.html', article=article)
    except (OperationalError, DatabaseError) as e:
        logger.error(f"Database error loading article {article_id}: {e}")
        flash('Database connection issue loading article.', 'error')
        return redirect(url_for('profile_articles'))
    except Exception as e:
        logger.error(f"Article view error: {e}")
        flash('Error loading article.', 'error')
        return redirect(url_for('profile_articles'))

@app.route('/share/<string:public_id>')
def share_article(public_id):
    """Public-facing route to view a shared article"""
    try:
        article = Article.query.filter_by(public_id=public_id).first_or_404()
        return render_template('article/share.html', article=article)
    except (OperationalError, DatabaseError) as e:
        logger.error(f"Database error loading shared article {public_id}: {e}")
        return render_template('errors/500.html'), 500
    except Exception as e:
        logger.error(f"Share article error: {e}")
        return render_template('errors/404.html'), 404

# --- 4. MAIN APP ROUTES ---

@app.route("/")
def index():
    """Main application route"""
    if current_user.is_authenticated:
        return render_template("app.html", user=current_user)
    else:
        return render_template("landing.html")

@app.route("/app")
@login_required
def app_main():
    """Main app interface (requires login)"""
    return render_template("app.html", user=current_user)

@app.route("/generate", methods=["POST"])
@login_required
def generate_article():
    if not CLIENT:
        return jsonify({"error": "AI service is not available."}), 503
    
    data = request.get_json()
    user_topic = data.get("topic")
    if not user_topic:
        return jsonify({"error": "Topic is missing."}), 400

    # Check monthly word quota
    if not check_monthly_word_quota(current_user):
        return jsonify({"error": f"You've reached your monthly limit of {MONTHLY_WORD_LIMIT} words. Please try again next month."}), 403

    full_prompt = construct_initial_prompt(user_topic)
    try:
        response = CLIENT.generate_content(contents=full_prompt)

        if not response.candidates or not response.candidates[0].content.parts:
            return jsonify({"error": "Model response was empty or blocked."}), 500

        raw_text = response.candidates[0].content.parts[0].text
        final_html = format_article_content(raw_text)
        
        # Save article to database
        article_id = save_article_to_db(current_user.id, user_topic, final_html, raw_text)

        return jsonify({
            "article_html": final_html, 
            "raw_text": raw_text,
            "article_id": article_id
        })
    except Exception as e:
        logger.error(f"Article generation error: {e}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route("/generate-guest", methods=["POST"])
def generate_guest_article():
    """Generate article for guest users"""
    if not CLIENT:
        return jsonify({"error": "AI service is not available."}), 503
    
    data = request.get_json()
    user_topic = data.get("topic")
    if not user_topic:
        return jsonify({"error": "Topic is missing."}), 400

    full_prompt = construct_initial_prompt(user_topic)
    try:
        response = CLIENT.generate_content(contents=full_prompt)

        if not response.candidates or not response.candidates[0].content.parts:
            return jsonify({"error": "Model response was empty or blocked."}), 500

        raw_text = response.candidates[0].content.parts[0].text
        final_html = format_article_content(raw_text)
        
        # For guests, we don't save to database
        return jsonify({
            "article_html": final_html, 
            "raw_text": raw_text
        })
    except Exception as e:
        logger.error(f"Guest article generation error: {e}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route("/refine", methods=["POST"])
def refine_article():
    """Refine article for both authenticated and guest users"""
    if not CLIENT:
        return jsonify({"error": "AI service is not available."}), 503
    
    data = request.get_json()
    raw_text, refinement_prompt = data.get("raw_text"), data.get("refinement_prompt")
    article_id = data.get("article_id")
    
    if not all([raw_text, refinement_prompt]):
        return jsonify({"error": "Missing data for refinement."}), 400

    try:
        history = [
            {"role": "user", "parts": [{"text": "You are an AI assistant. You provided this article draft."}]},
            {"role": "model", "parts": [{"text": raw_text}]},
            {"role": "user", "parts": [{"text": refinement_prompt}]}
        ]
        response = CLIENT.generate_content(contents=history)

        if not response.candidates or not response.candidates[0].content.parts:
            return jsonify({"error": "Refinement response was empty or blocked."}), 500

        refined_text = response.candidates[0].content.parts[0].text
        final_html = format_article_content(refined_text)
        
        # Update article in database if article_id provided and user is authenticated
        if article_id and current_user.is_authenticated:
            # Check monthly word quota
            word_count = len(refined_text.split())
            current_words = getattr(current_user, 'words_generated_this_month', 0) or 0
            if current_words + word_count > MONTHLY_WORD_LIMIT:
                return jsonify({"error": f"This refinement would exceed your monthly limit of {MONTHLY_WORD_LIMIT} words."}), 403
                
            save_article_to_db(current_user.id, "", final_html, refined_text, True, article_id)

        return jsonify({"article_html": final_html, "raw_text": refined_text})
    except Exception as e:
        logger.error(f"Article refinement error: {e}")
        return jsonify({"error": f"An unexpected error occurred during refinement: {str(e)}"}), 500

@app.route("/download-docx", methods=["POST"])
def download_docx():
    """Download article as DOCX for both authenticated and guest users"""
    data = request.get_json()
    html_content = data.get("html")
    topic = data.get("topic", "Generated Article")
    article_id = data.get("article_id")
    
    if not html_content:
        return jsonify({"error": "Missing HTML content."}), 400
    
    try:
        # Update download count if article_id provided and user is authenticated
        if article_id and current_user.is_authenticated:
            try:
                article = Article.query.filter_by(id=article_id, user_id=current_user.id).first()
                if article:
                    # Check monthly download quota
                    if not check_monthly_download_quota(current_user):
                        return jsonify({"error": f"You've reached your monthly limit of {MONTHLY_DOWNLOAD_LIMIT} downloads."}), 403
                    
                    article.increment_download()
                    current_user.downloads_this_month = (getattr(current_user, 'downloads_this_month', 0) or 0) + 1
                    db.session.commit()
            except Exception as e:
                logger.warning(f"Failed to update download count: {e}")
        
        # Generate DOCX
        soup = BeautifulSoup(html_content, 'html.parser')
        doc = Document()
        doc.add_heading(topic, level=0)
        
        for element in soup.find_all(['h2', 'h3', 'p', 'div']):
            if element.name == 'h2':
                doc.add_heading(element.get_text(), level=2)
            elif element.name == 'h3':
                doc.add_heading(element.get_text(), level=3)
            elif element.name == 'p' and not element.find_parents("div"):
                doc.add_paragraph(element.get_text())
            elif element.name == 'div' and "real-image-container" in element.get('class', []):
                title_p = element.find('p', class_='image-title')
                img_tag = element.find('img')
                alt_text_p = element.find('p', class_='alt-text-display')
                attr_p = element.find('p', class_='attribution')

                if title_p:
                    p = doc.add_paragraph(title_p.get_text())
                    p.alignment = 1
                    p.bold = True

                if img_tag and img_tag.get('src'):
                    try:
                        img_response = requests.get(img_tag['src'], stream=True, timeout=10)
                        img_response.raise_for_status()
                        doc.add_picture(io.BytesIO(img_response.content), width=Inches(5.5))
                    except requests.RequestException:
                        doc.add_paragraph(f"[Image failed to load from {img_tag['src']}]")

                if alt_text_p:
                    p = doc.add_paragraph()
                    clean_alt_text = alt_text_p.get_text()
                    if clean_alt_text.lower().startswith("alt text:"):
                        clean_alt_text = clean_alt_text[len("Alt Text:"):].strip()
                    run = p.add_run(clean_alt_text)
                    run.italic = True
                    p.alignment = 1

                if attr_p:
                    p = doc.add_paragraph(attr_p.get_text())
                    p.alignment = 1
                    p.italic = True

        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)
        filename = f"{topic[:50].strip().replace(' ', '_')}.docx"
        return send_file(file_stream, as_attachment=True, download_name=filename, 
                        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    except Exception as e:
        logger.error(f"DOCX generation error: {e}")
        return jsonify({"error": "Failed to generate document."}), 500

# --- 5. API ROUTES FOR USER DATA ---

@app.route('/api/user/articles')
@login_required
def api_user_articles():
    """Get user's articles via API"""
    try:
        articles = Article.query.filter_by(user_id=current_user.id)\
                               .order_by(Article.created_at.desc()).all()
        return jsonify([article.to_dict() for article in articles])
    except (OperationalError, DatabaseError) as e:
        logger.error(f"Database error in API articles: {e}")
        return jsonify({"error": "Database connection issue"}), 500
    except Exception as e:
        logger.error(f"API articles error: {e}")
        return jsonify({"error": "Failed to fetch articles"}), 500

@app.route('/api/user/stats')
@login_required
def api_user_stats():
    """Get user statistics"""
    try:
        total_articles = Article.query.filter_by(user_id=current_user.id).count()
        total_words = db.session.query(db.func.sum(Article.word_count))\
                               .filter_by(user_id=current_user.id).scalar() or 0
        total_downloads = db.session.query(db.func.sum(Article.download_count))\
                                    .filter_by(user_id=current_user.id).scalar() or 0
        
        return jsonify({
            'total_articles': total_articles,
            'total_words': total_words,
            'total_downloads': total_downloads,
            'words_this_month': getattr(current_user, 'words_generated_this_month', 0) or 0,
            'downloads_this_month': getattr(current_user, 'downloads_this_month', 0) or 0,
            'word_limit': MONTHLY_WORD_LIMIT,
            'download_limit': MONTHLY_DOWNLOAD_LIMIT,
            'member_since': current_user.created_at.isoformat() if current_user.created_at else None
        })
    except (OperationalError, DatabaseError) as e:
        logger.error(f"Database error in API stats: {e}")
        return jsonify({"error": "Database connection issue"}), 500
    except Exception as e:
        logger.error(f"API stats error: {e}")
        return jsonify({"error": "Failed to fetch stats"}), 500

@app.route('/api/articles/<int:article_id>/download', methods=['POST'])
@login_required
def api_download_article(article_id):
    """API endpoint to download an article"""
    try:
        article = Article.query.filter_by(id=article_id, user_id=current_user.id).first_or_404()
        
        # Check monthly download quota
        if not check_monthly_download_quota(current_user):
            return jsonify({"error": f"You've reached your monthly limit of {MONTHLY_DOWNLOAD_LIMIT} downloads."}), 403
        
        # Generate DOCX
        soup = BeautifulSoup(article.content_html, 'html.parser')
        doc = Document()
        doc.add_heading(article.title, level=0)
        
        # Similar DOCX generation logic as in download_docx route
        # ...
        
        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)
        filename = f"{article.title[:50].strip().replace(' ', '_')}.docx"
        
        # Update download count
        article.increment_download()
        current_user.downloads_this_month = (getattr(current_user, 'downloads_this_month', 0) or 0) + 1
        db.session.commit()
        
        return send_file(file_stream, as_attachment=True, download_name=filename, 
                        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    except (OperationalError, DatabaseError) as e:
        logger.error(f"Database error in API download: {e}")
        return jsonify({"error": "Database connection issue"}), 500
    except Exception as e:
        logger.error(f"API download error: {e}")
        return jsonify({"error": "Failed to download article"}), 500

# --- 6. ERROR HANDLERS ---

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    logger.error(f"Internal server error: {error}")
    return render_template('errors/500.html'), 500

@app.errorhandler(OperationalError)
def database_error(error):
    db.session.rollback()
    logger.error(f"Database operational error: {error}")
    flash('Database connection issue. Please try again in a moment.', 'error')
    return redirect(url_for('index'))

# --- 7. DATABASE INITIALIZATION ---

def init_db():
    """Initialize database tables"""
    try:
        with app.app_context():
            db.create_all()
            logger.info("Database tables created successfully")
            
            # Run migrations to ensure schema is up to date
            try:
                from migrations import run_migrations
                run_migrations()
            except ImportError:
                logger.warning("Migrations module not found, skipping migrations")
            except Exception as e:
                logger.warning(f"Migration error (non-fatal): {e}")
                
    except Exception as e:
        logger.error(f"Database initialization error: {e}")

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    # For production deployment
    init_db()
