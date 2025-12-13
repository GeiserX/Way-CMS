#!/usr/bin/env python3
"""
Website CMS - A simple web-based editor for HTML/CSS files
Designed for editing files downloaded from Wayback Archive.
"""

import os
import json
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory, abort, redirect, url_for, session
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
import mimetypes

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-me-in-production-' + os.urandom(32).hex())

# Configuration
CMS_BASE_DIR = os.environ.get('CMS_BASE_DIR', '/var/www/html')
CMS_PASSWORD = os.environ.get('CMS_PASSWORD', '')
ALLOWED_EXTENSIONS = {'html', 'htm', 'css', 'js', 'txt', 'xml', 'json', 'md'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB max file size

# Ensure base directory exists
Path(CMS_BASE_DIR).mkdir(parents=True, exist_ok=True)


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    """Decorator to require login if password is set."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if CMS_PASSWORD and not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
@login_required
def index():
    """Main page showing file browser."""
    return render_template('index.html', base_dir=CMS_BASE_DIR)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page (only shown if CMS_PASSWORD is set)."""
    if not CMS_PASSWORD:
        session['logged_in'] = True
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == CMS_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid password')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout."""
    session.pop('logged_in', None)
    return redirect(url_for('login'))


@app.route('/api/files')
@login_required
def list_files():
    """API endpoint to list files in directory."""
    path = request.args.get('path', '')
    
    # Security: ensure path is within base directory
    if path:
        full_path = os.path.join(CMS_BASE_DIR, path)
        if not os.path.abspath(full_path).startswith(os.path.abspath(CMS_BASE_DIR)):
            return jsonify({'error': 'Invalid path'}), 400
    else:
        full_path = CMS_BASE_DIR
    
    if not os.path.exists(full_path):
        return jsonify({'error': 'Path not found'}), 404
    
    files = []
    directories = []
    
    try:
        for item in os.listdir(full_path):
            item_path = os.path.join(full_path, item)
            rel_path = os.path.relpath(item_path, CMS_BASE_DIR)
            
            item_info = {
                'name': item,
                'path': rel_path.replace('\\', '/'),  # Normalize path separators
                'size': os.path.getsize(item_path) if os.path.isfile(item_path) else 0,
            }
            
            if os.path.isdir(item_path):
                directories.append(item_info)
            elif os.path.isfile(item_path) and (allowed_file(item) or item.startswith('.')):
                item_info['type'] = mimetypes.guess_type(item)[0] or 'application/octet-stream'
                files.append(item_info)
        
        # Sort: directories first, then files
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
    
    if not file_path:
        return jsonify({'error': 'No file path provided'}), 400
    
    # Security check
    full_path = os.path.join(CMS_BASE_DIR, file_path)
    if not os.path.abspath(full_path).startswith(os.path.abspath(CMS_BASE_DIR)):
        return jsonify({'error': 'Invalid path'}), 400
    
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        return jsonify({'error': 'File not found'}), 404
    
    try:
        # Try to read as text first
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
    
    if not file_path:
        return jsonify({'error': 'No file path provided'}), 400
    
    # Security check
    full_path = os.path.join(CMS_BASE_DIR, file_path)
    if not os.path.abspath(full_path).startswith(os.path.abspath(CMS_BASE_DIR)):
        return jsonify({'error': 'Invalid path'}), 400
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    try:
        # Write file
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return jsonify({
            'success': True,
            'path': file_path,
            'size': len(content)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/file', methods=['DELETE'])
@login_required
def delete_file():
    """API endpoint to delete a file."""
    file_path = request.args.get('path', '')
    
    if not file_path:
        return jsonify({'error': 'No file path provided'}), 400
    
    # Security check
    full_path = os.path.join(CMS_BASE_DIR, file_path)
    if not os.path.abspath(full_path).startswith(os.path.abspath(CMS_BASE_DIR)):
        return jsonify({'error': 'Invalid path'}), 400
    
    if not os.path.exists(full_path):
        return jsonify({'error': 'File not found'}), 404
    
    try:
        if os.path.isfile(full_path):
            os.remove(full_path)
        elif os.path.isdir(full_path):
            import shutil
            shutil.rmtree(full_path)
        else:
            return jsonify({'error': 'Not a file or directory'}), 400
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/search')
@login_required
def search_files():
    """API endpoint to search for text in files."""
    query = request.args.get('q', '')
    file_pattern = request.args.get('pattern', '*')
    
    if not query:
        return jsonify({'error': 'No search query provided'}), 400
    
    results = []
    
    try:
        import fnmatch
        for root, dirs, files in os.walk(CMS_BASE_DIR):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                if fnmatch.fnmatch(file, file_pattern):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, CMS_BASE_DIR).replace('\\', '/')
                    
                    if allowed_file(file) or file.startswith('.'):
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                if query.lower() in content.lower():
                                    # Find line numbers
                                    lines = content.split('\n')
                                    matches = []
                                    for i, line in enumerate(lines, 1):
                                        if query.lower() in line.lower():
                                            matches.append({
                                                'line': i,
                                                'text': line.strip()[:200]  # Truncate long lines
                                            })
                                    
                                    if matches:
                                        results.append({
                                            'path': rel_path,
                                            'matches': matches[:10]  # Limit to 10 matches per file
                                        })
                        except:
                            continue
        
        return jsonify({
            'query': query,
            'results': results[:100]  # Limit to 100 files
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
