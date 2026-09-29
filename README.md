<p align="center">
  <img src="https://raw.githubusercontent.com/GeiserX/Way-CMS/main/docs/images/banner.svg" alt="Way-CMS banner" width="900">
</p>

<p align="center">
  <img src="cms/static/images/way-cms-logo.png" width="150" alt="Way-CMS">
</p>

<h1 align="center">Way-CMS</h1>

<p align="center">
  <a href="https://github.com/GeiserX/Way-CMS/releases"><img src="https://img.shields.io/github/v/release/GeiserX/Way-CMS?style=flat-square" alt="Release"></a>
  <a href="https://github.com/GeiserX/Way-CMS/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/GeiserX/Way-CMS/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://github.com/GeiserX/Way-CMS/blob/main/LICENSE"><img src="https://img.shields.io/github/license/GeiserX/Way-CMS?style=flat-square" alt="License"></a>
  <a href="https://hub.docker.com/r/drumsergio/way-cms"><img src="https://img.shields.io/docker/pulls/drumsergio/way-cms?style=flat-square&logo=docker&logoColor=white" alt="Docker Pulls"></a>
  <a href="https://codecov.io/gh/GeiserX/Way-CMS"><img src="https://codecov.io/gh/GeiserX/Way-CMS/graph/badge.svg" alt="codecov"></a>
</p>

<p align="center"><strong>Simple, web-accessible CMS for editing HTML/CSS files downloaded from Wayback Archive with real-time preview.</strong></p>

Way-CMS lets you edit a site downloaded with [Wayback-Archive](https://github.com/GeiserX/Wayback-Archive) in the browser and see the result as you type. It runs next to an nginx container that serves the public site, and it can host several projects for several users.

## Features

- Browser editor for HTML, CSS, JS, TXT, XML, JSON and Markdown, with CodeMirror syntax highlighting.
- Live preview of HTML pages with their fonts, images and CSS loaded.
- File browser to create, rename, delete and upload files or whole ZIP archives.
- Search and replace in one file or across the site, with regex support.
- A backup before every save, plus daily automatic backups with 7-day, 4-week, 12-month and yearly retention.
- Password login with bcrypt, an optional read-only mode, session timeouts and rate limiting.
- Multi-tenant mode (v2.0.0+) with several projects and users, an admin panel and magic link login by email.
- Dark and light themes and keyboard shortcuts.

## Quick start

```bash
cp .env.example .env   # set WEBSITE_DIR, CMS_PASSWORD and SECRET_KEY
docker-compose -f docker-compose.prod.yml up -d
```

The public website is on http://localhost:8080 and the CMS admin on http://localhost:5001.

## Documentation

- [Installation](https://github.com/GeiserX/Way-CMS/blob/main/docs/installation.md): Docker for development and production, manual setup, reverse proxy, troubleshooting
- [Configuration](https://github.com/GeiserX/Way-CMS/blob/main/docs/configuration.md): environment variables, automatic backups, volumes, ports
- [Usage](https://github.com/GeiserX/Way-CMS/blob/main/docs/usage.md): full feature list, basic operations, keyboard shortcuts, supported file types
- [Multi-tenant mode](https://github.com/GeiserX/Way-CMS/blob/main/docs/multi-tenant.md): projects, users, magic links, SMTP settings, migration
- [Security notes](https://github.com/GeiserX/Way-CMS/blob/main/docs/security-notes.md)
- [Changelog](https://github.com/GeiserX/Way-CMS/blob/main/CHANGELOG.md)

## Related Projects

| Project | Description |
|---------|-------------|
| [Wayback-Archive](https://github.com/GeiserX/Wayback-Archive) | Download complete websites from the Wayback Machine with full asset preservation |
| [Wayback-Diff](https://github.com/GeiserX/Wayback-Diff) | Intelligent web page comparison tool with Wayback Machine support |
| [Website-Diff](https://github.com/GeiserX/Website-Diff) | Intelligent web page comparison tool with visual regression testing |
| [web-mirror](https://github.com/GeiserX/web-mirror) | Mirror any webpage to a local server for offline access |
| [media-download](https://github.com/GeiserX/media-download) | Download all media files from any web page into a folder schema |
| [n8n-nodes-way-cms](https://github.com/GeiserX/n8n-nodes-way-cms) | n8n community node for Way-CMS archived web content management |

## License

GPL-3.0 with commercial use restriction, see [LICENSE](https://github.com/GeiserX/Way-CMS/blob/main/LICENSE).
