# Way-CMS

<div align="center">
  <img src="cms/static/images/way-cms-logo.png" alt="Way-CMS Logo" width="350">
</div>

A simple, web-accessible CMS for editing HTML/CSS files downloaded from Wayback Archive. This tool allows you to self-service edit your archived website files through a modern web interface with real-time preview.

## Features

- **Web-based File Editor**: Edit HTML, CSS, JS, TXT, XML, JSON, MD, and image files directly in your browser
- **Syntax Highlighting**: CodeMirror-powered editor with syntax highlighting for multiple languages
- **Live Preview**: Real-time preview of HTML files with proper asset loading (fonts, images, CSS)
- **File Browser**: Navigate through your website directory structure with file icons
- **File Management**: Create, rename, delete files and folders
- **File Upload**: Upload individual files or ZIP archives
- **Search & Replace**: Find and replace text within files or across all files (with regex support)
- **Backup System**: Automatic backups before saves, browse and restore previous versions
- **Theme Toggle**: Switch between dark and light themes
- **Keyboard Shortcuts**: Full keyboard support for efficient editing
- **Password Protection**: Optional username/password authentication with bcrypt hashing
- **Read-Only Mode**: Optional read-only mode for safe browsing
- **Session Management**: Configurable session timeouts with persistent login
- **Rate Limiting**: Built-in protection against abuse
- **Docker Support**: Easy deployment with Docker and Docker Compose
- **Multi-Tenant Support** (v2.0.0+): Manage multiple projects with multiple users, role-based access control, and magic link authentication

## Quick Start with Docker (Recommended)

Way-CMS runs with **two services**: a public website (nginx) and the CMS admin interface (Flask).

### Development Setup (Builds from source)

Use `docker-compose.yml` for development:

```bash
docker-compose up -d
```

### Production Setup (Uses Docker Hub image)

Use `docker-compose.prod.yml` for production:

```bash
docker-compose -f docker-compose.prod.yml up -d
```

**Note:** The production compose file uses the pre-built image from Docker Hub (`drumsergio/way-cms:latest`). For a specific version, edit `docker-compose.prod.yml` and replace `:latest` with a version tag (e.g., `:v2.0.0` or `:v1.2.14`).

1. **Set up your website directory:**
   - Configure `WEBSITE_DIR` in your `.env` file (see Configuration section)

2. **Set environment variables** (optional, create a `.env` file or copy `.env.example`):
   ```env
   CMS_USERNAME=admin
   CMS_PASSWORD=your-secure-password
   SECRET_KEY=your-secret-key-here
   READ_ONLY_MODE=false
   SESSION_TIMEOUT_MINUTES=1440
   WEBSITE_URL=http://localhost:8080
   WEBSITE_NAME=My Website
   ```
   
   Or simply copy and edit the example:
   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

3. **Start the services:**
   ```bash
   docker-compose up -d
   ```

4. **Access the services:**
   - **Public Website**: http://localhost:8080
   - **CMS Admin**: http://localhost:5001

## Configuration

### Environment Variables

- `WEBSITE_DIR`: Path to your website files directory (default: `./website`, can be absolute or relative)
- `CMS_BASE_DIR`: Directory containing your website files inside container (default: `/var/www/html` - **do not change**)
- `CMS_USERNAME`: Admin username (default: `admin`)
- `CMS_PASSWORD`: Admin password in plain text (will be hashed automatically with bcrypt)
  - **Recommended**: Just use this - the app will hash it automatically at startup
  - Example: `CMS_PASSWORD=mySecurePassword123`
- `CMS_PASSWORD_HASH`: Optional bcrypt hash (if set, `CMS_PASSWORD` is ignored)
  - **More secure**: Prevents storing plain password in environment variables
  - Generate hash with: `python3 scripts/generate_password_hash.py "your-password"`
  - Example: `CMS_PASSWORD_HASH=$2b$12$abcd1234...` (long bcrypt hash)
- `SECRET_KEY`: Flask secret key for sessions (default: auto-generated, **change in production!**)
- `READ_ONLY_MODE`: Set to `true` to enable read-only mode (default: `false`)
- `SESSION_TIMEOUT_MINUTES`: Session timeout in minutes (default: `1440` = 24 hours)
- `WEBSITE_URL`: URL of your live website - shows a "🌐 Live Website" link in the CMS header (optional)
- `WEBSITE_NAME`: Name of your website - displayed in the breadcrumb and used for backup filenames (optional)
- `AUTO_BACKUP_ENABLED`: Enable automatic daily backups (default: `true`)
- `PORT`: Port to run the CMS server on (default: `5000`)
- `DEBUG`: Enable debug mode (default: `false`)

### Automatic Backups

Way-CMS automatically creates backups with the following schedule:

