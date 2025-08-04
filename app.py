import os
import io
import re
import requests
import markdown
import secrets
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from bs4 import BeautifulSoup
from docx import Document
from docx.shared import Inches
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from datetime import datetime
import json

# Import our models and forms
from models import db, User, Article, ChatSession
from forms import LoginForm, RegisterForm, ProfileForm, ChangePasswordForm

# --- 1. INITIALIZATION & HELPERS ---
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///inkdrive.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Google OAuth Configuration
app.config['GOOGLE_CLIENT_ID'] = os.getenv('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.getenv('GOOGLE_CLIENT_SECRET')

# Load environment variables from Render
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash-lite")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth_login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Validation check - ensure the critical variables are set
if not GCP_PROJECT_ID or not UNSPLASH_ACCESS_KEY or not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    missing_vars = []
    if not GCP_PROJECT_ID: missing_vars.append("GCP_PROJECT_ID")
    if not UNSPLASH_ACCESS_KEY: missing_vars.append("UNSPLASH_ACCESS_KEY")
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"): missing_vars.append("GOOGLE_APPLICATION_CREDENTIALS")
    print(f"⚠️  Warning: Missing environment variables: {', '.join(missing_vars)}")

# --- Initialize genai client with Vertex AI ---
try:
    genai.configure()
    CLIENT = genai.GenerativeModel(model_name=MODEL_NAME)
    print(f"✅ Google AI Client Initialized Successfully via Vertex AI.")
except Exception as e:
    print(f"❌ Failed to initialize Google AI client. Error details: {e}")
    CLIENT = None

# Helper functions (same as before)
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
    except requests.RequestException:
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

def save_article_to_db(user_id, topic, content_html, content_raw, is_refined=False):
    """Save article to database"""
    try:
        # Extract word count (rough estimate)
        word_count = len(content_raw.split())
        
        article = Article(
            user_id=user_id,
            title=topic[:200],  # Truncate if too long
            content_html=content_html,
            content_raw=content_raw,
            topic=topic,
            is_refined=is_refined,
            word_count=word_count
        )
        
        db.session.add(article)
        db.session.commit()
        
        # Update user's article count
        user = User.query.get(user_id)
        if user:
            user.articles_generated += 1
            db.session.commit()
        
        return article.id
    except Exception as e:
        db.session.rollback()
        print(f"Error saving article: {e}")
        return None

# --- 2. AUTHENTICATION ROUTES ---

@app.route('/auth/login', methods=['GET', 'POST'])
def auth_login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            user.update_last_login()
            flash('Welcome back!', 'success')
            
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Invalid email or password.', 'error')
    
    return render_template('auth/login.html', form=form)

@app.route('/auth/register', methods=['GET', 'POST'])
def auth_register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        # Check if user already exists
        existing_user = User.query.filter_by(email=form.email.data.lower()).first()
        if existing_user:
            flash('Email address already registered.', 'error')
            return render_template('auth/register.html', form=form)
        
        # Create new user
        user = User(
            email=form.email.data.lower(),
            name=form.name.data,
            is_verified=True  # Auto-verify for now
        )
        user.set_password(form.password.data)
        
        try:
            db.session.add(user)
            db.session.commit()
            
            login_user(user)
            flash('Registration successful! Welcome to InkDrive!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'error')
    
    return render_template('auth/register.html', form=form)

@app.route('/auth/google')
def auth_google():
    """Initiate Google OAuth flow"""
    if not app.config.get('GOOGLE_CLIENT_ID'):
        flash('Google authentication is not configured.', 'error')
        return redirect(url_for('auth_login'))
    
    # In a real implementation, you'd use a proper OAuth library
    # For now, we'll handle it via JavaScript on the frontend
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
                # Create new user
                user = User(
                    email=email.lower(),
                    name=name,
                    google_id=google_id,
                    profile_picture=picture,
                    is_verified=True
                )
                db.session.add(user)
        else:
            # Update existing Google user info
            user.name = name
            user.profile_picture = picture
        
        db.session.commit()
        login_user(user)
        user.update_last_login()
        
        return jsonify({'success': True, 'redirect': url_for('index')})
        
    except ValueError as e:
        return jsonify({'error': 'Invalid token'}), 400
    except Exception as e:
        db.session.rollback()
         Return the actual error message to the browser
        return jsonify({'error': f"An unexpected error occurred: {str(e)}"}), 500
```This change will make the pop-up show you the real database error (e.g., "OperationalError: unable to open database file"), which can be very helpful for debugging.

### Summary of Actions

1.  **Add the `DATABASE_URL` environment variable in your Render dashboard.** This is the most critical step and will likely fix both errors.
2.  Wait for your application to redeploy with the new setting.
3.  Try registering with both email and Google again.

If you continue to see errors, the improved error logging from Step 2, combined with checking the **"Logs"** tab for your service in Render, will give you the exact reason for the failure.

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
    # Get user's recent articles
    recent_articles = Article.query.filter_by(user_id=current_user.id)\
                                 .order_by(Article.created_at.desc())\
                                 .limit(10).all()
    
    # Get user's chat sessions
    recent_chats = ChatSession.query.filter_by(user_id=current_user.id)\
                                   .order_by(ChatSession.updated_at.desc())\
                                   .limit(10).all()
    
    # Calculate stats
    total_articles = Article.query.filter_by(user_id=current_user.id).count()
    total_words = db.session.query(db.func.sum(Article.word_count))\
                           .filter_by(user_id=current_user.id).scalar() or 0
    total_downloads = db.session.query(db.func.sum(Article.download_count))\
                                .filter_by(user_id=current_user.id).scalar() or 0
    
    stats = {
        'total_articles': total_articles,
        'total_words': total_words,
        'total_downloads': total_downloads,
        'member_since': current_user.created_at.strftime('%B %Y') if current_user.created_at else 'Unknown'
    }
    
    return render_template('profile/dashboard.html', 
                         user=current_user, 
                         recent_articles=recent_articles,
                         recent_chats=recent_chats,
                         stats=stats)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def profile_edit():
    """Edit user profile"""
    form = ProfileForm(obj=current_user)
    
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.theme_preference = form.theme_preference.data
        
        try:
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile_dashboard'))
        except Exception as e:
            db.session.rollback()
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
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'error')
            return render_template('profile/change_password.html', form=form)
        
        current_user.set_password(form.new_password.data)
        
        try:
            db.session.commit()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('profile_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('Failed to change password.', 'error')
    
    return render_template('profile/change_password.html', form=form)

@app.route('/profile/articles')
@login_required
def profile_articles():
    """View all user articles"""
    page = request.args.get('page', 1, type=int)
    articles = Article.query.filter_by(user_id=current_user.id)\
                           .order_by(Article.created_at.desc())\
                           .paginate(page=page, per_page=20, error_out=False)
    
    return render_template('profile/articles.html', articles=articles)

# --- 4. MAIN APP ROUTES (Updated for Authentication) ---

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
        return jsonify({"error": "AI client is not initialized."}), 500
    
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
        
        # Save article to database
        article_id = save_article_to_db(current_user.id, user_topic, final_html, raw_text)

        return jsonify({
            "article_html": final_html, 
            "raw_text": raw_text,
            "article_id": article_id
        })
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route("/refine", methods=["POST"])
@login_required
def refine_article():
    if not CLIENT:
        return jsonify({"error": "AI client is not initialized."}), 500
    
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
        
        # Update article in database if article_id provided
        if article_id:
            article = Article.query.filter_by(id=article_id, user_id=current_user.id).first()
            if article:
                article.content_html = final_html
                article.content_raw = refined_text
                article.is_refined = True
                article.updated_at = datetime.utcnow()
                db.session.commit()

        return jsonify({"article_html": final_html, "raw_text": refined_text})
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred during refinement: {str(e)}"}), 500

@app.route("/download-docx", methods=["POST"])
@login_required
def download_docx():
    data = request.get_json()
    html_content = data.get("html")
    topic = data.get("topic", "Generated Article")
    article_id = data.get("article_id")
    
    if not html_content:
        return jsonify({"error": "Missing HTML content."}), 400
    
    # Update download count if article_id provided
    if article_id:
        article = Article.query.filter_by(id=article_id, user_id=current_user.id).first()
        if article:
            article.increment_download()
    
    # Same DOCX generation logic as before
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
                    img_response = requests.get(img_tag['src'], stream=True)
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

# --- 5. API ROUTES FOR USER DATA ---

@app.route('/api/user/articles')
@login_required
def api_user_articles():
    """Get user's articles via API"""
    articles = Article.query.filter_by(user_id=current_user.id)\
                           .order_by(Article.created_at.desc()).all()
    return jsonify([article.to_dict() for article in articles])

@app.route('/api/user/stats')
@login_required
def api_user_stats():
    """Get user statistics"""
    total_articles = Article.query.filter_by(user_id=current_user.id).count()
    total_words = db.session.query(db.func.sum(Article.word_count))\
                           .filter_by(user_id=current_user.id).scalar() or 0
    total_downloads = db.session.query(db.func.sum(Article.download_count))\
                                .filter_by(user_id=current_user.id).scalar() or 0
    
    return jsonify({
        'total_articles': total_articles,
        'total_words': total_words,
        'total_downloads': total_downloads,
        'member_since': current_user.created_at.isoformat() if current_user.created_at else None
    })

# --- 6. DATABASE INITIALIZATION ---

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)

