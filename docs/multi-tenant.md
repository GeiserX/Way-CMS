# Multi-tenant mode

Way-CMS supports a **multi-tenant mode** for managing multiple websites with multiple users. This is ideal when you need to:

- Manage multiple website projects from a single CMS instance
- Give clients access to edit only their own projects
- Have an admin user who can access and manage all projects
- Send magic link emails for passwordless login

## Enabling Multi-Tenant Mode

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

## Multi-Tenant Features

### Admin Panel (👑 Admin button)
- **Users Tab**: Create/edit/delete users, send magic links
- **Projects Tab**: Create/edit/delete projects (each project = a folder)
- **Assignments Tab**: Assign users to projects (users can have access to multiple projects)
- **Settings Tab**: View email configuration, test SMTP connection, see system stats

### User Authentication
- **Magic Links**: Passwordless login via email (recommended)
- **Password Login**: Users can optionally set a password after first login
- **Session Management**: Persistent sessions with configurable timeout

### Project Management
- Each project is stored in its own folder under `PROJECTS_DIR`
- Admin users have access to ALL projects
- Regular users only see projects they're assigned to
- Project selector dropdown in the header (if user has multiple projects)

## Multi-Tenant Environment Variables

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

## Migration from Single-Tenant

When you enable multi-tenant mode on an existing single-tenant installation:

1. The existing website folder (`CMS_BASE_DIR`) is automatically migrated as the first project
2. The admin user is created with the credentials from `ADMIN_EMAIL` and `ADMIN_PASSWORD`
3. The admin is assigned to the migrated project

## Database

Multi-tenant mode uses SQLite for storing:
- Users (email, name, password hash, admin flag)
- Projects (name, slug/folder name, website URL)
- User-Project assignments (many-to-many)
- Magic links (tokens for passwordless login)

The database is stored at `/.way-cms-data/waycms.db` inside the container.