- **On startup**: Creates an initial backup
- **Daily**: Creates a backup every day at 2:00 AM
- **Retention policy**:
  - Keep daily backups for 7 days
  - Keep weekly backups (first backup of each week) for 4 weeks
  - Keep monthly backups (first backup of each month) for 12 months
  - Keep yearly backups (first backup of each year) forever

Backups are stored in `/.way-cms-backups/auto/` and use ZIP compression (`ZIP_DEFLATED`) to reduce file size. Backups are named using `WEBSITE_NAME` (or folder name if not set) with timestamps: `{WEBSITE_NAME}_YYYYMMDD_HHMMSS.zip`

To disable automatic backups, set `AUTO_BACKUP_ENABLED=false`.

See `.env.example` for a complete example configuration file.

### Volumes

- `WEBSITE_DIR` (configurable via env var, default: `./website`) - Your website files (read-only for nginx, read-write for CMS)
- `./.way-cms-backups` - Backup storage directory

**Note:** The website directory path is configurable via the `WEBSITE_DIR` environment variable. You can use an absolute path or a relative path to point to any directory containing your website files.

### Ports

- `8080` - Public website (nginx, mapped from container port 80)
- `5001` - CMS admin interface (mapped from container port 5000)

## Manual Setup (without Docker)

1. **Install dependencies:**
   ```bash
   pip install -r cms/requirements.txt
   ```

2. **Set environment variables:**
   ```bash
   export CMS_BASE_DIR=/path/to/your/website/files
   export CMS_USERNAME=admin
   export CMS_PASSWORD=your-password
   export SECRET_KEY=$(openssl rand -hex 32)
   ```

3. **Run the application:**
   ```bash
   cd cms
   python app.py
   ```

   The CMS will be available at http://localhost:5000

## Usage

### Basic Operations

1. **Browse Files**: Use the sidebar to navigate through your website directory
2. **Edit Files**: Click on any supported file to open it in the editor
3. **Save Changes**: Click the "Save" button or use `Ctrl+S` / `Cmd+S`
4. **Search**: Click the "Search" button to find text across all files
5. **Find & Replace**: Use the global find & replace for batch operations
6. **Create Files/Folders**: Use the "New File" and "New Folder" buttons
7. **Upload Files**: Use "Upload File" to add individual files or "Upload ZIP" for archives
8. **View Backups**: Click "Backups" to browse and restore previous versions
9. **Preview Images**: Click the 👁️ icon next to image files to preview them

### Keyboard Shortcuts

- `Ctrl+S` / `Cmd+S` - Save current file
- `Ctrl+F` / `Cmd+F` - Find in editor
- `Ctrl+H` / `Cmd+H` - Find & Replace in editor
- `Ctrl+G` / `Cmd+G` - Find next
- `F3` - Find next
- `Shift+F3` - Find previous
- `Ctrl+/` / `Cmd+/` - Toggle comment
- `Ctrl+Z` / `Cmd+Z` - Undo
- `Ctrl+Shift+Z` / `Cmd+Shift+Z` - Redo
- `Esc` - Close dialogs

## Supported File Types

### Editable Files
- HTML/HTM
- CSS
- JavaScript/JS
- TXT
- XML
- JSON
- Markdown/MD

### Uploadable/Previewable Files
- Images: PNG, JPG, JPEG, GIF, SVG, WEBP, ICO
- Fonts: WOFF, WOFF2, TTF, EOT
- Archives: ZIP

## Production Deployment

For production deployment:

1. **Set a strong SECRET_KEY:**
   ```bash
   export SECRET_KEY=$(openssl rand -hex 32)
   ```

2. **Use password hash instead of plain password:**
   ```bash
   python3 -c "import bcrypt; print(bcrypt.hashpw('your-password'.encode(), bcrypt.gensalt()).decode())"
   ```
   Then set `CMS_PASSWORD_HASH` with the output.

3. **Use a reverse proxy** (nginx/traefik) in front of both services with:
   - SSL/TLS certificates
   - Domain name routing
   - Rate limiting
   - Firewall rules

4. **Example nginx reverse proxy configuration:**
   ```nginx
   # Public website
   server {
       listen 443 ssl http2;
       server_name example.com;
       
       ssl_certificate /path/to/cert.pem;
       ssl_certificate_key /path/to/key.pem;
       
       location / {
           proxy_pass http://way-cms-website:80;  # Container internal port
       }
   }
   
   # CMS admin (restrict access)
   server {
       listen 443 ssl http2;
       server_name admin.example.com;
       
       ssl_certificate /path/to/cert.pem;
       ssl_certificate_key /path/to/key.pem;
       
       location / {
           proxy_pass http://way-cms-admin:5000;
       }
   }
   ```

## Troubleshooting

### Check logs:
```bash
docker-compose logs -f cms
docker-compose logs -f website
```

