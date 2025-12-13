#!/usr/bin/env python3
"""
Website CMS - A simple web-based editor for HTML/CSS files
Designed for editing files downloaded from Wayback Archive.
"""

import os
import json
import re
import shutil
import hashlib
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory, abort, redirect, url_for, session, send_file
from werkzeug.utils import secure_filename
from functools import wraps
import mimetypes

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-me-in-production-' + os.urandom(32).hex())

# Configuration
CMS_BASE_DIR = os.environ.get('CMS_BASE_DIR', '/var/www/html')
CMS_USERNAME = os.environ.get('CMS_USERNAME', 'admin')
CMS_PASSWORD_HASH = os.environ.get('CMS_PASSWORD_HASH', '')  # bcrypt hash
CMS_PASSWORD = os.environ.get('CMS_PASSWORD', '')  # Plain password (legacy, will hash it)
BACKUP_DIR = os.path.join(os.path.dirname(CMS_BASE_DIR), '.way-cms-backups')
ALLOWED_EXTENSIONS = {'html', 'htm', 'css', 'js', 'txt', 'xml', 'json', 'md', 'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'zip'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB max file size

# Ensure directories exist
Path(CMS_BASE_DIR).mkdir(parents=True, exist_ok=True)
Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)

# Initialize password hash if plain password provided
if CMS_PASSWORD and not CMS_PASSWORD_HASH:
    try:
        import bcrypt
        CMS_PASSWORD_HASH = bcrypt.hashpw(CMS_PASSWORD.encode(), bcrypt.gensalt()).decode()
    except ImportError:
        # Fallback to simple hash if bcrypt not available
        CMS_PASSWORD_HASH = hashlib.sha256(CMS_PASSWORD.encode()).hexdigest()


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
    """Decorator to require login if password is set."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if (CMS_PASSWORD_HASH or CMS_PASSWORD) and not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def has_auth_configured():
    """Check if authentication is configured."""
    return bool(CMS_PASSWORD_HASH or CMS_PASSWORD)


def safe_path(file_path):
    """Ensure path is within base directory."""
    full_path = os.path.join(CMS_BASE_DIR, file_path) if file_path else CMS_BASE_DIR
    full_path = os.path.abspath(full_path)
    base_path = os.path.abspath(CMS_BASE_DIR)
    if not full_path.startswith(base_path):
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
    return render_template('index.html', base_dir=CMS_BASE_DIR)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page with username and password."""
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
            return redirect(url_for('index'))
        
        return render_template('login.html', error='Invalid username or password')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout."""
    session.pop('logged_in', None)
    return redirect(url_for('login'))


def process_html_for_preview(html_content, file_path):
    """Process HTML content to fix relative paths for preview."""
    from urllib.parse import urljoin, urlparse
    import re
    
    # Get the directory of the file for resolving relative paths
    file_dir = '/'.join(file_path.split('/')[:-1]) if '/' in file_path else ''
    
    # Use base tag to set base URL for all relative paths
    # This is the simplest and most reliable approach
    base_url = f'/preview-assets/{file_dir}/' if file_dir else '/preview-assets/'
    base_url = base_url.replace('//', '/')
    
    # Inject or update base tag in head
    base_tag = f'<base href="{base_url}">'
    
    # Try to find and replace existing base tag
    if re.search(r'<base[^>]*>', html_content, re.IGNORECASE):
        html_content = re.sub(r'<base[^>]*>', base_tag, html_content, flags=re.IGNORECASE)
    # If no base tag, try to inject after <head>
    elif re.search(r'<head[^>]*>', html_content, re.IGNORECASE):
        html_content = re.sub(r'(<head[^>]*>)', f'\\1\n    {base_tag}', html_content, flags=re.IGNORECASE, count=1)
    # If no head tag, wrap content
    elif not re.search(r'<html', html_content, re.IGNORECASE):
        html_content = f'<html><head>{base_tag}</head><body>{html_content}</body></html>'
    else:
        # Has html but no head
        html_content = re.sub(r'(<html[^>]*>)', f'\\1<head>{base_tag}</head>', html_content, flags=re.IGNORECASE, count=1)
    
    # Additionally fix absolute paths that start with / to use preview-assets
    # This handles cases where base tag might not work perfectly
    def fix_absolute_paths(match):
        quote = match.group(1)  # Opening quote
        url = match.group(2)    # URL
        quote2 = match.group(3) # Closing quote
        
        # Skip external URLs, data URIs, etc.
        if url.startswith(('http://', 'https://', '//', 'data:', 'javascript:', '#', 'mailto:', 'tel:')):
            return match.group(0)
        
        # Fix absolute paths (starting with /)
        if url.startswith('/'):
            new_url = f'/preview-assets{url}'
            return f'{quote}{new_url}{quote2}'
        
        # Keep relative paths as-is (base tag will handle them)
        return match.group(0)
    
    # Fix href, src, action, background attributes
    html_content = re.sub(r'(href=["\'])([^"\']+)(["\'])', fix_absolute_paths, html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'(src=["\'])([^"\']+)(["\'])', fix_absolute_paths, html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'(action=["\'])([^"\']+)(["\'])', fix_absolute_paths, html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'(background=["\'])([^"\']+)(["\'])', fix_absolute_paths, html_content, flags=re.IGNORECASE)
    
    # Fix CSS url() references
    def fix_css_url(match):
        quote = match.group(1) if match.group(1) else ''
        url = match.group(2)
        quote2 = match.group(3) if match.group(3) else ''
        
        if url.startswith(('http://', 'https://', '//', 'data:', 'javascript:')):
            return match.group(0)
        
        if url.startswith('/'):
            new_url = f'/preview-assets{url}'
            return f'url({quote}{new_url}{quote2})'
        
        return match.group(0)
    
    html_content = re.sub(r'url\((["\']?)([^)"\']+)(["\']?)\)', fix_css_url, html_content, flags=re.IGNORECASE)
    
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


@app.route('/preview-assets/<path:asset_path>')
@login_required
def preview_assets(asset_path):
    """Serve assets for preview (CSS, JS, images, etc.)."""
    # Remove leading slash if present
    asset_path = asset_path.lstrip('/')
    full_path = safe_path(asset_path)
    if not full_path or not os.path.exists(full_path):
        abort(404)
    
    # Determine MIME type
    mimetype = mimetypes.guess_type(full_path)[0] or 'application/octet-stream'
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
            rel_path = os.path.relpath(item_path, CMS_BASE_DIR)
            
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
        for root, dirs, files in os.walk(CMS_BASE_DIR):
            dirs[:] = [d for d in dirs if not d.startswith('.way-cms')]
            
            for file in files:
                if fnmatch.fnmatch(file, file_pattern):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, CMS_BASE_DIR).replace('\\', '/')
                    
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
        for root, dirs, files in os.walk(CMS_BASE_DIR):
            dirs[:] = [d for d in dirs if not d.startswith('.way-cms')]
            for file in files:
                if fnmatch.fnmatch(file, file_pattern):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, CMS_BASE_DIR).replace('\\', '/')
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
        import io
        
        # Create a BytesIO buffer for the ZIP
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
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
                        arcname = os.path.relpath(file_path, CMS_BASE_DIR)
                        zip_file.write(file_path, arcname)
        
        zip_buffer.seek(0)
        
        # Determine filename
        if path:
            zip_filename = f"{os.path.basename(path) or 'folder'}.zip"
        else:
            zip_filename = f"{os.path.basename(CMS_BASE_DIR) or 'website'}.zip"
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload-zip', methods=['POST'])
@login_required
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
        if extract_path:
            extract_to = safe_path(extract_path)
            if not extract_to:
                os.unlink(tmp_path)
                return jsonify({'error': 'Invalid extraction path'}), 400
        else:
            extract_to = CMS_BASE_DIR
        
        # Create extraction directory if needed
        Path(extract_to).mkdir(parents=True, exist_ok=True)
        
        # Extract ZIP file
        extracted_files = []
        with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
            # Validate all paths are safe
            for member in zip_ref.namelist():
                # Prevent zip slip vulnerability
                member_path = os.path.join(extract_to, member)
                if not os.path.abspath(member_path).startswith(os.path.abspath(CMS_BASE_DIR)):
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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
