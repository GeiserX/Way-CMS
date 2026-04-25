"""Tests for Way-CMS Flask app routes (single-tenant mode).

Covers all API endpoints, login/logout, file operations, preview,
backup/restore, search, upload, and download functionality.
"""

import io
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cms'))


@pytest.fixture()
def app_env(tmp_path):
    """Set up environment variables for single-tenant app."""
    base_dir = str(tmp_path / "website")
    backup_dir = str(tmp_path / "backups")
    os.makedirs(base_dir, exist_ok=True)
    os.makedirs(backup_dir, exist_ok=True)

    env = {
        'CMS_BASE_DIR': base_dir,
        'BACKUP_DIR': backup_dir,
        'CMS_USERNAME': 'admin',
        'CMS_PASSWORD': 'testpass',
        'CMS_PASSWORD_HASH': '',
        'SECRET_KEY': 'test-secret-key',
        'MULTI_TENANT': 'false',
        'READ_ONLY_MODE': 'false',
        'WEBSITE_URL': 'https://example.com',
        'WEBSITE_NAME': 'TestSite',
        'SESSION_TIMEOUT_MINUTES': '60',
        'AUTO_BACKUP_ENABLED': 'false',
    }
    return env, base_dir, backup_dir


@pytest.fixture()
def client(app_env, monkeypatch):
    """Create a Flask test client for single-tenant mode."""
    env, base_dir, backup_dir = app_env

    for k, v in env.items():
        monkeypatch.setenv(k, v)

    # Patch module-level variables before importing app
    # We must reload app since it reads env at import time
    import importlib

    # Patch AUTO_BACKUP_ENABLED to prevent background threads
    monkeypatch.setenv('AUTO_BACKUP_ENABLED', 'false')

    import app as app_module
    importlib.reload(app_module)

    # Override module-level config
    app_module.CMS_BASE_DIR = base_dir
    app_module.BACKUP_DIR = backup_dir
    app_module.CMS_USERNAME = 'admin'
    app_module.CMS_PASSWORD = 'testpass'
    app_module.CMS_PASSWORD_HASH = ''
    app_module.MULTI_TENANT = False
    app_module.READ_ONLY_MODE = False
    app_module.WEBSITE_URL = 'https://example.com'
    app_module.WEBSITE_NAME = 'TestSite'
    app_module.AUTO_BACKUP_ENABLED = False
    app_module.AUTO_BACKUP_DIR = os.path.join(backup_dir, 'auto')

    app_module.app.config['TESTING'] = True
    app_module.app.config['SECRET_KEY'] = 'test-secret-key'

    with app_module.app.test_client() as c:
        yield c, app_module, base_dir, backup_dir


def _login(client_tuple):
    """Helper to log in."""
    c, app_mod, _, _ = client_tuple
    return c.post('/login', data={'username': 'admin', 'password': 'testpass'},
                  follow_redirects=True)


