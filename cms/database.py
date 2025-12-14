"""
Database module for Way-CMS multi-tenant system.
Uses SQLite for storing users, projects, and assignments.
"""

import sqlite3
import os
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime

# Database configuration
DATA_DIR = os.environ.get('DATA_DIR', '/.way-cms-data')
DB_PATH = os.path.join(DATA_DIR, 'waycms.db')

# Ensure data directory exists
def ensure_data_dir():
    """Create data directory if it doesn't exist."""
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

@contextmanager
def get_db():
    """Context manager for database connections."""
    ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key support
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Initialize the database schema."""
    ensure_data_dir()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                password_hash TEXT,
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        ''')
        
        # Projects table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                website_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # User-Project assignments (many-to-many)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_projects (
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                PRIMARY KEY (user_id, project_id)
            )
        ''')
        
        # Magic links for email authentication
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS magic_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_projects_slug ON projects(slug)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_magic_links_token ON magic_links(token)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_projects_user ON user_projects(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_projects_project ON user_projects(project_id)')
        
        print(f"[Database] Initialized at {DB_PATH}")

def migrate_from_single_tenant(old_base_dir, project_name, project_slug):
    """
    Migrate from single-tenant setup to multi-tenant.
    Creates a project entry for the existing website folder.
    """
    from models import Project
    
    # Check if project already exists
    existing = Project.get_by_slug(project_slug)
    if existing:
        print(f"[Migration] Project '{project_slug}' already exists, skipping")
        return existing
    
    # Create the project
    project = Project.create(
        name=project_name,
        slug=project_slug,
        website_url=os.environ.get('WEBSITE_URL', '')
    )
    
    print(f"[Migration] Created project '{project_name}' with slug '{project_slug}'")
    return project

def create_admin_user(email, password):
    """Create the initial admin user if it doesn't exist, or update password if it does."""
    from models import User
    
    existing = User.get_by_email(email)
    if existing:
        # User exists - update password if provided and ensure admin status
        if password:
            existing.set_password(password)
            print(f"[Database] Updated password for admin user '{email}'")
        if not existing.is_admin:
            existing.update(is_admin=True)
            print(f"[Database] Granted admin privileges to '{email}'")
        return existing
    
    user = User.create(email=email, name='Admin', is_admin=True)
    user.set_password(password)
    
    print(f"[Database] Created admin user '{email}'")
    return user

def check_db_exists():
    """Check if database file exists."""
    return os.path.exists(DB_PATH)

def get_db_stats():
    """Get database statistics."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM projects')
        project_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM user_projects')
        assignment_count = cursor.fetchone()[0]
        
        return {
            'users': user_count,
            'projects': project_count,
            'assignments': assignment_count,
            'db_path': DB_PATH
        }

