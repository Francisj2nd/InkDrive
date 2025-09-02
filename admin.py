import os
import logging
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import func
from models import db, User, GeneratedContent, ChatSession

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
        total_content_items = GeneratedContent.query.count()
        published_content = GeneratedContent.query.filter_by(is_public=True).count()
        total_chat_sessions = ChatSession.query.count()
        
        # Get recent activity
        recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
        recent_content = GeneratedContent.query.order_by(GeneratedContent.created_at.desc()).limit(10).all()
        
        # Get usage statistics
        total_words = db.session.query(func.sum(GeneratedContent.word_count)).scalar() or 0
        total_downloads = db.session.query(func.sum(GeneratedContent.download_count)).scalar() or 0
        total_views = db.session.query(func.sum(GeneratedContent.view_count)).scalar() or 0
        
        # Get monthly statistics
        current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_users = User.query.filter(User.created_at >= current_month_start).count()
        monthly_content = GeneratedContent.query.filter(GeneratedContent.created_at >= current_month_start).count()
        
        stats = {
            'total_users': total_users,
            'active_users': active_users,
            'total_content_items': total_content_items,
            'published_content': published_content,
            'total_chat_sessions': total_chat_sessions,
            'total_words': total_words,
            'total_downloads': total_downloads,
            'total_views': total_views,
            'monthly_users': monthly_users,
            'monthly_content': monthly_content
        }
        
        return render_template('admin/dashboard.html', 
                             stats=stats, 
                             recent_users=recent_users, 
                             recent_content=recent_content)
    except Exception as e:
        logger.error(f"Admin dashboard error: {e}")
        flash('Error loading dashboard data.', 'error')
        return render_template('admin/dashboard.html', stats={}, recent_users=[], recent_content=[])

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
        
        # Get user's content
        content_items = GeneratedContent.query.filter_by(user_id=user_id).order_by(GeneratedContent.created_at.desc()).limit(20).all()
        
        # Get user's chat sessions
        chat_sessions = ChatSession.query.filter_by(user_id=user_id).order_by(ChatSession.created_at.desc()).limit(10).all()
        
        # Calculate user statistics
        total_words = db.session.query(func.sum(GeneratedContent.word_count)).filter_by(user_id=user_id).scalar() or 0
        total_downloads = db.session.query(func.sum(GeneratedContent.download_count)).filter_by(user_id=user_id).scalar() or 0
        total_views = db.session.query(func.sum(GeneratedContent.view_count)).filter_by(user_id=user_id).scalar() or 0
        
        user_stats = {
            'total_content_items': len(content_items),
            'total_words': total_words,
            'total_downloads': total_downloads,
            'total_views': total_views,
            'words_this_month': user.words_generated_this_month or 0,
            'downloads_this_month': user.downloads_this_month or 0
        }
        
        return render_template('admin/user_detail.html', 
                             user=user, 
                             content_items=content_items,
                             chat_sessions=chat_sessions,
                             user_stats=user_stats)
    except Exception as e:
        logger.error(f"Admin user detail error: {e}")
        flash('Error loading user details.', 'error')
        return redirect(url_for('admin.users'))

@admin_bp.route('/content')
@login_required
@superadmin_required
def content():
    """Content management page"""
    try:
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '').strip()
        filter_type = request.args.get('filter', 'all')
        
        query = GeneratedContent.query
        
        if search:
            query = query.filter(
                db.or_(
                    GeneratedContent.title.ilike(f'%{search}%'),
                    GeneratedContent.topic.ilike(f'%{search}%')
                )
            )
        
        if filter_type == 'published':
            query = query.filter_by(is_public=True)
        elif filter_type == 'unpublished':
            query = query.filter_by(is_public=False)
        
        content_items = query.order_by(GeneratedContent.created_at.desc()).paginate(
            page=page, per_page=50, error_out=False
        )
        
        return render_template('admin/content.html',
                             content_items=content_items,
                             search=search, 
                             filter_type=filter_type)
    except Exception as e:
        logger.error(f"Admin content page error: {e}")
        flash('Error loading content.', 'error')
        return redirect(url_for('admin.dashboard'))

# Studio Type Mapping
STUDIO_TYPE_MAPPING = {
    'article': ['ARTICLE'],
    'social': ['SOCIAL_POST', 'EMAIL', 'AD_COPY'],
    'editing': ['TEXT_REFINEMENT', 'SUMMARY', 'TRANSLATION'],
    'repurpose': ['REPURPOSE_TWEET', 'REPURPOSE_SLIDES'],
    'seo': ['SEO_KEYWORDS', 'SEO_HEADLINES'],
    'business': ['PRESS_RELEASE', 'JOB_DESCRIPTION'],
    'brainstorming': ['IDEAS'],
    'scriptwriting': ['SCRIPT'],
    'ecommerce': ['ECOMMERCE'],
    'webcopy': ['WEBCOPY'],
}

