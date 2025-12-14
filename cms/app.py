#!/usr/bin/env python3
"""
Website CMS - A simple web-based editor for HTML/CSS files
Designed for editing files downloaded from Wayback Archive.
Supports both single-tenant and multi-tenant modes.
"""

import os
import json
import re
import shutil
import hashlib
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory, abort, redirect, url_for, session, send_file, g
from werkzeug.utils import secure_filename
from functools import wraps
import mimetypes
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ============== Multi-Tenant Configuration ==============
MULTI_TENANT = os.environ.get('MULTI_TENANT', 'false').lower() == 'true'
DATA_DIR = os.environ.get('DATA_DIR', '/.way-cms-data')
PROJECTS_BASE_DIR = os.environ.get('PROJECTS_BASE_DIR', '/var/www/projects')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', '')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')

# ============== Single-Tenant Configuration (Legacy) ==============
CMS_BASE_DIR = os.environ.get('CMS_BASE_DIR', '/var/www/html')
CMS_USERNAME = os.environ.get('CMS_USERNAME', 'admin')
CMS_PASSWORD_HASH = os.environ.get('CMS_PASSWORD_HASH', '')  # bcrypt hash
CMS_PASSWORD = os.environ.get('CMS_PASSWORD', '')  # Plain password (legacy, will hash it)

# ============== Common Configuration ==============
BACKUP_DIR = os.environ.get('BACKUP_DIR', '/.way-cms-backups')  # Fixed path for docker mount
ALLOWED_EXTENSIONS = {'html', 'htm', 'css', 'js', 'txt', 'xml', 'json', 'md', 'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'zip', 'ico', 'woff', 'woff2', 'ttf', 'eot'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB max file size
READ_ONLY_MODE = os.environ.get('READ_ONLY_MODE', 'false').lower() == 'true'
SESSION_TIMEOUT_MINUTES = int(os.environ.get('SESSION_TIMEOUT_MINUTES', '1440'))  # Default 24 hours
WEBSITE_URL = os.environ.get('WEBSITE_URL', '')  # URL of the live website
WEBSITE_NAME = os.environ.get('WEBSITE_NAME', '')  # Name of the website (for breadcrumb)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-me-in-production-' + os.urandom(32).hex())
# Configure sessions with configurable timeout
app.config['PERMANENT_SESSION_LIFETIME'] = SESSION_TIMEOUT_MINUTES * 60  # Convert minutes to seconds
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Rate limiting - initialize after app is created
try:
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["1000 per hour", "100 per minute"],
        storage_uri="memory://"
    )
except Exception:
    limiter = None

# Ensure directories exist - gracefully handle permission errors
try:
    Path(CMS_BASE_DIR).mkdir(parents=True, exist_ok=True)
except (PermissionError, OSError):
    # Fallback for CI/testing environments
    import tempfile
    CMS_BASE_DIR = tempfile.mkdtemp(prefix='way-cms-')
    Path(CMS_BASE_DIR).mkdir(parents=True, exist_ok=True)

try:
    Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
except (PermissionError, OSError):
    # Fallback for CI/testing environments - use temp directory
    import tempfile
    BACKUP_DIR = tempfile.mkdtemp(prefix='way-cms-backups-')
    Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)

# Initialize password hash if plain password provided (single-tenant mode)
if not MULTI_TENANT and CMS_PASSWORD and not CMS_PASSWORD_HASH:
    try:
        import bcrypt
        CMS_PASSWORD_HASH = bcrypt.hashpw(CMS_PASSWORD.encode(), bcrypt.gensalt()).decode()
    except ImportError:
        # Fallback to simple hash if bcrypt not available
        CMS_PASSWORD_HASH = hashlib.sha256(CMS_PASSWORD.encode()).hexdigest()

# ============== Multi-Tenant Initialization ==============
if MULTI_TENANT:
    try:
        from database import init_db, create_admin_user, migrate_from_single_tenant, check_db_exists
        from admin_routes import admin_bp
        from auth_routes import auth_bp
        import auth as mt_auth
        from models import Project, User
        
        # Check if this is first run (migration scenario)
        first_run = not check_db_exists()
        
        # Initialize database
        init_db()
        
        # Create admin user if configured
        admin_user = None
        if ADMIN_EMAIL and ADMIN_PASSWORD:
            admin_user = create_admin_user(ADMIN_EMAIL, ADMIN_PASSWORD)
        
        # Register blueprints
        app.register_blueprint(admin_bp)
        app.register_blueprint(auth_bp)
        
        # Create projects base directory
        try:
            Path(PROJECTS_BASE_DIR).mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError):
            import tempfile
            PROJECTS_BASE_DIR = tempfile.mkdtemp(prefix='way-cms-projects-')
        
        # Migration: If CMS_BASE_DIR has content, create a project for it
        if first_run and CMS_BASE_DIR and os.path.exists(CMS_BASE_DIR):
            # Check if there's actual content (not empty)
            has_content = any(os.scandir(CMS_BASE_DIR))
            if has_content:
                # Generate project name and slug from existing settings or folder name
                project_name = WEBSITE_NAME or os.path.basename(CMS_BASE_DIR.rstrip('/')) or 'Migrated Website'
                project_slug = project_name.lower().replace(' ', '-').replace('_', '-')
                # Clean slug
                project_slug = re.sub(r'[^a-z0-9-]', '', project_slug)
                if not project_slug:
                    project_slug = 'migrated-website'
                
                # Check if project already exists
                existing_project = Project.get_by_slug(project_slug)
                if not existing_project:
                    # Create symlink or copy content to new location
                    new_project_path = os.path.join(PROJECTS_BASE_DIR, project_slug)
                    if not os.path.exists(new_project_path):
                        try:
                            # Try to create a symlink first (preserves disk space)
                            os.symlink(CMS_BASE_DIR, new_project_path)
                            print(f"[Migration] Created symlink from {CMS_BASE_DIR} to {new_project_path}")
                        except (OSError, NotImplementedError):
                            # Fallback: copy the directory
                            shutil.copytree(CMS_BASE_DIR, new_project_path)
                            print(f"[Migration] Copied {CMS_BASE_DIR} to {new_project_path}")
                    
                    # Create the project in the database
                    project = Project.create(
                        name=project_name,
                        slug=project_slug,
                        website_url=WEBSITE_URL or None
                    )
                    print(f"[Migration] Created project '{project_name}' (slug: {project_slug})")
                    
                    # Assign admin user to this project (admins have access to all, but good for visibility)
                    if admin_user:
                        project.assign_user(admin_user.id)
                        print(f"[Migration] Assigned admin user to project")
        
        print(f"[Way-CMS] Multi-tenant mode enabled. Projects dir: {PROJECTS_BASE_DIR}")
    except ImportError as e:
        print(f"[Way-CMS] Warning: Could not initialize multi-tenant mode: {e}")
        MULTI_TENANT = False


def get_current_base_dir():
    """Get the current base directory for file operations.
    In multi-tenant mode, returns the current project's directory.
    In single-tenant mode, returns CMS_BASE_DIR.
    """
    if MULTI_TENANT:
        project_slug = session.get('current_project_slug')
        if project_slug:
            return os.path.join(PROJECTS_BASE_DIR, project_slug)
    return CMS_BASE_DIR


def get_current_backup_dir():
    """Get the backup directory for the current project/site."""
    if MULTI_TENANT:
        project_slug = session.get('current_project_slug')
        if project_slug:
            return os.path.join(BACKUP_DIR, project_slug)
    return BACKUP_DIR


def verify_password(password, password_hash):
    """Verify password against hash."""
    try:
        import bcrypt
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except (ImportError, ValueError):
        # Fallback for simple hash
        return hashlib.sha256(password.encode()).hexdigest() == password_hash


def allowed_file(filename):
    """Check if file extension is allowed."""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def login_required(f):
    """Decorator to require login.
    Works in both single-tenant and multi-tenant modes.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if MULTI_TENANT:
            # Multi-tenant: check for user_id in session
            if not session.get('user_id'):
                if request.is_json or request.headers.get('Accept') == 'application/json':
                    return jsonify({'error': 'Authentication required'}), 401
                return redirect(url_for('login'))
            # Also check if a project is selected
            if not session.get('current_project_id'):
                # User logged in but no project selected - redirect to select one
                if request.is_json or request.headers.get('Accept') == 'application/json':
                    return jsonify({'error': 'No project selected'}), 400
                return redirect(url_for('index'))
        else:
            # Single-tenant: check for logged_in flag
            if (CMS_PASSWORD_HASH or CMS_PASSWORD) and not session.get('logged_in'):
                return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def read_only_check(f):
    """Decorator to check if system is in read-only mode."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if READ_ONLY_MODE and request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return jsonify({'error': 'System is in read-only mode'}), 403
        return f(*args, **kwargs)
    return decorated_function


def has_auth_configured():
    """Check if authentication is configured."""
    return bool(CMS_PASSWORD_HASH or CMS_PASSWORD)


def safe_path(file_path):
    """Ensure path is within base directory - security hardened.
    Uses the current project directory in multi-tenant mode.
    """
    base_dir = get_current_base_dir()
    
    if not file_path:
        return os.path.abspath(base_dir)
    
    # Normalize the path - remove any .. or . components
    # Use os.path.normpath but then verify it's still within base
    normalized = os.path.normpath(file_path).replace('\\', '/')
    
    # Remove any leading slashes or dots that could be dangerous
    normalized = normalized.lstrip('/').lstrip('.')
    
    # Join with base directory
    full_path = os.path.join(base_dir, normalized)
    full_path = os.path.abspath(full_path)
    base_path = os.path.abspath(base_dir)
    
    # Critical security check: ensure resolved path is within base
    if not full_path.startswith(base_path + os.sep) and full_path != base_path:
        return None
    
    return full_path


