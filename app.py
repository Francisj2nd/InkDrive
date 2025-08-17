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
from google.api_core import exceptions as google_exceptions
import vertexai
from vertexai.generative_models import GenerativeModel
from datetime import datetime, timedelta
import json
import logging
from sqlalchemy.exc import OperationalError, DatabaseError
from sqlalchemy import func
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Import our models and forms
from models import db, User, Article, ChatSession
from forms import LoginForm, RegisterForm, ProfileForm, ChangePasswordForm

# Import admin blueprint
from admin import admin_bp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. INITIALIZATION & HELPERS ---
app = Flask(__name__)

# Register admin blueprint
app.register_blueprint(admin_bp)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///inkdrive.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Engine options - conditionally add connect_args for PostgreSQL
engine_options = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}
if 'postgresql' in app.config['SQLALCHEMY_DATABASE_URI']:
    engine_options['connect_args'] = {
        'connect_timeout': 10,
        'sslmode': 'require'
    }
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options

# Fix for Render PostgreSQL URLs
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)

# Google OAuth Configuration
app.config['GOOGLE_CLIENT_ID'] = os.getenv('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.getenv('GOOGLE_CLIENT_SECRET')

# Email Configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['CONTACT_EMAIL'] = 'francisj2nd@gmail.com'

# Load environment variables from Render
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash-lite")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")

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
if not GOOGLE_API_KEY: missing_vars.append("GOOGLE_API_KEY")
if not GOOGLE_CSE_ID: missing_vars.append("GOOGLE_CSE_ID")
if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"): missing_vars.append("GOOGLE_APPLICATION_CREDENTIALS")

if missing_vars:
    logger.warning(f"Missing environment variables: {', '.join(missing_vars)}")

# --- Initialize genai client with Vertex AI ---
CLIENT = None
try:
    if GCP_PROJECT_ID and os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        vertexai.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
        CLIENT = GenerativeModel(model_name=MODEL_NAME)
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

def construct_social_post_prompt(topic, goal, platform):
    """Constructs a prompt for generating social media posts."""
    return f"""
    You are a social media marketing expert. Your task is to generate 3 distinct social media posts for the {platform} platform.

    **Topic:** {topic}
    **Goal of the posts:** {goal}

    **Requirements:**
    1.  **Platform:** Tailor the tone and length for {platform}.
    2.  **Variety:** Provide three distinct options with different angles or hooks.
    3.  **Hashtags:** Include relevant and trending hashtags for each post.
    4.  **Formatting:** Present each post clearly separated. Use "---" between each post option.

    Generate the social media posts now.
    """

def construct_email_prompt(topic, audience, tone):
    """Constructs a prompt for generating an email."""
    return f"""
    You are an expert copywriter specializing in email marketing. Your task is to write a compelling marketing email.

    **Topic/Product:** {topic}
    **Target Audience:** {audience}
    **Desired Tone:** {tone}

    **Requirements:**
    1.  **Subject Line:** Generate 3-5 engaging subject line options.
    2.  **Email Body:** Write a complete email body based on the topic. It should have a clear hook, body, and call-to-action (CTA).
    3.  **Formatting:** Use Markdown for formatting (e.g., bolding, bullet points). Start with the subject lines, followed by "---", then the email body.

    Generate the email content now.
    """

def construct_refine_text_prompt(text_to_refine, target_tone):
    """Constructs a prompt for refining text to a specific tone."""
    return f"""
    You are an expert editor. Your task is to revise the following text to match a "{target_tone}" tone.

    **Original Text:**
    ---
    {text_to_refine}
    ---

    **Instructions:**
    1.  Rewrite the text to embody a "{target_tone}" tone and style.
    2.  Do not add any new information or change the core meaning.
    3.  Return only the revised text, without any commentary or preamble.

    Revise the text now.
    """