@admin_bp.route('/studios')
@login_required
@superadmin_required
def studios():
    """Studio management page"""
    try:
        studio_stats = []
        for studio_name, studio_types in STUDIO_TYPE_MAPPING.items():
            query = ChatSession.query.filter(ChatSession.studio_type.in_(studio_types))

            total_sessions = query.count()
            total_users = query.with_entities(ChatSession.user_id).distinct().count()

            # For articles, we can get a more accurate count from the GeneratedContent table
            if studio_name == 'article':
                total_content_items = GeneratedContent.query.filter(GeneratedContent.chat_session.has(ChatSession.studio_type.in_(studio_types))).count()
            else:
                # For other studios, we can count chat sessions that resulted in an article
                total_content_items = query.filter(ChatSession.content_items.any()).count()

            studio_stats.append({
                'name': studio_name.replace('_', ' ').title(),
                'key': studio_name,
                'total_sessions': total_sessions,
                'total_users': total_users,
                'total_content_items': total_content_items,
            })

        return render_template('admin/studios.html', studio_stats=studio_stats)
    except Exception as e:
        logger.error(f"Admin studios page error: {e}")
        flash('Error loading studios.', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/studios/<string:studio_name>')
@login_required
@superadmin_required
def studio_detail(studio_name):
    """Studio detail page with content and user analysis."""
    if studio_name not in STUDIO_TYPE_MAPPING:
        abort(404)

    try:
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '').strip()

        studio_types = STUDIO_TYPE_MAPPING[studio_name]

        # Base query for all chat sessions in this studio
        base_query = ChatSession.query.filter(ChatSession.studio_type.in_(studio_types))

        # --- Overall Stats ---
        total_sessions = base_query.count()
        total_users = base_query.with_entities(ChatSession.user_id).distinct().count()

        # Query for content linked to these chat sessions
        content_query = GeneratedContent.query.join(ChatSession).filter(ChatSession.studio_type.in_(studio_types))
        total_content_items = content_query.count()
        total_words = db.session.query(func.sum(GeneratedContent.word_count)).join(ChatSession).filter(ChatSession.studio_type.in_(studio_types)).scalar() or 0

        studio_stats = {
            'name': studio_name.replace('_', ' ').title(),
            'key': studio_name,
            'total_sessions': total_sessions,
            'total_users': total_users,
            'total_content_items': total_content_items,
            'total_words': total_words
        }

        # --- Content Tab Query ---
        content_query = base_query
        if search:
            # Search across chat session title, content title, or user name/email
            content_query = content_query.join(User).outerjoin(GeneratedContent, ChatSession.content_items).filter(
                db.or_(
                    ChatSession.title.ilike(f'%{search}%'),
                    GeneratedContent.title.ilike(f'%{search}%'),
                    User.name.ilike(f'%{search}%'),
                    User.email.ilike(f'%{search}%')
                )
            )

        # Paginate the content (chat sessions)
        paginated_content = content_query.order_by(ChatSession.created_at.desc()).paginate(
            page=page, per_page=20, error_out=False
        )

        # --- Users Tab Query ---
        # Get top users by number of sessions in this studio
        top_users_query = db.session.query(
            User,
            func.count(ChatSession.id).label('session_count')
        ).join(ChatSession).filter(
            ChatSession.studio_type.in_(studio_types)
        ).group_by(
            User.id
        ).order_by(
            func.count(ChatSession.id).desc()
        ).limit(50).all()

        return render_template('admin/studio_detail.html',
                             studio=studio_stats,
                             content=paginated_content,
                             users=top_users_query,
                             search=search)
    except Exception as e:
        logger.error(f"Admin studio detail page error for '{studio_name}': {e}")
        flash(f"Error loading details for {studio_name} studio.", 'error')
        return redirect(url_for('admin.studios'))


@admin_bp.route('/content/<int:content_id>')
@login_required
@superadmin_required
def content_detail(content_id):
    """Content detail page"""
    try:
        content = GeneratedContent.query.get_or_404(content_id)
        return render_template('admin/content_detail.html', content=content)
    except Exception as e:
        logger.error(f"Admin content detail error: {e}")
        flash('Error loading content details.', 'error')
        return redirect(url_for('admin.content'))

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
        
        # Delete all user's content
        GeneratedContent.query.filter_by(user_id=user_id).delete()
        
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

