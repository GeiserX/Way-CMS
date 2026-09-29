# Getting started

## Docker (recommended)

Way-CMS runs with **two services**: a public website (nginx) and the CMS admin interface (Flask).

### Development Setup (Builds from source)

Use `docker-compose.yml` for development:

```bash
docker compose up -d
```

### Production Setup (Uses Docker Hub image)

Use `docker-compose.prod.yml` for production:

```bash
docker compose -f docker-compose.prod.yml up -d
```

**Note:** The production compose file pins `drumsergio/way-cms:2.0.21`. Set `CMS_VERSION` in `.env` to use another tag (image tags have no `v` prefix: `2.0.21`, not `v2.0.21`). The image is built for `linux/amd64`; on Apple Silicon run `export DOCKER_DEFAULT_PLATFORM=linux/amd64` first.

1. **Set up your website directory:**
   - Configure `WEBSITE_DIR` in your `.env` file (see [Configuration](configuration.md))

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
   docker compose up -d
   ```

4. **Access the services:**
   - **Public Website**: http://localhost:8080
   - **CMS Admin**: http://localhost:5001

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
