# Configuration

## Environment Variables

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

## Automatic Backups

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

## Volumes

- `WEBSITE_DIR` (configurable via env var, default: `./website`) - Your website files (read-only for nginx, read-write for CMS)
- `./.way-cms-backups` - Backup storage directory

**Note:** The website directory path is configurable via the `WEBSITE_DIR` environment variable. You can use an absolute path or a relative path to point to any directory containing your website files.

## Ports

- `8080` - Public website (nginx, mapped from container port 80)
- `5001` - CMS admin interface (mapped from container port 5000)

