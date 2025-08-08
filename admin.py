import os
import logging
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import func
from models import db, User, Article, ChatSession

# Configure logging
logger = logging.getLogger(__name__)

# Create admin blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Superadmin email addresses (can be configured via environment variable)
SUPERADMIN_EMAILS = os.getenv('SUPERADMIN_EMAILS', 'admin@inkdrive.com').split(',')

def is_superadmin():
    """Check if current user is a superadmin"""
    if not current_user.is_authenticated:
        return False
    return current_user.email.lower().strip() in [email.lower().strip() for email in SUPERADMIN_EMAILS]

def superadmin_required(f):
    """Decorator to require superadmin access"""
    def decorated_function(*args, **kwargs):
        if not is_superadmin():
            abort(404)  # Return 404 to hide the existence of admin pages
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@admin_bp.route('/')
@login_required
@superadmin_required
def dashboard():
    """Admin dashboard with platform statistics"""
    try:
        # Get platform statistics
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        total_articles = Article.query.count()
        published_articles = Article.query.filter_by(is_public=True).count()
        total_chat_sessions = ChatSession.query.count()
        
        # Get recent activity
        recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
        recent_articles = Article.query.order_by(Article.created_at.desc()).limit(10).all()
        
        # Get usage statistics
        total_words = db.session.query(func.sum(Article.word_count)).scalar() or 0
        total_downloads = db.session.query(func.sum(Article.download_count)).scalar() or 0
        total_views = db.session.query(func.sum(Article.view_count)).scalar() or 0
        
        # Get monthly statistics
        current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_users = User.query.filter(User.created_at >= current_month_start).count()
        monthly_articles = Article.query.filter(Article.created_at >= current_month_start).count()
        
        stats = {
            'total_users': total_users,
            'active_users': active_users,
            'total_articles': total_articles,
            'published_articles': published_articles,
            'total_chat_sessions': total_chat_sessions,
            'total_words': total_words,
            'total_downloads': total_downloads,
            'total_views': total_views,
            'monthly_users': monthly_users,
            'monthly_articles': monthly_articles
        }
        
        return render_template('admin/dashboard.html', 
                             stats=stats, 
                             recent_users=recent_users, 
                             recent_articles=recent_articles)
    except Exception as e:
        logger.error(f"Admin dashboard error: {e}")
        flash('Error loading dashboard data.', 'error')
        return render_template('admin/dashboard.html', stats={}, recent_users=[], recent_articles=[])

