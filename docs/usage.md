# Usage

## Feature list

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

