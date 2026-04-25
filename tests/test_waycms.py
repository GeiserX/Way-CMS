"""Tests for Way-CMS core modules: database, models, auth, email_service."""

import os
import sys
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


# Add cms directory to path (also done in conftest but needed for direct imports)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cms'))


# ---------------------------------------------------------------------------
# database module
# ---------------------------------------------------------------------------

class TestDatabase:
    def test_init_db_creates_tables(self, shared_db):
        cursor = shared_db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        assert 'users' in tables
        assert 'projects' in tables
        assert 'user_projects' in tables
        assert 'magic_links' in tables

    def test_get_db_stats(self):
        from database import get_db_stats
        stats = get_db_stats()
        assert 'users' in stats
        assert 'projects' in stats
        assert 'assignments' in stats

    def test_create_admin_user(self):
        from database import create_admin_user
        user = create_admin_user('admin@test.com', 'password123')
        assert user is not None
        assert user.email == 'admin@test.com'
        assert user.is_admin is True
        assert user.check_password('password123')

    def test_create_admin_user_updates_existing(self):
        from database import create_admin_user
        create_admin_user('admin2@test.com', 'oldpassword')
        user2 = create_admin_user('admin2@test.com', 'newpassword')
        assert user2 is not None
        assert user2.check_password('newpassword')


# ---------------------------------------------------------------------------
# User model
# ---------------------------------------------------------------------------

class TestUserModel:
    def test_create_user(self):
        from models import User
        user = User.create(email='user@test.com', name='Test User')
        assert user is not None
        assert user.email == 'user@test.com'
        assert user.name == 'Test User'
        assert user.is_admin is False

    def test_create_admin_user(self):
        from models import User
        user = User.create(email='useradmin@test.com', name='Admin', is_admin=True)
        assert user is not None
        assert user.is_admin is True

    def test_get_by_id(self):
        from models import User
        created = User.create(email='getbyid@test.com')
        assert created is not None
        fetched = User.get_by_id(created.id)
        assert fetched is not None
        assert fetched.email == 'getbyid@test.com'

    def test_get_by_email(self):
        from models import User
        User.create(email='byemail@test.com')
        fetched = User.get_by_email('byemail@test.com')
        assert fetched is not None

    def test_get_by_email_case_insensitive(self):
        from models import User
        User.create(email='case@test.com')
        fetched = User.get_by_email('CASE@TEST.COM')
        assert fetched is not None

    def test_get_by_email_not_found(self):
        from models import User
        assert User.get_by_email('nonexistent@test.com') is None

    def test_get_all(self):
        from models import User
        User.create(email='all_a@test.com')
        User.create(email='all_b@test.com')
        users = User.get_all()
        emails = [u.email for u in users]
        assert 'all_a@test.com' in emails
        assert 'all_b@test.com' in emails

    def test_update_user(self):
        from models import User
        user = User.create(email='update@test.com', name='Old')
        assert user is not None
        user.update(name='New')
        assert user.name == 'New'
        fetched = User.get_by_id(user.id)
        assert fetched.name == 'New'

    def test_delete_user(self):
        from models import User
        user = User.create(email='delete@test.com')
        assert user is not None
        uid = user.id
        assert user.delete() is True
        assert User.get_by_id(uid) is None

    def test_set_and_check_password(self):
        from models import User
        user = User.create(email='pwd@test.com')
        assert user is not None
        assert user.has_password() is False
        user.set_password('secret123')
        assert user.has_password() is True
        assert user.check_password('secret123') is True
        assert user.check_password('wrong') is False

    def test_check_password_no_hash(self):
        from models import User
        user = User.create(email='nohash@test.com')
        assert user is not None
        assert user.check_password('anything') is False

    def test_update_last_login(self):
        from models import User
        user = User.create(email='login@test.com')
        assert user is not None
        assert user.last_login is None
        user.update_last_login()
        assert user.last_login is not None

    def test_to_dict(self):
        from models import User
        user = User.create(email='dict@test.com', name='DictUser')
        assert user is not None
        d = user.to_dict()
        assert d['email'] == 'dict@test.com'
        assert d['name'] == 'DictUser'
        assert 'password_hash' not in d
        assert 'has_password' in d

    def test_has_access_to_project_admin(self):
        from models import User, Project
        admin = User.create(email='admaccess@test.com', is_admin=True)
        project = Project.create(name='P1', slug='p1')
        assert admin is not None and project is not None
        assert admin.has_access_to_project(project.id) is True

    def test_has_access_to_project_non_admin(self):
        from models import User, Project
        user = User.create(email='noaccess@test.com')
        project = Project.create(name='P2', slug='p2')
        assert user is not None and project is not None
        assert user.has_access_to_project(project.id) is False

    def test_has_access_after_assignment(self):
        from models import User, Project
        user = User.create(email='assigned@test.com')
        project = Project.create(name='P3', slug='p3')
        assert user is not None and project is not None
        project.assign_user(user.id)
        assert user.has_access_to_project(project.id) is True

    def test_get_projects_admin_sees_all(self):
        from models import User, Project
        admin = User.create(email='adminproj@test.com', is_admin=True)
        Project.create(name='Proj1', slug='proj1')
        Project.create(name='Proj2', slug='proj2')
        assert admin is not None
        projects = admin.get_projects()
        assert len(projects) >= 2

    def test_get_projects_regular_user(self):
        from models import User, Project
        user = User.create(email='regproj@test.com')
        p1 = Project.create(name='Assigned', slug='assigned-proj')
        Project.create(name='NotAssigned', slug='not-assigned')
        assert user is not None and p1 is not None
        p1.assign_user(user.id)
        projects = user.get_projects()
        slugs = [p.slug for p in projects]
        assert 'assigned-proj' in slugs


