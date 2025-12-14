"""
Models for Way-CMS multi-tenant system.
"""

import secrets
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from .database import get_db


class User:
    """User model for authentication and authorization."""
    
    def __init__(self, id: int, email: str, name: Optional[str], 
                 password_hash: Optional[str], is_admin: bool,
                 created_at: datetime, last_login: Optional[datetime]):
        self.id = id
        self.email = email
        self.name = name
        self.password_hash = password_hash
        self.is_admin = is_admin
        self.created_at = created_at
        self.last_login = last_login
    
    @classmethod
    def from_row(cls, row) -> Optional['User']:
        """Create User from database row."""
        if not row:
            return None
        return cls(
            id=row['id'],
            email=row['email'],
            name=row['name'],
            password_hash=row['password_hash'],
            is_admin=bool(row['is_admin']),
            created_at=row['created_at'],
            last_login=row['last_login']
        )
    
    @classmethod
    def get_by_id(cls, user_id: int) -> Optional['User']:
        """Get user by ID."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
            return cls.from_row(cursor.fetchone())
    
    @classmethod
    def get_by_email(cls, email: str) -> Optional['User']:
        """Get user by email."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE email = ?', (email.lower(),))
            return cls.from_row(cursor.fetchone())
    
    @classmethod
    def get_all(cls) -> List['User']:
        """Get all users."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
            return [cls.from_row(row) for row in cursor.fetchall()]
    
    @classmethod
    def create(cls, email: str, name: Optional[str] = None, is_admin: bool = False) -> 'User':
        """Create a new user."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO users (email, name, is_admin) VALUES (?, ?, ?)',
                (email.lower(), name, is_admin)
            )
            user_id = cursor.lastrowid
            return cls.get_by_id(user_id)
    
    def update(self, name: Optional[str] = None, is_admin: Optional[bool] = None) -> 'User':
        """Update user details."""
        with get_db() as conn:
            cursor = conn.cursor()
            if name is not None:
                cursor.execute('UPDATE users SET name = ? WHERE id = ?', (name, self.id))
                self.name = name
            if is_admin is not None:
                cursor.execute('UPDATE users SET is_admin = ? WHERE id = ?', (is_admin, self.id))
                self.is_admin = is_admin
        return self
    
    def delete(self) -> bool:
        """Delete user."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM users WHERE id = ?', (self.id,))
            return cursor.rowcount > 0
    
    def set_password(self, password: str) -> None:
        """Set user password."""
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, self.id))
            self.password_hash = password_hash
    
    def check_password(self, password: str) -> bool:
        """Check if password is correct."""
        if not self.password_hash:
            return False
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    def has_password(self) -> bool:
        """Check if user has set a password."""
        return self.password_hash is not None
    
    def update_last_login(self) -> None:
        """Update last login timestamp."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET last_login = ? WHERE id = ?', (datetime.now(), self.id))
            self.last_login = datetime.now()
    
    def get_projects(self) -> List['Project']:
        """Get all projects assigned to this user."""
        if self.is_admin:
            return Project.get_all()
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT p.* FROM projects p
                JOIN user_projects up ON p.id = up.project_id
                WHERE up.user_id = ?
                ORDER BY p.name
            ''', (self.id,))
            return [Project.from_row(row) for row in cursor.fetchall()]
    
    def has_access_to_project(self, project_id: int) -> bool:
        """Check if user has access to a project."""
        if self.is_admin:
            return True
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT 1 FROM user_projects WHERE user_id = ? AND project_id = ?',
                (self.id, project_id)
            )
            return cursor.fetchone() is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'is_admin': self.is_admin,
            'has_password': self.has_password(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }


class Project:
    """Project model representing a website/folder."""
    
    def __init__(self, id: int, name: str, slug: str, 
                 website_url: Optional[str], created_at: datetime):
        self.id = id
        self.name = name
        self.slug = slug
        self.website_url = website_url
        self.created_at = created_at
    
    @classmethod
    def from_row(cls, row) -> Optional['Project']:
        """Create Project from database row."""
        if not row:
            return None
        return cls(
            id=row['id'],
            name=row['name'],
            slug=row['slug'],
            website_url=row['website_url'],
            created_at=row['created_at']
        )
    
    @classmethod
    def get_by_id(cls, project_id: int) -> Optional['Project']:
        """Get project by ID."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
            return cls.from_row(cursor.fetchone())
    
    @classmethod
    def get_by_slug(cls, slug: str) -> Optional['Project']:
        """Get project by slug."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM projects WHERE slug = ?', (slug,))
            return cls.from_row(cursor.fetchone())
    
    @classmethod
    def get_all(cls) -> List['Project']:
        """Get all projects."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM projects ORDER BY name')
            return [cls.from_row(row) for row in cursor.fetchall()]
    
    @classmethod
    def create(cls, name: str, slug: str, website_url: Optional[str] = None) -> 'Project':
        """Create a new project."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO projects (name, slug, website_url) VALUES (?, ?, ?)',
                (name, slug, website_url)
            )
            project_id = cursor.lastrowid
            return cls.get_by_id(project_id)
    
    def update(self, name: Optional[str] = None, website_url: Optional[str] = None) -> 'Project':
        """Update project details (slug cannot be changed)."""
        with get_db() as conn:
            cursor = conn.cursor()
            if name is not None:
                cursor.execute('UPDATE projects SET name = ? WHERE id = ?', (name, self.id))
                self.name = name
            if website_url is not None:
                cursor.execute('UPDATE projects SET website_url = ? WHERE id = ?', (website_url, self.id))
                self.website_url = website_url
        return self
    
    def delete(self) -> bool:
        """Delete project."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM projects WHERE id = ?', (self.id,))
            return cursor.rowcount > 0
    
    def get_users(self) -> List['User']:
        """Get all users assigned to this project."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u.* FROM users u
                JOIN user_projects up ON u.id = up.user_id
                WHERE up.project_id = ?
                ORDER BY u.email
            ''', (self.id,))
            return [User.from_row(row) for row in cursor.fetchall()]
    
    def assign_user(self, user_id: int) -> bool:
        """Assign a user to this project."""
        with get_db() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    'INSERT INTO user_projects (user_id, project_id) VALUES (?, ?)',
                    (user_id, self.id)
                )
                return True
            except Exception:
                return False  # Already assigned
    
    def unassign_user(self, user_id: int) -> bool:
        """Remove a user from this project."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM user_projects WHERE user_id = ? AND project_id = ?',
                (user_id, self.id)
            )
            return cursor.rowcount > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'website_url': self.website_url,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class MagicLink:
    """Magic link model for passwordless authentication."""
    
    TOKEN_LENGTH = 32  # bytes
    DEFAULT_EXPIRY_HOURS = 24
    
    def __init__(self, id: int, token: str, user_id: int,
                 expires_at: datetime, used: bool, created_at: datetime):
        self.id = id
        self.token = token
        self.user_id = user_id
        self.expires_at = expires_at
        self.used = used
        self.created_at = created_at
    
    @classmethod
    def from_row(cls, row) -> Optional['MagicLink']:
        """Create MagicLink from database row."""
        if not row:
            return None
        return cls(
            id=row['id'],
            token=row['token'],
            user_id=row['user_id'],
            expires_at=datetime.fromisoformat(row['expires_at']) if isinstance(row['expires_at'], str) else row['expires_at'],
            used=bool(row['used']),
            created_at=row['created_at']
        )
    
    @classmethod
    def generate_token(cls) -> str:
        """Generate a secure random token."""
        return secrets.token_urlsafe(cls.TOKEN_LENGTH)
    
    @classmethod
    def create(cls, user_id: int, expiry_hours: Optional[int] = None) -> 'MagicLink':
        """Create a new magic link for a user."""
        if expiry_hours is None:
            import os
            expiry_hours = int(os.environ.get('MAGIC_LINK_EXPIRY_HOURS', cls.DEFAULT_EXPIRY_HOURS))
        
        token = cls.generate_token()
        expires_at = datetime.now() + timedelta(hours=expiry_hours)
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO magic_links (token, user_id, expires_at) VALUES (?, ?, ?)',
                (token, user_id, expires_at.isoformat())
            )
            link_id = cursor.lastrowid
            
            cursor.execute('SELECT * FROM magic_links WHERE id = ?', (link_id,))
            return cls.from_row(cursor.fetchone())
    
    @classmethod
    def get_by_token(cls, token: str) -> Optional['MagicLink']:
        """Get magic link by token."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM magic_links WHERE token = ?', (token,))
            return cls.from_row(cursor.fetchone())
    
    def is_valid(self) -> bool:
        """Check if magic link is valid (not used and not expired)."""
        if self.used:
            return False
        if datetime.now() > self.expires_at:
            return False
        return True
    
    def mark_used(self) -> None:
        """Mark the magic link as used."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE magic_links SET used = TRUE WHERE id = ?', (self.id,))
            self.used = True
    
    def get_user(self) -> Optional[User]:
        """Get the user associated with this magic link."""
        return User.get_by_id(self.user_id)
    
    @classmethod
    def cleanup_expired(cls) -> int:
        """Delete expired magic links. Returns count deleted."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM magic_links WHERE expires_at < ? OR used = TRUE',
                (datetime.now().isoformat(),)
            )
            return cursor.rowcount


class UserProject:
    """Helper class for user-project assignments."""
    
    @classmethod
    def get_all_assignments(cls) -> List[Dict[str, Any]]:
        """Get all user-project assignments."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT up.user_id, up.project_id, u.email, u.name as user_name, p.name as project_name, p.slug
                FROM user_projects up
                JOIN users u ON up.user_id = u.id
                JOIN projects p ON up.project_id = p.id
                ORDER BY u.email, p.name
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    @classmethod
    def assign(cls, user_id: int, project_id: int) -> bool:
        """Assign a user to a project."""
        with get_db() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    'INSERT INTO user_projects (user_id, project_id) VALUES (?, ?)',
                    (user_id, project_id)
                )
                return True
            except Exception:
                return False
    
    @classmethod
    def unassign(cls, user_id: int, project_id: int) -> bool:
        """Remove a user from a project."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM user_projects WHERE user_id = ? AND project_id = ?',
                (user_id, project_id)
            )
            return cursor.rowcount > 0

