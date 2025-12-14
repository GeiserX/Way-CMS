# Changelog

All notable changes to Way-CMS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-12-14

### 🎉 Major Release: Multi-Tenant Support

This is a major release that transforms Way-CMS from a single-tenant application into a fully-featured multi-tenant CMS platform.

### Added

#### Multi-Tenant Architecture
- **SQLite Database**: New database system for managing users, projects, and assignments
- **User Management**: Complete user CRUD operations with email-based authentication
- **Project Management**: Create and manage multiple website projects from a single instance
- **User-Project Assignments**: Many-to-many relationship allowing users to access multiple projects
- **Role-Based Access Control**: Admin users with full access, regular users with project-specific access

#### Authentication System
- **Magic Link Authentication**: Passwordless login via email links
- **Password Authentication**: Optional password-based login (users can set passwords after first login)
- **Session Management**: Enhanced session handling with configurable timeouts
- **Email Integration**: SMTP support for sending magic links and welcome emails

#### Admin Panel
- **Admin Dashboard**: New admin panel accessible via 👑 Admin button (admin users only)
- **Users Tab**: Create, edit, delete users; send magic links; manage user roles
- **Projects Tab**: Create, edit, delete projects; manage project folders and URLs
- **Assignments Tab**: Assign users to projects; manage user-project relationships
- **Settings Tab**: Email configuration testing, system statistics

#### UI Enhancements
- **Project Selector**: Dropdown in breadcrumb area for switching between projects
- **Admin Button**: Visible only to admin users in the header
- **Enhanced Login Page**: Magic link request button, password login option
- **Welcome Emails**: Beautiful HTML email templates for new user onboarding

#### Migration System
- **Automatic Migration**: Existing single-tenant installations automatically migrate to first project
- **Backward Compatibility**: Single-tenant mode still supported via `MULTI_TENANT=false`

### Changed

- **File Operations**: All file operations are now project-aware in multi-tenant mode
- **Backup System**: Backups are organized by project in multi-tenant mode
- **Directory Structure**: New `PROJECTS_BASE_DIR` for storing all project folders
- **Database Location**: SQLite database stored in `DATA_DIR` (default: `/.way-cms-data`)

### Environment Variables

#### New Multi-Tenant Variables
- `MULTI_TENANT`: Enable multi-tenant mode (default: `false`)
- `ADMIN_EMAIL`: Initial admin email (required for first run)
- `ADMIN_PASSWORD`: Initial admin password (required for first run)
- `PROJECTS_BASE_DIR`: Container path for all projects (default: `/var/www/projects`)
- `DATA_DIR`: Container path for SQLite database (default: `/.way-cms-data`)
- `APP_URL`: Public URL for magic link emails
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`: SMTP configuration
- `SMTP_FROM`, `SMTP_FROM_NAME`: Email sender information
- `MAGIC_LINK_EXPIRY_HOURS`: Magic link expiration time (default: 24)

### Technical Details

- **Database**: SQLite with foreign key constraints
- **Models**: User, Project, UserProject, MagicLink with full CRUD operations
- **Authentication**: bcrypt password hashing, secure token generation
- **Email**: SMTP with HTML email templates
- **API Routes**: New `/auth/*` and `/admin/*` endpoints
- **Security**: Admin routes protected with `@admin_required` decorator
- **Project Access**: All file operations check user permissions

### Migration Guide

To upgrade from 1.x to 2.0.0:

1. **Backup your data** before upgrading
2. **Set environment variables** for multi-tenant mode (see README)
3. **Start the application** - existing website will be auto-migrated as first project
4. **Log in** with `ADMIN_EMAIL` and `ADMIN_PASSWORD`
5. **Access admin panel** to create additional users and projects

For single-tenant mode, set `MULTI_TENANT=false` - everything works as before.

### Breaking Changes

- **None**: Single-tenant mode remains fully backward compatible
- Multi-tenant mode requires new environment variables (see above)

### Documentation

- Updated README.md with comprehensive multi-tenant documentation
- Added multi-tenant setup instructions
- Updated docker-compose.yml with new environment variables

---

## [1.2.14] - Previous Release

### Features
- Web-based file editor with syntax highlighting
- Live preview with asset loading
- File browser and management
- Search & replace functionality
- Automatic backup system
- Theme toggle
- Keyboard shortcuts
- Password protection
- Docker support
