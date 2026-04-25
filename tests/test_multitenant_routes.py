"""Tests for Way-CMS multi-tenant admin and auth routes.

Covers admin_routes.py and auth_routes.py blueprints with
database-backed users, projects, and assignments.
"""

import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cms'))


@pytest.fixture()
def mt_client(shared_db, tmp_path, monkeypatch):
    """Create a Flask test client with multi-tenant blueprints registered."""
    import importlib

    base_dir = str(tmp_path / "projects")
    backup_dir = str(tmp_path / "backups")
    os.makedirs(base_dir, exist_ok=True)
    os.makedirs(backup_dir, exist_ok=True)

    monkeypatch.setenv('MULTI_TENANT', 'false')  # We register blueprints manually
    monkeypatch.setenv('AUTO_BACKUP_ENABLED', 'false')
    monkeypatch.setenv('SECRET_KEY', 'test-secret')
    monkeypatch.setenv('CMS_BASE_DIR', str(tmp_path / "website"))
    monkeypatch.setenv('BACKUP_DIR', backup_dir)
    monkeypatch.setenv('CMS_PASSWORD', '')
    monkeypatch.setenv('CMS_PASSWORD_HASH', '')

    import auth as auth_module
    import app as app_module
    importlib.reload(auth_module)
    importlib.reload(app_module)

    app_module.AUTO_BACKUP_ENABLED = False
    app_module.app.config['TESTING'] = True
    app_module.app.config['SECRET_KEY'] = 'test-secret'

    # Register blueprints if not already registered
    from admin_routes import admin_bp
    from auth_routes import auth_bp

    # Check if already registered (from previous test or reload)
    registered = [bp.name for bp in app_module.app.blueprints.values()]
    if 'admin' not in registered:
        app_module.app.register_blueprint(admin_bp)
    if 'auth' not in registered:
        app_module.app.register_blueprint(auth_bp)

    with app_module.app.test_client() as c:
        yield c, app_module


def _create_admin(password='adminpass'):
    """Create an admin user for tests."""
    from models import User
    user = User.create(email='admin@test.com', name='Admin', is_admin=True)
    user.set_password(password)
    return user


def _create_regular_user(email='user@test.com', password='userpass'):
    """Create a regular user."""
    from models import User
    user = User.create(email=email, name='Regular', is_admin=False)
    if password:
        user.set_password(password)
    return user


def _login_as(client, email, password):
    """Log in via the auth blueprint password endpoint."""
    return client.post('/auth/login', json={
        'email': email,
        'password': password,
    })


def _login_admin(client):
    """Create admin and log in."""
    admin = _create_admin()
    _login_as(client, 'admin@test.com', 'adminpass')
    return admin


# ---------------------------------------------------------------------------
# Auth Routes
# ---------------------------------------------------------------------------