### Restart services:
```bash
docker-compose restart
```

### Stop services:
```bash
docker-compose down
```

### Rebuild after code changes:
```bash
docker-compose build --no-cache cms
docker-compose up -d
```

## Multi-Tenant Mode

Way-CMS supports a **multi-tenant mode** for managing multiple websites with multiple users. This is ideal when you need to:

- Manage multiple website projects from a single CMS instance
- Give clients access to edit only their own projects
- Have an admin user who can access and manage all projects
- Send magic link emails for passwordless login

### Enabling Multi-Tenant Mode

1. **Set environment variables** in your `.env` file:

```env
# Enable multi-tenant mode
MULTI_TENANT=true

# Initial admin user (required on first run)
ADMIN_EMAIL=admin@yourcompany.com
ADMIN_PASSWORD=your-secure-admin-password

# Public URL for magic link emails
APP_URL=https://cms.yourcompany.com

# Email configuration (required for magic links)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=noreply@yourcompany.com
SMTP_FROM_NAME=Way-CMS

# Directory for all projects
PROJECTS_DIR=./projects
```

2. **Start the services:**
```bash
docker-compose up -d
```

3. **Access the CMS** at http://localhost:5001 and log in with your admin credentials.

### Multi-Tenant Features

#### Admin Panel (👑 Admin button)
- **Users Tab**: Create/edit/delete users, send magic links
- **Projects Tab**: Create/edit/delete projects (each project = a folder)
- **Assignments Tab**: Assign users to projects (users can have access to multiple projects)
- **Settings Tab**: View email configuration, test SMTP connection, see system stats

#### User Authentication
- **Magic Links**: Passwordless login via email (recommended)
- **Password Login**: Users can optionally set a password after first login
- **Session Management**: Persistent sessions with configurable timeout

#### Project Management
- Each project is stored in its own folder under `PROJECTS_DIR`
- Admin users have access to ALL projects
- Regular users only see projects they're assigned to
- Project selector dropdown in the header (if user has multiple projects)

### Multi-Tenant Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MULTI_TENANT` | Enable multi-tenant mode | `false` |
| `PROJECTS_DIR` | Host directory for all project folders | `./projects` |
| `PROJECTS_BASE_DIR` | Container path for projects | `/var/www/projects` |
| `DATA_DIR` | Container path for SQLite database | `/.way-cms-data` |
| `ADMIN_EMAIL` | Initial admin email (first run) | - |
| `ADMIN_PASSWORD` | Initial admin password (first run) | - |
| `APP_URL` | Public URL for magic link emails | `http://localhost:5001` |
| `SMTP_HOST` | SMTP server hostname | - |
| `SMTP_PORT` | SMTP server port | `587` |
| `SMTP_USER` | SMTP username | - |
| `SMTP_PASSWORD` | SMTP password | - |
| `SMTP_FROM` | Sender email address | - |
| `SMTP_FROM_NAME` | Sender display name | `Way-CMS` |
| `SMTP_USE_TLS` | Use TLS for SMTP | `true` |
| `MAGIC_LINK_EXPIRY_HOURS` | Magic link expiry time | `24` |

### Migration from Single-Tenant

When you enable multi-tenant mode on an existing single-tenant installation:

1. The existing website folder (`CMS_BASE_DIR`) is automatically migrated as the first project
2. The admin user is created with the credentials from `ADMIN_EMAIL` and `ADMIN_PASSWORD`
3. The admin is assigned to the migrated project

### Database

Multi-tenant mode uses SQLite for storing:
- Users (email, name, password hash, admin flag)
- Projects (name, slug/folder name, website URL)
- User-Project assignments (many-to-many)
- Magic links (tokens for passwordless login)

The database is stored at `/.way-cms-data/waycms.db` inside the container.

## Security Notes

- **Default Setup**: If no password is set, the CMS uses default credentials (`admin`/`admin`). **Always change this in production!**
- **Production Use**: Always set a strong `CMS_PASSWORD_HASH` and use HTTPS in production
- **File Permissions**: The CMS can only access files within the `CMS_BASE_DIR` directory (single-tenant) or assigned projects (multi-tenant)
- **Network Access**: By default, the CMS binds to `0.0.0.0` (all interfaces). Use a reverse proxy with HTTPS in production
- **Read-Only Mode**: Enable `READ_ONLY_MODE=true` for safe browsing without editing capabilities
- **Session Security**: Sessions are protected with HTTP-only cookies and SameSite policies
- **Rate Limiting**: Default limits are 1000 requests per hour, 100 per minute
- **Multi-Tenant Security**: Each user can only access their assigned projects; admin routes are protected with `@admin_required` decorator

## License

GPL-3.0 with commercial use restriction (see LICENSE file)