def create_backup(file_path):
    """Create a backup of a file before modification."""
    full_path = safe_path(file_path)
    if not full_path or not os.path.exists(full_path):
        return None
    
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_subdir = os.path.join(BACKUP_DIR, file_path)
        os.makedirs(os.path.dirname(backup_subdir), exist_ok=True)
        
        backup_filename = f"{os.path.basename(file_path)}.{timestamp}"
        backup_path = os.path.join(os.path.dirname(backup_subdir), backup_filename)
        
        shutil.copy2(full_path, backup_path)
        return backup_path
    except Exception as e:
        print(f"Backup failed: {e}")
        return None


@app.route('/')
@login_required
def index():
    """Main page showing file browser."""
    base_dir = get_current_base_dir()
    
    if MULTI_TENANT:
        # Multi-tenant: get info from current project
        from models import Project
        from auth import get_current_user
        
        user = get_current_user()
        if not user:
            return redirect(url_for('login'))
        
        # Get projects - admins see all projects, regular users see assigned projects
        if user.is_admin:
            projects = Project.get_all()
        else:
            projects = user.get_projects()
        
        # Get current project
        project = Project.get_by_id(session.get('current_project_id'))
        
        # If no project selected but user has projects, select the first one
        if not project and projects:
            project = projects[0]
            from auth import set_current_project
            set_current_project(project)
        
        if project:
            folder_name = project.name
            website_url = project.website_url or ''
        else:
            folder_name = 'No Project'
            website_url = ''
        
        return render_template('index.html', 
                             base_dir=base_dir, 
                             folder_name=folder_name, 
                             website_url=website_url,
                             multi_tenant=True,
                             user=user,
                             projects=projects,
                             current_project=project,
                             is_admin=user.is_admin)
    else:
        # Single-tenant: use environment variables
        if WEBSITE_NAME:
            folder_name = WEBSITE_NAME
        else:
            folder_name = os.path.basename(CMS_BASE_DIR.rstrip('/')) or os.path.basename(os.path.dirname(CMS_BASE_DIR)) or 'Website'
        return render_template('index.html', 
                             base_dir=base_dir, 
                             folder_name=folder_name, 
                             website_url=WEBSITE_URL,
                             multi_tenant=False)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page with username and password."""
    if MULTI_TENANT:
        # Multi-tenant: use database authentication
        if session.get('user_id'):
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            
            if not email:
                return render_template('login.html', error='Email is required', multi_tenant=True)
            
            from models import User
            from auth import login_user as mt_login_user
            
            user = User.get_by_email(email)
            if not user:
                return render_template('login.html', error='Invalid email or password', multi_tenant=True)
            
            if password:
                # Password authentication
                if not user.has_password():
                    return render_template('login.html', 
                                         error='No password set. Use magic link to login.',
                                         multi_tenant=True)
                if not user.check_password(password):
                    return render_template('login.html', error='Invalid email or password', multi_tenant=True)
                
                mt_login_user(user)
                return redirect(url_for('index'))
            else:
                # Request magic link
                return render_template('login.html', 
                                     error='Please enter your password or request a magic link',
                                     multi_tenant=True)
        
        return render_template('login.html', multi_tenant=True)
    else:
        # Single-tenant: legacy authentication
        if not has_auth_configured():
            session['logged_in'] = True
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            username = request.form.get('username', '')
            password = request.form.get('password', '')
            
            # Check username
            if username != CMS_USERNAME:
                return render_template('login.html', error='Invalid username or password')
            
            # Check password
            if CMS_PASSWORD_HASH:
                if verify_password(password, CMS_PASSWORD_HASH):
                    session['logged_in'] = True
                    session['username'] = username
                    return redirect(url_for('index'))
            elif password == CMS_PASSWORD:
                session['logged_in'] = True
                session['username'] = username
                session.permanent = True  # Make session permanent (use cookie expiration)
                return redirect(url_for('index'))
            
            return render_template('login.html', error='Invalid username or password')
        
        return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout."""
    if MULTI_TENANT:
        # Use the auth module's logout function for proper cleanup
        from auth import logout_user
        logout_user()
    else:
        session.pop('logged_in', None)
        session.pop('username', None)
    return redirect(url_for('login'))


def resolve_relative_path(base_path, relative_url):
    """Resolve relative URL to absolute path within CMS_BASE_DIR."""
    from urllib.parse import urljoin, urlparse
    import posixpath
    
    # Normalize paths to use forward slashes
    base_path = base_path.replace('\\', '/')
    relative_url = relative_url.replace('\\', '/')
    
    # Get directory of base file
    base_dir = '/'.join(base_path.split('/')[:-1]) if '/' in base_path else ''
    
    # Join relative URL with base directory
    if relative_url.startswith('/'):
        # Absolute path from root
        resolved = relative_url.lstrip('/')
    elif relative_url.startswith('../'):
        # Parent directory navigation
        parts = base_dir.split('/') if base_dir else []
        rel_parts = relative_url.split('/')
        
        for part in rel_parts:
            if part == '..':
                if parts:
                    parts.pop()
            elif part and part != '.':
                parts.append(part)
        
        resolved = '/'.join(parts)
    elif relative_url.startswith('./'):
        # Current directory
        resolved = (base_dir + '/' + relative_url[2:]) if base_dir else relative_url[2:]
    else:
        # Simple relative path
        resolved = (base_dir + '/' + relative_url) if base_dir else relative_url
    
    # Normalize path
    resolved = posixpath.normpath(resolved).replace('\\', '/')
    return resolved