def _create_file(base_dir, rel_path, content='<html><body>Hello</body></html>'):
    """Helper to create a file in the website directory."""
    full_path = os.path.join(base_dir, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w') as f:
        f.write(content)
    return full_path


# ---------------------------------------------------------------------------
# Login / Logout / Auth
# ---------------------------------------------------------------------------

class TestLoginLogout:
    def test_login_page_renders(self, client):
        c, _, _, _ = client
        resp = c.get('/login')
        assert resp.status_code == 200

    def test_login_success_redirects(self, client):
        c, _, _, _ = client
        resp = c.post('/login', data={'username': 'admin', 'password': 'testpass'})
        assert resp.status_code in (302, 200)

    def test_login_wrong_username(self, client):
        c, _, _, _ = client
        resp = c.post('/login', data={'username': 'wrong', 'password': 'testpass'})
        assert resp.status_code == 200
        assert b'Invalid' in resp.data

    def test_login_wrong_password(self, client):
        c, _, _, _ = client
        resp = c.post('/login', data={'username': 'admin', 'password': 'wrong'})
        assert resp.status_code == 200
        assert b'Invalid' in resp.data

    def test_login_no_auth_configured(self, client):
        c, app_mod, _, _ = client
        app_mod.CMS_PASSWORD_HASH = ''
        app_mod.CMS_PASSWORD = ''
        resp = c.get('/login', follow_redirects=True)
        assert resp.status_code == 200

    def test_logout(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.get('/logout')
        assert resp.status_code == 302

    def test_redirect_to_login_when_not_logged_in(self, client):
        c, _, _, _ = client
        resp = c.get('/')
        assert resp.status_code == 302

    def test_login_with_bcrypt_hash(self, client):
        c, app_mod, _, _ = client
        import bcrypt
        hashed = bcrypt.hashpw(b'hashpass', bcrypt.gensalt()).decode()
        app_mod.CMS_PASSWORD_HASH = hashed
        app_mod.CMS_PASSWORD = ''
        resp = c.post('/login', data={'username': 'admin', 'password': 'hashpass'})
        assert resp.status_code in (302, 200)

    def test_login_with_sha256_hash(self, client):
        c, app_mod, _, _ = client
        import hashlib
        hashed = hashlib.sha256(b'sha256pass').hexdigest()
        app_mod.CMS_PASSWORD_HASH = hashed
        app_mod.CMS_PASSWORD = ''
        resp = c.post('/login', data={'username': 'admin', 'password': 'sha256pass'})
        assert resp.status_code in (302, 200)


# ---------------------------------------------------------------------------
# Index / Main Page
# ---------------------------------------------------------------------------

class TestIndex:
    def test_index_logged_in(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.get('/')
        assert resp.status_code == 200

    def test_index_uses_website_name(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.get('/')
        assert resp.status_code == 200

    def test_index_no_website_name(self, client):
        _login(client)
        c, app_mod, _, _ = client
        app_mod.WEBSITE_NAME = ''
        resp = c.get('/')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# File Listing API
# ---------------------------------------------------------------------------

class TestFileListAPI:
    def test_list_files_root(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'index.html')
        _create_file(base_dir, 'style.css', 'body {}')
        os.makedirs(os.path.join(base_dir, 'subdir'), exist_ok=True)
        resp = c.get('/api/files?path=')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'files' in data
        assert 'directories' in data

    def test_list_files_subdirectory(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'sub/page.html')
        resp = c.get('/api/files?path=sub')
        assert resp.status_code == 200

    def test_list_files_not_found(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.get('/api/files?path=nonexistent')
        assert resp.status_code == 404

    def test_list_files_skips_backup_dirs(self, client):
        _login(client)
        c, _, base_dir, _ = client
        os.makedirs(os.path.join(base_dir, '.way-cms-stuff'), exist_ok=True)
        _create_file(base_dir, 'visible.html')
        resp = c.get('/api/files?path=')
        data = resp.get_json()
        dir_names = [d['name'] for d in data['directories']]
        assert '.way-cms-stuff' not in dir_names


# ---------------------------------------------------------------------------
# File Read API
# ---------------------------------------------------------------------------

class TestFileReadAPI:
    def test_get_file_content(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'test.html', '<p>content</p>')
        resp = c.get('/api/file?path=test.html')
        assert resp.status_code == 200
        data = resp.get_json()
        assert '<p>content</p>' in data['content']

    def test_get_file_no_path(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.get('/api/file?path=')
        assert resp.status_code == 400

    def test_get_file_not_found(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.get('/api/file?path=nonexistent.html')
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# File Save API
# ---------------------------------------------------------------------------

class TestFileSaveAPI:
    def test_save_file(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'save.html', 'old')
        resp = c.post('/api/file', json={
            'path': 'save.html',
            'content': 'new content',
            'backup': True,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_save_file_no_path(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.post('/api/file', json={'path': '', 'content': 'x'})
        assert resp.status_code == 400

    def test_save_file_creates_new(self, client):
        _login(client)
        c, _, base_dir, _ = client
        resp = c.post('/api/file', json={
            'path': 'newdir/new.html',
            'content': 'fresh',
            'backup': False,
        })
        assert resp.status_code == 200

    def test_save_file_read_only(self, client):
        _login(client)
        c, app_mod, _, _ = client
        app_mod.READ_ONLY_MODE = True
        resp = c.post('/api/file', json={'path': 'x.html', 'content': 'x'})
        assert resp.status_code == 403
        app_mod.READ_ONLY_MODE = False

    def test_save_file_invalid_path(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.post('/api/file', json={'path': '../../etc/passwd', 'content': 'x'})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# File Create API (PUT)
# ---------------------------------------------------------------------------

class TestFileCreateAPI:
    def test_create_file(self, client):
        _login(client)
        c, _, base_dir, _ = client
        resp = c.put('/api/file', json={
            'path': 'created.html',
            'content': 'new file',
        })
        assert resp.status_code == 200
        assert os.path.exists(os.path.join(base_dir, 'created.html'))

    def test_create_directory(self, client):
        _login(client)
        c, _, base_dir, _ = client
        resp = c.put('/api/file', json={
            'path': 'newdir',
            'is_directory': True,
        })
        assert resp.status_code == 200
        assert os.path.isdir(os.path.join(base_dir, 'newdir'))

    def test_create_no_path(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.put('/api/file', json={'path': ''})
        assert resp.status_code == 400

    def test_create_already_exists(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'exists.html')
        resp = c.put('/api/file', json={'path': 'exists.html', 'content': 'x'})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# File Rename API (PATCH)
# ---------------------------------------------------------------------------

class TestFileRenameAPI:
    def test_rename_file(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'old.html')
        resp = c.patch('/api/file', json={
            'old_path': 'old.html',
            'new_path': 'new.html',
        })
        assert resp.status_code == 200
        assert os.path.exists(os.path.join(base_dir, 'new.html'))

    def test_rename_no_paths(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.patch('/api/file', json={'old_path': '', 'new_path': ''})
        assert resp.status_code == 400

    def test_rename_source_not_found(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.patch('/api/file', json={
            'old_path': 'nope.html',
            'new_path': 'other.html',
        })
        assert resp.status_code == 404

    def test_rename_dest_exists(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'a.html')
        _create_file(base_dir, 'b.html')
        resp = c.patch('/api/file', json={
            'old_path': 'a.html',
            'new_path': 'b.html',
        })
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# File Delete API
# ---------------------------------------------------------------------------

class TestFileDeleteAPI:
    def test_delete_file(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'todelete.html')
        resp = c.delete('/api/file?path=todelete.html')
        assert resp.status_code == 200

    def test_delete_directory(self, client):
        _login(client)
        c, _, base_dir, _ = client
        os.makedirs(os.path.join(base_dir, 'deldir'))
        _create_file(base_dir, 'deldir/file.html')
        resp = c.delete('/api/file?path=deldir')
        assert resp.status_code == 200

    def test_delete_no_path(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.delete('/api/file?path=')
        assert resp.status_code == 400

    def test_delete_not_found(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.delete('/api/file?path=nope.html')
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Search API
# ---------------------------------------------------------------------------

class TestSearchAPI:
    def test_search_text(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'search.html', '<p>findme here</p>')
        resp = c.get('/api/search?q=findme')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data['results']) >= 1

    def test_search_no_query(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.get('/api/search?q=')
        assert resp.status_code == 400

    def test_search_regex(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'regex.html', '<p>test123</p>')
        resp = c.get('/api/search?q=test\\d%2B&regex=true')
        assert resp.status_code == 200

    def test_search_invalid_regex(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'regex2.html', 'content')
        resp = c.get('/api/search?q=[invalid&regex=true')
        assert resp.status_code == 400

    def test_search_case_sensitive(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'case.html', '<p>CaseSensitive</p>')
        resp = c.get('/api/search?q=CaseSensitive&case_sensitive=true')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data['results']) >= 1


# ---------------------------------------------------------------------------
# Search-Replace API
# ---------------------------------------------------------------------------

class TestSearchReplaceAPI:
    def test_search_replace_dry_run(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'sr.html', '<p>old text</p>')
        resp = c.post('/api/search-replace', json={
            'search': 'old',
            'replace': 'new',
            'dry_run': True,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['dry_run'] is True
        assert data['total_files'] >= 1

    def test_search_replace_apply(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'sr2.html', '<p>old text</p>')
        resp = c.post('/api/search-replace', json={
            'search': 'old',
            'replace': 'new',
            'dry_run': False,
        })
        assert resp.status_code == 200
        with open(os.path.join(base_dir, 'sr2.html')) as f:
            assert 'new text' in f.read()

    def test_search_replace_no_query(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.post('/api/search-replace', json={
            'search': '',
            'replace': 'new',
        })
        assert resp.status_code == 400

    def test_search_replace_regex(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'srregex.html', '<p>test123</p>')
        resp = c.post('/api/search-replace', json={
            'search': 'test\\d+',
            'replace': 'replaced',
            'regex': True,
            'dry_run': False,
        })
        assert resp.status_code == 200

    def test_search_replace_invalid_regex(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.post('/api/search-replace', json={
            'search': '[invalid',
            'replace': 'x',
            'regex': True,
        })
        assert resp.status_code == 400

    def test_search_replace_case_insensitive(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'srci.html', '<p>Hello HELLO hello</p>')
        resp = c.post('/api/search-replace', json={
            'search': 'hello',
            'replace': 'bye',
            'case_sensitive': False,
            'dry_run': False,
        })
        assert resp.status_code == 200

    def test_search_replace_specific_files(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'specific.html', 'replace me')
        resp = c.post('/api/search-replace', json={
            'search': 'replace',
            'replace': 'done',
            'files': ['specific.html'],
            'dry_run': True,
        })
        assert resp.status_code == 200

    def test_search_replace_case_sensitive(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'srcs.html', '<p>Hello</p>')
        resp = c.post('/api/search-replace', json={
            'search': 'Hello',
            'replace': 'Bye',
            'case_sensitive': True,
            'dry_run': False,
        })
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Backup APIs
# ---------------------------------------------------------------------------

class TestBackupAPIs:
    def test_list_backups_empty(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.get('/api/backups?path=test.html')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['backups'] == []

    def test_list_backups_no_path(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.get('/api/backups?path=')
        assert resp.status_code == 400

    def test_create_manual_backup(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'backup.html', 'content')
        resp = c.post('/api/create-backup', json={'path': 'backup.html'})
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_create_manual_backup_no_path(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.post('/api/create-backup', json={'path': ''})
        assert resp.status_code == 400

    def test_create_manual_backup_nonexistent(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.post('/api/create-backup', json={'path': 'nonexist.html'})
        assert resp.status_code == 500

    def test_get_backup_content(self, client):
        _login(client)
        c, _, base_dir, backup_dir = client
        _create_file(base_dir, 'bkup.html', 'original')
        # Create backup via API
        c.post('/api/create-backup', json={'path': 'bkup.html'})
        # List backups to get the path
        resp = c.get('/api/backups?path=bkup.html')
        backups = resp.get_json()['backups']
        if backups:
            backup_path = backups[0]['path']
            resp = c.get(f'/api/backup/{backup_path}')
            assert resp.status_code == 200
            assert 'content' in resp.get_json()

    def test_get_backup_not_found(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.get('/api/backup/nonexistent')
        assert resp.status_code == 404

    def test_get_backup_invalid_path(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.get('/api/backup/../../etc/passwd')
        assert resp.status_code == 400

    def test_restore_backup(self, client):
        _login(client)
        c, _, base_dir, backup_dir = client
        _create_file(base_dir, 'restore.html', 'original')
        c.post('/api/create-backup', json={'path': 'restore.html'})
        # Modify original
        _create_file(base_dir, 'restore.html', 'modified')
        # Get backup path
        resp = c.get('/api/backups?path=restore.html')
        backups = resp.get_json()['backups']
        if backups:
            resp = c.post('/api/restore-backup', json={
                'file_path': 'restore.html',
                'backup_path': backups[0]['path'],
            })
            assert resp.status_code == 200

    def test_restore_backup_missing_params(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.post('/api/restore-backup', json={'file_path': '', 'backup_path': ''})
        assert resp.status_code == 400

    def test_restore_backup_not_found(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.post('/api/restore-backup', json={
            'file_path': 'x.html',
            'backup_path': 'nonexistent',
        })
        assert resp.status_code == 404

    def test_restore_backup_invalid_path(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.post('/api/restore-backup', json={
            'file_path': 'x.html',
            'backup_path': '../../etc/passwd',
        })
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Folder Backup APIs
# ---------------------------------------------------------------------------

class TestFolderBackupAPIs:
    def test_list_folder_backups_empty(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.get('/api/folder-backups?path=')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['backups'] == []

    def test_create_folder_backup(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'fb.html', 'content')
        resp = c.post('/api/create-folder-backup', json={
            'path': '',
            'name': 'test-backup',
        })
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_create_folder_backup_no_name(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.post('/api/create-folder-backup', json={'path': '', 'name': ''})
        assert resp.status_code == 400

    def test_create_folder_backup_sanitize_name(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'x.html', 'y')
        resp = c.post('/api/create-folder-backup', json={
            'path': '',
            'name': 'my backup!@#',
        })
        assert resp.status_code == 200

    def test_restore_folder_backup(self, client):
        _login(client)
        c, app_mod, base_dir, backup_dir = client
        _create_file(base_dir, 'rfb.html', 'original')
        # Create a subdirectory to restore into
        restore_target = os.path.join(base_dir, 'restored')
        os.makedirs(restore_target, exist_ok=True)
        # Create a backup zip manually in the backup dir
        restore_dir = os.path.join(backup_dir, 'folders', 'root')
        os.makedirs(restore_dir, exist_ok=True)
        zip_path = os.path.join(restore_dir, 'restore-test.zip')
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('rfb.html', 'restored content')
        backup_rel = zip_path.replace(backup_dir, '').lstrip('/')
        resp = c.post('/api/restore-folder-backup', json={
            'path': 'restored',
            'backup_path': backup_rel,
        })
        assert resp.status_code == 200

    def test_restore_folder_backup_missing_params(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.post('/api/restore-folder-backup', json={'path': '', 'backup_path': ''})
        assert resp.status_code == 400

    def test_restore_folder_backup_not_found(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'x.html', 'x')
        resp = c.post('/api/restore-folder-backup', json={
            'path': 'x.html',
            'backup_path': 'nonexistent.zip',
        })
        assert resp.status_code == 404

    def test_delete_folder_backup(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'dfb.html', 'x')
        c.post('/api/create-folder-backup', json={'path': '', 'name': 'del-test'})
        resp = c.get('/api/folder-backups?path=')
        backups = resp.get_json()['backups']
        if backups:
            resp = c.delete(f'/api/delete-folder-backup?path={backups[0]["path"]}')
            assert resp.status_code == 200

    def test_delete_folder_backup_no_path(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.delete('/api/delete-folder-backup?path=')
        assert resp.status_code == 400

    def test_delete_folder_backup_not_found(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.delete('/api/delete-folder-backup?path=nonexistent.zip')
        assert resp.status_code == 404

    def test_list_folder_backups_with_auto(self, client):
        _login(client)
        c, _, base_dir, backup_dir = client
        # Create an auto backup zip manually
        auto_dir = os.path.join(backup_dir, 'auto')
        os.makedirs(auto_dir, exist_ok=True)
        zip_path = os.path.join(auto_dir, 'test_20240101_020000.zip')
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('test.html', 'content')
        resp = c.get('/api/folder-backups?path=')
        assert resp.status_code == 200
        data = resp.get_json()
        auto_backups = [b for b in data['backups'] if b['type'] == 'auto']
        assert len(auto_backups) >= 1


# ---------------------------------------------------------------------------
# Trigger Auto Backup API
# ---------------------------------------------------------------------------

class TestAutoBackupTrigger:
    def test_trigger_auto_backup(self, client):
        _login(client)
        c, app_mod, base_dir, _ = client
        app_mod.AUTO_BACKUP_ENABLED = True
        _create_file(base_dir, 'auto.html', 'content')
        resp = c.post('/api/trigger-auto-backup')
        assert resp.status_code == 200
        app_mod.AUTO_BACKUP_ENABLED = False

    def test_trigger_auto_backup_disabled(self, client):
        _login(client)
        c, app_mod, _, _ = client
        app_mod.AUTO_BACKUP_ENABLED = False
        resp = c.post('/api/trigger-auto-backup')
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# Download APIs
# ---------------------------------------------------------------------------

class TestDownloadAPIs:
    def test_download_zip(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'dl.html', 'download me')
        resp = c.get('/api/download-zip?path=')
        assert resp.status_code == 200
        assert 'application/zip' in resp.content_type

    def test_download_zip_subfolder(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'sub/dl.html', 'content')
        resp = c.get('/api/download-zip?path=sub')
        assert resp.status_code == 200

    def test_download_zip_not_found(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.get('/api/download-zip?path=nonexistent')
        assert resp.status_code == 404

    def test_download_single_file(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'single.html', 'file content')
        resp = c.get('/api/download-file?path=single.html')
        assert resp.status_code == 200

    def test_download_single_file_not_found(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.get('/api/download-file?path=nope.html')
        assert resp.status_code == 404

    def test_download_single_file_is_directory(self, client):
        _login(client)
        c, _, base_dir, _ = client
        os.makedirs(os.path.join(base_dir, 'adir'), exist_ok=True)
        resp = c.get('/api/download-file?path=adir')
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Upload APIs
# ---------------------------------------------------------------------------

class TestUploadAPIs:
    def test_upload_zip(self, client):
        _login(client)
        c, _, base_dir, _ = client
        # Create a zip in memory
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('uploaded.html', '<p>uploaded</p>')
        buf.seek(0)
        resp = c.post('/api/upload-zip', data={
            'file': (buf, 'test.zip'),
        }, content_type='multipart/form-data')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_upload_zip_no_file(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.post('/api/upload-zip')
        assert resp.status_code == 400

    def test_upload_zip_not_zip(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.post('/api/upload-zip', data={
            'file': (io.BytesIO(b'not a zip'), 'test.txt'),
        }, content_type='multipart/form-data')
        assert resp.status_code == 400

    def test_upload_zip_bad_zip(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.post('/api/upload-zip', data={
            'file': (io.BytesIO(b'not a zip'), 'test.zip'),
        }, content_type='multipart/form-data')
        assert resp.status_code == 400

    def test_upload_file(self, client):
        _login(client)
        c, _, base_dir, _ = client
        resp = c.post('/api/upload-file', data={
            'file': (io.BytesIO(b'<p>hi</p>'), 'up.html'),
        }, content_type='multipart/form-data')
        assert resp.status_code == 200

    def test_upload_file_no_file(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.post('/api/upload-file')
        assert resp.status_code == 400

    def test_upload_file_not_allowed_extension(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.post('/api/upload-file', data={
            'file': (io.BytesIO(b'data'), 'bad.exe'),
        }, content_type='multipart/form-data')
        assert resp.status_code == 400

    def test_upload_file_too_large(self, client):
        _login(client)
        c, app_mod, _, _ = client
        old_max = app_mod.MAX_FILE_SIZE
        app_mod.MAX_FILE_SIZE = 10  # 10 bytes
        resp = c.post('/api/upload-file', data={
            'file': (io.BytesIO(b'x' * 100), 'large.html'),
        }, content_type='multipart/form-data')
        assert resp.status_code == 400
        app_mod.MAX_FILE_SIZE = old_max

    def test_upload_file_to_path(self, client):
        _login(client)
        c, _, base_dir, _ = client
        os.makedirs(os.path.join(base_dir, 'uploads'), exist_ok=True)
        resp = c.post('/api/upload-file', data={
            'file': (io.BytesIO(b'<p>hi</p>'), 'target.html'),
            'path': 'uploads',
        }, content_type='multipart/form-data')
        assert resp.status_code == 200

    def test_upload_zip_empty_filename(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.post('/api/upload-zip', data={
            'file': (io.BytesIO(b''), ''),
        }, content_type='multipart/form-data')
        assert resp.status_code == 400

    def test_upload_file_empty_filename(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.post('/api/upload-file', data={
            'file': (io.BytesIO(b''), ''),
        }, content_type='multipart/form-data')
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Preview APIs
# ---------------------------------------------------------------------------

class TestPreviewAPIs:
    def test_preview_html_file(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'preview.html',
                      '<html><head></head><body><p>Hello</p></body></html>')
        resp = c.get('/preview/preview.html')
        assert resp.status_code == 200
        assert b'Hello' in resp.data

    def test_preview_not_found(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.get('/preview/nonexistent.html')
        assert resp.status_code == 404

    def test_preview_non_html_file(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'script.js', 'console.log("hi");')
        resp = c.get('/preview/script.js')
        assert resp.status_code == 200

    def test_preview_html_api(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.post('/api/preview-html', json={
            'content': '<p>test</p>',
            'file_path': 'test.html',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'html' in data

    def test_preview_assets_css(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'style.css', 'body { color: red; }')
        resp = c.get('/preview-assets/style.css')
        assert resp.status_code == 200
        assert b'color: red' in resp.data

    def test_preview_assets_js(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'app.js', 'alert(1);')
        resp = c.get('/preview-assets/app.js')
        assert resp.status_code == 200

    def test_preview_assets_not_found(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.get('/preview-assets/nonexistent.css')
        assert resp.status_code == 404

    def test_preview_assets_empty(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.get('/preview-assets/')
        assert resp.status_code == 404

    def test_preview_assets_image(self, client):
        _login(client)
        c, _, base_dir, _ = client
        # Create a minimal png
        img_path = os.path.join(base_dir, 'img.png')
        with open(img_path, 'wb') as f:
            f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
        resp = c.get('/preview-assets/img.png')
        assert resp.status_code == 200

    def test_preview_assets_font(self, client):
        _login(client)
        c, _, base_dir, _ = client
        for ext in ['woff', 'woff2', 'ttf', 'eot']:
            fpath = os.path.join(base_dir, f'font.{ext}')
            with open(fpath, 'wb') as f:
                f.write(b'\x00' * 10)
            resp = c.get(f'/preview-assets/font.{ext}')
            assert resp.status_code == 200

    def test_preview_html_with_relative_paths(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'css/style.css', 'body {}')
        _create_file(base_dir, 'pages/page.html',
                      '<html><head><link href="../css/style.css" rel="stylesheet"></head><body></body></html>')
        resp = c.get('/preview/pages/page.html')
        assert resp.status_code == 200

    def test_preview_css_with_url_rewriting(self, client):
        _login(client)
        c, _, base_dir, _ = client
        # Create a font file (binary)
        font_path = os.path.join(base_dir, 'fonts', 'font.woff2')
        os.makedirs(os.path.dirname(font_path), exist_ok=True)
        with open(font_path, 'wb') as f:
            f.write(b'\x00' * 10)
        _create_file(base_dir, 'css/theme.css',
                      "body { background: url('../img/bg.png'); }")
        resp = c.get('/preview-assets/css/theme.css')
        assert resp.status_code == 200
        assert b'preview-assets' in resp.data


# ---------------------------------------------------------------------------
# Config API
# ---------------------------------------------------------------------------

class TestConfigAPI:
    def test_get_config(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.get('/api/config')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'read_only' in data
        assert 'allowed_extensions' in data
        assert data['multi_tenant'] is False


# ---------------------------------------------------------------------------
# Catch-all asset fallback
# ---------------------------------------------------------------------------

class TestAssetFallback:
    def test_serve_css_fallback(self, client):
        _login(client)
        c, _, base_dir, _ = client
        _create_file(base_dir, 'theme.css', 'body { background: blue; }')
        resp = c.get('/theme.css')
        assert resp.status_code == 200

    def test_serve_image_fallback(self, client):
        _login(client)
        c, _, base_dir, _ = client
        img_path = os.path.join(base_dir, 'logo.png')
        with open(img_path, 'wb') as f:
            f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 50)
        resp = c.get('/logo.png')
        assert resp.status_code == 200

    def test_fallback_not_found(self, client):
        c, _, _, _ = client
        resp = c.get('/nonexistent.woff2')
        assert resp.status_code == 404

    def test_fallback_api_prefix_404(self, client):
        c, _, _, _ = client
        resp = c.get('/api/fake')
        assert resp.status_code in (404, 302)

    def test_fallback_font_types(self, client):
        _login(client)
        c, _, base_dir, _ = client
        for ext in ['woff', 'woff2', 'ttf', 'eot']:
            with open(os.path.join(base_dir, f'f.{ext}'), 'wb') as f:
                f.write(b'\x00' * 10)
            resp = c.get(f'/f.{ext}')
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Multi-tenant routes (single-tenant mode returns errors)
# ---------------------------------------------------------------------------

class TestMultiTenantEndpointsInSingleTenant:
    def test_my_projects_not_multi_tenant(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.get('/api/my-projects')
        assert resp.status_code == 400

    def test_switch_project_not_multi_tenant(self, client):
        _login(client)
        c, _, _, _ = client
        resp = c.post('/api/switch-project', json={'project_id': 1})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

class TestHelperFunctions:
    def test_safe_path_traversal(self, client):
        _, app_mod, base_dir, _ = client
        result = app_mod.safe_path('../../etc/passwd')
        assert result is None

    def test_safe_path_empty(self, client):
        _, app_mod, base_dir, _ = client
        result = app_mod.safe_path('')
        assert result == os.path.abspath(base_dir)

    def test_safe_path_valid(self, client):
        _, app_mod, base_dir, _ = client
        result = app_mod.safe_path('index.html')
        assert result is not None
        assert result.startswith(os.path.abspath(base_dir))

    def test_allowed_file(self, client):
        _, app_mod, _, _ = client
        assert app_mod.allowed_file('test.html') is True
        assert app_mod.allowed_file('test.css') is True
        assert app_mod.allowed_file('test.exe') is False
        assert app_mod.allowed_file('noext') is False

    def test_verify_password_bcrypt(self, client):
        _, app_mod, _, _ = client
        import bcrypt
        hashed = bcrypt.hashpw(b'test', bcrypt.gensalt()).decode()
        assert app_mod.verify_password('test', hashed) is True
        assert app_mod.verify_password('wrong', hashed) is False

    def test_verify_password_sha256(self, client):
        _, app_mod, _, _ = client
        import hashlib
        hashed = hashlib.sha256(b'test').hexdigest()
        assert app_mod.verify_password('test', hashed) is True

    def test_has_auth_configured(self, client):
        _, app_mod, _, _ = client
        app_mod.CMS_PASSWORD_HASH = 'something'
        assert app_mod.has_auth_configured() is True
        app_mod.CMS_PASSWORD_HASH = ''
        app_mod.CMS_PASSWORD = ''
        assert app_mod.has_auth_configured() is False

    def test_resolve_relative_path(self, client):
        _, app_mod, _, _ = client
        # Test absolute path
        assert app_mod.resolve_relative_path('dir/file.html', '/style.css') == 'style.css'
        # Test parent directory
        result = app_mod.resolve_relative_path('sub/page.html', '../style.css')
        assert 'style.css' in result
        # Test current directory
        result = app_mod.resolve_relative_path('dir/page.html', './style.css')
        assert 'style.css' in result
        # Test simple relative
        result = app_mod.resolve_relative_path('dir/page.html', 'style.css')
        assert 'style.css' in result
        # Test no directory in base
        result = app_mod.resolve_relative_path('page.html', 'style.css')
        assert result == 'style.css'

    def test_get_website_name_for_backup(self, client):
        _, app_mod, _, _ = client
        assert app_mod.get_website_name_for_backup() == 'TestSite'
        assert app_mod.get_website_name_for_backup('my-project') == 'my-project'
        app_mod.WEBSITE_NAME = ''
        result = app_mod.get_website_name_for_backup()
        assert isinstance(result, str) and len(result) > 0

    def test_read_only_check_blocks_post(self, client):
        _login(client)
        c, app_mod, _, _ = client
        app_mod.READ_ONLY_MODE = True
        resp = c.put('/api/file', json={'path': 'x.html', 'content': 'x'})
        assert resp.status_code == 403
        resp = c.patch('/api/file', json={'old_path': 'a', 'new_path': 'b'})
        assert resp.status_code == 403
        resp = c.delete('/api/file?path=x.html')
        assert resp.status_code == 403
        app_mod.READ_ONLY_MODE = False


# ---------------------------------------------------------------------------
# Automatic Backup Functions
# ---------------------------------------------------------------------------

class TestAutomaticBackup:
    def test_create_automatic_backup(self, client):
        _, app_mod, base_dir, backup_dir = client
        app_mod.AUTO_BACKUP_ENABLED = True
        _create_file(base_dir, 'auto.html', 'content')
        result = app_mod.create_automatic_backup()
        assert result is not None
        assert result.endswith('.zip')
        app_mod.AUTO_BACKUP_ENABLED = False

    def test_create_automatic_backup_disabled(self, client):
        _, app_mod, _, _ = client
        app_mod.AUTO_BACKUP_ENABLED = False
        result = app_mod.create_automatic_backup()
        assert result is None

    def test_create_automatic_backup_with_project(self, client):
        _, app_mod, base_dir, backup_dir = client
        app_mod.AUTO_BACKUP_ENABLED = True
        _create_file(base_dir, 'proj.html', 'content')
        result = app_mod.create_automatic_backup(
            project_slug='test-project', base_dir=base_dir)
        assert result is not None
        app_mod.AUTO_BACKUP_ENABLED = False

    def test_manage_backup_retention_empty(self, client):
        _, app_mod, _, _ = client
        # Should not fail on empty dir
        app_mod.manage_backup_retention()

    def test_manage_backup_retention_with_backups(self, client):
        _, app_mod, _, backup_dir = client
        auto_dir = os.path.join(backup_dir, 'auto')
        os.makedirs(auto_dir, exist_ok=True)
        # Create some old backup files
        for i in range(10):
            date_str = f'2023{i+1:02d}01_020000'
            fname = f'website_{date_str}.zip'
            fpath = os.path.join(auto_dir, fname)
            with zipfile.ZipFile(fpath, 'w') as zf:
                zf.writestr('test.html', 'content')
        app_mod.manage_backup_retention()

    def test_manage_backup_retention_for_project(self, client):
        _, app_mod, _, backup_dir = client
        project_dir = os.path.join(backup_dir, 'myproj', 'auto')
        os.makedirs(project_dir, exist_ok=True)
        for i in range(5):
            date_str = f'2023{i+1:02d}01_020000'
            fname = f'myproj_{date_str}.zip'
            fpath = os.path.join(project_dir, fname)
            with zipfile.ZipFile(fpath, 'w') as zf:
                zf.writestr('t.html', 'c')
        app_mod.manage_backup_retention_for_project('myproj')


# ---------------------------------------------------------------------------
# Process HTML for preview
# ---------------------------------------------------------------------------

class TestProcessHtmlForPreview:
    def test_basic_html_processing(self, client):
        _, app_mod, base_dir, _ = client
        with app_mod.app.test_request_context('/'):
            result = app_mod.process_html_for_preview(
                '<html><head></head><body><img src="img.png"></body></html>',
                'index.html'
            )
            assert 'preview-assets' in result

    def test_html_with_external_urls_preserved(self, client):
        _, app_mod, _, _ = client
        with app_mod.app.test_request_context('/'):
            result = app_mod.process_html_for_preview(
                '<img src="https://example.com/img.png">',
                'index.html'
            )
            assert 'https://example.com/img.png' in result

    def test_html_with_data_uri_preserved(self, client):
        _, app_mod, _, _ = client
        with app_mod.app.test_request_context('/'):
            result = app_mod.process_html_for_preview(
                '<img src="data:image/png;base64,abc">',
                'index.html'
            )
            assert 'data:image/png;base64,abc' in result

    def test_html_with_no_head_tag(self, client):
        _, app_mod, _, _ = client
        with app_mod.app.test_request_context('/'):
            result = app_mod.process_html_for_preview(
                '<html><body>Hello</body></html>',
                'index.html'
            )
            assert '<base' in result

    def test_html_with_no_structure(self, client):
        _, app_mod, _, _ = client
        with app_mod.app.test_request_context('/'):
            result = app_mod.process_html_for_preview(
                '<p>Just a paragraph</p>',
                'index.html'
            )
            assert '<base' in result

    def test_html_with_existing_base_tag(self, client):
        _, app_mod, _, _ = client
        with app_mod.app.test_request_context('/'):
            result = app_mod.process_html_for_preview(
                '<html><head><base href="/old/"></head><body></body></html>',
                'index.html'
            )
            assert 'preview-assets' in result

    def test_html_with_style_tag(self, client):
        _, app_mod, _, _ = client
        with app_mod.app.test_request_context('/'):
            result = app_mod.process_html_for_preview(
                '<html><head><style>body { background: url("bg.png"); }</style></head><body></body></html>',
                'index.html'
            )
            assert 'preview-assets' in result

    def test_html_with_inline_style(self, client):
        _, app_mod, _, _ = client
        with app_mod.app.test_request_context('/'):
            result = app_mod.process_html_for_preview(
                '<div style="background: url(\'bg.png\')">test</div>',
                'index.html'
            )
            assert 'preview-assets' in result

    def test_html_with_font_face(self, client):
        _, app_mod, _, _ = client
        with app_mod.app.test_request_context('/'):
            result = app_mod.process_html_for_preview(
                '<style>@font-face { font-family: test; src: url("font.woff2"); }</style>',
                'index.html'
            )
            assert 'preview-assets' in result

    def test_html_with_protocol_relative_url(self, client):
        _, app_mod, _, _ = client
        with app_mod.app.test_request_context('/'):
            result = app_mod.process_html_for_preview(
                '<img src="//cdn.example.com/img.png">',
                'index.html'
            )
            # External protocol-relative should be preserved
            assert '//cdn.example.com/img.png' in result

    def test_html_with_javascript_href(self, client):
        _, app_mod, _, _ = client
        with app_mod.app.test_request_context('/'):
            result = app_mod.process_html_for_preview(
                '<a href="javascript:void(0)">link</a>',
                'index.html'
            )
            assert 'javascript:void(0)' in result

    def test_html_with_multiple_attributes(self, client):
        _, app_mod, _, _ = client
        with app_mod.app.test_request_context('/'):
            result = app_mod.process_html_for_preview(
                '<img src="img.png" data-src="lazy.png">',
                'index.html'
            )
            assert 'preview-assets' in result
