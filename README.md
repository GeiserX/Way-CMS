# Way-CMS

A simple, web-accessible CMS for editing HTML/CSS files downloaded from Wayback Archive. This tool allows you to self-service edit your archived website files through a modern web interface.

## Features

- **Web-based File Editor**: Edit HTML, CSS, JS, TXT, XML, JSON, and MD files directly in your browser
- **Syntax Highlighting**: CodeMirror-powered editor with syntax highlighting for multiple languages
- **File Browser**: Navigate through your website directory structure
- **Search Functionality**: Search for text across all files
- **Password Protection**: Optional password protection (set via environment variable)
- **Docker Support**: Easy deployment with Docker and Docker Compose

## Quick Start with Docker (Recommended)

Way-CMS now runs with **two services**: a public website (nginx) and the CMS admin interface (Flask).

1. **Create a directory for your website files:**
   ```bash
   mkdir website
   # Copy your Wayback Archive downloaded files into the website directory
   ```

2. **Start the services:**
   ```bash
   docker-compose up -d
   ```

3. **Access the services:**
   - **Public Website**: http://localhost (port 80)
   - **CMS Admin**: http://localhost:5000 (port 5000)

See [DOCKER.md](DOCKER.md) for detailed setup instructions and production deployment guide.

## Configuration

### Environment Variables

- `CMS_BASE_DIR`: Directory containing your website files (default: `/var/www/html`)
- `CMS_PASSWORD`: Optional password for accessing the CMS (default: empty, no password required)
- `SECRET_KEY`: Secret key for Flask sessions (default: auto-generated, change in production)
- `PORT`: Port to run the server on (default: `5000`)
- `DEBUG`: Enable debug mode (default: `false`)

### Example with Password

```bash
CMS_PASSWORD=your-secure-password docker-compose up -d
```

Or in `docker-compose.yml`:

```yaml
environment:
  - CMS_PASSWORD=your-secure-password
```

## Manual Setup (without Docker)

1. **Install dependencies:**
   ```bash
   pip install -r cms/requirements.txt
   ```

2. **Set environment variables:**
   ```bash
   export CMS_BASE_DIR=/path/to/your/website/files
   export CMS_PASSWORD=your-password  # optional
   ```

3. **Run the application:**
   ```bash
   cd cms
   python app.py
   ```

## Usage

1. **Browse Files**: Use the sidebar to navigate through your website directory
2. **Edit Files**: Click on any supported file to open it in the editor
3. **Save Changes**: Click the "Save" button or use Ctrl+S / Cmd+S
4. **Search**: Click the "Search" button to find text across all files
5. **Delete Files**: Use the "Delete" button in the editor toolbar (use with caution!)

## Supported File Types

- HTML/HTM
- CSS
- JavaScript/JS
- TXT
- XML
- JSON
- Markdown/MD

## Security Notes

- **Default Setup**: If no password is set, the CMS is accessible to anyone who can reach the server
- **Production Use**: Always set a strong `CMS_PASSWORD` and use HTTPS in production
- **File Permissions**: The CMS can only access files within the `CMS_BASE_DIR` directory
- **Network Access**: By default, the CMS binds to `0.0.0.0` (all interfaces). Use a reverse proxy (nginx, traefik) with HTTPS in production

## License

GPL-3.0 with commercial use restriction (see LICENSE file)