def process_html_for_preview(html_content, file_path):
    """Process HTML content to fix relative paths for preview - comprehensive rewrite."""
    import re
    from urllib.parse import urlparse
    
    # Get the directory of the file for resolving relative paths
    file_dir = '/'.join(file_path.split('/')[:-1]) if '/' in file_path else ''
    
    # Convert all relative and absolute paths to use preview-assets endpoint
    def fix_url_attribute(match):
        """Fix URLs in HTML attributes (href, src, action, etc.)."""
        attr_name = match.group(1)  # href, src, etc.
        quote1 = match.group(2) or ''     # Opening quote (can be empty for unquoted)
        url = match.group(3)        # URL
        quote2 = match.group(4) or ''     # Closing quote (can be empty for unquoted)
        
        # Skip external URLs, data URIs, javascript, anchors, etc.
        if url.startswith(('http://', 'https://', 'data:', 'javascript:', '#', 'mailto:', 'tel:', 'blob:')):
            return match.group(0)
        
        # Skip empty URLs
        if not url or not url.strip():
            return match.group(0)
        
        # Handle protocol-relative URLs (//path) - check if they're actually local files
        if url.startswith('//'):
            test_path = url.lstrip('/')
            test_full_path = safe_path(test_path)
            if test_full_path and os.path.exists(test_full_path):
                # This is a local file with // prefix - convert to preview-assets
                new_url = f'/preview-assets/{test_path}'.replace('//', '/')
                if not quote1 and not quote2:
                    quote1 = quote2 = '"'
                return f'{attr_name}={quote1}{new_url}{quote2}'
            # If not local, it's external - preserve as-is
            return match.group(0)
        
        # For ANY absolute path starting with /, check if it's a local file first
        # This MUST come first to catch ALL absolute paths including domain-structured ones
        if url.startswith('/'):
            test_path = url.lstrip('/')
            test_full_path = safe_path(test_path)
            if test_full_path and os.path.exists(test_full_path):
                # This is a local file - use the path directly (absolute paths are already from root)
                # Just prepend /preview-assets/ to the path
                new_url = f'/preview-assets/{test_path}'.replace('//', '/')
                if not quote1 and not quote2:
                    quote1 = quote2 = '"'
                return f'{attr_name}={quote1}{new_url}{quote2}'
        
        # For truly external CDN URLs (if they don't exist locally), preserve them
        external_services = [
            'cdnjs.cloudflare.com', 'cdn.jsdelivr.net', 'unpkg.com', 'maxcdn.bootstrapcdn.com'
        ]
        if any(service in url for service in external_services):
            # Only preserve if not a local file
            test_path = url.lstrip('/')
            test_full_path = safe_path(test_path)
            if not (test_full_path and os.path.exists(test_full_path)):
                return match.group(0)  # External URL, preserve as-is
        
        # Resolve relative path - handles both absolute (/) and relative paths
        resolved = resolve_relative_path(file_path, url)
        new_url = f'/preview-assets/{resolved}'.replace('//', '/')
        
        # If original was unquoted, keep it unquoted (but safer to quote it)
        # For better compatibility, always quote
        if not quote1 and not quote2:
            quote1 = quote2 = '"'
        
        return f'{attr_name}={quote1}{new_url}{quote2}'
    
    def fix_css_url(match):
        """Fix URLs in CSS url() functions."""
        prefix = match.group(1)  # "url(" part
        quote1 = match.group(2) or ''  # Optional opening quote
        url = match.group(3)     # URL
        quote2 = match.group(4) or ''  # Optional closing quote
        suffix = match.group(5)  # ")" part
        
        # Skip external URLs, data URIs
        if url.startswith(('http://', 'https://', 'data:', 'javascript:', 'blob:')):
            return match.group(0)
        
        if not url:
            return match.group(0)
        
        # Handle protocol-relative URLs (//path) - check if they're actually local files
        if url.startswith('//'):
            test_path = url.lstrip('/')
            test_full_path = safe_path(test_path)
            if test_full_path and os.path.exists(test_full_path):
                # This is a local file with // prefix - convert to preview-assets
                new_url = f'/preview-assets/{test_path}'.replace('//', '/')
                return f'{prefix}{quote1}{new_url}{quote2}{suffix}'
            # If not local, it's external - preserve as-is
            return match.group(0)
        
        # Check if this is a local file with domain structure (like Wayback-Archive)
        local_domain_paths = ['fonts.googleapis.com', 'fonts.gstatic.com']
        for domain_path in local_domain_paths:
            if url.startswith(f'/{domain_path}/') or url.startswith(f'{domain_path}/'):
                # Check if file exists locally
                test_path = url.lstrip('/')
                test_full_path = safe_path(test_path)
                if test_full_path and os.path.exists(test_full_path):
                    # This is a local file - resolve it properly
                    resolved = resolve_relative_path(file_path, url)
                    new_url = f'/preview-assets/{resolved}'.replace('//', '/')
                    return f'{prefix}{quote1}{new_url}{quote2}{suffix}'
        
        # For ANY absolute path starting with /, check if it's a local file first
        # This ensures images, fonts, and other assets in paths like /images/logo.png
        # or /templates/fonts/fontawesome.woff2 are correctly identified as local
        if url.startswith('/'):
            test_path = url.lstrip('/')
            test_full_path = safe_path(test_path)
            if test_full_path and os.path.exists(test_full_path):
                # This is a local file - convert to preview-assets
                resolved = resolve_relative_path(file_path, url)
                new_url = f'/preview-assets/{resolved}'.replace('//', '/')
                return f'{prefix}{quote1}{new_url}{quote2}{suffix}'
        
        # For external CDNs (if not local), preserve them
        external_services = [
            'cdnjs.cloudflare.com', 'cdn.jsdelivr.net', 'unpkg.com', 'maxcdn.bootstrapcdn.com'
        ]
        if any(service in url for service in external_services):
            test_path = url.lstrip('/')
            test_full_path = safe_path(test_path)
            if not (test_full_path and os.path.exists(test_full_path)):
                return match.group(0)  # External, preserve
        
        # Resolve relative path (for local files)
        resolved = resolve_relative_path(file_path, url)
        new_url = f'/preview-assets/{resolved}'.replace('//', '/')
        
        return f'{prefix}{quote1}{new_url}{quote2}{suffix}'
    
    def fix_style_attribute(match):
        """Fix URLs inside style attributes."""
        prefix = match.group(1)  # 'style='
        quote = match.group(2)   # Opening quote
        style_content = match.group(3)  # The actual style content
        
        # Fix url() inside style
        style_content = re.sub(
            r'(url\s*\(\s*)(["\']?)([^)"\']+)(["\']?\s*)(\))',
            fix_css_url,
            style_content,
            flags=re.IGNORECASE
        )
        
        return f'{prefix}{quote}{style_content}{quote}'
    
    # Fix all href, src, action, background, poster, etc.
    # Handle both quoted and unquoted attributes (common in minified HTML)
    # Improved pattern to handle quoted and unquoted attributes more reliably
    # Match href=/path or href="/path" or href='/path'
    attributes_pattern = r'\b(href|src|action|background|poster|data-src|data-background|data-bg)\s*=\s*(["\']?)([^"\'\s<>]+)(["\']?)'
    html_content = re.sub(attributes_pattern, fix_url_attribute, html_content, flags=re.IGNORECASE)
    
    # Fix style attributes (for inline styles with url())
    html_content = re.sub(r'(style=)(["\'])([^"\']+)(["\'])', fix_style_attribute, html_content, flags=re.IGNORECASE)
    
    # Fix @font-face rules and CSS url() in <style> tags - use DOTALL to handle multiline
    def fix_style_tag(match):
        tag_attrs = match.group(1) or ''
        style_content = match.group(2)
        
        # Fix all url() references in CSS (including font files)
        def fix_url_in_css(m):
            prefix = m.group(1)  # "url("
            quote1 = m.group(2) or ''
            url = m.group(3)
            quote2 = m.group(4) or ''
            suffix = m.group(5)  # ")"
            
            # Skip external URLs, data URIs
            if url.startswith(('http://', 'https://', 'data:', 'javascript:', 'blob:')):
                return m.group(0)
            
            if not url:
                return m.group(0)
            
            # Handle protocol-relative URLs (//path) - check if they're actually local files
            if url.startswith('//'):
                test_path = url.lstrip('/')
                test_full_path = safe_path(test_path)
                if test_full_path and os.path.exists(test_full_path):
                    new_url = f'/preview-assets/{test_path}'.replace('//', '/')
                    return f'{prefix}{quote1}{new_url}{quote2}{suffix}'
                return m.group(0)  # External
            
            # For ANY absolute path starting with /, check if it's a local file first
            # This ensures images, fonts, and other assets in paths like /images/logo.png
            # or /templates/fonts/fontawesome.woff2 or /fonts.googleapis.com/css-xxx.css are correctly identified
            if url.startswith('/'):
                test_path = url.lstrip('/')
                test_full_path = safe_path(test_path)
                if test_full_path and os.path.exists(test_full_path):
                    # This is a local file - use the path directly (absolute paths are already from root)
                    new_url = f'/preview-assets/{test_path}'.replace('//', '/')
                    return f'{prefix}{quote1}{new_url}{quote2}{suffix}'
            
            # For external CDNs (if not local), preserve them
            external_services = [
                'cdnjs.cloudflare.com', 'cdn.jsdelivr.net', 'unpkg.com', 'maxcdn.bootstrapcdn.com'
            ]
            if any(service in url for service in external_services):
                test_path = url.lstrip('/')
                test_full_path = safe_path(test_path)
                if not (test_full_path and os.path.exists(test_full_path)):
                    return m.group(0)  # External, preserve
            
            # Resolve path (handles font files: .woff, .woff2, .ttf, .eot, etc.)
            resolved = resolve_relative_path(file_path, url)
            new_url = f'/preview-assets/{resolved}'.replace('//', '/')
            return f'{prefix}{quote1}{new_url}{quote2}{suffix}'
        
        # Fix @font-face src declarations (handles src:url(...) format)
        def fix_font_face(m):
            font_face_content = m.group(1)
            # Fix src:url(...) format (common in Font Awesome and other icon fonts)
            def fix_src_url(match):
                prefix = match.group(1)  # "src:" part
                url_part = match.group(2)  # "url(" part
                quote1 = match.group(3) or ''
                url = match.group(4)
                quote2 = match.group(5) or ''
                suffix = match.group(6)  # ")" part
                
                # Skip external URLs, data URIs
                if url.startswith(('http://', 'https://', 'data:', 'javascript:', 'blob:')):
                    return match.group(0)
                
                if not url:
                    return match.group(0)
                
                # Handle protocol-relative URLs (//path) - check if they're actually local files
                if url.startswith('//'):
                    test_path = url.lstrip('/')
                    test_full_path = safe_path(test_path)
                    if test_full_path and os.path.exists(test_full_path):
                        new_url = f'/preview-assets/{test_path}'.replace('//', '/')
                        return f'{prefix}{url_part}{quote1}{new_url}{quote2}{suffix}'
                    return match.group(0)  # External
                
                # For ANY absolute path starting with /, check if it's a local file first
                if url.startswith('/'):
                    test_path = url.lstrip('/')
                    test_full_path = safe_path(test_path)
                    if test_full_path and os.path.exists(test_full_path):
                        # This is a local file - use the path directly (absolute paths are already from root)
                        new_url = f'/preview-assets/{test_path}'.replace('//', '/')
                        return f'{prefix}{url_part}{quote1}{new_url}{quote2}{suffix}'
                
                # Resolve path for local files
                resolved = resolve_relative_path(file_path, url)
                new_url = f'/preview-assets/{resolved}'.replace('//', '/')
                return f'{prefix}{url_part}{quote1}{new_url}{quote2}{suffix}'
            
            # Fix both src:url(...) and url(...) formats
            # Pattern for src:url(...) - handles Font Awesome format
            font_face_content = re.sub(
                r'(src\s*:\s*)(url\s*\(\s*)(["\']?)([^)"\']+)(["\']?\s*)(\))',
                fix_src_url,
                font_face_content,
                flags=re.IGNORECASE
            )
            # Pattern for regular url(...) - handles Google Fonts format
            font_face_content = re.sub(
                r'(url\s*\(\s*)(["\']?)([^)"\']+)(["\']?\s*)(\))',
                fix_url_in_css,
                font_face_content,
                flags=re.IGNORECASE
            )
            return f'@font-face{{{font_face_content}}}'
        
        # Fix @font-face rules
        style_content = re.sub(
            r'@font-face\s*\{([^}]+)\}',
            fix_font_face,
            style_content,
            flags=re.IGNORECASE | re.DOTALL
        )
        
        # Pattern for url() in CSS - handles whitespace and quotes
        css_url_pattern = r'(url\s*\(\s*)(["\']?)([^)"\']+)(["\']?\s*)(\))'
        style_content = re.sub(css_url_pattern, fix_url_in_css, style_content, flags=re.IGNORECASE)
        
        return f'<style{tag_attrs}>{style_content}</style>'
    
    # Match style tags - including multiline content
    html_content = re.sub(r'<style([^>]*)>((?:[^<]|<(?!/style>))*?)</style>', fix_style_tag, html_content, flags=re.IGNORECASE | re.DOTALL)
    
    # Final catch-all pass: fix any remaining url(//...) patterns that might have been missed
    # This handles edge cases where style tags weren't properly matched
    def fix_remaining_url(m):
        prefix = m.group(1)
        quote1 = m.group(2) or ''
        url = m.group(3)
        quote2 = m.group(4) or ''
        suffix = m.group(5)
        
        if url.startswith('//'):
            test_path = url.lstrip('/')
            test_full_path = safe_path(test_path)
            if test_full_path and os.path.exists(test_full_path):
                new_url = f'/preview-assets/{test_path}'.replace('//', '/')
                return f'{prefix}{quote1}{new_url}{quote2}{suffix}'
        return m.group(0)
    
    html_content = re.sub(r'(url\s*\(\s*)(["\']?)(//[^)"\']+)(["\']?\s*)(\))', fix_remaining_url, html_content, flags=re.IGNORECASE)
    
    # For iframe srcdoc to work properly, we need absolute URLs or a proper base tag
    # Get the current request host to make absolute URLs
    from flask import request
    try:
        base_host = request.host_url.rstrip('/')
    except RuntimeError:
        # Outside request context - use relative
        base_host = ''
    
    # Inject base tag with absolute URL for better compatibility with srcdoc
    base_url = f'{base_host}/preview-assets/{file_dir}/' if file_dir else f'{base_host}/preview-assets/'
    base_url = base_url.replace('//', '/').replace(':/', '://')  # Fix double slashes but preserve protocol
    base_tag = f'<base href="{base_url}">'
    
    # Inject base tag if not present - ALWAYS inject/update for proper asset resolution
    if re.search(r'<base[^>]*>', html_content, re.IGNORECASE):
        # Replace existing base tag
        html_content = re.sub(r'<base[^>]*>', base_tag, html_content, flags=re.IGNORECASE, count=1)
    else:
        # Inject new base tag
        if re.search(r'<head[^>]*>', html_content, re.IGNORECASE):
            html_content = re.sub(r'(<head[^>]*>)', f'\\1\n    {base_tag}', html_content, flags=re.IGNORECASE, count=1)
        elif re.search(r'<html', html_content, re.IGNORECASE):
            html_content = re.sub(r'(<html[^>]*>)', f'\\1\n<head>{base_tag}</head>', html_content, flags=re.IGNORECASE, count=1)
        else:
            # No HTML structure - wrap it
            html_content = f'<html><head>{base_tag}</head><body>{html_content}</body></html>'
    
    return html_content