def construct_article_to_tweet_prompt(article_text):
    """Constructs a prompt for converting an article into a Twitter thread."""
    return f"""
    You are a social media expert specializing in content repurposing. Your task is to convert the following article into a compelling, numbered Twitter thread.

    **Article Text:**
    ---
    {article_text}
    ---

    **Instructions:**
    1.  **Create a Thread:** Generate a series of tweets that summarize the key points of the article.
    2.  **Numbered Tweets:** Start each tweet with a number (e.g., "1/n", "2/n").
    3.  **Engaging Hook:** The first tweet should be a strong hook to grab the reader's attention.
    4.  **Concise and Clear:** Each tweet must be under 280 characters.
    5.  **Add Hashtags:** Include relevant hashtags in the final tweet.
    6.  **Separator:** Use "---" on a new line to separate each tweet in the output.
    7.  **Return Only the Thread:** Do not include any preamble, commentary, or extra text. Only return the tweets separated by "---".

    Generate the Twitter thread now.
    """

def get_image_url(query):
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        logger.warning("Google Search API credentials not configured.")
        return None

    api_url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "searchType": "image",
        "num": 1
    }
    try:
        response = requests.get(api_url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        if "items" in data and len(data["items"]) > 0:
            item = data["items"][0]
            return {"url": item["link"], "source": item["image"]["contextLink"]}
        return None
    except requests.RequestException as e:
        logger.error(f"Error fetching image from Google: {e}")
        return None

def format_article_content(raw_markdown_text, topic=""):
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
                f'<img src="{image_data["url"]}" alt="{alt_text}">'
                f'<p class="alt-text-display"><strong>Alt Text:</strong> {alt_text}</p>'
                f'<p class="source-link"><a href="{image_data["source"]}" target="_blank">Source</a></p>'
                f'</div>'
            )
            hybrid_content = hybrid_content.replace(original_placeholder, new_image_tag, 1)
        else:
            hybrid_content = hybrid_content.replace(original_placeholder, f'<p>[Image Placeholder: {title} - Could not fetch image]</p>', 1)

    final_html = markdown.markdown(hybrid_content, extensions=['fenced_code', 'tables'])
    return final_html

@retry_db_operation(max_retries=3)
def save_article_to_db(user_id, topic, content_html, content_raw, is_refined=False, article_id=None, chat_session_id=None):
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
                public_id=str(uuid.uuid4())[:8],  # Generate a short public ID for sharing
                chat_session_id=chat_session_id  # Link to chat session
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

@retry_db_operation(max_retries=3)
def save_chat_session_to_db(user_id, session_id, title, messages, raw_text='', studio_type='ARTICLE'):
    """Save or update chat session to database"""
    try:
        # Check if chat session exists
        chat_session = ChatSession.query.filter_by(session_id=session_id, user_id=user_id).first()

        if chat_session:
            # Update existing session
            chat_session.title = title[:200]
            chat_session.set_messages(messages)
            chat_session.raw_text = raw_text
            chat_session.studio_type = studio_type
            chat_session.updated_at = datetime.utcnow()
        else:
            # Create new session
            chat_session = ChatSession(
                user_id=user_id,
                session_id=session_id,
                title=title[:200],
                raw_text=raw_text,
                studio_type=studio_type
            )
            chat_session.set_messages(messages)
            db.session.add(chat_session)

        db.session.commit()
        return chat_session.id
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving chat session: {e}")
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

def send_contact_email(name, email, subject, message):
    """Send contact form email"""
    try:
        if not app.config['MAIL_USERNAME'] or not app.config['MAIL_PASSWORD']:
            logger.warning("Email credentials not configured")
            return False

        msg = MIMEMultipart()
        msg['From'] = app.config['MAIL_USERNAME']
        msg['To'] = app.config['CONTACT_EMAIL']
        msg['Subject'] = f"InkDrive Contact Form: {subject}"

        body = f"""
New contact form submission from InkDrive:

Name: {name}
Email: {email}
Subject: {subject}

Message:
{message}

---
This message was sent from the InkDrive contact form.
        """

        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
        server.starttls()
        server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        text = msg.as_string()
        server.sendmail(app.config['MAIL_USERNAME'], app.config['CONTACT_EMAIL'], text)
        server.quit()

        return True
    except Exception as e:
        logger.error(f"Error sending contact email: {e}")
        return False

# --- 2. AUTHENTICATION ROUTES ---

