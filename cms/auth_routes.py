"""
Authentication routes for Way-CMS multi-tenant system.
"""

import os
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session
from .auth import (
    get_current_user, login_user, logout_user, 
    verify_magic_link, authenticate_with_password,
    get_magic_link_url, create_magic_link, login_required,
    set_current_project
)
from .models import User, MagicLink, Project
from .email_service import get_email_service, EmailConfig

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/magic-link', methods=['POST'])
def request_magic_link():
    """Request a magic link to be sent to email."""
    data = request.json if request.is_json else request.form
    email = data.get('email', '').strip().lower()
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    user = User.get_by_email(email)
    if not user:
        # Don't reveal if user exists or not for security
        return jsonify({'success': True, 'message': 'If your email is registered, you will receive a login link.'})
    
    if not EmailConfig.is_configured():
        return jsonify({'error': 'Email service is not configured. Please contact administrator.'}), 500
    
    # Create magic link
    magic_link = create_magic_link(user)
    magic_link_url = get_magic_link_url(magic_link.token)
    
    # Send email
    email_service = get_email_service()
    success, error = email_service.send_magic_link(
        to_email=user.email,
        magic_link_url=magic_link_url,
        user_name=user.name
    )
    
    if not success:
        return jsonify({'error': f'Failed to send email: {error}'}), 500
    
    return jsonify({'success': True, 'message': 'Login link sent to your email.'})


@auth_bp.route('/verify/<token>')
def verify_token(token):
    """Verify magic link token and log in user."""
    success, user, error = verify_magic_link(token)
    
    if not success:
        return render_template('login.html', error=error)
    
    # Log in the user
    login_user(user)
    
    # Redirect to index
    return redirect(url_for('index'))


@auth_bp.route('/login', methods=['POST'])
def login_with_password():
    """Log in with email and password."""
    data = request.json if request.is_json else request.form
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    if not email or not password:
        if request.is_json:
            return jsonify({'error': 'Email and password are required'}), 400
        return render_template('login.html', error='Email and password are required')
    
    success, user, error = authenticate_with_password(email, password)
    
    if not success:
        if request.is_json:
            return jsonify({'error': error}), 401
        return render_template('login.html', error=error)
    
    # Log in the user
    login_user(user)
    
    if request.is_json:
        return jsonify({'success': True, 'user': user.to_dict()})
    
    return redirect(url_for('index'))


@auth_bp.route('/set-password', methods=['POST'])
@login_required
def set_password():
    """Set or change password for current user."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.json
    new_password = data.get('password', '')
    current_password = data.get('current_password', '')
    
    if not new_password:
        return jsonify({'error': 'New password is required'}), 400
    
    if len(new_password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    
    # If user already has a password, require current password
    if user.has_password():
        if not current_password:
            return jsonify({'error': 'Current password is required'}), 400
        if not user.check_password(current_password):
            return jsonify({'error': 'Current password is incorrect'}), 401
    
    # Set new password
    user.set_password(new_password)
    
    return jsonify({'success': True, 'message': 'Password updated successfully'})


@auth_bp.route('/me', methods=['GET'])
@login_required
def get_current_user_info():
    """Get current user information."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not logged in'}), 401
    
    projects = user.get_projects()
    current_project_id = session.get('current_project_id')
    
    return jsonify({
        'user': user.to_dict(),
        'projects': [p.to_dict() for p in projects],
        'current_project_id': current_project_id
    })


@auth_bp.route('/switch-project', methods=['POST'])
@login_required
def switch_project():
    """Switch to a different project."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.json
    project_id = data.get('project_id')
    
    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400
    
    project = Project.get_by_id(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    # Check access
    if not user.has_access_to_project(project_id):
        return jsonify({'error': 'Access denied to this project'}), 403
    
    # Switch project
    set_current_project(project)
    
    return jsonify({
        'success': True,
        'project': project.to_dict()
    })


@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """Log out current user."""
    logout_user()
    return redirect(url_for('login'))


@auth_bp.route('/check-email', methods=['POST'])
def check_email():
    """Check if email exists and has password set."""
    data = request.json
    email = data.get('email', '').strip().lower()
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    user = User.get_by_email(email)
    
    # Don't reveal if user exists for security, but provide hints for UX
    if user:
        return jsonify({
            'exists': True,
            'has_password': user.has_password()
        })
    else:
        return jsonify({
            'exists': False,
            'has_password': False
        })