@app.route('/preview/<path:file_path>')
@login_required
def preview_file(file_path):
    """Serve file for preview (for iframe) with processed HTML."""
    full_path = safe_path(file_path)
    if not full_path or not os.path.exists(full_path):
        abort(404)
    
    # For HTML files, process and serve with fixed paths
    if file_path.endswith(('.html', '.htm')):
        try:
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            processed = process_html_for_preview(content, file_path)
            return processed, 200, {'Content-Type': 'text/html; charset=utf-8'}
        except Exception as e:
            return f'<html><body>Error loading preview: {str(e)}</body></html>', 500
    
    # For other files, serve normally
    return send_file(full_path)


@app.route('/preview-assets/', defaults={'asset_path': ''})
@app.route('/preview-assets/<path:asset_path>')
def preview_assets(asset_path):
    """Serve assets for preview (CSS, JS, images, etc.)."""
    # Normalize path - remove leading/trailing slashes, but handle empty
    asset_path = asset_path.strip('/')
    
    # If empty after strip, it means root request - serve nothing or handle appropriately
    if not asset_path:
        abort(404)  # Root preview-assets doesn't make sense
    
    full_path = safe_path(asset_path)
    
    # If direct path doesn't exist, try common variations
    if not full_path or not os.path.exists(full_path):
        # Try without leading slash variations
        test_paths = [
            asset_path,
            asset_path.lstrip('/'),
            '/' + asset_path.lstrip('/'),
        ]
        
        for test_path in test_paths:
            test_full = safe_path(test_path.lstrip('/'))
            if test_full and os.path.exists(test_full):
                full_path = test_full
                break
        
        # Still not found - try with common extensions
        if not full_path or not os.path.exists(full_path):
            for ext in ['.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.woff', '.woff2', '.ttf', '.eot']:
                test_path = asset_path + ext
                test_full = safe_path(test_path.lstrip('/'))
                if test_full and os.path.exists(test_full):
                    full_path = test_full
                    break
        
        if not full_path or not os.path.exists(full_path):
            abort(404)
    
    # Security: Double-check path is within base directory
    base_dir = get_current_base_dir()
    if not os.path.abspath(full_path).startswith(os.path.abspath(base_dir)):
        abort(403)
    
    # Determine MIME type with proper charset for text files
    mimetype = mimetypes.guess_type(full_path)[0]
    
    # Set appropriate MIME types for common web assets
    if full_path.endswith('.css'):
        mimetype = 'text/css; charset=utf-8'
        # Process CSS files to rewrite url() functions for fonts, images, etc.
        try:
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                css_content = f.read()
            
            # Process CSS content similar to how we process HTML
            def fix_css_url_in_file(match):
                prefix = match.group(1)
                quote1 = match.group(2) or ''
                url = match.group(3)
                quote2 = match.group(4) or ''
                suffix = match.group(5)
                
                # Skip external URLs, data URIs
                if url.startswith(('http://', 'https://', '//', 'data:', 'javascript:', 'blob:')):
                    return match.group(0)
                
                if not url:
                    return match.group(0)
                
                # For ANY absolute path starting with /, check if it's a local file
                if url.startswith('/'):
                    test_path = url.lstrip('/')
                    test_full_path = safe_path(test_path)
                    if test_full_path and os.path.exists(test_full_path):
                        # Use the path directly (absolute paths are already from root)
                        new_url = f'/preview-assets/{test_path}'.replace('//', '/')
                        return f'{prefix}{quote1}{new_url}{quote2}{suffix}'
                
                # For relative paths, resolve relative to the CSS file location
                if not url.startswith('/'):
                    css_dir = '/'.join(asset_path.split('/')[:-1]) if '/' in asset_path else ''
                    resolved = resolve_relative_path(asset_path, url)
                    new_url = f'/preview-assets/{resolved}'.replace('//', '/')
                    return f'{prefix}{quote1}{new_url}{quote2}{suffix}'
                
                return match.group(0)
            
            # Fix all url() references in CSS
            css_url_pattern = r'(url\s*\(\s*)(["\']?)([^)"\']+)(["\']?\s*)(\))'
            css_content = re.sub(css_url_pattern, fix_css_url_in_file, css_content, flags=re.IGNORECASE)
            
            # Also fix @font-face src declarations
            def fix_font_face_in_css(m):
                font_face_content = m.group(1)
                def fix_src_url_in_css(match):
                    prefix = match.group(1)
                    url_part = match.group(2)
                    quote1 = match.group(3) or ''
                    url = match.group(4)
                    quote2 = match.group(5) or ''
                    suffix = match.group(6)
                    
                    if url.startswith(('http://', 'https://', '//', 'data:', 'javascript:', 'blob:')):
                        return match.group(0)
                    
                    if not url:
                        return match.group(0)
                    
                    if url.startswith('/'):
                        test_path = url.lstrip('/')
                        test_full_path = safe_path(test_path)
                        if test_full_path and os.path.exists(test_full_path):
                            new_url = f'/preview-assets/{test_path}'.replace('//', '/')
                            return f'{prefix}{url_part}{quote1}{new_url}{quote2}{suffix}'
                    
                    if not url.startswith('/'):
                        resolved = resolve_relative_path(asset_path, url)
                        new_url = f'/preview-assets/{resolved}'.replace('//', '/')
                        return f'{prefix}{url_part}{quote1}{new_url}{quote2}{suffix}'
                    
                    return match.group(0)
                
                font_face_content = re.sub(
                    r'(src\s*:\s*)(url\s*\(\s*)(["\']?)([^)"\']+)(["\']?\s*)(\))',
                    fix_src_url_in_css,
                    font_face_content,
                    flags=re.IGNORECASE
                )
                font_face_content = re.sub(
                    r'(url\s*\(\s*)(["\']?)([^)"\']+)(["\']?\s*)(\))',
                    fix_css_url_in_file,
                    font_face_content,
                    flags=re.IGNORECASE
                )
                return f'@font-face{{{font_face_content}}}'
            
            css_content = re.sub(
                r'@font-face\s*\{([^}]+)\}',
                fix_font_face_in_css,
                css_content,
                flags=re.IGNORECASE | re.DOTALL
            )
            
            return css_content, 200, {'Content-Type': mimetype}
        except Exception as e:
            # If processing fails, serve original file
            pass
    elif full_path.endswith('.js'):
        mimetype = 'application/javascript; charset=utf-8'
    elif full_path.endswith('.json'):
        mimetype = 'application/json; charset=utf-8'
    elif full_path.endswith('.html') or full_path.endswith('.htm'):
        mimetype = 'text/html; charset=utf-8'
    elif full_path.endswith('.woff'):
        mimetype = 'font/woff'
    elif full_path.endswith('.woff2'):
        mimetype = 'font/woff2'
    elif full_path.endswith('.ttf'):
        mimetype = 'font/ttf'
    elif full_path.endswith('.eot'):
        mimetype = 'application/vnd.ms-fontobject'
    
    if not mimetype:
        mimetype = 'application/octet-stream'
    
    return send_file(full_path, mimetype=mimetype)


@app.route('/api/preview-html', methods=['POST'])
@login_required
def preview_html():
    """API endpoint to preview HTML content in real-time."""
    data = request.json
    html_content = data.get('content', '')
    file_path = data.get('file_path', '')
    
    processed = process_html_for_preview(html_content, file_path)
    return jsonify({'html': processed})


