# Security notes

How to report a vulnerability: [SECURITY.md](https://github.com/GeiserX/Way-CMS/blob/main/SECURITY.md).

- **Default Setup**: If no password is set, the CMS uses default credentials (`admin`/`admin`). **Always change this in production!**
- **Production Use**: Always set a strong `CMS_PASSWORD_HASH` and use HTTPS in production
- **File Permissions**: The CMS can only access files within the `CMS_BASE_DIR` directory (single-tenant) or assigned projects (multi-tenant)
- **Network Access**: By default, the CMS binds to `0.0.0.0` (all interfaces). Use a reverse proxy with HTTPS in production
- **Read-Only Mode**: Enable `READ_ONLY_MODE=true` for safe browsing without editing capabilities
- **Session Security**: Sessions are protected with HTTP-only cookies and SameSite policies
- **Rate Limiting**: Default limits are 1000 requests per hour, 100 per minute
- **Multi-Tenant Security**: Each user can only access their assigned projects; admin routes are protected with `@admin_required` decorator

