"""
Admin routes for Way-CMS multi-tenant system.
"""

import os
from flask import Blueprint, request, jsonify, render_template, session
from .auth import admin_required, get_current_user, login_required
from .models import User, Project, UserProject, MagicLink
from .email_service import get_email_service, EmailConfig
from .database import get_db_stats

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('')
@admin_required
def admin_panel():
    """Admin panel page."""
    user = get_current_user()
    return render_template('admin.html', user=user)


# ============== User Management ==============

@admin_bp.route('/users', methods=['GET'])
@admin_required
def list_users():
    """List all users."""
    users = User.get_all()
    return jsonify({
        'users': [u.to_dict() for u in users]
    })


@admin_bp.route('/users', methods=['POST'])
@admin_required
def create_user():
    """Create a new user."""
    data = request.json
    
    email = data.get('email', '').strip().lower()
    name = data.get('name', '').strip()
    is_admin = data.get('is_admin', False)
    project_ids = data.get('project_ids', [])
    send_welcome_email = data.get('send_welcome_email', True)
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    # Check if user already exists
    existing = User.get_by_email(email)
    if existing:
        return jsonify({'error': 'User with this email already exists'}), 400
    
    # Create user
    user = User.create(email=email, name=name, is_admin=is_admin)
    
    # Assign projects
    for project_id in project_ids:
        project = Project.get_by_id(project_id)
        if project:
            project.assign_user(user.id)
    
    # Send welcome email with magic link
    if send_welcome_email and EmailConfig.is_configured():
        magic_link = MagicLink.create(user.id)
        from .auth import get_magic_link_url
        magic_link_url = get_magic_link_url(magic_link.token)
        
        # Get project names for email
        project_names = [Project.get_by_id(pid).name for pid in project_ids if Project.get_by_id(pid)]
        
        email_service = get_email_service()
        success, error = email_service.send_welcome_email(
            to_email=email,
            magic_link_url=magic_link_url,
            user_name=name,
            project_names=project_names
        )
        
        if not success:
            return jsonify({
                'user': user.to_dict(),
                'warning': f'User created but email failed: {error}'
            })
    
    return jsonify({'user': user.to_dict()})


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    """Update a user."""
    user = User.get_by_id(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.json
    
    if 'name' in data:
        user.update(name=data['name'])
    if 'is_admin' in data:
        user.update(is_admin=data['is_admin'])
    
    return jsonify({'user': user.to_dict()})


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Delete a user."""
    user = User.get_by_id(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Prevent deleting self
    current_user = get_current_user()
    if current_user and current_user.id == user_id:
        return jsonify({'error': 'Cannot delete yourself'}), 400
    
    user.delete()
    return jsonify({'success': True})


@admin_bp.route('/users/<int:user_id>/send-link', methods=['POST'])
@admin_required
def send_magic_link_to_user(user_id):
    """Send a magic link email to a user."""
    user = User.get_by_id(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if not EmailConfig.is_configured():
        return jsonify({'error': 'Email is not configured'}), 400
    
    magic_link = MagicLink.create(user.id)
    from .auth import get_magic_link_url
    magic_link_url = get_magic_link_url(magic_link.token)
    
    email_service = get_email_service()
    success, error = email_service.send_magic_link(
        to_email=user.email,
        magic_link_url=magic_link_url,
        user_name=user.name
    )
    
    if not success:
        return jsonify({'error': error}), 500
    
    return jsonify({'success': True, 'message': f'Magic link sent to {user.email}'})


# ============== Project Management ==============

@admin_bp.route('/projects', methods=['GET'])
@admin_required
def list_projects():
    """List all projects."""
    projects = Project.get_all()
    return jsonify({
        'projects': [p.to_dict() for p in projects]
    })


@admin_bp.route('/projects', methods=['POST'])
@admin_required
def create_project():
    """Create a new project."""
    data = request.json
    
    name = data.get('name', '').strip()
    slug = data.get('slug', '').strip().lower()
    website_url = data.get('website_url', '').strip()
    
    if not name:
        return jsonify({'error': 'Project name is required'}), 400
    if not slug:
        return jsonify({'error': 'Project slug is required'}), 400
    
    # Validate slug format
    import re
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$', slug):
        return jsonify({'error': 'Slug must contain only lowercase letters, numbers, and hyphens'}), 400
    
    # Check if slug already exists
    existing = Project.get_by_slug(slug)
    if existing:
        return jsonify({'error': 'Project with this slug already exists'}), 400
    
    # Create project
    project = Project.create(name=name, slug=slug, website_url=website_url or None)
    
    # Create project directory
    from .auth import ensure_project_dir
    ensure_project_dir(project)
    
    return jsonify({'project': project.to_dict()})


@admin_bp.route('/projects/<int:project_id>', methods=['PUT'])
@admin_required
def update_project(project_id):
    """Update a project."""
    project = Project.get_by_id(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    data = request.json
    
    if 'name' in data:
        project.update(name=data['name'])
    if 'website_url' in data:
        project.update(website_url=data['website_url'])
    
    return jsonify({'project': project.to_dict()})


@admin_bp.route('/projects/<int:project_id>', methods=['DELETE'])
@admin_required
def delete_project(project_id):
    """Delete a project."""
    project = Project.get_by_id(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    # Note: This doesn't delete the project folder - that would need manual cleanup
    project.delete()
    return jsonify({'success': True})


# ============== Assignment Management ==============

@admin_bp.route('/assignments', methods=['GET'])
@admin_required
def list_assignments():
    """List all user-project assignments."""
    assignments = UserProject.get_all_assignments()
    return jsonify({'assignments': assignments})


@admin_bp.route('/assignments', methods=['POST'])
@admin_required
def assign_user_to_project():
    """Assign a user to a project."""
    data = request.json
    
    user_id = data.get('user_id')
    project_id = data.get('project_id')
    
    if not user_id or not project_id:
        return jsonify({'error': 'user_id and project_id are required'}), 400
    
    user = User.get_by_id(user_id)
    project = Project.get_by_id(project_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    success = UserProject.assign(user_id, project_id)
    if not success:
        return jsonify({'error': 'Assignment already exists'}), 400
    
    return jsonify({'success': True})


@admin_bp.route('/assignments', methods=['DELETE'])
@admin_required
def unassign_user_from_project():
    """Remove a user from a project."""
    user_id = request.args.get('user_id', type=int)
    project_id = request.args.get('project_id', type=int)
    
    if not user_id or not project_id:
        return jsonify({'error': 'user_id and project_id are required'}), 400
    
    success = UserProject.unassign(user_id, project_id)
    if not success:
        return jsonify({'error': 'Assignment not found'}), 404
    
    return jsonify({'success': True})


# ============== Email Settings ==============

@admin_bp.route('/email/test', methods=['POST'])
@admin_required
def test_email():
    """Test email configuration."""
    email_service = get_email_service()
    success, message = email_service.test_connection()
    
    return jsonify({
        'success': success,
        'message': message,
        'configured': EmailConfig.is_configured()
    })


@admin_bp.route('/email/config', methods=['GET'])
@admin_required
def get_email_config():
    """Get email configuration (masked)."""
    config = EmailConfig.get_config()
    return jsonify({
        'configured': EmailConfig.is_configured(),
        'host': config['host'],
        'port': config['port'],
        'user': config['user'][:3] + '***' if config['user'] else '',
        'from_email': config['from_email'],
        'from_name': config['from_name']
    })


# ============== Stats ==============

@admin_bp.route('/stats', methods=['GET'])
@admin_required
def get_stats():
    """Get system statistics."""
    stats = get_db_stats()
    return jsonify(stats)