@app.route('/api/files')
@login_required
def list_files():
    """API endpoint to list files in directory."""
    path = request.args.get('path', '')
    full_path = safe_path(path)
    
    if not full_path or not os.path.exists(full_path):
        return jsonify({'error': 'Path not found'}), 404
    
    files = []
    directories = []
    
    try:
        for item in os.listdir(full_path):
            if item.startswith('.way-cms'):
                continue  # Skip backup directories
            
            item_path = os.path.join(full_path, item)
            rel_path = os.path.relpath(item_path, get_current_base_dir())
            
            item_info = {
                'name': item,
                'path': rel_path.replace('\\', '/'),
                'size': os.path.getsize(item_path) if os.path.isfile(item_path) else 0,
            }
            
            if os.path.isdir(item_path):
                directories.append(item_info)
            elif os.path.isfile(item_path) and (allowed_file(item) or item.startswith('.')):
                item_info['type'] = mimetypes.guess_type(item)[0] or 'application/octet-stream'
                files.append(item_info)
        
        directories.sort(key=lambda x: x['name'].lower())
        files.sort(key=lambda x: x['name'].lower())
        
        return jsonify({
            'path': path,
            'directories': directories,
            'files': files
        })
    except PermissionError:
        return jsonify({'error': 'Permission denied'}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/file')
@login_required
def get_file():
    """API endpoint to read file contents."""
    file_path = request.args.get('path', '')
    full_path = safe_path(file_path)
    
    if not file_path:
        return jsonify({'error': 'No file path provided'}), 400
    
    if not full_path or not os.path.exists(full_path) or not os.path.isfile(full_path):
        return jsonify({'error': 'File not found'}), 404
    
    try:
        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        return jsonify({
            'path': file_path,
            'content': content,
            'size': len(content)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/file', methods=['POST'])
@login_required
@read_only_check
def save_file():
    """API endpoint to save file contents."""
    data = request.json
    file_path = data.get('path', '')
    content = data.get('content', '')
    create_backup_flag = data.get('backup', True)
    
    if not file_path:
        return jsonify({'error': 'No file path provided'}), 400
    
    full_path = safe_path(file_path)
    if not full_path:
        return jsonify({'error': 'Invalid path'}), 400
    
    # Create backup if file exists
    backup_path = None
    if create_backup_flag and os.path.exists(full_path):
        backup_path = create_backup(file_path)
    
    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return jsonify({
            'success': True,
            'path': file_path,
            'size': len(content),
            'backup': backup_path
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/file', methods=['PUT'])
@login_required
@read_only_check
def create_file():
    """API endpoint to create new file or folder."""
    data = request.json
    path = data.get('path', '')
    is_directory = data.get('is_directory', False)
    content = data.get('content', '')
    
    if not path:
        return jsonify({'error': 'No path provided'}), 400
    
    full_path = safe_path(path)
    if not full_path:
        return jsonify({'error': 'Invalid path'}), 400
    
    if os.path.exists(full_path):
        return jsonify({'error': 'File or directory already exists'}), 400
    
    try:
        if is_directory:
            os.makedirs(full_path, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        return jsonify({'success': True, 'path': path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/file', methods=['PATCH'])
@login_required
@read_only_check
def rename_file():
    """API endpoint to rename file or folder."""
    data = request.json
    old_path = data.get('old_path', '')
    new_path = data.get('new_path', '')
    
    if not old_path or not new_path:
        return jsonify({'error': 'Both old_path and new_path required'}), 400
    
    old_full = safe_path(old_path)
    new_full = safe_path(new_path)
    
    if not old_full or not new_full:
        return jsonify({'error': 'Invalid path'}), 400
    
    if not os.path.exists(old_full):
        return jsonify({'error': 'Source not found'}), 404
    
    if os.path.exists(new_full):
        return jsonify({'error': 'Destination already exists'}), 400
    
    try:
        # Create backup before rename
        if os.path.isfile(old_full):
            create_backup(old_path)
        
        os.rename(old_full, new_full)
        return jsonify({'success': True, 'new_path': new_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/file', methods=['DELETE'])
@login_required
@read_only_check
def delete_file():
    """API endpoint to delete a file."""
    file_path = request.args.get('path', '')
    full_path = safe_path(file_path)
    
    if not file_path:
        return jsonify({'error': 'No file path provided'}), 400
    
    if not full_path or not os.path.exists(full_path):
        return jsonify({'error': 'File not found'}), 404
    
    try:
        if os.path.isfile(full_path):
            os.remove(full_path)
        elif os.path.isdir(full_path):
            shutil.rmtree(full_path)
        else:
            return jsonify({'error': 'Not a file or directory'}), 400
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/search', methods=['GET'])
@login_required
def search_files():
    """API endpoint to search for text in files."""
    query = request.args.get('q', '')
    file_pattern = request.args.get('pattern', '*')
    use_regex = request.args.get('regex', 'false').lower() == 'true'
    case_sensitive = request.args.get('case_sensitive', 'false').lower() == 'true'
    
    if not query:
        return jsonify({'error': 'No search query provided'}), 400
    
    results = []
    regex = None
    if use_regex:
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(query, flags)
        except re.error as e:
            return jsonify({'error': f'Invalid regex: {e}'}), 400
    
    try:
        import fnmatch
        base_dir = get_current_base_dir()
        for root, dirs, files in os.walk(base_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.way-cms')]
            
            for file in files:
                if fnmatch.fnmatch(file, file_pattern):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, base_dir).replace('\\', '/')
                    
                    if allowed_file(file) or file.startswith('.'):
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                matches = []
                                
                                if regex:
                                    for match in regex.finditer(content):
                                        line_num = content[:match.start()].count('\n') + 1
                                        line_text = content.split('\n')[line_num - 1].strip()[:200]
                                        matches.append({
                                            'line': line_num,
                                            'text': line_text,
                                            'match': match.group()[:100]
                                        })
                                else:
                                    search_text = query if case_sensitive else query.lower()
                                    content_search = content if case_sensitive else content.lower()
                                    if search_text in content_search:
                                        lines = content.split('\n')
                                        for i, line in enumerate(lines, 1):
                                            line_search = line if case_sensitive else line.lower()
                                            if search_text in line_search:
                                                matches.append({
                                                    'line': i,
                                                    'text': line.strip()[:200],
                                                    'match': query
                                                })
                                
                                if matches:
                                    results.append({
                                        'path': rel_path,
                                        'matches': matches[:20]
                                    })
                        except:
                            continue
        
        return jsonify({
            'query': query,
            'results': results[:100]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/search-replace', methods=['POST'])
@login_required
@read_only_check
def search_replace():
    """Enhanced search and replace with preview."""
    data = request.json
    search = data.get('search', '')
    replace = data.get('replace', '')
    file_pattern = data.get('pattern', '*')
    use_regex = data.get('regex', False)
    case_sensitive = data.get('case_sensitive', False)
    dry_run = data.get('dry_run', True)
    file_paths = data.get('files', [])  # Optional: specific files
    
    if not search:
        return jsonify({'error': 'Search query required'}), 400
    
    changes = []
    files_to_process = file_paths if file_paths else []
    
    if not files_to_process:
        # Find all matching files
        import fnmatch
        base_dir = get_current_base_dir()
        for root, dirs, files in os.walk(base_dir):
            dirs[:] = [d for d in dirs if not d.startswith('.way-cms')]
            for file in files:
                if fnmatch.fnmatch(file, file_pattern):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, base_dir).replace('\\', '/')
                    if allowed_file(file):
                        files_to_process.append(rel_path)
    
    regex = None
    if use_regex:
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(search, flags)
        except re.error as e:
            return jsonify({'error': f'Invalid regex: {e}'}), 400
    
    for file_path in files_to_process:
        full_path = safe_path(file_path)
        if not full_path or not os.path.exists(full_path):
            continue
        
        try:
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            original_content = content
            
            if regex:
                if dry_run:
                    matches = list(regex.finditer(content))
                    count = len(matches)
                else:
                    content = regex.sub(replace, content)
                    count = len(re.findall(regex, original_content))
            else:
                if case_sensitive:
                    count = content.count(search)
                    if not dry_run:
                        content = content.replace(search, replace)
                else:
                    # Case-insensitive replace
                    import re as re_module
                    pattern = re_module.compile(re_module.escape(search), re_module.IGNORECASE)
                    count = len(pattern.findall(content))
                    if not dry_run:
                        content = pattern.sub(replace, content)
            
            if count > 0:
                change_info = {
                    'file': file_path,
                    'matches': count,
                    'preview': content[:500] if not dry_run else original_content[:500]
                }
                
                if not dry_run:
                    # Create backup and save
                    create_backup(file_path)
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    change_info['saved'] = True
                
                changes.append(change_info)
        except Exception as e:
            changes.append({
                'file': file_path,
                'error': str(e)
            })
    
    return jsonify({
        'changes': changes,
        'total_files': len(changes),
        'dry_run': dry_run
    })


@app.route('/api/backups')
@login_required
def list_backups():
    """List all backups for a file."""
    file_path = request.args.get('path', '')
    
    if not file_path:
        return jsonify({'error': 'File path required'}), 400
    
    backup_dir = os.path.join(BACKUP_DIR, os.path.dirname(file_path))
    if not os.path.exists(backup_dir):
        return jsonify({'backups': []})
    
    backups = []
    base_filename = os.path.basename(file_path)
    
    try:
        for item in os.listdir(backup_dir):
            if item.startswith(base_filename + '.'):
                item_path = os.path.join(backup_dir, item)
                if os.path.isfile(item_path):
                    stat = os.stat(item_path)
                    timestamp_match = re.search(r'\.(\d{8}_\d{6})$', item)
                    timestamp_str = timestamp_match.group(1) if timestamp_match else ''
                    
                    backups.append({
                        'filename': item,
                        'path': item_path.replace(BACKUP_DIR, '').lstrip('/'),
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        'timestamp': timestamp_str
                    })
        
        backups.sort(key=lambda x: x['modified'], reverse=True)
        return jsonify({'backups': backups})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/backup/<path:backup_path>')
@login_required
def get_backup(backup_path):
    """Get backup file content."""
    full_path = os.path.join(BACKUP_DIR, backup_path)
    if not os.path.abspath(full_path).startswith(os.path.abspath(BACKUP_DIR)):
        return jsonify({'error': 'Invalid path'}), 400
    
    if not os.path.exists(full_path):
        return jsonify({'error': 'Backup not found'}), 404
    
    try:
        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        return jsonify({
            'content': content,
            'path': backup_path
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/restore-backup', methods=['POST'])
@login_required
def restore_backup():
    """Restore a file from backup."""
    data = request.json
    file_path = data.get('file_path', '')
    backup_path = data.get('backup_path', '')
    
    if not file_path or not backup_path:
        return jsonify({'error': 'Both file_path and backup_path required'}), 400
    
    full_backup_path = os.path.join(BACKUP_DIR, backup_path)
    if not os.path.abspath(full_backup_path).startswith(os.path.abspath(BACKUP_DIR)):
        return jsonify({'error': 'Invalid backup path'}), 400
    
    full_file_path = safe_path(file_path)
    if not full_file_path:
        return jsonify({'error': 'Invalid file path'}), 400
    
    if not os.path.exists(full_backup_path):
        return jsonify({'error': 'Backup not found'}), 404
    
    try:
        # Create backup of current file
        if os.path.exists(full_file_path):
            create_backup(file_path)
        
        # Restore from backup
        shutil.copy2(full_backup_path, full_file_path)
        
        return jsonify({'success': True, 'file_path': file_path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/create-backup', methods=['POST'])
@login_required
def create_manual_backup():
    """Create a manual backup of current state."""
    data = request.json
    file_path = data.get('path', '')
    
    if not file_path:
        return jsonify({'error': 'File path required'}), 400
    
    backup_path = create_backup(file_path)
    if backup_path:
        return jsonify({'success': True, 'backup': backup_path})
    else:
        return jsonify({'error': 'Backup creation failed'}), 500


@app.route('/api/folder-backups', methods=['GET'])
@login_required
def list_folder_backups():
    """List all folder backups (ZIP files) including automatic backups."""
    folder_path = request.args.get('path', '')
    
    backups = []
    
    # Check manual backups directory
    folder_backup_dir = os.path.join(BACKUP_DIR, 'folders', folder_path if folder_path else 'root')
    if os.path.exists(folder_backup_dir):
        try:
            for item in os.listdir(folder_backup_dir):
                if item.endswith('.zip'):
                    item_path = os.path.join(folder_backup_dir, item)
                    if os.path.isfile(item_path):
                        stat = os.stat(item_path)
                        backup_name = item[:-4] if item.endswith('.zip') else item
                        
                        backups.append({
                            'name': backup_name,
                            'filename': item,
                            'path': item_path.replace(BACKUP_DIR, '').lstrip('/'),
                            'size': stat.st_size,
                            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            'formatted_date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                            'type': 'manual'
                        })
        except Exception as e:
            print(f"Error reading manual backups: {e}")
    
    # Check automatic backups directory (only for root path)
    if not folder_path:
        auto_backup_dir = os.path.join(BACKUP_DIR, 'auto')
        if os.path.exists(auto_backup_dir):
            try:
                for item in os.listdir(auto_backup_dir):
                    if item.endswith('.zip'):
                        item_path = os.path.join(auto_backup_dir, item)
                        if os.path.isfile(item_path):
                            stat = os.stat(item_path)
                            backup_name = item[:-4] if item.endswith('.zip') else item
                            
                            backups.append({
                                'name': f"[Auto] {backup_name}",
                                'filename': item,
                                'path': f"auto/{item}",
                                'size': stat.st_size,
                                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                'formatted_date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                                'type': 'auto'
                            })
            except Exception as e:
                print(f"Error reading automatic backups: {e}")
    
    backups.sort(key=lambda x: x['modified'], reverse=True)
    return jsonify({'backups': backups})


@app.route('/api/create-folder-backup', methods=['POST'])
@login_required
@read_only_check
def create_folder_backup():
    """Create a folder backup (ZIP)."""
    data = request.json
    folder_path = data.get('path', '')
    backup_name = data.get('name', '').strip()
    
    if not backup_name:
        return jsonify({'error': 'Backup name required'}), 400
    
    # Sanitize backup name
    backup_name = re.sub(r'[^a-zA-Z0-9_-]', '_', backup_name)
    if not backup_name:
        backup_name = 'backup'
    
    full_folder_path = safe_path(folder_path)
    if not full_folder_path:
        return jsonify({'error': 'Invalid folder path'}), 400
    
    # Create backup directory
    folder_backup_dir = os.path.join(BACKUP_DIR, 'folders', folder_path if folder_path else 'root')
    os.makedirs(folder_backup_dir, exist_ok=True)
    
    backup_filename = f"{backup_name}.zip"
    backup_path = os.path.join(folder_backup_dir, backup_filename)
    
    try:
        import zipfile
        import tempfile
        
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            if os.path.isfile(full_folder_path):
                # Single file
                zip_file.write(full_folder_path, os.path.basename(full_folder_path))
            else:
                # Directory - walk and add all files
                for root, dirs, files in os.walk(full_folder_path):
                    # Skip backup directories
                    dirs[:] = [d for d in dirs if not d.startswith('.way-cms')]
                    
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Relative path within the archive
                        arcname = os.path.relpath(file_path, full_folder_path)
                        zip_file.write(file_path, arcname)
        
        stat = os.stat(backup_path)
        return jsonify({
            'success': True,
            'backup': {
                'name': backup_name,
                'filename': backup_filename,
                'path': backup_path.replace(BACKUP_DIR, '').lstrip('/'),
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'formatted_date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/restore-folder-backup', methods=['POST'])
@login_required
@read_only_check
def restore_folder_backup():
    """Restore a folder from backup ZIP."""
    data = request.json
    folder_path = data.get('path', '')
    backup_path = data.get('backup_path', '')
    
    if not folder_path or not backup_path:
        return jsonify({'error': 'Both folder path and backup path required'}), 400
    
    full_backup_path = os.path.join(BACKUP_DIR, backup_path)
    if not os.path.abspath(full_backup_path).startswith(os.path.abspath(BACKUP_DIR)):
        return jsonify({'error': 'Invalid backup path'}), 400
    
    if not os.path.exists(full_backup_path):
        return jsonify({'error': 'Backup not found'}), 404
    
    full_folder_path = safe_path(folder_path)
    if not full_folder_path:
        return jsonify({'error': 'Invalid folder path'}), 400
    
    try:
        import zipfile
        
        # Extract ZIP to folder
        with zipfile.ZipFile(full_backup_path, 'r') as zip_file:
            zip_file.extractall(full_folder_path)
        
        return jsonify({'success': True, 'message': 'Folder restored successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/trigger-auto-backup', methods=['POST'])
@login_required
@read_only_check
def trigger_auto_backup():
    """Manually trigger an automatic backup."""
    try:
        backup_path = create_automatic_backup()
        if backup_path:
            stat = os.stat(backup_path)
            return jsonify({
                'success': True,
                'backup': {
                    'path': backup_path.replace(BACKUP_DIR, '').lstrip('/'),
                    'size': stat.st_size,
                    'formatted_date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                }
            })
        else:
            return jsonify({'error': 'Failed to create backup'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/delete-folder-backup', methods=['DELETE'])
@login_required
@read_only_check
def delete_folder_backup():
    """Delete a folder backup."""
    backup_path = request.args.get('path', '')
    
    if not backup_path:
        return jsonify({'error': 'Backup path required'}), 400
    
    full_backup_path = os.path.join(BACKUP_DIR, backup_path)
    if not os.path.abspath(full_backup_path).startswith(os.path.abspath(BACKUP_DIR)):
        return jsonify({'error': 'Invalid backup path'}), 400
    
    if not os.path.exists(full_backup_path):
        return jsonify({'error': 'Backup not found'}), 404
    
    try:
        os.remove(full_backup_path)
        return jsonify({'success': True, 'message': 'Backup deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download-zip')
@login_required
def download_folder_zip():
    """Download a folder as ZIP."""
    path = request.args.get('path', '')
    full_path = safe_path(path)
    
    if not full_path:
        return jsonify({'error': 'Invalid path'}), 400
    
    if not os.path.exists(full_path):
        return jsonify({'error': 'Path not found'}), 404
    
    try:
        import zipfile
        import tempfile
        
        # Determine filename - use WEBSITE_NAME if available
        if path:
            zip_filename = f"{os.path.basename(path) or 'folder'}.zip"
        else:
            zip_filename = f"{get_website_name_for_backup()}.zip"
        
        # Create temp file for the ZIP (avoids BytesIO hanging issues)
        fd, tmp_path = tempfile.mkstemp(suffix='.zip')
        os.close(fd)
        
        try:
            with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                if os.path.isfile(full_path):
                    # Single file
                    zip_file.write(full_path, os.path.basename(full_path))
                else:
                    # Directory - walk and add all files
                    for root, dirs, files in os.walk(full_path):
                        # Skip backup directories
                        dirs[:] = [d for d in dirs if not d.startswith('.way-cms')]
                        
                        for file in files:
                            file_path = os.path.join(root, file)
                            # Calculate relative path from base directory
                            arcname = os.path.relpath(file_path, get_current_base_dir())
                            zip_file.write(file_path, arcname)
            
            # Send the file and delete after
            response = send_file(
                tmp_path,
                mimetype='application/zip',
                as_attachment=True,
                download_name=zip_filename
            )
            
            # Schedule cleanup after response is sent
            @response.call_on_close
            def cleanup():
                try:
                    os.unlink(tmp_path)
                except:
                    pass
            
            return response
        except Exception as e:
            # Clean up on error
            try:
                os.unlink(tmp_path)
            except:
                pass
            raise e
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download-file')
@login_required
def download_single_file():
    """Download a single file."""
    path = request.args.get('path', '')
    full_path = safe_path(path)
    
    if not full_path:
        return jsonify({'error': 'Invalid path'}), 400
    
    if not os.path.exists(full_path):
        return jsonify({'error': 'File not found'}), 404
    
    if not os.path.isfile(full_path):
        return jsonify({'error': 'Path is not a file'}), 400
    
    try:
        return send_file(
            full_path,
            as_attachment=True,
            download_name=os.path.basename(full_path)
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload-zip', methods=['POST'])
@login_required
@read_only_check
def upload_zip():
    """Upload and extract a ZIP file to restore folder."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    extract_path = request.form.get('path', '')  # Optional: where to extract
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.zip'):
        return jsonify({'error': 'File must be a ZIP archive'}), 400
    
    try:
        import zipfile
        import tempfile
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
            file.save(tmp_file.name)
            tmp_path = tmp_file.name
        
        # Determine extraction directory
        base_dir = get_current_base_dir()
        if extract_path:
            extract_to = safe_path(extract_path)
            if not extract_to:
                os.unlink(tmp_path)
                return jsonify({'error': 'Invalid extraction path'}), 400
        else:
            extract_to = base_dir
        
        # Create extraction directory if needed
        Path(extract_to).mkdir(parents=True, exist_ok=True)
        
        # Extract ZIP file
        extracted_files = []
        with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
            # Validate all paths are safe
            for member in zip_ref.namelist():
                # Prevent zip slip vulnerability
                member_path = os.path.join(extract_to, member)
                if not os.path.abspath(member_path).startswith(os.path.abspath(base_dir)):
                    os.unlink(tmp_path)
                    return jsonify({'error': 'Invalid file path in ZIP'}), 400
            
            zip_ref.extractall(extract_to)
            extracted_files = zip_ref.namelist()
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        return jsonify({
            'success': True,
            'extracted_to': extract_path or '',
            'files_count': len(extracted_files),
            'files': extracted_files[:50]  # First 50 files
        })
    except zipfile.BadZipFile:
        return jsonify({'error': 'Invalid ZIP file'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload-file', methods=['POST'])
@login_required
@read_only_check
def upload_file():
    """API endpoint to upload individual files."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    upload_path = request.form.get('path', '')  # Optional: where to upload
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Check file extension
    if not allowed_file(file.filename):
        return jsonify({'error': f'File type not allowed. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        return jsonify({'error': f'File too large. Max size: {MAX_FILE_SIZE / 1024 / 1024}MB'}), 400
    
    try:
        # Determine upload directory
        base_dir = get_current_base_dir()
        if upload_path:
            upload_to = safe_path(upload_path)
            if not upload_to or not os.path.isdir(upload_to):
                return jsonify({'error': 'Invalid upload path'}), 400
        else:
            upload_to = base_dir
        
        # Secure filename
        filename = secure_filename(file.filename)
        target_path = os.path.join(upload_to, filename)
        target_path = safe_path(os.path.relpath(target_path, base_dir))
        
        if not target_path:
            return jsonify({'error': 'Invalid target path'}), 400
        
        # Save file
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        file.save(target_path)
        
        return jsonify({
            'success': True,
            'path': os.path.relpath(target_path, base_dir),
            'size': file_size
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/my-projects', methods=['GET'])
@login_required
def get_my_projects():
    """API endpoint to get current user's projects (multi-tenant only)."""
    if not MULTI_TENANT:
        return jsonify({'error': 'Not in multi-tenant mode'}), 400
    
    from auth import get_current_user
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    
    projects = user.get_projects()
    current_project_id = session.get('current_project_id')
    
    return jsonify({
        'projects': [p.to_dict() for p in projects],
        'current_project_id': current_project_id
    })


@app.route('/api/switch-project', methods=['POST'])
@login_required
def switch_project():
    """API endpoint to switch to a different project (multi-tenant only)."""
    if not MULTI_TENANT:
        return jsonify({'error': 'Not in multi-tenant mode'}), 400
    
    from auth import get_current_user, set_current_project
    from models import Project
    
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    project_id = data.get('project_id')
    
    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400
    
    project = Project.get_by_id(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    if not user.has_access_to_project(project_id):
        return jsonify({'error': 'Access denied to this project'}), 403
    
    set_current_project(project)
    
    return jsonify({
        'success': True,
        'project': project.to_dict()
    })


@app.route('/api/config', methods=['GET'])
@login_required
def get_config():
    """API endpoint to get system configuration (for frontend)."""
    config = {
        'read_only': READ_ONLY_MODE,
        'session_timeout': SESSION_TIMEOUT_MINUTES,
        'allowed_extensions': list(ALLOWED_EXTENSIONS),
        'max_file_size': MAX_FILE_SIZE,
        'multi_tenant': MULTI_TENANT
    }
    
    if MULTI_TENANT:
        from auth import get_current_user, get_current_project
        user = get_current_user()
        project = get_current_project()
        config['user'] = user.to_dict() if user else None
        config['current_project'] = project.to_dict() if project else None
        config['is_admin'] = user.is_admin if user else False
    
    return jsonify(config)


# Catch-all route for serving assets directly from website directory
# This is a fallback for when HTML rewriting doesn't catch all paths
@app.route('/<path:asset_path>')
def serve_asset_fallback(asset_path):
    """Serve assets directly from website directory as fallback."""
    # Only serve if it looks like a static asset (not API or HTML pages)
    if asset_path.startswith('api/') or asset_path.startswith('preview'):
        abort(404)
    
    full_path = safe_path(asset_path)
    if not full_path or not os.path.exists(full_path) or not os.path.isfile(full_path):
        abort(404)
    
    # Security: ensure within base directory
    base_dir = get_current_base_dir()
    if not os.path.abspath(full_path).startswith(os.path.abspath(base_dir)):
        abort(403)
    
    # Determine MIME type
    mimetype = mimetypes.guess_type(full_path)[0]
    
    # Set appropriate MIME types for common assets
    if full_path.endswith('.css'):
        mimetype = 'text/css; charset=utf-8'
        # Process CSS to fix url() references
        try:
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                css_content = f.read()
            
            def fix_css_url_fallback(match):
                prefix = match.group(1)
                quote1 = match.group(2) or ''
                url = match.group(3)
                quote2 = match.group(4) or ''
                suffix = match.group(5)
                
                if url.startswith(('http://', 'https://', '//', 'data:', 'javascript:', 'blob:')):
                    return match.group(0)
                
                if not url:
                    return match.group(0)
                
                # For absolute paths, check if local
                if url.startswith('/'):
                    test_path = url.lstrip('/')
                    test_full_path = safe_path(test_path)
                    if test_full_path and os.path.exists(test_full_path):
                        return match.group(0)  # File exists, keep as-is since catch-all will serve it
                
                return match.group(0)
            
            css_url_pattern = r'(url\s*\(\s*)(["\']?)([^)"\']+)(["\']?\s*)(\))'
            css_content = re.sub(css_url_pattern, fix_css_url_fallback, css_content, flags=re.IGNORECASE)
            
            return css_content, 200, {'Content-Type': mimetype}
        except Exception:
            pass
    elif full_path.endswith('.woff'):
        mimetype = 'font/woff'
    elif full_path.endswith('.woff2'):
        mimetype = 'font/woff2'
    elif full_path.endswith('.ttf'):
        mimetype = 'font/ttf'
    elif full_path.endswith('.eot'):
        mimetype = 'application/vnd.ms-fontobject'
    
    if not mimetype:
        mimetype = 'application/octet-stream'
    
    return send_file(full_path, mimetype=mimetype)


# Automatic backup system
AUTO_BACKUP_ENABLED = os.environ.get('AUTO_BACKUP_ENABLED', 'true').lower() == 'true'
AUTO_BACKUP_DIR = os.path.join(BACKUP_DIR, 'auto')

def get_website_name_for_backup(project_slug=None):
    """Get website name for backup filename."""
    if project_slug:
        return re.sub(r'[^a-zA-Z0-9_-]', '_', project_slug)
    if WEBSITE_NAME:
        # Sanitize for filename
        return re.sub(r'[^a-zA-Z0-9_-]', '_', WEBSITE_NAME)
    return os.path.basename(CMS_BASE_DIR.rstrip('/')) or 'website'

def create_automatic_backup(project_slug=None, base_dir=None):
    """Create an automatic backup of a website directory.
    In multi-tenant mode, backs up a specific project.
    In single-tenant mode, backs up CMS_BASE_DIR.
    """
    if not AUTO_BACKUP_ENABLED:
        print("[AutoBackup] Automatic backups disabled")
        return None
    
    # Determine backup directory
    if base_dir is None:
        base_dir = CMS_BASE_DIR
    
    backup_dir = AUTO_BACKUP_DIR
    if project_slug:
        backup_dir = os.path.join(BACKUP_DIR, project_slug, 'auto')
    
    try:
        import zipfile
        
        print(f"[AutoBackup] Creating backup... base_dir={base_dir}, backup_dir={backup_dir}")
        
        # Create auto backup directory
        os.makedirs(backup_dir, exist_ok=True)
        print(f"[AutoBackup] Directory created/exists: {backup_dir}")
        
        # Generate backup filename with timestamp
        website_name = get_website_name_for_backup(project_slug)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"{website_name}_{timestamp}.zip"
        backup_path = os.path.join(backup_dir, backup_filename)
        print(f"[AutoBackup] Creating backup at: {backup_path}")
        
        # Create ZIP backup
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            if os.path.isdir(base_dir):
                for root, dirs, files in os.walk(base_dir):
                    # Skip backup directories
                    dirs[:] = [d for d in dirs if not d.startswith('.way-cms')]
                    
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            # Relative path within the archive
                            arcname = os.path.relpath(file_path, base_dir)
                            zip_file.write(file_path, arcname)
                        except (OSError, IOError) as e:
                            # Skip files that can't be read (permissions, etc.)
                            print(f"[AutoBackup] Warning: Could not backup {file_path}: {e}")
        
        print(f"[AutoBackup] Backup created successfully: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"[AutoBackup] Error creating automatic backup: {e}")
        import traceback
        traceback.print_exc()
        return None

def manage_backup_retention_for_project(project_slug):
    """Manage backup retention for a specific project."""
    project_backup_dir = os.path.join(BACKUP_DIR, project_slug, 'auto')
    if not os.path.exists(project_backup_dir):
        return
    
    try:
        now = datetime.now()
        backups = []
        
        # Collect all backup files with their timestamps
        for filename in os.listdir(project_backup_dir):
            if not filename.endswith('.zip'):
                continue
            
            backup_path = os.path.join(project_backup_dir, filename)
            if not os.path.isfile(backup_path):
                continue
            
            try:
                # Extract timestamp from filename: website_name_YYYYMMDD_HHMMSS.zip
                parts = filename.replace('.zip', '').split('_')
                if len(parts) >= 3:
                    date_str = parts[-2]  # YYYYMMDD
                    backup_date = datetime.strptime(date_str, '%Y%m%d')
                    backups.append((backup_path, backup_date, now - backup_date))
            except (ValueError, IndexError):
                # Skip files with invalid format
                continue
        
        # Sort by date (oldest first)
        backups.sort(key=lambda x: x[1])
        
        # Keep all yearly backups (first backup of each year)
        yearly_backups = {}
        for backup_path, backup_date, age in backups:
            year = backup_date.year
            if year not in yearly_backups:
                yearly_backups[year] = backup_path
        
        # Keep all monthly backups (first backup of each month) for last 12 months
        monthly_backups = {}
        for backup_path, backup_date, age in backups:
            if age.days <= 365:  # Within a year
                month_key = (backup_date.year, backup_date.month)
                if month_key not in monthly_backups:
                    monthly_backups[month_key] = backup_path
        
        # Keep all weekly backups (first backup of each week) for last 4 weeks
        weekly_backups = {}
        for backup_path, backup_date, age in backups:
            if age.days <= 28:  # Within 4 weeks
                week_key = (backup_date.year, backup_date.isocalendar()[1])  # ISO week
                if week_key not in weekly_backups:
                    weekly_backups[week_key] = backup_path
        
        # Keep all daily backups for last 7 days
        daily_backups = set()
        for backup_path, backup_date, age in backups:
            if age.days <= 7:
                daily_backups.add(backup_path)
        
        # Combine all backups to keep
        backups_to_keep = set(yearly_backups.values()) | set(monthly_backups.values()) | \
                         set(weekly_backups.values()) | daily_backups
        
        # Delete backups not in the keep list
        deleted_count = 0
        for backup_path, backup_date, age in backups:
            if backup_path not in backups_to_keep:
                try:
                    os.remove(backup_path)
                    deleted_count += 1
                except OSError as e:
                    print(f"Warning: Could not delete old backup {backup_path}: {e}")
        
        if deleted_count > 0:
            print(f"Cleaned up {deleted_count} old backup(s) for project {project_slug}")
            
    except Exception as e:
        print(f"Error managing backup retention for project {project_slug}: {e}")

def manage_backup_retention():
    """Manage backup retention: keep daily (7 days), weekly (4 weeks), monthly (12 months), yearly (all).
    In multi-tenant mode, manages retention for all projects.
    """
    if MULTI_TENANT:
        # Manage retention for each project
        from models import Project
        projects = Project.get_all()
        for project in projects:
            manage_backup_retention_for_project(project.slug)
        return
    
    # Single-tenant mode - use global AUTO_BACKUP_DIR
    if not os.path.exists(AUTO_BACKUP_DIR):
        return
    
    try:
        now = datetime.now()
        backups = []
        
        # Collect all backup files with their timestamps
        for filename in os.listdir(AUTO_BACKUP_DIR):
            if not filename.endswith('.zip'):
                continue
            
            backup_path = os.path.join(AUTO_BACKUP_DIR, filename)
            if not os.path.isfile(backup_path):
                continue
            
            try:
                # Extract timestamp from filename: website_name_YYYYMMDD_HHMMSS.zip
                parts = filename.replace('.zip', '').split('_')
                if len(parts) >= 3:
                    date_str = parts[-2]  # YYYYMMDD
                    backup_date = datetime.strptime(date_str, '%Y%m%d')
                    backups.append((backup_path, backup_date, now - backup_date))
            except (ValueError, IndexError):
                # Skip files with invalid format
                continue
        
        # Sort by date (oldest first)
        backups.sort(key=lambda x: x[1])
        
        # Keep all yearly backups (first backup of each year)
        yearly_backups = {}
        for backup_path, backup_date, age in backups:
            year = backup_date.year
            if year not in yearly_backups:
                yearly_backups[year] = backup_path
        
        # Keep all monthly backups (first backup of each month) for last 12 months
        monthly_backups = {}
        for backup_path, backup_date, age in backups:
            if age.days <= 365:  # Within a year
                month_key = (backup_date.year, backup_date.month)
                if month_key not in monthly_backups:
                    monthly_backups[month_key] = backup_path
        
        # Keep all weekly backups (first backup of each week) for last 4 weeks
        weekly_backups = {}
        for backup_path, backup_date, age in backups:
            if age.days <= 28:  # Within 4 weeks
                week_key = (backup_date.year, backup_date.isocalendar()[1])  # ISO week
                if week_key not in weekly_backups:
                    weekly_backups[week_key] = backup_path
        
        # Keep all daily backups for last 7 days
        daily_backups = set()
        for backup_path, backup_date, age in backups:
            if age.days <= 7:
                daily_backups.add(backup_path)
        
        # Combine all backups to keep
        backups_to_keep = set(yearly_backups.values()) | set(monthly_backups.values()) | \
                         set(weekly_backups.values()) | daily_backups
        
        # Delete backups not in the keep list
        deleted_count = 0
        for backup_path, backup_date, age in backups:
            if backup_path not in backups_to_keep:
                try:
                    os.remove(backup_path)
                    deleted_count += 1
                except OSError as e:
                    print(f"Warning: Could not delete old backup {backup_path}: {e}")
        
        if deleted_count > 0:
            print(f"Cleaned up {deleted_count} old backup(s)")
            
    except Exception as e:
        print(f"Error managing backup retention: {e}")

def schedule_daily_backup():
    """Schedule daily automatic backups."""
    if not AUTO_BACKUP_ENABLED:
        return
    
    def backup_worker():
        while True:
            try:
                # Wait until next day at 2 AM
                now = datetime.now()
                next_backup = now.replace(hour=2, minute=0, second=0, microsecond=0)
                if next_backup <= now:
                    next_backup += timedelta(days=1)
                
                wait_seconds = (next_backup - now).total_seconds()
                time.sleep(wait_seconds)
                
                # Create backup with file lock to prevent multiple workers
                try:
                    import fcntl
                    lock_fd = os.open(_backup_lock_file, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
                    try:
                        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        # We got the lock
                        print(f"Creating scheduled daily backup at {datetime.now()}")
                        if MULTI_TENANT:
                            from models import Project
                            projects = Project.get_all()
                            for project in projects:
                                project_path = os.path.join(PROJECTS_BASE_DIR, project.slug)
                                if os.path.exists(project_path):
                                    create_automatic_backup(project_slug=project.slug, base_dir=project_path)
                                    manage_backup_retention_for_project(project.slug)
                        else:
                            create_automatic_backup()
                            manage_backup_retention()
                        fcntl.flock(lock_fd, fcntl.LOCK_UN)
                    except (IOError, OSError):
                        # Another worker is doing the backup
                        pass
                    finally:
                        os.close(lock_fd)
                except (ImportError, OSError):
                    # File locking not available, just create backup
                    if MULTI_TENANT:
                        from models import Project
                        projects = Project.get_all()
                        for project in projects:
                            project_path = os.path.join(PROJECTS_BASE_DIR, project.slug)
                            if os.path.exists(project_path):
                                create_automatic_backup(project_slug=project.slug, base_dir=project_path)
                    else:
                        create_automatic_backup()
                    manage_backup_retention()
                
            except Exception as e:
                print(f"Error in backup scheduler: {e}")
                # On error, retry after 1 hour
                time.sleep(3600)
    
    # Start backup thread as daemon (will die with main process)
    backup_thread = threading.Thread(target=backup_worker, daemon=True)
    backup_thread.start()
    print("Automatic backup scheduler started")

# Initialize automatic backups on startup
# Only initialize once (important for Gunicorn with multiple workers)
# Use file-based locking to prevent multiple workers from running backups
_backup_lock_file = os.path.join(BACKUP_DIR, '.backup_init_lock')

def initialize_automatic_backups():
    """Initialize automatic backup system (call once on app startup).
    Uses file locking to prevent multiple Gunicorn workers from running backups.
    """
    if not AUTO_BACKUP_ENABLED:
        return
    
    # Try to acquire lock (only one worker should succeed)
    try:
        import fcntl
        lock_fd = os.open(_backup_lock_file, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # We got the lock - we're the master worker
            print("[AutoBackup] Master worker acquired lock, initializing backups...")
        except (IOError, OSError):
            # Another worker already has the lock
            os.close(lock_fd)
            print("[AutoBackup] Another worker is handling backups, skipping initialization")
            return
    except (ImportError, OSError, IOError):
        # File locking not available (Windows) or lock file issues
        # Fall back to simple check - this might still create multiple backups on Windows
        if os.path.exists(_backup_lock_file):
            # Check if lock file is recent (less than 30 seconds old)
            try:
                lock_age = time.time() - os.path.getmtime(_backup_lock_file)
                if lock_age < 30:
                    print("[AutoBackup] Backup initialization recently completed, skipping")
                    return
            except:
                pass
        
        # Create lock file
        try:
            with open(_backup_lock_file, 'w') as f:
                f.write(str(os.getpid()))
        except:
            pass
    
    # Create initial backup on startup (delay slightly to allow app to fully initialize)
    def create_startup_backup():
        try:
            print("Creating initial automatic backup...")
            if MULTI_TENANT:
                # In multi-tenant mode, backup all projects
                from models import Project
                projects = Project.get_all()
                if projects:
                    for project in projects:
                        project_path = os.path.join(PROJECTS_BASE_DIR, project.slug)
                        if os.path.exists(project_path):
                            print(f"[AutoBackup] Backing up project: {project.name} (slug: {project.slug})")
                            create_automatic_backup(project_slug=project.slug, base_dir=project_path)
                            # Manage retention for this project
                            manage_backup_retention_for_project(project.slug)
                else:
                    # No projects yet, skip backup
                    print("[AutoBackup] No projects found, skipping initial backup")
            else:
                # Single-tenant mode
                create_automatic_backup()
                manage_backup_retention()
        except Exception as e:
            print(f"Warning: Could not create initial backup: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Release lock after backup
            try:
                if 'lock_fd' in locals():
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                    os.close(lock_fd)
            except:
                pass
    
    # Delay startup backup by 10 seconds to allow app to initialize
    startup_thread = threading.Thread(target=lambda: (time.sleep(10), create_startup_backup()), daemon=True)
    startup_thread.start()
    
    # Start daily backup scheduler
    schedule_daily_backup()

# Initialize backups when app is created
initialize_automatic_backups()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