class TestAuthRoutes:
    def test_login_with_password_json(self, mt_client):
        c, _ = mt_client
        _create_admin()
        resp = _login_as(c, 'admin@test.com', 'adminpass')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_login_with_password_wrong(self, mt_client):
        c, _ = mt_client
        _create_admin()
        resp = _login_as(c, 'admin@test.com', 'wrong')
        assert resp.status_code == 401

    def test_login_missing_fields(self, mt_client):
        c, _ = mt_client
        resp = c.post('/auth/login', json={'email': '', 'password': ''})
        assert resp.status_code == 400

    def test_login_form_post(self, mt_client):
        c, _ = mt_client
        _create_admin()
        resp = c.post('/auth/login', data={
            'email': 'admin@test.com',
            'password': 'adminpass',
        })
        # Should redirect on success
        assert resp.status_code == 302

    def test_login_form_wrong_password(self, mt_client):
        c, _ = mt_client
        _create_admin()
        resp = c.post('/auth/login', data={
            'email': 'admin@test.com',
            'password': 'wrong',
        })
        assert resp.status_code == 200  # renders login page with error

    def test_login_no_password_set(self, mt_client):
        c, _ = mt_client
        from models import User
        User.create(email='nopwd@test.com', name='NoPwd')
        resp = _login_as(c, 'nopwd@test.com', 'anything')
        assert resp.status_code == 401

    def test_verify_token_success(self, mt_client):
        c, _ = mt_client
        from models import User, MagicLink
        user = User.create(email='verify@test.com', name='V')
        link = MagicLink.create(user.id, expiry_hours=1)
        resp = c.get(f'/auth/verify/{link.token}')
        assert resp.status_code == 302  # redirect to index

    def test_verify_token_invalid(self, mt_client):
        c, _ = mt_client
        resp = c.get('/auth/verify/invalid-token')
        assert resp.status_code == 200  # renders login with error

    def test_set_password_new(self, mt_client):
        c, _ = mt_client
        from models import User
        user = User.create(email='setpwd@test.com', name='SetPwd')
        # Login via magic link to set session
        from models import MagicLink
        link = MagicLink.create(user.id, expiry_hours=1)
        c.get(f'/auth/verify/{link.token}')
        resp = c.post('/auth/set-password', json={
            'password': 'newpassword123',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_set_password_change_existing(self, mt_client):
        c, _ = mt_client
        _create_admin()
        _login_as(c, 'admin@test.com', 'adminpass')
        resp = c.post('/auth/set-password', json={
            'current_password': 'adminpass',
            'password': 'newpassword123',
        })
        assert resp.status_code == 200

    def test_set_password_wrong_current(self, mt_client):
        c, _ = mt_client
        _create_admin()
        _login_as(c, 'admin@test.com', 'adminpass')
        resp = c.post('/auth/set-password', json={
            'current_password': 'wrong',
            'password': 'newpassword123',
        })
        assert resp.status_code == 401

    def test_set_password_too_short(self, mt_client):
        c, _ = mt_client
        _create_admin()
        _login_as(c, 'admin@test.com', 'adminpass')
        resp = c.post('/auth/set-password', json={
            'current_password': 'adminpass',
            'password': 'short',
        })
        assert resp.status_code == 400

    def test_set_password_empty(self, mt_client):
        c, _ = mt_client
        _create_admin()
        _login_as(c, 'admin@test.com', 'adminpass')
        resp = c.post('/auth/set-password', json={'password': ''})
        assert resp.status_code == 400

    def test_set_password_not_logged_in(self, mt_client):
        c, _ = mt_client
        resp = c.post('/auth/set-password', json={'password': 'newpass123'})
        assert resp.status_code == 401

    def test_get_me(self, mt_client):
        c, _ = mt_client
        _create_admin()
        _login_as(c, 'admin@test.com', 'adminpass')
        resp = c.get('/auth/me')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['user']['email'] == 'admin@test.com'

    def test_get_me_not_logged_in(self, mt_client):
        c, _ = mt_client
        resp = c.get('/auth/me', headers={'Accept': 'application/json'})
        assert resp.status_code == 401

    def test_switch_project(self, mt_client):
        c, _ = mt_client
        from models import Project
        _create_admin()
        _login_as(c, 'admin@test.com', 'adminpass')
        project = Project.create(name='Test', slug='test-proj')
        resp = c.post('/auth/switch-project', json={'project_id': project.id})
        assert resp.status_code == 200

    def test_switch_project_not_found(self, mt_client):
        c, _ = mt_client
        _create_admin()
        _login_as(c, 'admin@test.com', 'adminpass')
        resp = c.post('/auth/switch-project', json={'project_id': 99999})
        assert resp.status_code == 404

    def test_switch_project_no_id(self, mt_client):
        c, _ = mt_client
        _create_admin()
        _login_as(c, 'admin@test.com', 'adminpass')
        resp = c.post('/auth/switch-project', json={})
        assert resp.status_code == 400

    def test_switch_project_access_denied(self, mt_client):
        c, _ = mt_client
        from models import Project
        _create_regular_user()
        _login_as(c, 'user@test.com', 'userpass')
        project = Project.create(name='Secret', slug='secret-proj')
        resp = c.post('/auth/switch-project', json={'project_id': project.id})
        assert resp.status_code == 403

    def test_logout_auth(self, mt_client):
        c, _ = mt_client
        _create_admin()
        _login_as(c, 'admin@test.com', 'adminpass')
        resp = c.get('/auth/logout')
        assert resp.status_code == 302

    def test_check_email_exists(self, mt_client):
        c, _ = mt_client
        _create_admin()
        resp = c.post('/auth/check-email', json={'email': 'admin@test.com'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['exists'] is True
        assert data['has_password'] is True

    def test_check_email_not_found(self, mt_client):
        c, _ = mt_client
        resp = c.post('/auth/check-email', json={'email': 'nobody@test.com'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['exists'] is False

    def test_check_email_empty(self, mt_client):
        c, _ = mt_client
        resp = c.post('/auth/check-email', json={'email': ''})
        assert resp.status_code == 400

    @patch('auth_routes.EmailConfig')
    @patch('auth_routes.get_email_service')
    def test_request_magic_link(self, mock_email_svc, mock_config, mt_client):
        c, _ = mt_client
        _create_admin()
        mock_config.is_configured.return_value = True
        mock_svc = MagicMock()
        mock_svc.send_magic_link.return_value = (True, '')
        mock_email_svc.return_value = mock_svc
        resp = c.post('/auth/magic-link', json={'email': 'admin@test.com'})
        assert resp.status_code == 200

    def test_request_magic_link_no_email(self, mt_client):
        c, _ = mt_client
        resp = c.post('/auth/magic-link', json={'email': ''})
        assert resp.status_code == 400

    def test_request_magic_link_unknown_user(self, mt_client):
        c, _ = mt_client
        resp = c.post('/auth/magic-link', json={'email': 'unknown@test.com'})
        # Should still return success (don't reveal user existence)
        assert resp.status_code == 200

    @patch('auth_routes.EmailConfig')
    def test_request_magic_link_email_not_configured(self, mock_config, mt_client):
        c, _ = mt_client
        _create_admin()
        mock_config.is_configured.return_value = False
        resp = c.post('/auth/magic-link', json={'email': 'admin@test.com'})
        assert resp.status_code == 500

    @patch('auth_routes.EmailConfig')
    @patch('auth_routes.get_email_service')
    def test_request_magic_link_email_fails(self, mock_email_svc, mock_config, mt_client):
        c, _ = mt_client
        _create_admin()
        mock_config.is_configured.return_value = True
        mock_svc = MagicMock()
        mock_svc.send_magic_link.return_value = (False, 'SMTP error')
        mock_email_svc.return_value = mock_svc
        resp = c.post('/auth/magic-link', json={'email': 'admin@test.com'})
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# Admin Routes - User Management
# ---------------------------------------------------------------------------

class TestAdminUserManagement:
    def test_admin_panel(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        resp = c.get('/admin')
        assert resp.status_code == 200

    def test_admin_panel_not_admin(self, mt_client):
        c, _ = mt_client
        _create_regular_user()
        _login_as(c, 'user@test.com', 'userpass')
        resp = c.get('/admin', headers={'Accept': 'application/json'})
        assert resp.status_code == 403

    def test_admin_panel_not_logged_in(self, mt_client):
        c, _ = mt_client
        resp = c.get('/admin', headers={'Accept': 'application/json'})
        assert resp.status_code == 401

    def test_list_users(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        resp = c.get('/admin/users')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'users' in data

    def test_create_user(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        resp = c.post('/admin/users', json={
            'email': 'new@test.com',
            'name': 'New User',
            'password': 'password123',
            'is_admin': False,
            'send_welcome_email': False,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['user']['email'] == 'new@test.com'

    def test_create_user_no_email(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        resp = c.post('/admin/users', json={
            'email': '',
            'name': 'No Email',
            'send_welcome_email': False,
        })
        assert resp.status_code == 400

    def test_create_user_duplicate(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        c.post('/admin/users', json={
            'email': 'dup@test.com',
            'password': 'pass1234',
            'send_welcome_email': False,
        })
        resp = c.post('/admin/users', json={
            'email': 'dup@test.com',
            'password': 'pass1234',
            'send_welcome_email': False,
        })
        assert resp.status_code == 400

    def test_create_user_no_password_no_email(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        resp = c.post('/admin/users', json={
            'email': 'nopwd@test.com',
            'send_welcome_email': False,
        })
        assert resp.status_code == 400

    def test_create_user_with_projects(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        from models import Project
        proj = Project.create(name='ForUser', slug='for-user')
        resp = c.post('/admin/users', json={
            'email': 'withproj@test.com',
            'password': 'password123',
            'project_ids': [proj.id],
            'send_welcome_email': False,
        })
        assert resp.status_code == 200

    @patch('admin_routes.EmailConfig')
    @patch('admin_routes.get_email_service')
    def test_create_user_with_welcome_email(self, mock_email_svc, mock_config, mt_client):
        c, _ = mt_client
        _login_admin(c)
        mock_config.is_configured.return_value = True
        mock_svc = MagicMock()
        mock_svc.send_welcome_email.return_value = (True, '')
        mock_email_svc.return_value = mock_svc
        resp = c.post('/admin/users', json={
            'email': 'welcome@test.com',
            'name': 'Welcome',
            'send_welcome_email': True,
        })
        assert resp.status_code == 200

    @patch('admin_routes.EmailConfig')
    @patch('admin_routes.get_email_service')
    def test_create_user_welcome_email_fails(self, mock_email_svc, mock_config, mt_client):
        c, _ = mt_client
        _login_admin(c)
        mock_config.is_configured.return_value = True
        mock_svc = MagicMock()
        mock_svc.send_welcome_email.return_value = (False, 'SMTP error')
        mock_email_svc.return_value = mock_svc
        resp = c.post('/admin/users', json={
            'email': 'failmail@test.com',
            'name': 'FailMail',
            'send_welcome_email': True,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'warning' in data

    def test_update_user(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        from models import User
        user = User.create(email='upd@test.com', name='Old')
        resp = c.put(f'/admin/users/{user.id}', json={
            'name': 'Updated',
            'is_admin': True,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['user']['name'] == 'Updated'

    def test_update_user_not_found(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        resp = c.put('/admin/users/99999', json={'name': 'X'})
        assert resp.status_code == 404

    def test_delete_user(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        from models import User
        user = User.create(email='del@test.com')
        resp = c.delete(f'/admin/users/{user.id}')
        assert resp.status_code == 200

    def test_delete_user_not_found(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        resp = c.delete('/admin/users/99999')
        assert resp.status_code == 404

    def test_delete_self_prevented(self, mt_client):
        c, _ = mt_client
        admin = _login_admin(c)
        resp = c.delete(f'/admin/users/{admin.id}')
        assert resp.status_code == 400

    @patch('admin_routes.EmailConfig')
    @patch('admin_routes.get_email_service')
    def test_send_magic_link_to_user(self, mock_email_svc, mock_config, mt_client):
        c, _ = mt_client
        _login_admin(c)
        from models import User
        user = User.create(email='sendlink@test.com', name='SL')
        mock_config.is_configured.return_value = True
        mock_svc = MagicMock()
        mock_svc.send_magic_link.return_value = (True, '')
        mock_email_svc.return_value = mock_svc
        resp = c.post(f'/admin/users/{user.id}/send-link')
        assert resp.status_code == 200

    def test_send_magic_link_user_not_found(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        resp = c.post('/admin/users/99999/send-link')
        assert resp.status_code == 404

    @patch('admin_routes.EmailConfig')
    def test_send_magic_link_email_not_configured(self, mock_config, mt_client):
        c, _ = mt_client
        _login_admin(c)
        from models import User
        user = User.create(email='noconfig@test.com')
        mock_config.is_configured.return_value = False
        resp = c.post(f'/admin/users/{user.id}/send-link')
        assert resp.status_code == 400

    @patch('admin_routes.EmailConfig')
    @patch('admin_routes.get_email_service')
    def test_send_magic_link_email_fails(self, mock_email_svc, mock_config, mt_client):
        c, _ = mt_client
        _login_admin(c)
        from models import User
        user = User.create(email='failsend@test.com')
        mock_config.is_configured.return_value = True
        mock_svc = MagicMock()
        mock_svc.send_magic_link.return_value = (False, 'SMTP error')
        mock_email_svc.return_value = mock_svc
        resp = c.post(f'/admin/users/{user.id}/send-link')
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# Admin Routes - Project Management
# ---------------------------------------------------------------------------

class TestAdminProjectManagement:
    def test_list_projects(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        resp = c.get('/admin/projects')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'projects' in data

    @patch('auth.ensure_project_dir')
    def test_create_project(self, mock_ensure, mt_client):
        c, _ = mt_client
        _login_admin(c)
        mock_ensure.return_value = '/tmp/fake-project-dir'
        resp = c.post('/admin/projects', json={
            'name': 'New Project',
            'slug': 'new-project',
            'website_url': 'https://example.com',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['project']['slug'] == 'new-project'

    def test_create_project_no_name(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        resp = c.post('/admin/projects', json={
            'name': '',
            'slug': 'no-name',
        })
        assert resp.status_code == 400

    def test_create_project_no_slug(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        resp = c.post('/admin/projects', json={
            'name': 'No Slug',
            'slug': '',
        })
        assert resp.status_code == 400

    def test_create_project_invalid_slug(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        resp = c.post('/admin/projects', json={
            'name': 'Bad Slug',
            'slug': 'Bad Slug!',
        })
        assert resp.status_code == 400

    @patch('auth.ensure_project_dir')
    def test_create_project_duplicate_slug(self, mock_ensure, mt_client):
        c, _ = mt_client
        _login_admin(c)
        mock_ensure.return_value = '/tmp/fake-dir'
        c.post('/admin/projects', json={'name': 'P1', 'slug': 'dupslug'})
        resp = c.post('/admin/projects', json={'name': 'P2', 'slug': 'dupslug'})
        assert resp.status_code == 400

    def test_update_project(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        from models import Project
        proj = Project.create(name='Old', slug='old-proj')
        resp = c.put(f'/admin/projects/{proj.id}', json={
            'name': 'Updated',
            'website_url': 'https://new.com',
        })
        assert resp.status_code == 200

    def test_update_project_not_found(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        resp = c.put('/admin/projects/99999', json={'name': 'X'})
        assert resp.status_code == 404

    def test_delete_project(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        from models import Project
        proj = Project.create(name='Delete', slug='del-proj')
        resp = c.delete(f'/admin/projects/{proj.id}')
        assert resp.status_code == 200

    def test_delete_project_not_found(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        resp = c.delete('/admin/projects/99999')
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Admin Routes - Assignments
# ---------------------------------------------------------------------------

class TestAdminAssignments:
    def test_list_assignments(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        resp = c.get('/admin/assignments')
        assert resp.status_code == 200

    def test_assign_user_to_project(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        from models import User, Project
        user = User.create(email='assign@test.com')
        proj = Project.create(name='Assign', slug='assign-proj')
        resp = c.post('/admin/assignments', json={
            'user_id': user.id,
            'project_id': proj.id,
        })
        assert resp.status_code == 200

    def test_assign_missing_ids(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        resp = c.post('/admin/assignments', json={})
        assert resp.status_code == 400

    def test_assign_user_not_found(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        from models import Project
        proj = Project.create(name='X', slug='x-proj')
        resp = c.post('/admin/assignments', json={
            'user_id': 99999,
            'project_id': proj.id,
        })
        assert resp.status_code == 404

    def test_assign_project_not_found(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        from models import User
        user = User.create(email='noprj@test.com')
        resp = c.post('/admin/assignments', json={
            'user_id': user.id,
            'project_id': 99999,
        })
        assert resp.status_code == 404

    def test_assign_duplicate(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        from models import User, Project
        user = User.create(email='dupas@test.com')
        proj = Project.create(name='DupAs', slug='dupas-proj')
        c.post('/admin/assignments', json={
            'user_id': user.id,
            'project_id': proj.id,
        })
        resp = c.post('/admin/assignments', json={
            'user_id': user.id,
            'project_id': proj.id,
        })
        assert resp.status_code == 400

    def test_unassign_user_from_project(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        from models import User, Project, UserProject
        user = User.create(email='unas@test.com')
        proj = Project.create(name='UnAs', slug='unas-proj')
        UserProject.assign(user.id, proj.id)
        resp = c.delete(f'/admin/assignments?user_id={user.id}&project_id={proj.id}')
        assert resp.status_code == 200

    def test_unassign_missing_ids(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        resp = c.delete('/admin/assignments')
        assert resp.status_code == 400

    def test_unassign_not_found(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        resp = c.delete('/admin/assignments?user_id=99999&project_id=99999')
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Admin Routes - Email & Stats
# ---------------------------------------------------------------------------

class TestAdminEmailAndStats:
    @patch('admin_routes.get_email_service')
    def test_test_email(self, mock_email_svc, mt_client):
        c, _ = mt_client
        _login_admin(c)
        mock_svc = MagicMock()
        mock_svc.test_connection.return_value = (True, 'OK')
        mock_email_svc.return_value = mock_svc
        resp = c.post('/admin/email/test')
        assert resp.status_code == 200

    def test_get_email_config(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        resp = c.get('/admin/email/config')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'configured' in data

    def test_get_stats(self, mt_client):
        c, _ = mt_client
        _login_admin(c)
        resp = c.get('/admin/stats')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'users' in data
        assert 'projects' in data


# ---------------------------------------------------------------------------
# Auth module functions
# ---------------------------------------------------------------------------

class TestAuthModuleFunctions:
    def test_get_current_user_no_session(self, mt_client):
        c, app_mod = mt_client
        with app_mod.app.test_request_context('/'):
            from auth import get_current_user
            assert get_current_user() is None

    def test_get_current_project_no_session(self, mt_client):
        c, app_mod = mt_client
        with app_mod.app.test_request_context('/'):
            from auth import get_current_project
            assert get_current_project() is None

    def test_login_user_sets_session(self, mt_client):
        c, app_mod = mt_client
        from models import User
        from auth import login_user
        user = User.create(email='sessiontest@test.com', name='Session')
        user.set_password('pass')
        with app_mod.app.test_request_context('/'):
            from flask import session as flask_session
            login_user(user)
            assert flask_session.get('user_id') == user.id

    def test_logout_clears_session(self, mt_client):
        c, app_mod = mt_client
        from auth import logout_user
        with app_mod.app.test_request_context('/'):
            from flask import session as flask_session
            flask_session['user_id'] = 1
            logout_user()
            assert 'user_id' not in flask_session

    def test_set_current_project_session(self, mt_client):
        c, app_mod = mt_client
        from models import Project
        from auth import set_current_project
        proj = Project.create(name='SessProj', slug='sess-proj')
        with app_mod.app.test_request_context('/'):
            from flask import session as flask_session
            set_current_project(proj)
            assert flask_session['current_project_id'] == proj.id
            assert flask_session['current_project_slug'] == 'sess-proj'

    def test_ensure_project_dir(self, mt_client, tmp_path):
        c, _ = mt_client
        from models import Project
        from auth import ensure_project_dir
        proj = Project.create(name='EnsDir', slug='ens-dir')
        with patch('auth.get_projects_base_dir', return_value=str(tmp_path)):
            path = ensure_project_dir(proj)
            assert os.path.isdir(path)

    def test_create_magic_link(self, mt_client):
        c, _ = mt_client
        from models import User
        from auth import create_magic_link
        user = User.create(email='cml@test.com')
        link = create_magic_link(user)
        assert link is not None
        assert link.user_id == user.id

    def test_verify_magic_link_used(self, mt_client):
        c, _ = mt_client
        from models import User, MagicLink
        from auth import verify_magic_link
        user = User.create(email='usedlink@test.com')
        link = MagicLink.create(user.id, expiry_hours=1)
        link.mark_used()
        ok, _, err = verify_magic_link(link.token)
        assert ok is False


# ---------------------------------------------------------------------------
# Email Service additional coverage
# ---------------------------------------------------------------------------

class TestEmailServiceAdditional:
    @patch('email_service.smtplib.SMTP_SSL')
    def test_send_email_ssl(self, mock_smtp_ssl, mt_client):
        from email_service import EmailService
        env = {
            'SMTP_HOST': 'smtp.test.com',
            'SMTP_PORT': '465',
            'SMTP_USER': 'user@test.com',
            'SMTP_PASSWORD': 'secret',
            'SMTP_FROM': 'noreply@test.com',
        }
        with patch.dict(os.environ, env):
            mock_server = MagicMock()
            mock_smtp_ssl.return_value = mock_server
            svc = EmailService()
            ok, err = svc.send_email('to@test.com', 'Test', '<p>hi</p>', 'hi')
            assert ok is True

    @patch('email_service.smtplib.SMTP')
    def test_send_email_auth_error(self, mock_smtp, mt_client):
        import smtplib
        from email_service import EmailService
        env = {
            'SMTP_HOST': 'smtp.test.com',
            'SMTP_PORT': '587',
            'SMTP_USER': 'user@test.com',
            'SMTP_PASSWORD': 'bad',
            'SMTP_FROM': 'noreply@test.com',
        }
        with patch.dict(os.environ, env):
            mock_server = MagicMock()
            mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b'Auth failed')
            mock_smtp.return_value = mock_server
            svc = EmailService()
            ok, err = svc.send_email('to@test.com', 'Test', '<p>hi</p>')
            assert ok is False
            assert 'authentication' in err.lower()

    @patch('email_service.smtplib.SMTP')
    def test_send_email_connect_error(self, mock_smtp, mt_client):
        import smtplib
        from email_service import EmailService
        env = {
            'SMTP_HOST': 'bad.host',
            'SMTP_PORT': '587',
            'SMTP_USER': 'user@test.com',
            'SMTP_PASSWORD': 'secret',
            'SMTP_FROM': 'noreply@test.com',
        }
        with patch.dict(os.environ, env):
            mock_smtp.side_effect = smtplib.SMTPConnectError(421, b'Connection refused')
            svc = EmailService()
            ok, err = svc.send_email('to@test.com', 'Test', '<p>hi</p>')
            assert ok is False

    @patch('email_service.smtplib.SMTP')
    def test_send_email_generic_error(self, mock_smtp, mt_client):
        from email_service import EmailService
        env = {
            'SMTP_HOST': 'smtp.test.com',
            'SMTP_PORT': '587',
            'SMTP_USER': 'user@test.com',
            'SMTP_PASSWORD': 'secret',
            'SMTP_FROM': 'noreply@test.com',
        }
        with patch.dict(os.environ, env):
            mock_smtp.side_effect = Exception('Generic error')
            svc = EmailService()
            ok, err = svc.send_email('to@test.com', 'Test', '<p>hi</p>')
            assert ok is False

    @patch('email_service.smtplib.SMTP')
    def test_send_magic_link_email(self, mock_smtp, mt_client):
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
            ok, err = svc.send_magic_link('to@test.com', 'https://example.com/verify/abc', 'TestUser')
            assert ok is True

    @patch('email_service.smtplib.SMTP')
    def test_send_welcome_email(self, mock_smtp, mt_client):
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
            ok, err = svc.send_welcome_email(
                'to@test.com', 'https://example.com/verify/abc',
                'TestUser', ['Project A', 'Project B']
            )
            assert ok is True

    @patch('email_service.smtplib.SMTP')
    def test_send_welcome_email_no_projects(self, mock_smtp, mt_client):
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
            ok, err = svc.send_welcome_email('to@test.com', 'https://example.com/verify/abc')
            assert ok is True

    @patch('email_service.smtplib.SMTP')
    def test_test_connection_success(self, mock_smtp, mt_client):
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
            ok, msg = svc.test_connection()
            assert ok is True

    @patch('email_service.smtplib.SMTP_SSL')
    def test_test_connection_ssl(self, mock_smtp_ssl, mt_client):
        from email_service import EmailService
        env = {
            'SMTP_HOST': 'smtp.test.com',
            'SMTP_PORT': '465',
            'SMTP_USER': 'user@test.com',
            'SMTP_PASSWORD': 'secret',
            'SMTP_FROM': 'noreply@test.com',
        }
        with patch.dict(os.environ, env):
            mock_server = MagicMock()
            mock_smtp_ssl.return_value = mock_server
            svc = EmailService()
            ok, msg = svc.test_connection()
            assert ok is True

    @patch('email_service.smtplib.SMTP')
    def test_test_connection_auth_failure(self, mock_smtp, mt_client):
        import smtplib
        from email_service import EmailService
        env = {
            'SMTP_HOST': 'smtp.test.com',
            'SMTP_PORT': '587',
            'SMTP_USER': 'user@test.com',
            'SMTP_PASSWORD': 'bad',
            'SMTP_FROM': 'noreply@test.com',
        }
        with patch.dict(os.environ, env):
            mock_server = MagicMock()
            mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b'Bad')
            mock_smtp.return_value = mock_server
            svc = EmailService()
            ok, msg = svc.test_connection()
            assert ok is False

    @patch('email_service.smtplib.SMTP')
    def test_test_connection_connect_failure(self, mock_smtp, mt_client):
        import smtplib
        from email_service import EmailService
        env = {
            'SMTP_HOST': 'bad.host',
            'SMTP_PORT': '587',
            'SMTP_USER': 'user@test.com',
            'SMTP_PASSWORD': 'secret',
            'SMTP_FROM': 'noreply@test.com',
        }
        with patch.dict(os.environ, env):
            mock_smtp.side_effect = smtplib.SMTPConnectError(421, b'Refused')
            svc = EmailService()
            ok, msg = svc.test_connection()
            assert ok is False

    @patch('email_service.smtplib.SMTP')
    def test_test_connection_generic_failure(self, mock_smtp, mt_client):
        from email_service import EmailService
        env = {
            'SMTP_HOST': 'smtp.test.com',
            'SMTP_PORT': '587',
            'SMTP_USER': 'user@test.com',
            'SMTP_PASSWORD': 'secret',
            'SMTP_FROM': 'noreply@test.com',
        }
        with patch.dict(os.environ, env):
            mock_smtp.side_effect = Exception('Network error')
            svc = EmailService()
            ok, msg = svc.test_connection()
            assert ok is False

    def test_test_connection_not_configured(self, mt_client):
        from email_service import EmailService
        env = {k: v for k, v in os.environ.items() if not k.startswith('SMTP')}
        with patch.dict(os.environ, env, clear=True):
            svc = EmailService()
            ok, msg = svc.test_connection()
            assert ok is False

    def test_get_email_service_singleton(self, mt_client):
        import email_service
        email_service._email_service = None
        svc1 = email_service.get_email_service()
        svc2 = email_service.get_email_service()
        assert svc1 is svc2
        email_service._email_service = None  # cleanup


# ---------------------------------------------------------------------------
# Database additional coverage
# ---------------------------------------------------------------------------

class TestDatabaseAdditional:
    def test_check_db_exists(self):
        from database import check_db_exists
        assert check_db_exists() is True

    def test_migrate_from_single_tenant(self):
        from database import migrate_from_single_tenant
        proj = migrate_from_single_tenant('/old/dir', 'Old Site', 'old-site')
        assert proj is not None
        assert proj.slug == 'old-site'

    def test_migrate_existing_skips(self):
        from database import migrate_from_single_tenant
        from models import Project
        Project.create(name='Existing', slug='existing-site')
        proj = migrate_from_single_tenant('/dir', 'Existing', 'existing-site')
        assert proj is not None
        assert proj.name == 'Existing'

    def test_get_db_rollback_on_error(self):
        """Test that get_db rolls back on exception."""
        from database import get_db
        try:
            with get_db() as conn:
                conn.execute("INSERT INTO users (email) VALUES ('rollback@test.com')")
                raise ValueError("Force rollback")
        except ValueError:
            pass
        # The insert should have been rolled back
        from models import User
        assert User.get_by_email('rollback@test.com') is None