@app.route('/auth/login', methods=['GET', 'POST'])
def auth_login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = User.query.filter_by(email=form.email.data.lower()).first()

            if user:
                try:
                    password_valid = user.check_password(form.password.data)
                except Exception as e:
                    logger.error(f"Password check error for user {user.id}: {e}")
                    password_valid = False

                if password_valid:
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
                is_active=True,
                words_generated_this_month=0,
                downloads_this_month=0,
                articles_generated=0,
                total_words_generated=0,
                last_quota_reset=datetime.utcnow()
            )

            # Set password with error handling
            try:
                user.set_password(form.password.data)
            except ValueError as e:
                flash('Invalid password format.', 'error')
                return render_template('auth/register.html', form=form)

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
                    is_active=True,
                    words_generated_this_month=0,
                    downloads_this_month=0,
                    articles_generated=0,
                    total_words_generated=0,
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
        # Get user's recent articles with error handling (limit to 5)
        recent_articles = []
        published_articles = []
        total_articles = 0
        total_words = 0
        total_downloads = 0

        try:
            recent_articles = Article.query.filter_by(user_id=current_user.id)\
                                         .order_by(Article.created_at.desc())\
                                         .limit(5).all()

            # Get published articles (limit to 5)
            published_articles = Article.query.filter_by(user_id=current_user.id, is_public=True)\
                                             .order_by(Article.published_at.desc())\
                                             .limit(5).all()

            # Calculate stats
            total_articles = Article.query.filter_by(user_id=current_user.id).count()

            # Total words should be cumulative (never decrease)
            total_words = db.session.query(db.func.sum(Article.word_count))\
                                   .filter_by(user_id=current_user.id).scalar() or 0

            total_downloads = db.session.query(db.func.sum(Article.download_count))\
                                        .filter_by(user_id=current_user.id).scalar() or 0
        except (OperationalError, DatabaseError) as e:
            logger.error(f"Database error loading dashboard data: {e}")
            flash('Some dashboard data may not be available due to connection issues.', 'warning')

        # Check if we need to reset monthly quotas with error handling
        try:
            if current_user.last_quota_reset is None or (datetime.utcnow() - user.last_quota_reset) > timedelta(days=30):
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
                             published_articles=published_articles,
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

@app.route('/article/<int:article_id>/publish', methods=['POST'])
@login_required
def publish_article(article_id):
    """Publish an article"""
    try:
        article = Article.query.filter_by(id=article_id, user_id=current_user.id).first_or_404()

        if article.is_public:
            return jsonify({"error": "Article is already published"}), 400

        article.publish()

        public_url = url_for('share_article', public_id=article.public_id, _external=True)

        return jsonify({
            "success": True,
            "message": "Article published successfully!",
            "public_url": public_url
        })
    except (OperationalError, DatabaseError) as e:
        logger.error(f"Database error publishing article {article_id}: {e}")
        return jsonify({"error": "Database connection issue"}), 500
    except Exception as e:
        logger.error(f"Article publish error: {e}")
        return jsonify({"error": "Failed to publish article"}), 500

@app.route('/article/<int:article_id>/unpublish', methods=['POST'])
@login_required
def unpublish_article(article_id):
    """Unpublish an article"""
    try:
        article = Article.query.filter_by(id=article_id, user_id=current_user.id).first_or_404()

        if not article.is_public:
            return jsonify({"error": "Article is not published"}), 400

        article.unpublish()

        return jsonify({
            "success": True,
            "message": "Article unpublished successfully!"
        })
    except (OperationalError, DatabaseError) as e:
        logger.error(f"Database error unpublishing article {article_id}: {e}")
        return jsonify({"error": "Database connection issue"}), 500
    except Exception as e:
        logger.error(f"Article unpublish error: {e}")
        return jsonify({"error": "Failed to unpublish article"}), 500

@app.route('/article/<int:article_id>/delete', methods=['POST'])
@login_required
def delete_article(article_id):
    """Delete an article and its associated chat session"""
    try:
        article = Article.query.filter_by(id=article_id, user_id=current_user.id).first_or_404()

        # Find and delete associated chat session if it exists
        if article.chat_session_id:
            chat_session = ChatSession.query.filter_by(id=article.chat_session_id, user_id=current_user.id).first()
            if chat_session:
                db.session.delete(chat_session)

        # Delete the article
        db.session.delete(article)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Article and associated chat deleted successfully!"
        })
    except (OperationalError, DatabaseError) as e:
        db.session.rollback()
        logger.error(f"Database error deleting article {article_id}: {e}")
        return jsonify({"error": "Database connection issue"}), 500
    except Exception as e:
        db.session.rollback()
        logger.error(f"Article delete error: {e}")
        return jsonify({"error": "Failed to delete article"}), 500

