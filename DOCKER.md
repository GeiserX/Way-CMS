# Docker Setup Guide

Way-CMS can be deployed using Docker Compose with two services:

1. **Website** (nginx) - Serves the public-facing website on port 80
2. **CMS** (Flask) - Provides the admin interface on port 5000

## Quick Start

1. **Create a directory for your website files:**
   ```bash
   mkdir website
   # Copy your website files into the website directory
   ```

2. **Set environment variables** (optional):
   ```bash
   export CMS_USERNAME=admin
   export CMS_PASSWORD=your-secure-password
   export SECRET_KEY=your-secret-key-here
   ```

   Or create a `.env` file:
   ```env
   CMS_USERNAME=admin
   CMS_PASSWORD=your-secure-password
   SECRET_KEY=your-secret-key-here
   ```

3. **Start the services:**
   ```bash
   docker-compose up -d
   ```

4. **Access the services:**
   - **Public Website**: http://localhost:8080 (port 8080)
   - **CMS Admin**: http://localhost:5000 (port 5000)

## Configuration

### Environment Variables

- `CMS_USERNAME` - Admin username (default: `admin`)
- `CMS_PASSWORD` - Admin password (default: `admin`)
- `CMS_PASSWORD_HASH` - Optional bcrypt hash (if set, `CMS_PASSWORD` is ignored)
- `SECRET_KEY` - Flask secret key for sessions (default: auto-generated, **change in production!**)

### Volumes

- `./website` - Your website files (read-only for nginx, read-write for CMS)
- `./.way-cms-backups` - Backup storage directory

### Ports

- `8080` - Public website (nginx, mapped from container port 80)
- `5000` - CMS admin interface

## Updating Website Files

Website files are shared between both services. When you edit files through the CMS:

1. Changes are saved to the `./website` directory
2. Nginx automatically serves the updated files
3. No restart needed for static file changes

## Backups

Backups are stored in `./.way-cms-backups` and are preserved across container restarts.

## Production Deployment

For production:

1. **Set a strong SECRET_KEY:**
   ```bash
   export SECRET_KEY=$(openssl rand -hex 32)
   ```

2. **Use password hash instead of plain password:**
   ```python
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