# ---------------------------------------------------------------------------
# Project model
# ---------------------------------------------------------------------------

class TestProjectModel:
    def test_create_project(self):
        from models import Project
        p = Project.create(name='My Site', slug='my-site', website_url='https://example.com')
        assert p is not None
        assert p.name == 'My Site'
        assert p.slug == 'my-site'
        assert p.website_url == 'https://example.com'

    def test_get_by_slug(self):
        from models import Project
        Project.create(name='Sluggy', slug='sluggy')
        found = Project.get_by_slug('sluggy')
        assert found is not None
        assert found.name == 'Sluggy'

    def test_get_by_slug_not_found(self):
        from models import Project
        assert Project.get_by_slug('nonexistent') is None

    def test_update_project(self):
        from models import Project
        p = Project.create(name='Old', slug='old-proj')
        assert p is not None
        p.update(name='New')
        assert p.name == 'New'

    def test_delete_project(self):
        from models import Project
        p = Project.create(name='ToDelete', slug='to-delete')
        assert p is not None
        pid = p.id
        assert p.delete() is True
        assert Project.get_by_id(pid) is None

    def test_assign_and_unassign_user(self):
        from models import User, Project
        user = User.create(email='assigntest@test.com')
        p = Project.create(name='PAssign', slug='p-assign')
        assert user is not None and p is not None
        assert p.assign_user(user.id) is True
        users = p.get_users()
        assert any(u.email == 'assigntest@test.com' for u in users)
        assert p.unassign_user(user.id) is True
        users = p.get_users()
        assert not any(u.email == 'assigntest@test.com' for u in users)

    def test_to_dict(self):
        from models import Project
        p = Project.create(name='DictProj', slug='dict-proj')
        assert p is not None
        d = p.to_dict()
        assert d['name'] == 'DictProj'
        assert d['slug'] == 'dict-proj'


# ---------------------------------------------------------------------------
# MagicLink model
# ---------------------------------------------------------------------------