@app.route('/share/<string:public_id>')
def share_article(public_id):
    """Public-facing route to view a published article"""
    try:
        # Fixed query: Only get articles that are both matching public_id AND published
        article = Article.query.filter_by(public_id=public_id, is_public=True).first()

        if not article:
            # Article doesn't exist or is not published
            abort(404)

        # Increment view count
        article.increment_view()

        # Get random published articles for social proof (excluding current article)
        try:
            # Use a simpler query that works with both SQLite and PostgreSQL
            featured_articles = Article.query.filter(
                Article.is_public == True,
                Article.id != article.id
            ).limit(6).all()
        except Exception as e:
            logger.warning(f"Error fetching featured articles: {e}")
            featured_articles = []

        return render_template('article/share.html', article=article, featured_articles=featured_articles)
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
        return render_template("dashboard.html", user=current_user)
    else:
        # Get random published articles for social proof
        try:
            # Use a simpler query that works with both SQLite and PostgreSQL
            featured_articles = Article.query.filter_by(is_public=True).limit(6).all()
        except Exception as e:
            logger.warning(f"Error fetching featured articles for landing: {e}")
            featured_articles = []

        return render_template("landing.html", featured_articles=featured_articles)

@app.route('/studio/article')
@login_required
def article_studio():
    """The new Article Studio page"""
    return render_template('article_studio.html', user=current_user)

@app.route('/studio/social')
@login_required
def social_studio():
    """The new Social & Comms Studio page"""
    return render_template('social_studio.html', user=current_user)

@app.route('/studio/editing')
@login_required
def editing_studio():
    """The new Editing & Refinement Studio page"""
    return render_template('editing_studio.html', user=current_user)

@app.route('/studio/repurpose')
@login_required
def repurpose_studio():
    """The new Content Repurposing Studio page"""
    return render_template('repurposing_studio.html', user=current_user)

