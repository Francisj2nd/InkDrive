from flask import Blueprint, render_template
from flask_login import login_required, current_user

studio_bp = Blueprint('studio', __name__, subdomain='studio')

@studio_bp.route('/article')
@login_required
def article_studio():
    """The new Article Studio page"""
    return render_template('article_studio.html', user=current_user, page_type='studio', studio_type='article')

@studio_bp.route('/social')
@login_required
def social_studio():
    """The new Social & Comms Studio page"""
    return render_template('social_studio.html', user=current_user, page_type='studio', studio_type='social')

@studio_bp.route('/editing')
@login_required
def editing_studio():
    """The new Editing & Refinement Studio page"""
    return render_template('editing_studio.html', user=current_user, page_type='studio', studio_type='editing')

@studio_bp.route('/repurpose')
@login_required
def repurpose_studio():
    """The new Content Repurposing Studio page"""
    return render_template('repurposing_studio.html', user=current_user, page_type='studio', studio_type='repurpose')

@studio_bp.route('/seo')
@login_required
def seo_studio():
    """The new SEO Strategy Studio page"""
    return render_template('seo_studio.html', user=current_user, page_type='studio', studio_type='seo')

@studio_bp.route('/brainstorming')
@login_required
def brainstorming_studio():
    """The new Brainstorming Studio page"""
    return render_template('brainstorming_studio.html', user=current_user, page_type='studio', studio_type='brainstorming')

@studio_bp.route('/scriptwriting')
@login_required
def scriptwriting_studio():
    """The new Scriptwriting Studio page"""
    return render_template('scriptwriting_studio.html', user=current_user, page_type='studio', studio_type='scriptwriting')

@studio_bp.route('/ecommerce')
@login_required
def ecommerce_studio():
    """The new E-commerce Studio page"""
    return render_template('ecommerce_studio.html', user=current_user, page_type='studio', studio_type='ecommerce')

@studio_bp.route('/webcopy')
@login_required
def webcopy_studio():
    """The new Web Copy Studio page"""
    return render_template('webcopy_studio.html', user=current_user, page_type='studio', studio_type='webcopy')

@studio_bp.route('/business')
@login_required
def business_studio():
    """The new Business Docs Studio page"""
    return render_template('business_studio.html', user=current_user, page_type='studio', studio_type='business')
