"""
Authentication module for Way-CMS multi-tenant system.
Handles magic links, password auth, and decorators.
"""

import os
from functools import wraps
from flask import session, redirect, url_for, jsonify, request
from .models import User, MagicLink, Project


def get_current_user() -> User | None:
    """Get the currently logged in user from session."""
    user_id = session.get('user_id')
    if not user_id:
        return None
    return User.get_by_id(user_id)


def get_current_project() -> Project | None:
    """Get the currently selected project from session."""
    project_id = session.get('current_project_id')
    if not project_id:
        return None
    return Project.get_by_id(project_id)


def login_user(user: User) -> None:
    """Log in a user by setting session data."""
    session['user_id'] = user.id
    session['user_email'] = user.email
    session['is_admin'] = user.is_admin
    session.permanent = True
    user.update_last_login()
    
    # Set default project if user has projects
    projects = user.get_projects()
    if projects and not session.get('current_project_id'):
        session['current_project_id'] = projects[0].id
        session['current_project_slug'] = projects[0].slug


def logout_user() -> None:
    """Log out the current user."""
    session.clear()


def set_current_project(project: Project) -> None:
    """Set the current project in session."""
    session['current_project_id'] = project.id
    session['current_project_slug'] = project.slug


def login_required(f):
    """Decorator to require login for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            if request.is_json or request.headers.get('Accept') == 'application/json':
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin privileges for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            if request.is_json or request.headers.get('Accept') == 'application/json':
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login'))
        if not user.is_admin:
            if request.is_json or request.headers.get('Accept') == 'application/json':
                return jsonify({'error': 'Admin privileges required'}), 403
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


def project_access_required(f):
    """Decorator to require access to the current project."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            if request.is_json or request.headers.get('Accept') == 'application/json':
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login'))
        
        project = get_current_project()
        if not project:
            if request.is_json or request.headers.get('Accept') == 'application/json':
                return jsonify({'error': 'No project selected'}), 400
            return redirect(url_for('index'))
        
        if not user.has_access_to_project(project.id):
            if request.is_json or request.headers.get('Accept') == 'application/json':
                return jsonify({'error': 'Access denied to this project'}), 403
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function


def create_magic_link(user: User) -> MagicLink:
    """Create a magic link for a user."""
    return MagicLink.create(user.id)


def verify_magic_link(token: str) -> tuple[bool, User | None, str]:
    """
    Verify a magic link token.
    Returns: (success, user, error_message)
    """
    magic_link = MagicLink.get_by_token(token)
    
    if not magic_link:
        return False, None, 'Invalid or expired link'
    
    if not magic_link.is_valid():
        return False, None, 'This link has expired or already been used'
    
    user = magic_link.get_user()
    if not user:
        return False, None, 'User not found'
    
    # Mark the link as used
    magic_link.mark_used()
    
    return True, user, ''


def get_magic_link_url(token: str) -> str:
    """Get the full URL for a magic link."""
    app_url = os.environ.get('APP_URL', 'http://localhost:5000')
    return f"{app_url}/auth/verify/{token}"


def authenticate_with_password(email: str, password: str) -> tuple[bool, User | None, str]:
    """
    Authenticate a user with email and password.
    Returns: (success, user, error_message)
    """
    user = User.get_by_email(email)
    
    if not user:
        return False, None, 'Invalid email or password'
    
    if not user.has_password():
        return False, None, 'No password set. Please use magic link to login.'
    
    if not user.check_password(password):
        return False, None, 'Invalid email or password'
    
    return True, user, ''


def get_projects_base_dir() -> str:
    """Get the base directory for all projects."""
    return os.environ.get('PROJECTS_BASE_DIR', '/var/www/projects')


def get_project_path(project: Project) -> str:
    """Get the full filesystem path for a project."""
    base_dir = get_projects_base_dir()
    return os.path.join(base_dir, project.slug)


def ensure_project_dir(project: Project) -> str:
    """Ensure project directory exists and return its path."""
    from pathlib import Path
    project_path = get_project_path(project)
    Path(project_path).mkdir(parents=True, exist_ok=True)
    return project_path