@app.route('/api/v1/generate/social', methods=['POST'])
@login_required
def generate_social():
    """Generates social media post content."""
    if not CLIENT:
        return jsonify({"error": "AI service is not available."}), 503

    data = request.get_json()
    topic = data.get("topic")
    goal = data.get("goal")
    platform = data.get("platform")
    chat_session_id = data.get("chat_session_id")

    if not all([topic, goal, platform]):
        return jsonify({"error": "Missing required fields: topic, goal, or platform."}), 400

    if not check_monthly_word_quota(current_user):
        return jsonify({"error": f"You've reached your monthly word limit."}), 403

    full_prompt = construct_social_post_prompt(topic, goal, platform)
    try:
        response = CLIENT.generate_content(contents=full_prompt)
        raw_text = response.candidates[0].content.parts[0].text

        # Split the response into individual posts
        posts = [p.strip() for p in raw_text.split('---') if p.strip()]

        # Save to chat history
        if not chat_session_id:
            chat_session_id = f"chat_{int(datetime.utcnow().timestamp())}_{current_user.id}"

        # Create a user message that summarizes the request
        user_message = f"Topic: {topic}, Goal: {goal}, Platform: {platform}"

        messages = [
            {"content": user_message, "isUser": True, "id": f"msg_{int(datetime.utcnow().timestamp())}_user"},
            {"content": raw_text, "isUser": False, "id": f"msg_{int(datetime.utcnow().timestamp())}_ai"}
        ]

        session_title = f"Social Posts for '{topic}'"
        save_chat_session_to_db(current_user.id, chat_session_id, session_title, messages, raw_text, studio_type='SOCIAL_POST')

        return jsonify({
            "posts": posts,
            "chat_session_id": chat_session_id
        })
    except Exception as e:
        logger.error(f"Social post generation error: {e}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/v1/generate/email', methods=['POST'])
@login_required
def generate_email():
    """Generates email campaign content."""
    if not CLIENT:
        return jsonify({"error": "AI service is not available."}), 503

    data = request.get_json()
    topic = data.get("topic")
    audience = data.get("audience")
    tone = data.get("tone")
    chat_session_id = data.get("chat_session_id")

    if not all([topic, audience, tone]):
        return jsonify({"error": "Missing required fields: topic, audience, or tone."}), 400

    if not check_monthly_word_quota(current_user):
        return jsonify({"error": f"You've reached your monthly word limit."}), 403

    full_prompt = construct_email_prompt(topic, audience, tone)
    try:
        response = CLIENT.generate_content(contents=full_prompt)
        raw_text = response.candidates[0].content.parts[0].text

        # Save to chat history
        if not chat_session_id:
            chat_session_id = f"chat_{int(datetime.utcnow().timestamp())}_{current_user.id}"

        user_message = f"Topic: {topic}, Audience: {audience}, Tone: {tone}"
        messages = [
            {"content": user_message, "isUser": True, "id": f"msg_{int(datetime.utcnow().timestamp())}_user"},
            {"content": raw_text, "isUser": False, "id": f"msg_{int(datetime.utcnow().timestamp())}_ai"}
        ]

        session_title = f"Email for '{topic}'"
        save_chat_session_to_db(current_user.id, chat_session_id, session_title, messages, raw_text, studio_type='EMAIL')

        return jsonify({
            "email_content": raw_text,
            "chat_session_id": chat_session_id
        })
    except Exception as e:
        logger.error(f"Email generation error: {e}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route("/api/v1/generate/article", methods=["POST"])
@login_required
def generate_article():
    if not CLIENT:
        return jsonify({"error": "AI service is not available."}), 503

    data = request.get_json()
    user_topic = data.get("topic")
    chat_session_id = data.get("chat_session_id")

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
        final_html = format_article_content(raw_text, user_topic)

        # Save chat session to database
        if not chat_session_id:
            chat_session_id = f"chat_{int(datetime.utcnow().timestamp())}_{current_user.id}"

        messages = [
            {"content": user_topic, "isUser": True, "id": f"msg_{int(datetime.utcnow().timestamp())}_user"},
            {"content": final_html, "isUser": False, "id": f"msg_{int(datetime.utcnow().timestamp())}_ai"}
        ]

        db_chat_session_id = save_chat_session_to_db(current_user.id, chat_session_id, user_topic, messages, raw_text, studio_type='ARTICLE')

        # Save article to database with chat session link
        article_id = save_article_to_db(current_user.id, user_topic, final_html, raw_text, False, None, db_chat_session_id)

        return jsonify({
            "article_html": final_html,
            "raw_text": raw_text,
            "article_id": article_id,
            "chat_session_id": chat_session_id,
            "refinements_remaining": 5  # Always 5 for authenticated users on new article
        })
    except Exception as e:
        logger.error(f"Article generation error: {e}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route("/api/v1/generate/article-guest", methods=["POST"])
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
        final_html = format_article_content(raw_text, user_topic)

        # For guests, we don't save to database
        return jsonify({
            "article_html": final_html,
            "raw_text": raw_text,
            "refinements_remaining": 1  # Only 1 for guests
        })
    except Exception as e:
        logger.error(f"Guest article generation error: {e}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route("/api/v1/refine/article", methods=["POST"])
def refine_article():
    """Refine article for both authenticated and guest users"""
    if not CLIENT:
        return jsonify({"error": "AI service is not available."}), 503

    data = request.get_json()
    raw_text, refinement_prompt = data.get("raw_text"), data.get("refinement_prompt")
    article_id = data.get("article_id")
    chat_session_id = data.get("chat_session_id")
    refinements_used = data.get("refinements_used", 0)
    topic = data.get("topic", "")

    if not all([raw_text, refinement_prompt]):
        return jsonify({"error": "Missing data for refinement."}), 400

    # Check refinement limits and word quota for authenticated users
    if current_user.is_authenticated:
        if refinements_used >= 5:
            return jsonify({"error": "You've used all 5 refinements for this article."}), 403

        if not check_monthly_word_quota(current_user):
            return jsonify({"error": f"You've reached your monthly limit of {MONTHLY_WORD_LIMIT} words. Please try again next month."}), 403
    else:
        # Guest users get only 1 refinement
        if refinements_used >= 1:
            return jsonify({"error": "You've used your 1 refinement. Sign up for a free account to get 5 refinements per article."}), 403

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
        final_html = format_article_content(refined_text, topic)

        # Update word count for authenticated users
        if current_user.is_authenticated:
            word_count = len(refined_text.split())
            current_user.words_generated_this_month = (current_user.words_generated_this_month or 0) + word_count
            db.session.commit()

            # Update article in database if article_id provided
            if article_id:
                save_article_to_db(current_user.id, "", final_html, refined_text, True, article_id)

            # Update chat session
            if chat_session_id:
                chat_session = ChatSession.query.filter_by(session_id=chat_session_id, user_id=current_user.id).first()
                if chat_session:
                    messages = chat_session.get_messages()
                    messages.append({"content": refinement_prompt, "isUser": True, "id": f"msg_{int(datetime.utcnow().timestamp())}_user"})
                    messages.append({"content": final_html, "isUser": False, "id": f"msg_{int(datetime.utcnow().timestamp())}_ai"})
                    chat_session.set_messages(messages)
                    chat_session.raw_text = refined_text
                    chat_session.has_refined = True
                    db.session.commit()

        new_refinements_used = refinements_used + 1
        remaining_refinements = (5 if current_user.is_authenticated else 1) - new_refinements_used

        return jsonify({
            "article_html": final_html,
            "raw_text": refined_text,
            "refinements_used": new_refinements_used,
            "refinements_remaining": remaining_refinements
        })
    except Exception as e:
        logger.error(f"Article refinement error: {e}")
        return jsonify({"error": f"An unexpected error occurred during refinement: {str(e)}"}), 500

@app.route('/api/v1/refine/text', methods=['POST'])
@login_required
def refine_text():
    """Refines a piece of text to a specific tone."""
    if not CLIENT:
        return jsonify({"error": "AI service is not available."}), 503

    data = request.get_json()
    text_to_refine = data.get("text")
    target_tone = data.get("tone")
    chat_session_id = data.get("chat_session_id")

    if not text_to_refine or not target_tone:
        return jsonify({"error": "Missing required fields: text or tone."}), 400

    if not check_monthly_word_quota(current_user):
        return jsonify({"error": f"You've reached your monthly word limit."}), 403

    full_prompt = construct_refine_text_prompt(text_to_refine, target_tone)
    try:
        response = CLIENT.generate_content(contents=full_prompt)
        refined_text = response.candidates[0].content.parts[0].text

        # Save to chat history
        if not chat_session_id:
            chat_session_id = f"chat_{int(datetime.utcnow().timestamp())}_{current_user.id}"

        user_message = f"Refine the following text to be more '{target_tone}':\n\n{text_to_refine[:200]}..."
        messages = [
            {"content": user_message, "isUser": True, "id": f"msg_{int(datetime.utcnow().timestamp())}_user"},
            {"content": refined_text, "isUser": False, "id": f"msg_{int(datetime.utcnow().timestamp())}_ai"}
        ]

        session_title = f"Refinement: {target_tone}"
        save_chat_session_to_db(current_user.id, chat_session_id, session_title, messages, refined_text, studio_type='TEXT_REFINEMENT')

        return jsonify({
            "refined_text": refined_text,
            "chat_session_id": chat_session_id
        })
    except Exception as e:
        logger.error(f"Text refinement error: {e}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/v1/repurpose/article-to-tweet', methods=['POST'])
@login_required
def repurpose_article_to_tweet():
    """Converts an article into a Twitter thread."""
    if not CLIENT:
        return jsonify({"error": "AI service is not available."}), 503

    data = request.get_json()
    article_text = data.get("article")
    chat_session_id = data.get("chat_session_id")

    if not article_text:
        return jsonify({"error": "Missing required field: article."}), 400

    if not check_monthly_word_quota(current_user):
        return jsonify({"error": f"You've reached your monthly word limit."}), 403

    full_prompt = construct_article_to_tweet_prompt(article_text)
    try:
        response = CLIENT.generate_content(contents=full_prompt)
        tweet_thread = response.candidates[0].content.parts[0].text

        # Save to chat history
        if not chat_session_id:
            chat_session_id = f"chat_{int(datetime.utcnow().timestamp())}_{current_user.id}"

        user_message = f"Convert the following article to a Twitter thread:\n\n{article_text[:200]}..."
        messages = [
            {"content": user_message, "isUser": True, "id": f"msg_{int(datetime.utcnow().timestamp())}_user"},
            {"content": tweet_thread, "isUser": False, "id": f"msg_{int(datetime.utcnow().timestamp())}_ai"}
        ]

        session_title = "Article to Tweet Thread"
        save_chat_session_to_db(current_user.id, chat_session_id, session_title, messages, tweet_thread, studio_type='REPURPOSE_TWEET')

        return jsonify({
            "tweet_thread": tweet_thread,
            "chat_session_id": chat_session_id
        })
    except Exception as e:
        logger.error(f"Article to tweet error: {e}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

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
                # Check monthly download quota
                if not check_monthly_download_quota(current_user):
                    return jsonify({"error": f"You've reached your monthly limit of {MONTHLY_DOWNLOAD_LIMIT} downloads."}), 403

                article = Article.query.filter_by(id=article_id, user_id=current_user.id).first()
                if article:
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

@app.route('/api/user/chat-history')
@login_required
def api_user_chat_history():
    """Get user's chat history from database"""
    try:
        chat_sessions = ChatSession.query.filter_by(user_id=current_user.id)\
                                        .order_by(ChatSession.updated_at.desc()).all()
        return jsonify([session.to_dict() for session in chat_sessions])
    except (OperationalError, DatabaseError) as e:
        logger.error(f"Database error in API chat history: {e}")
        return jsonify({"error": "Database connection issue"}), 500
    except Exception as e:
        logger.error(f"API chat history error: {e}")
        return jsonify({"error": "Failed to fetch chat history"}), 500

@app.route('/api/chat-session/<string:session_id>')
@login_required
def api_get_chat_session(session_id):
    """Get a specific chat session"""
    try:
        chat_session = ChatSession.query.filter_by(session_id=session_id, user_id=current_user.id).first()
        if not chat_session:
            return jsonify({"error": "Chat session not found"}), 404

        return jsonify(chat_session.to_dict())
    except (OperationalError, DatabaseError) as e:
        logger.error(f"Database error getting chat session: {e}")
        return jsonify({"error": "Database connection issue"}), 500
    except Exception as e:
        logger.error(f"API get chat session error: {e}")
        return jsonify({"error": "Failed to fetch chat session"}), 500

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

@app.route('/api/chat-sessions/<string:session_id>', methods=['DELETE'])
@login_required
def delete_chat_session(session_id):
    """Delete a chat session and all associated articles"""
    try:
        # Find the chat session
        chat_session = ChatSession.query.filter_by(session_id=session_id, user_id=current_user.id).first()
        if not chat_session:
            return jsonify({"error": "Chat session not found"}), 404

        # Delete all articles associated with this chat session
        Article.query.filter_by(chat_session_id=chat_session.id, user_id=current_user.id).delete()

        # Delete the chat session
        db.session.delete(chat_session)
        db.session.commit()

        return jsonify({"success": True, "message": "Chat session and associated articles deleted"})
    except (OperationalError, DatabaseError) as e:
        db.session.rollback()
        logger.error(f"Database error deleting chat session: {e}")
        return jsonify({"error": "Database connection issue"}), 500
    except Exception as e:
        db.session.rollback()
        logger.error(f"Chat session deletion error: {e}")
        return jsonify({"error": "Failed to delete chat session"}), 500

# --- 6. LEGAL PAGES ---

@app.route('/privacy')
def privacy_policy():
    """Privacy Policy page"""
    return render_template('legal/privacy.html')

@app.route('/terms')
def terms_of_service():
    """Terms of Service page"""
    return render_template('legal/terms.html')

@app.route('/support')
def support():
    """Support page"""
    return render_template('legal/support.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    """Contact page"""
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            subject = request.form.get('subject', '').strip()
            message = request.form.get('message', '').strip()

            if not all([name, email, subject, message]):
                flash('Please fill in all required fields.', 'error')
                return render_template('legal/contact.html')

            # Send email
            if send_contact_email(name, email, subject, message):
                flash('Thank you for your message! We\'ll get back to you soon.', 'success')
            else:
                flash('Sorry, there was an error sending your message. Please try again later.', 'error')

        except Exception as e:
            logger.error(f"Contact form error: {e}")
            flash('Sorry, there was an error processing your request.', 'error')

    return render_template('legal/contact.html')

# --- 7. ERROR HANDLERS ---

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

# --- 8. DATABASE INITIALIZATION ---

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