@admin_bp.route('/api/content/<int:content_id>/delete', methods=['POST'])
@login_required
@superadmin_required
def delete_content(content_id):
    """Delete a content item"""
    try:
        content = GeneratedContent.query.get_or_404(content_id)
        
        content_title = content.title
        author_name = content.author.name
        
        # Delete associated chat session if it exists and no other content items reference it
        if content.chat_session_id:
            other_content = GeneratedContent.query.filter(
                GeneratedContent.chat_session_id == content.chat_session_id,
                GeneratedContent.id != content_id
            ).count()
            
            if other_content == 0:
                chat_session = ChatSession.query.get(content.chat_session_id)
                if chat_session:
                    db.session.delete(chat_session)
        
        db.session.delete(content)
        db.session.commit()
        
        logger.info(f"Admin {current_user.email} deleted content '{content_title}' by {author_name}")
        
        return jsonify({
            'success': True,
            'message': f'Content "{content_title}" by {author_name} deleted successfully.'
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Admin delete content error: {e}")
        return jsonify({'error': 'Failed to delete content'}), 500

@admin_bp.route('/api/content/<int:content_id>/toggle-public', methods=['POST'])
@login_required
@superadmin_required
def toggle_content_public(content_id):
    """Toggle content public status"""
    try:
        content = GeneratedContent.query.get_or_404(content_id)
        
        if content.is_public:
            content.unpublish()
            status = 'unpublished'
        else:
            content.publish()
            status = 'published'
        
        logger.info(f"Admin {current_user.email} {status} content '{content.title}' by {content.author.name}")
        
        return jsonify({
            'success': True,
            'message': f'Content "{content.title}" has been {status}.',
            'is_public': content.is_public
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Admin toggle content public error: {e}")
        return jsonify({'error': 'Failed to update content status'}), 500

@admin_bp.route('/api/sessions/<int:session_id>/delete', methods=['POST'])
@login_required
@superadmin_required
def delete_session(session_id):
    """Delete a chat session and all associated content."""
    try:
        session = ChatSession.query.get_or_404(session_id)
        session_title = session.title
        author_name = session.user.name

        # Delete all content associated with this chat session
        GeneratedContent.query.filter_by(chat_session_id=session.id).delete()

        # Delete the chat session
        db.session.delete(session)
        db.session.commit()

        logger.info(f"Admin {current_user.email} deleted session '{session_title}' by {author_name}")

        return jsonify({
            'success': True,
            'message': f'Session "{session_title}" and its content have been deleted.'
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Admin delete session error: {e}")
        return jsonify({'error': 'Failed to delete session'}), 500

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
                'total_content_items': GeneratedContent.query.count(),
                'published_content': GeneratedContent.query.filter_by(is_public=True).count(),
                'total_chat_sessions': ChatSession.query.count(),
                'total_words': db.session.query(func.sum(GeneratedContent.word_count)).scalar() or 0,
                'total_downloads': db.session.query(func.sum(GeneratedContent.download_count)).scalar() or 0,
                'total_views': db.session.query(func.sum(GeneratedContent.view_count)).scalar() or 0
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
            
            monthly_content = GeneratedContent.query.filter(
                GeneratedContent.created_at >= month_start,
                GeneratedContent.created_at < month_end
            ).count()
            
            stats['monthly_stats'][month_start.strftime('%Y-%m')] = {
                'new_users': monthly_users,
                'new_content': monthly_content
            }
        
        # Get top users by activity
        top_users = db.session.query(
            User.id, User.name, User.email,
            func.count(GeneratedContent.id).label('content_count'),
            func.sum(GeneratedContent.word_count).label('total_words')
        ).join(GeneratedContent).group_by(User.id).order_by(func.count(GeneratedContent.id).desc()).limit(20).all()
        
        for user_data in top_users:
            stats['user_activity'].append({
                'user_id': user_data.id,
                'name': user_data.name,
                'email': user_data.email,
                'content_count': user_data.content_count,
                'total_words': user_data.total_words or 0
            })
        
        # Get content statistics
        top_content = GeneratedContent.query.order_by(GeneratedContent.view_count.desc()).limit(10).all()
        for content in top_content:
            stats['content_stats'].append({
                'title': content.title,
                'author': content.author.name,
                'view_count': content.view_count or 0,
                'download_count': content.download_count or 0,
                'word_count': content.word_count or 0,
                'is_public': content.is_public,
                'created_at': content.created_at.isoformat() if content.created_at else None
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