@admin_bp.route('/users')
@login_required
@superadmin_required
def users():
    """User management page"""
    try:
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '').strip()
        
        query = User.query
        
        if search:
            query = query.filter(
                db.or_(
                    User.email.ilike(f'%{search}%'),
                    User.name.ilike(f'%{search}%')
                )
            )
        
        users = query.order_by(User.created_at.desc()).paginate(
            page=page, per_page=50, error_out=False
        )
        
        return render_template('admin/users.html', users=users, search=search)
    except Exception as e:
        logger.error(f"Admin users page error: {e}")
        flash('Error loading users.', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/users/<int:user_id>')
@login_required
@superadmin_required
def user_detail(user_id):
    """User detail page"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Get user's articles
        articles = Article.query.filter_by(user_id=user_id).order_by(Article.created_at.desc()).limit(20).all()
        
        # Get user's chat sessions
        chat_sessions = ChatSession.query.filter_by(user_id=user_id).order_by(ChatSession.created_at.desc()).limit(10).all()
        
        # Calculate user statistics
        total_words = db.session.query(func.sum(Article.word_count)).filter_by(user_id=user_id).scalar() or 0
        total_downloads = db.session.query(func.sum(Article.download_count)).filter_by(user_id=user_id).scalar() or 0
        total_views = db.session.query(func.sum(Article.view_count)).filter_by(user_id=user_id).scalar() or 0
        
        user_stats = {
            'total_articles': len(articles),
            'total_words': total_words,
            'total_downloads': total_downloads,
            'total_views': total_views,
            'words_this_month': user.words_generated_this_month or 0,
            'downloads_this_month': user.downloads_this_month or 0
        }
        
        return render_template('admin/user_detail.html', 
                             user=user, 
                             articles=articles, 
                             chat_sessions=chat_sessions,
                             user_stats=user_stats)
    except Exception as e:
        logger.error(f"Admin user detail error: {e}")
        flash('Error loading user details.', 'error')
        return redirect(url_for('admin.users'))

@admin_bp.route('/articles')
@login_required
@superadmin_required
def articles():
    """Article management page"""
    try:
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '').strip()
        filter_type = request.args.get('filter', 'all')
        
        query = Article.query
        
        if search:
            query = query.filter(
                db.or_(
                    Article.title.ilike(f'%{search}%'),
                    Article.topic.ilike(f'%{search}%')
                )
            )
        
        if filter_type == 'published':
            query = query.filter_by(is_public=True)
        elif filter_type == 'unpublished':
            query = query.filter_by(is_public=False)
        
        articles = query.order_by(Article.created_at.desc()).paginate(
            page=page, per_page=50, error_out=False
        )
        
        return render_template('admin/articles.html', 
                             articles=articles, 
                             search=search, 
                             filter_type=filter_type)
    except Exception as e:
        logger.error(f"Admin articles page error: {e}")
        flash('Error loading articles.', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/articles/<int:article_id>')
@login_required
@superadmin_required
def article_detail(article_id):
    """Article detail page"""
    try:
        article = Article.query.get_or_404(article_id)
        return render_template('admin/article_detail.html', article=article)
    except Exception as e:
        logger.error(f"Admin article detail error: {e}")
        flash('Error loading article details.', 'error')
        return redirect(url_for('admin.articles'))

@admin_bp.route('/api/users/<int:user_id>/delete', methods=['POST'])
@login_required
@superadmin_required
def delete_user(user_id):
    """Delete a user account and all associated data"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Prevent deleting superadmins
        if user.email.lower().strip() in [email.lower().strip() for email in SUPERADMIN_EMAILS]:
            return jsonify({'error': 'Cannot delete superadmin accounts'}), 403
        
        # Delete all user's articles
        Article.query.filter_by(user_id=user_id).delete()
        
        # Delete all user's chat sessions
        ChatSession.query.filter_by(user_id=user_id).delete()
        
        # Delete the user
        username = user.name
        user_email = user.email
        db.session.delete(user)
        db.session.commit()
        
        logger.info(f"Admin {current_user.email} deleted user {user_email} ({username})")
        
        return jsonify({
            'success': True,
            'message': f'User {username} ({user_email}) and all associated data deleted successfully.'
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Admin delete user error: {e}")
        return jsonify({'error': 'Failed to delete user'}), 500

@admin_bp.route('/api/users/<int:user_id>/toggle-active', methods=['POST'])
@login_required
@superadmin_required
def toggle_user_active(user_id):
    """Toggle user active status"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Prevent deactivating superadmins
        if user.email.lower().strip() in [email.lower().strip() for email in SUPERADMIN_EMAILS]:
            return jsonify({'error': 'Cannot deactivate superadmin accounts'}), 403
        
        user.is_active = not user.is_active
        db.session.commit()
        
        status = 'activated' if user.is_active else 'deactivated'
        logger.info(f"Admin {current_user.email} {status} user {user.email}")
        
        return jsonify({
            'success': True,
            'message': f'User {user.name} has been {status}.',
            'is_active': user.is_active
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Admin toggle user active error: {e}")
        return jsonify({'error': 'Failed to update user status'}), 500

@admin_bp.route('/api/users/<int:user_id>/reset-limits', methods=['POST'])
@login_required
@superadmin_required
def reset_user_limits(user_id):
    """Reset user's monthly limits"""
    try:
        user = User.query.get_or_404(user_id)
        
        user.words_generated_this_month = 0
        user.downloads_this_month = 0
        user.last_quota_reset = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Admin {current_user.email} reset monthly limits for user {user.email}")
        
        return jsonify({
            'success': True,
            'message': f'Monthly limits reset for {user.name}.'
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Admin reset user limits error: {e}")
        return jsonify({'error': 'Failed to reset user limits'}), 500

@admin_bp.route('/api/articles/<int:article_id>/delete', methods=['POST'])
@login_required
@superadmin_required
def delete_article(article_id):
    """Delete an article"""
    try:
        article = Article.query.get_or_404(article_id)
        
        article_title = article.title
        author_name = article.author.name
        
        # Delete associated chat session if it exists and no other articles reference it
        if article.chat_session_id:
            other_articles = Article.query.filter(
                Article.chat_session_id == article.chat_session_id,
                Article.id != article_id
            ).count()
            
            if other_articles == 0:
                chat_session = ChatSession.query.get(article.chat_session_id)
                if chat_session:
                    db.session.delete(chat_session)
        
        db.session.delete(article)
        db.session.commit()
        
        logger.info(f"Admin {current_user.email} deleted article '{article_title}' by {author_name}")
        
        return jsonify({
            'success': True,
            'message': f'Article "{article_title}" by {author_name} deleted successfully.'
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Admin delete article error: {e}")
        return jsonify({'error': 'Failed to delete article'}), 500

@admin_bp.route('/api/articles/<int:article_id>/toggle-public', methods=['POST'])
@login_required
@superadmin_required
def toggle_article_public(article_id):
    """Toggle article public status"""
    try:
        article = Article.query.get_or_404(article_id)
        
        if article.is_public:
            article.unpublish()
            status = 'unpublished'
        else:
            article.publish()
            status = 'published'
        
        logger.info(f"Admin {current_user.email} {status} article '{article.title}' by {article.author.name}")
        
        return jsonify({
            'success': True,
            'message': f'Article "{article.title}" has been {status}.',
            'is_public': article.is_public
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Admin toggle article public error: {e}")
        return jsonify({'error': 'Failed to update article status'}), 500

@admin_bp.route('/api/stats/export')
@login_required
@superadmin_required
def export_stats():
    """Export platform statistics"""
    try:
        # Get comprehensive statistics
        stats = {
            'platform_overview': {
                'total_users': User.query.count(),
                'active_users': User.query.filter_by(is_active=True).count(),
                'total_articles': Article.query.count(),
                'published_articles': Article.query.filter_by(is_public=True).count(),
                'total_chat_sessions': ChatSession.query.count(),
                'total_words': db.session.query(func.sum(Article.word_count)).scalar() or 0,
                'total_downloads': db.session.query(func.sum(Article.download_count)).scalar() or 0,
                'total_views': db.session.query(func.sum(Article.view_count)).scalar() or 0
            },
            'monthly_stats': {},
            'user_activity': [],
            'content_stats': []
        }
        
        # Get monthly statistics for the last 12 months
        for i in range(12):
            month_start = (datetime.utcnow().replace(day=1) - timedelta(days=30*i)).replace(hour=0, minute=0, second=0, microsecond=0)
            month_end = month_start.replace(month=month_start.month+1) if month_start.month < 12 else month_start.replace(year=month_start.year+1, month=1)
            
            monthly_users = User.query.filter(
                User.created_at >= month_start,
                User.created_at < month_end
            ).count()
            
            monthly_articles = Article.query.filter(
                Article.created_at >= month_start,
                Article.created_at < month_end
            ).count()
            
            stats['monthly_stats'][month_start.strftime('%Y-%m')] = {
                'new_users': monthly_users,
                'new_articles': monthly_articles
            }
        
        # Get top users by activity
        top_users = db.session.query(
            User.id, User.name, User.email,
            func.count(Article.id).label('article_count'),
            func.sum(Article.word_count).label('total_words')
        ).join(Article).group_by(User.id).order_by(func.count(Article.id).desc()).limit(20).all()
        
        for user_data in top_users:
            stats['user_activity'].append({
                'user_id': user_data.id,
                'name': user_data.name,
                'email': user_data.email,
                'article_count': user_data.article_count,
                'total_words': user_data.total_words or 0
            })
        
        # Get content statistics
        top_articles = Article.query.order_by(Article.view_count.desc()).limit(10).all()
        for article in top_articles:
            stats['content_stats'].append({
                'title': article.title,
                'author': article.author.name,
                'view_count': article.view_count or 0,
                'download_count': article.download_count or 0,
                'word_count': article.word_count or 0,
                'is_public': article.is_public,
                'created_at': article.created_at.isoformat() if article.created_at else None
            })
        
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Admin export stats error: {e}")
        return jsonify({'error': 'Failed to export statistics'}), 500

# Error handlers for admin blueprint
@admin_bp.errorhandler(404)
def admin_not_found(error):
    return render_template('admin/404.html'), 404

@admin_bp.errorhandler(500)
def admin_internal_error(error):
    db.session.rollback()
    return render_template('admin/500.html'), 500