class TestMagicLinkModel:
    def test_create_magic_link(self):
        from models import User, MagicLink
        user = User.create(email='magic@test.com')
        assert user is not None
        link = MagicLink.create(user.id, expiry_hours=1)
        assert link is not None
        assert link.user_id == user.id
        assert link.used is False

    def test_get_by_token(self):
        from models import User, MagicLink
        user = User.create(email='token@test.com')
        assert user is not None
        link = MagicLink.create(user.id, expiry_hours=1)
        assert link is not None
        found = MagicLink.get_by_token(link.token)
        assert found is not None
        assert found.id == link.id

    def test_is_valid_fresh_link(self):
        from models import User, MagicLink
        user = User.create(email='valid@test.com')
        assert user is not None
        link = MagicLink.create(user.id, expiry_hours=1)
        assert link is not None
        assert link.is_valid() is True

    def test_is_valid_used_link(self):
        from models import User, MagicLink
        user = User.create(email='used@test.com')
        assert user is not None
        link = MagicLink.create(user.id, expiry_hours=1)
        assert link is not None
        link.mark_used()
        assert link.is_valid() is False

    def test_is_valid_expired_link(self):
        from models import User, MagicLink
        user = User.create(email='expired@test.com')
        assert user is not None
        link = MagicLink.create(user.id, expiry_hours=1)
        assert link is not None
        link.expires_at = datetime.now() - timedelta(hours=2)
        assert link.is_valid() is False

    def test_mark_used(self):
        from models import User, MagicLink
        user = User.create(email='markused@test.com')
        assert user is not None
        link = MagicLink.create(user.id, expiry_hours=1)
        assert link is not None
        link.mark_used()
        assert link.used is True
        found = MagicLink.get_by_token(link.token)
        assert found.used is True

    def test_get_user(self):
        from models import User, MagicLink
        user = User.create(email='getuser@test.com')
        assert user is not None
        link = MagicLink.create(user.id, expiry_hours=1)
        assert link is not None
        found_user = link.get_user()
        assert found_user.email == 'getuser@test.com'

    def test_generate_token_unique(self):
        from models import MagicLink
        t1 = MagicLink.generate_token()
        t2 = MagicLink.generate_token()
        assert t1 != t2

    def test_cleanup_expired(self):
        from models import User, MagicLink
        user = User.create(email='cleanup@test.com')
        assert user is not None
        link = MagicLink.create(user.id, expiry_hours=1)
        assert link is not None
        link.mark_used()
        count = MagicLink.cleanup_expired()
        assert count >= 1


# ---------------------------------------------------------------------------
# UserProject model
# ---------------------------------------------------------------------------

class TestUserProjectModel:
    def test_assign_and_get_all(self):
        from models import User, Project, UserProject
        user = User.create(email='up@test.com')
        proj = Project.create(name='UP', slug='up-proj')
        assert user is not None and proj is not None
        UserProject.assign(user.id, proj.id)
        assignments = UserProject.get_all_assignments()
        assert len(assignments) >= 1

    def test_unassign(self):
        from models import User, Project, UserProject
        user = User.create(email='unassign@test.com')
        proj = Project.create(name='UnAss', slug='unass-proj')
        assert user is not None and proj is not None
        UserProject.assign(user.id, proj.id)
        assert UserProject.unassign(user.id, proj.id) is True
        assert UserProject.unassign(user.id, proj.id) is False


# ---------------------------------------------------------------------------
# auth module
# ---------------------------------------------------------------------------

class TestAuthModule:
    def test_authenticate_with_password_success(self):
        from models import User
        from auth import authenticate_with_password
        user = User.create(email='authpwd@test.com')
        assert user is not None
        user.set_password('testpass')
        ok, found_user, err = authenticate_with_password('authpwd@test.com', 'testpass')
        assert ok is True
        assert found_user.email == 'authpwd@test.com'
        assert err == ''

    def test_authenticate_with_password_wrong_password(self):
        from models import User
        from auth import authenticate_with_password
        user = User.create(email='wrongpwd@test.com')
        assert user is not None
        user.set_password('correct')
        ok, _, err = authenticate_with_password('wrongpwd@test.com', 'incorrect')
        assert ok is False
        assert 'Invalid' in err

    def test_authenticate_with_password_no_user(self):
        from auth import authenticate_with_password
        ok, _, err = authenticate_with_password('nobody@test.com', 'pass')
        assert ok is False

    def test_authenticate_with_password_no_password_set(self):
        from models import User
        from auth import authenticate_with_password
        User.create(email='nopwd@test.com')
        ok, _, err = authenticate_with_password('nopwd@test.com', 'any')
        assert ok is False
        assert 'magic link' in err.lower() or 'password' in err.lower()

    def test_verify_magic_link_success(self):
        from models import User, MagicLink
        from auth import verify_magic_link
        user = User.create(email='verifyml@test.com')
        assert user is not None
        link = MagicLink.create(user.id, expiry_hours=1)
        assert link is not None
        ok, found, err = verify_magic_link(link.token)
        assert ok is True
        assert found.email == 'verifyml@test.com'

    def test_verify_magic_link_invalid_token(self):
        from auth import verify_magic_link
        ok, _, err = verify_magic_link('invalid-token-xyz')
        assert ok is False
        assert 'Invalid' in err or 'expired' in err

    def test_get_magic_link_url(self):
        from auth import get_magic_link_url
        url = get_magic_link_url('abc123')
        assert 'auth/verify/abc123' in url

    def test_get_project_path(self):
        from models import Project
        from auth import get_project_path
        p = Project.create(name='Path', slug='path-test')
        assert p is not None
        path = get_project_path(p)
        assert 'path-test' in path


