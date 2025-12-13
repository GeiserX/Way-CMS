# Way-CMS

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

## Quick Start with Docker (Recommended)

Way-CMS runs with **two services**: a public website (nginx) and the CMS admin interface (Flask).

1. **Create a directory for your website files:**
   ```bash
   mkdir website
   # Copy your Wayback Archive downloaded files into the website directory
   ```

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

- `CMS_BASE_DIR`: Directory containing your website files (default: `/var/www/html`)
- `CMS_USERNAME`: Admin username (default: `admin`)
- `CMS_PASSWORD`: Admin password in plain text (will be hashed automatically)
- `CMS_PASSWORD_HASH`: Optional bcrypt hash (if set, `CMS_PASSWORD` is ignored)
- `SECRET_KEY`: Flask secret key for sessions (default: auto-generated, **change in production!**)
- `READ_ONLY_MODE`: Set to `true` to enable read-only mode (default: `false`)
- `SESSION_TIMEOUT_MINUTES`: Session timeout in minutes (default: `1440` = 24 hours)
- `WEBSITE_URL`: URL of your live website - shows a "🌐 Live Website" link in the CMS header (optional)
- `WEBSITE_NAME`: Name of your website - displayed in the breadcrumb instead of folder name (optional)
- `PORT`: Port to run the CMS server on (default: `5000`)
- `DEBUG`: Enable debug mode (default: `false`)

See `.env.example` for a complete example configuration file.

### Volumes

- `./website` - Your website files (read-only for nginx, read-write for CMS)
- `./.way-cms-backups` - Backup storage directory

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

## Security Notes

- **Default Setup**: If no password is set, the CMS uses default credentials (`admin`/`admin`). **Always change this in production!**
- **Production Use**: Always set a strong `CMS_PASSWORD_HASH` and use HTTPS in production
- **File Permissions**: The CMS can only access files within the `CMS_BASE_DIR` directory
- **Network Access**: By default, the CMS binds to `0.0.0.0` (all interfaces). Use a reverse proxy with HTTPS in production
- **Read-Only Mode**: Enable `READ_ONLY_MODE=true` for safe browsing without editing capabilities
- **Session Security**: Sessions are protected with HTTP-only cookies and SameSite policies
- **Rate Limiting**: Default limits are 1000 requests per hour, 100 per minute

## License

GPL-3.0 with commercial use restriction (see LICENSE file)