# ---------------------------------------------------------------------------
# EmailConfig
# ---------------------------------------------------------------------------

class TestEmailConfig:
    def test_not_configured_by_default(self):
        from email_service import EmailConfig
        env = {k: v for k, v in os.environ.items() if not k.startswith('SMTP')}
        with patch.dict(os.environ, env, clear=True):
            assert EmailConfig.is_configured() is False

    def test_configured_with_all_vars(self):
        from email_service import EmailConfig
        env = {
            'SMTP_HOST': 'smtp.test.com',
            'SMTP_PORT': '587',
            'SMTP_USER': 'user@test.com',
            'SMTP_PASSWORD': 'secret',
            'SMTP_FROM': 'noreply@test.com',
        }
        with patch.dict(os.environ, env):
            assert EmailConfig.is_configured() is True

    def test_port_465_ssl_detection(self):
        from email_service import EmailConfig
        env = {
            'SMTP_HOST': 'smtp.test.com',
            'SMTP_PORT': '465',
            'SMTP_USER': 'user@test.com',
            'SMTP_PASSWORD': 'secret',
            'SMTP_FROM': 'noreply@test.com',
        }
        with patch.dict(os.environ, env):
            config = EmailConfig.get_config()
            assert config['use_tls'] is False

    def test_port_587_tls_detection(self):
        from email_service import EmailConfig
        env = {
            'SMTP_HOST': 'smtp.test.com',
            'SMTP_PORT': '587',
            'SMTP_USER': 'user@test.com',
            'SMTP_PASSWORD': 'secret',
            'SMTP_FROM': 'noreply@test.com',
        }
        with patch.dict(os.environ, env):
            config = EmailConfig.get_config()
            assert config['use_tls'] is True

    def test_explicit_tls_override(self):
        from email_service import EmailConfig
        env = {
            'SMTP_HOST': 'smtp.test.com',
            'SMTP_PORT': '465',
            'SMTP_USER': 'user@test.com',
            'SMTP_PASSWORD': 'secret',
            'SMTP_FROM': 'noreply@test.com',
            'SMTP_USE_TLS': 'true',
        }
        with patch.dict(os.environ, env):
            config = EmailConfig.get_config()
            assert config['use_tls'] is True


# ---------------------------------------------------------------------------
# EmailService
# ---------------------------------------------------------------------------

class TestEmailService:
    def test_send_email_not_configured(self):
        from email_service import EmailService
        env = {k: v for k, v in os.environ.items() if not k.startswith('SMTP')}
        with patch.dict(os.environ, env, clear=True):
            svc = EmailService()
            ok, err = svc.send_email('to@test.com', 'Subject', '<p>body</p>')
            assert ok is False
            assert 'not configured' in err.lower()

    @patch('email_service.smtplib.SMTP')
    def test_send_email_success(self, mock_smtp):
        from email_service import EmailService
        env = {
            'SMTP_HOST': 'smtp.test.com',
            'SMTP_PORT': '587',
            'SMTP_USER': 'user@test.com',
            'SMTP_PASSWORD': 'secret',
            'SMTP_FROM': 'noreply@test.com',
        }
        with patch.dict(os.environ, env):
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            svc = EmailService()
            ok, err = svc.send_email('to@test.com', 'Test', '<p>hi</p>')
            assert ok is True
            mock_server.send_message.assert_called_once()
