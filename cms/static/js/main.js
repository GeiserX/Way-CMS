// Resizable panes functionality
function initResizablePanes() {
    const sidebar = document.querySelector('.sidebar');
    const sidebarHandle = document.getElementById('sidebar-resize-handle');
    const editorArea = document.querySelector('.editor-area');
    
    if (sidebarHandle && sidebar && editorArea) {
        let isResizing = false;
        
        sidebarHandle.addEventListener('mousedown', (e) => {
            isResizing = true;
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            
            const startX = e.pageX;
            const startWidth = sidebar.offsetWidth;
            
            function doResize(e) {
                if (!isResizing) return;
                const diff = e.pageX - startX;
                const newWidth = Math.max(200, Math.min(window.innerWidth * 0.5, startWidth + diff));
                sidebar.style.width = newWidth + 'px';
            }
            
            function stopResize() {
                isResizing = false;
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
            }
            
            document.addEventListener('mousemove', doResize);
            document.addEventListener('mouseup', stopResize);
        });
    }
    
    // Resize handle between editor and preview - will be created when preview is shown
    setupEditorPreviewResize();
}

// Setup resize handle between editor and preview
function setupEditorPreviewResize() {
    const editorPane = document.querySelector('.editor-pane');
    const previewPane = document.querySelector('.preview-pane');
    const editorContainer = document.querySelector('.editor-with-preview');
    
    if (!editorPane || !previewPane || !editorContainer) {
        return; // Elements not ready yet
    }
    
    // Remove existing handle if it exists
    const existingHandle = document.getElementById('editor-preview-resize-handle');
    if (existingHandle) {
        existingHandle.remove();
    }
    
    // Create resize handle
    const handle = document.createElement('div');
    handle.id = 'editor-preview-resize-handle';
    handle.className = 'resize-handle';
    handle.style.display = previewPane.style.display === 'none' ? 'none' : 'block';
    previewPane.parentNode.insertBefore(handle, previewPane);
    
    let isResizing = false;
    
    handle.addEventListener('mousedown', (e) => {
        e.preventDefault();
        e.stopPropagation();
        isResizing = true;
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        
        const startX = e.pageX;
        const editorStartWidth = editorPane.offsetWidth;
        const previewStartWidth = previewPane.offsetWidth;
        const containerWidth = editorContainer.offsetWidth;
        
        function doResize(e) {
            if (!isResizing) return;
            const diff = e.pageX - startX;
            const newEditorWidth = Math.max(200, Math.min(containerWidth - 200, editorStartWidth + diff));
            const editorPercent = (newEditorWidth / containerWidth) * 100;
            editorPane.style.flex = `0 0 ${editorPercent}%`;
            previewPane.style.flex = `1 1 ${100 - editorPercent}%`;
        }
        
        function stopResize() {
            isResizing = false;
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            document.removeEventListener('mousemove', doResize);
            document.removeEventListener('mouseup', stopResize);
        }
        
        document.addEventListener('mousemove', doResize);
        document.addEventListener('mouseup', stopResize);
    });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initResizablePanes();
});

// Note: togglePreview is defined later in the file

// File browser navigation
function navigateTo(path) {
    currentPath = path;
    loadFiles(path);
    updateBreadcrumb(path);
}

function updateBreadcrumb(path) {
    const breadcrumbEl = document.getElementById('breadcrumb');
    const parts = path.split('/').filter(p => p);
    
    // Get folder name from data attribute or use default
    const folderName = breadcrumbEl.dataset.folderName || 'Root';
    breadcrumbEl.innerHTML = `<span class="breadcrumb-item" onclick="navigateTo('')">${escapeHtml(folderName)}</span>`;
    
    let currentPath = '';
    parts.forEach((part, index) => {
        currentPath += (currentPath ? '/' : '') + part;
        const span = document.createElement('span');
        span.className = 'breadcrumb-item';
        span.textContent = ' / ' + part;
        span.onclick = () => navigateTo(currentPath);
        breadcrumbEl.appendChild(span);
    });
}

function loadFiles(path) {
    const fileListEl = document.getElementById('fileList');
    fileListEl.innerHTML = '<div class="loading">Loading files...</div>';
    
    fetch(`${API_BASE}/api/files?path=${encodeURIComponent(path)}`)
        .then(res => res.json())
        .then(data => {
            fileListEl.innerHTML = '';
            
            // Add directories
            data.directories.forEach(dir => {
                const item = document.createElement('div');
                item.className = 'dir-item';
                item.innerHTML = `
                    <span class="dir-icon">📁</span>
                    <span style="flex: 1;">${escapeHtml(dir.name)}</span>
                    <button class="btn btn-secondary" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;" onclick="event.stopPropagation(); showRenameDialog('${dir.path.replace(/'/g, "\\'")}', true)">Rename</button>
                `;
                item.onclick = () => navigateTo(dir.path);
                fileListEl.appendChild(item);
            });
            
            // Add files
            data.files.forEach(file => {
                const item = document.createElement('div');
                item.className = 'file-item';
                const fileIcon = getFileIcon(file.name);
                const isImage = /\.(jpg|jpeg|png|gif|svg|webp|ico)$/i.test(file.name);
                item.innerHTML = `
                    <span class="file-icon">${fileIcon}</span>
                    <span style="flex: 1;">${escapeHtml(file.name)}</span>
                    ${isImage ? `<button class="btn btn-secondary" style="padding: 0.25rem 0.5rem; font-size: 0.75rem; margin-right: 0.25rem;" onclick="event.stopPropagation(); previewImage('${file.path.replace(/'/g, "\\'")}')" title="Preview Image">👁️</button>` : ''}
                    <button class="btn btn-secondary" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;" onclick="event.stopPropagation(); showRenameDialog('${file.path.replace(/'/g, "\\'")}', false)">Rename</button>
                `;
                item.onclick = () => openFile(file.path);
                fileListEl.appendChild(item);
            });
            
            if (data.directories.length === 0 && data.files.length === 0) {
                fileListEl.innerHTML = '<div class="loading">No files found</div>';
            }
        })
        .catch(err => {
            fileListEl.innerHTML = `<div class="loading" style="color: #f44336;">Error: ${err.message}</div>`;
        });
}

function openFile(path) {
    currentFilePath = path;
    
    // Update active file in sidebar
    document.querySelectorAll('.file-item').forEach(el => el.classList.remove('active'));
    event.currentTarget.classList.add('active');
    
    // Show editor toolbar
    document.getElementById('editor-toolbar').style.display = 'flex';
    document.getElementById('current-file').textContent = path;
    document.getElementById('file-status').textContent = '';
    document.getElementById('file-status').className = 'status';
    
    // Load file content
    fetch(`${API_BASE}/api/file?path=${encodeURIComponent(path)}`)
        .then(res => res.json())
        .then(data => {
            const container = document.getElementById('editor-container');
            
            // Auto-enable preview for HTML files
            const isHtml = path.endsWith('.html') || path.endsWith('.htm');
            if (isHtml && previewEnabled === false) {
                previewEnabled = true;
            }
            
            // Create editor container with preview option
            container.innerHTML = `
                <div class="editor-with-preview" id="editor-wrapper">
                    <div class="editor-pane">
                        <textarea id="editor"></textarea>
                    </div>
                    <div class="preview-pane" id="preview-pane" style="display: ${isHtml && previewEnabled ? 'block' : 'none'};">
                        <iframe class="preview-iframe" id="preview-iframe" srcdoc=""></iframe>
                    </div>
                </div>
            `;
            
            // Update preview toggle button state
            const previewToggle = document.getElementById('preview-toggle');
            if (previewToggle) {
                previewToggle.textContent = (isHtml && previewEnabled) ? 'Hide Preview' : 'Preview';
            }
            
            // Load initial preview for HTML files using the preview endpoint
            if (isHtml && previewEnabled) {
                const iframe = document.getElementById('preview-iframe');
                if (iframe) {
                    // Use iframe.src instead of srcdoc for better cookie/session handling
                    // This ensures assets can load with proper authentication
                    const previewUrl = `/preview/${encodeURIComponent(path)}`;
                    iframe.src = previewUrl;
                    
                    // Setup resize handle after preview is loaded
                    setTimeout(setupEditorPreviewResize, 200);
                }
            } else {
                // Hide resize handle if preview is not enabled
                const handle = document.getElementById('editor-preview-resize-handle');
                if (handle) {
                    handle.style.display = 'none';
                }
            }
            
            // Determine mode based on file extension
            const ext = path.split('.').pop().toLowerCase();
            let mode = 'text/plain';
            if (['html', 'htm'].includes(ext)) mode = 'text/html';
            else if (ext === 'css') mode = 'text/css';
            else if (['js', 'javascript'].includes(ext)) mode = 'text/javascript';
            else if (ext === 'xml') mode = 'text/xml';
            else if (ext === 'json') mode = 'application/json';
            
            // Initialize CodeMirror
            currentEditor = CodeMirror.fromTextArea(document.getElementById('editor'), {
                mode: mode,
                theme: 'monokai',
                lineNumbers: true,
                lineWrapping: true,
                indentUnit: 2,
                indentWithTabs: false,
                autofocus: true
            });
            
            currentEditor.setValue(data.content);
            currentEditor.on('change', () => {
                document.getElementById('file-status').textContent = 'Unsaved changes';
                document.getElementById('file-status').className = 'status unsaved';
                updatePreview();
            });
            
            // Keyboard shortcuts
            currentEditor.on('keydown', (cm, e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                    e.preventDefault();
                    saveFile();
                } else if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                    e.preventDefault();
                    showFindReplace();
                }
            });
            
            // Update preview if HTML file
            if (path.endsWith('.html') || path.endsWith('.htm')) {
                updatePreview();
            }
        })
        .catch(err => {
            alert('Error loading file: ' + err.message);
        });
}

let previewUpdateTimer = null;

function updatePreview() {
    if (!previewEnabled || !currentEditor || !currentFilePath) return;
    if (!currentFilePath.endsWith('.html') && !currentFilePath.endsWith('.htm')) return;
    
    const previewIframe = document.getElementById('preview-iframe');
    if (!previewIframe) return;
    
    // Debounce preview updates (wait 800ms after typing stops for better performance)
    clearTimeout(previewUpdateTimer);
    previewUpdateTimer = setTimeout(() => {
        const content = currentEditor.getValue();
        
        // Use API to process HTML with proper asset path resolution
        fetch(`${API_BASE}/api/preview-html`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                content: content,
                file_path: currentFilePath
            })
        })
        .then(res => {
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }
            return res.json();
        })
        .then(data => {
            if (data.html) {
                // For better asset loading with cookies/sessions, save content and reload via src
                // Create a blob URL that points back to our server for proper asset resolution
                // Actually, use iframe.src pointing to /preview/ endpoint for proper cookie handling
                // But for real-time updates, we need srcdoc - so ensure base tag is correct
                previewIframe.srcdoc = data.html;
            }
        })
        .catch(err => {
            console.error('Preview update error:', err);
            // Ultimate fallback: direct blob
            const blob = new Blob([content], { type: 'text/html' });
            const url = URL.createObjectURL(blob);
            previewIframe.src = url;
        });
    }, 800);
}

function togglePreview() {
    if (!currentFilePath || (!currentFilePath.endsWith('.html') && !currentFilePath.endsWith('.htm'))) {
        alert('Preview is only available for HTML files');
        return;
    }
    
    previewEnabled = !previewEnabled;
    const previewPane = document.getElementById('preview-pane');
    const previewToggle = document.getElementById('preview-toggle');
    
    if (previewEnabled) {
        previewPane.style.display = 'block';
        previewToggle.textContent = 'Hide Preview';
        updatePreview();
    } else {
        previewPane.style.display = 'none';
        previewToggle.textContent = 'Preview';
    }
}

function saveFile() {
    if (!currentEditor || !currentFilePath) return;
    
    const content = currentEditor.getValue();
    
    fetch(`${API_BASE}/api/file`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            path: currentFilePath,
            content: content,
            backup: true
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            alert('Error saving file: ' + data.error);
        } else {
            document.getElementById('file-status').textContent = 'Saved' + (data.backup ? ' (backed up)' : '');
            document.getElementById('file-status').className = 'status saved';
            setTimeout(() => {
                document.getElementById('file-status').textContent = '';
            }, 3000);
            updatePreview();
        }
    })
    .catch(err => {
        alert('Error saving file: ' + err.message);
    });
}

function closeEditor() {
    currentEditor = null;
    currentFilePath = null;
    previewEnabled = false;
    document.getElementById('editor-toolbar').style.display = 'none';
    document.getElementById('editor-container').innerHTML = `
        <div class="welcome-message">
            <h2>Welcome to Way-CMS</h2>
            <p>Select a file from the sidebar to start editing</p>
            <p>Supported formats: HTML, CSS, JS, TXT, XML, JSON, MD</p>
        </div>
    `;
    document.querySelectorAll('.file-item').forEach(el => el.classList.remove('active'));
}

function deleteCurrentFile() {
    if (!currentFilePath) return;
    
    if (!confirm(`Are you sure you want to delete "${currentFilePath}"?`)) {
        return;
    }
    
    fetch(`${API_BASE}/api/file?path=${encodeURIComponent(currentFilePath)}`, {
        method: 'DELETE'
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            alert('Error deleting file: ' + data.error);
        } else {
            closeEditor();
            loadFiles(currentPath);
        }
    })
    .catch(err => {
        alert('Error deleting file: ' + err.message);
    });
}

function refreshFiles() {
    loadFiles(currentPath);
}

// Find & Replace in Editor
function showFindReplace() {
    document.getElementById('editor-find-modal').style.display = 'flex';
    document.getElementById('editor-find-input').focus();
}

function closeEditorFindReplace() {
    document.getElementById('editor-find-modal').style.display = 'none';
}

function editorFindNext() {
    if (!currentEditor) return;
    const query = document.getElementById('editor-find-input').value;
    if (!query) return;
    
    currentEditor.execCommand('find');
}

function editorReplace() {
    if (!currentEditor) return;
    const find = document.getElementById('editor-find-input').value;
    const replace = document.getElementById('editor-replace-input').value;
    
    const cursor = currentEditor.getSearchCursor(find);
    if (cursor.findNext()) {
        cursor.replace(replace);
        document.getElementById('file-status').textContent = 'Unsaved changes';
        document.getElementById('file-status').className = 'status unsaved';
        updatePreview();
    }
}

function editorReplaceAll() {
    if (!currentEditor) return;
    const find = document.getElementById('editor-find-input').value;
    const replace = document.getElementById('editor-replace-input').value;
    
    if (!confirm(`Replace all occurrences of "${find}" with "${replace}"?`)) {
        return;
    }
    
    let count = 0;
    const cursor = currentEditor.getSearchCursor(find);
    while (cursor.findNext()) {
        cursor.replace(replace);
        count++;
    }
    
    if (count > 0) {
        document.getElementById('file-status').textContent = `Replaced ${count} occurrences (unsaved)`;
        document.getElementById('file-status').className = 'status unsaved';
        updatePreview();
        alert(`Replaced ${count} occurrences`);
    } else {
        alert('No matches found');
    }
}

// Create File/Folder
function showCreateFileDialog() {
    createType = 'file';
    createPath = currentPath || '';
    document.getElementById('create-dialog-title').textContent = 'Create New File';
    document.getElementById('create-dialog-label').textContent = 'File Name:';
    document.getElementById('create-dialog-input').value = '';
    document.getElementById('create-dialog').style.display = 'flex';
    document.getElementById('create-dialog-input').focus();
}

function showCreateFolderDialog() {
    createType = 'folder';
    createPath = currentPath || '';
    document.getElementById('create-dialog-title').textContent = 'Create New Folder';
    document.getElementById('create-dialog-label').textContent = 'Folder Name:';
    document.getElementById('create-dialog-input').value = '';
    document.getElementById('create-dialog').style.display = 'flex';
    document.getElementById('create-dialog-input').focus();
}

function closeCreateDialog() {
    document.getElementById('create-dialog').style.display = 'none';
    createType = null;
    createPath = null;
}

function confirmCreate() {
    const name = document.getElementById('create-dialog-input').value.trim();
    if (!name) {
        alert('Please enter a name');
        return;
    }
    
    const path = createPath ? `${createPath}/${name}` : name;
    
    fetch(`${API_BASE}/api/file`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            path: path,
            is_directory: createType === 'folder',
            content: createType === 'file' ? '' : undefined
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            alert('Error: ' + data.error);
        } else {
            closeCreateDialog();
            loadFiles(currentPath);
            if (createType === 'file') {
                openFile(path);
            }
        }
    })
    .catch(err => {
        alert('Error: ' + err.message);
    });
}

// Rename File/Folder
function showRenameDialog(path, isDirectory) {
    renameTarget = { path, isDirectory };
    const name = path.split('/').pop();
    document.getElementById('rename-input').value = name;
    document.getElementById('rename-dialog').style.display = 'flex';
    document.getElementById('rename-input').focus();
}

function closeRenameDialog() {
    document.getElementById('rename-dialog').style.display = 'none';
    renameTarget = null;
}

function confirmRename() {
    if (!renameTarget) return;
    
    const newName = document.getElementById('rename-input').value.trim();
    if (!newName) {
        alert('Please enter a name');
        return;
    }
    
    const oldPath = renameTarget.path;
    const pathParts = oldPath.split('/');
    pathParts[pathParts.length - 1] = newName;
    const newPath = pathParts.join('/');
    
    fetch(`${API_BASE}/api/file`, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            old_path: oldPath,
            new_path: newPath
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            alert('Error: ' + data.error);
        } else {
            closeRenameDialog();
            if (currentFilePath === oldPath) {
                currentFilePath = newPath;
                openFile(newPath);
            }
            loadFiles(currentPath);
        }
    })
    .catch(err => {
        alert('Error: ' + err.message);
    });
}

// Global Search
function toggleSearch() {
    const modal = document.getElementById('search-modal');
    modal.style.display = modal.style.display === 'none' ? 'flex' : 'none';
    if (modal.style.display === 'flex') {
        document.getElementById('search-query').focus();
    }
}

function performSearch() {
    const query = document.getElementById('search-query').value;
    const pattern = document.getElementById('search-pattern').value || '*';
    
    if (!query) {
        alert('Please enter a search query');
        return;
    }
    
    const resultsEl = document.getElementById('search-results');
    resultsEl.innerHTML = '<div class="loading">Searching...</div>';
    
    fetch(`${API_BASE}/api/search?q=${encodeURIComponent(query)}&pattern=${encodeURIComponent(pattern)}`)
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                resultsEl.innerHTML = `<div class="loading" style="color: #f44336;">Error: ${data.error}</div>`;
                return;
            }
            
            if (data.results.length === 0) {
                resultsEl.innerHTML = '<div class="loading">No results found</div>';
                return;
            }
            
            resultsEl.innerHTML = '';
            data.results.forEach(result => {
                const item = document.createElement('div');
                item.className = 'search-result-item';
                
                let matchesHtml = '';
                result.matches.forEach(match => {
                    matchesHtml += `
                        <div class="match-line">
                            <span class="line-number">Line ${match.line}:</span>
                            ${escapeHtml(match.text)}
                        </div>
                    `;
                });
                
                item.innerHTML = `
                    <div class="file-path" onclick="openFile('${result.path.replace(/'/g, "\\'")}'); toggleSearch();">
                        ${escapeHtml(result.path)}
                    </div>
                    ${matchesHtml}
                `;
                resultsEl.appendChild(item);
            });
        })
        .catch(err => {
            resultsEl.innerHTML = `<div class="loading" style="color: #f44336;">Error: ${err.message}</div>`;
        });
}

// Global Find & Replace
function toggleGlobalReplace() {
    const modal = document.getElementById('global-replace-modal');
    modal.style.display = modal.style.display === 'none' ? 'flex' : 'none';
    if (modal.style.display === 'flex') {
        document.getElementById('global-search-input').focus();
    }
}

function performGlobalSearch() {
    const search = document.getElementById('global-search-input').value;
    const replace = document.getElementById('global-replace-input').value;
    const pattern = document.getElementById('global-file-pattern').value || '*';
    const useRegex = document.getElementById('global-regex').checked;
    const caseSensitive = document.getElementById('global-case-sensitive').checked;
    
    if (!search) {
        alert('Please enter a search query');
        return;
    }
    
    const resultsEl = document.getElementById('global-results');
    resultsEl.innerHTML = '<div class="loading">Searching...</div>';
    
    fetch(`${API_BASE}/api/search-replace`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            search: search,
            replace: replace,
            pattern: pattern,
            regex: useRegex,
            case_sensitive: caseSensitive,
            dry_run: true
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            resultsEl.innerHTML = `<div class="loading" style="color: #f44336;">Error: ${data.error}</div>`;
            return;
        }
        
        if (data.changes.length === 0) {
            resultsEl.innerHTML = '<div class="loading">No matches found</div>';
            return;
        }
        
        let html = `<div style="margin-bottom: 1rem; padding: 0.5rem; background: #2d2d2d; border-radius: 4px;">
            Found ${data.changes.length} file(s) with matches. Total matches: ${data.changes.reduce((sum, c) => sum + (c.matches || 0), 0)}
        </div>`;
        
        data.changes.forEach(change => {
            if (change.error) {
                html += `<div class="search-result-item" style="color: #f44336;">
                    ${escapeHtml(change.file)}: ${escapeHtml(change.error)}
                </div>`;
            } else {
                html += `<div class="search-result-item">
                    <div class="file-path">${escapeHtml(change.file)} - ${change.matches} match(es)</div>
                    <div style="font-size: 0.75rem; color: #999; margin-top: 0.5rem;">
                        ${escapeHtml(change.preview.substring(0, 200))}...
                    </div>
                </div>`;
            }
        });
        
        resultsEl.innerHTML = html;
    })
    .catch(err => {
        resultsEl.innerHTML = `<div class="loading" style="color: #f44336;">Error: ${err.message}</div>`;
    });
}

function performGlobalReplace() {
    const search = document.getElementById('global-search-input').value;
    const replace = document.getElementById('global-replace-input').value;
    const pattern = document.getElementById('global-file-pattern').value || '*';
    const useRegex = document.getElementById('global-regex').checked;
    const caseSensitive = document.getElementById('global-case-sensitive').checked;
    
    if (!search) {
        alert('Please enter a search query');
        return;
    }
    
    if (!confirm(`This will replace all occurrences in matching files. Continue?`)) {
        return;
    }
    
    const resultsEl = document.getElementById('global-results');
    resultsEl.innerHTML = '<div class="loading">Replacing...</div>';
    
    fetch(`${API_BASE}/api/search-replace`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            search: search,
            replace: replace,
            pattern: pattern,
            regex: useRegex,
            case_sensitive: caseSensitive,
            dry_run: false
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            resultsEl.innerHTML = `<div class="loading" style="color: #f44336;">Error: ${data.error}</div>`;
            return;
        }
        
        const successCount = data.changes.filter(c => c.saved).length;
        resultsEl.innerHTML = `<div style="padding: 1rem; background: #4caf50; color: white; border-radius: 4px; margin-bottom: 1rem;">
            Successfully replaced in ${successCount} file(s)
        </div>`;
        
        // Refresh current file if it was modified
        if (currentFilePath && data.changes.some(c => c.file === currentFilePath && c.saved)) {
            openFile(currentFilePath);
        }
        
        loadFiles(currentPath);
    })
    .catch(err => {
        resultsEl.innerHTML = `<div class="loading" style="color: #f44336;">Error: ${err.message}</div>`;
    });
}

// Backup System
function createBackup() {
    if (!currentFilePath) {
        alert('No file open to backup');
        return;
    }
    
    fetch(`${API_BASE}/api/create-backup`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            path: currentFilePath
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            alert('Error creating backup: ' + data.error);
        } else {
            alert('Backup created successfully!');
        }
    })
    .catch(err => {
        alert('Error: ' + err.message);
    });
}

function toggleBackups() {
    const filePath = currentFilePath || prompt('Enter file path to view backups:');
    if (!filePath) return;
    
    document.getElementById('backups-file-name').textContent = filePath;
    document.getElementById('backups-modal').style.display = 'flex';
    
    loadBackups(filePath);
}

function loadBackups(filePath) {
    const backupsList = document.getElementById('backups-list');
    backupsList.innerHTML = '<div class="loading">Loading backups...</div>';
    
    fetch(`${API_BASE}/api/backups?path=${encodeURIComponent(filePath)}`)
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                backupsList.innerHTML = `<div class="loading" style="color: #f44336;">Error: ${data.error}</div>`;
                return;
            }
            
            if (data.backups.length === 0) {
                backupsList.innerHTML = '<div class="loading">No backups found</div>';
                return;
            }
            
            backupsList.innerHTML = '';
            data.backups.forEach(backup => {
                const item = document.createElement('div');
                item.className = 'search-result-item';
                item.style.marginBottom = '1rem';
                item.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div class="file-path">${backup.timestamp || backup.filename}</div>
                            <div style="font-size: 0.75rem; color: #999;">${backup.modified} - ${(backup.size / 1024).toFixed(1)} KB</div>
                        </div>
                        <div style="display: flex; gap: 0.5rem;">
                            <button class="btn btn-secondary" onclick="viewBackup('${backup.path.replace(/'/g, "\\'")}')">View</button>
                            <button class="btn btn-primary" onclick="restoreBackup('${filePath.replace(/'/g, "\\'")}', '${backup.path.replace(/'/g, "\\'")}')">Restore</button>
                        </div>
                    </div>
                `;
                backupsList.appendChild(item);
            });
        })
        .catch(err => {
            backupsList.innerHTML = `<div class="loading" style="color: #f44336;">Error: ${err.message}</div>`;
        });
}

function viewBackup(backupPath) {
    fetch(`${API_BASE}/api/backup/${encodeURIComponent(backupPath)}`)
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                alert('Error: ' + data.error);
                return;
            }
            
            // Open in new window or show in modal
            const blob = new Blob([data.content], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            window.open(url, '_blank');
        })
        .catch(err => {
            alert('Error: ' + err.message);
        });
}

function restoreBackup(filePath, backupPath) {
    if (!confirm(`Restore "${filePath}" from backup? This will overwrite the current file.`)) {
        return;
    }
    
    fetch(`${API_BASE}/api/restore-backup`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            file_path: filePath,
            backup_path: backupPath
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            alert('Error: ' + data.error);
        } else {
            alert('File restored successfully!');
            if (currentFilePath === filePath) {
                openFile(filePath);
            }
            loadFiles(currentPath);
        }
    })
    .catch(err => {
        alert('Error: ' + err.message);
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Download ZIP functionality
function downloadCurrentFolder() {
    const path = currentPath || '';
    const url = `${API_BASE}/api/download-zip?path=${encodeURIComponent(path)}`;
    window.location.href = url;
}

// Upload ZIP functionality
function showUploadZipDialog() {
    document.getElementById('upload-zip-dialog').style.display = 'flex';
    document.getElementById('zip-file-input').value = '';
    document.getElementById('zip-extract-path').value = '';
}

function closeUploadZipDialog() {
    document.getElementById('upload-zip-dialog').style.display = 'none';
}

function uploadZipFile() {
    const fileInput = document.getElementById('zip-file-input');
    const extractPath = document.getElementById('zip-extract-path').value.trim();
    const progressEl = document.getElementById('upload-progress');
    
    if (!fileInput.files || fileInput.files.length === 0) {
        alert('Please select a ZIP file');
        return;
    }
    
    const file = fileInput.files[0];
    if (!file.name.endsWith('.zip')) {
        alert('Please select a ZIP file');
        return;
    }
    
    progressEl.style.display = 'block';
    
    const formData = new FormData();
    formData.append('file', file);
    if (extractPath) {
        formData.append('path', extractPath);
    }
    
    fetch(`${API_BASE}/api/upload-zip`, {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        progressEl.style.display = 'none';
        if (data.error) {
            alert('Error: ' + data.error);
        } else {
            alert(`Successfully extracted ${data.files_count} file(s) to ${data.extracted_to || 'root'}`);
            closeUploadZipDialog();
            loadFiles(currentPath);
        }
    })
    .catch(err => {
        progressEl.style.display = 'none';
        alert('Error uploading: ' + err.message);
    });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    navigateTo('');
    
    // Handle Enter key in search
    document.getElementById('search-query').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            performSearch();
        }
    });
    
    // Handle Enter key in create dialog
    document.getElementById('create-dialog-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            confirmCreate();
        }
    });
    
    // Handle Enter key in rename dialog
    document.getElementById('rename-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            confirmRename();
        }
    });
    
    // Handle Escape to close modals
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal').forEach(modal => {
                if (modal.style.display === 'flex') {
                    modal.style.display = 'none';
                }
            });
        }
    });
});

// File icon helper function
function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const icons = {
        'html': '🌐', 'htm': '🌐',
        'css': '🎨',
        'js': '📜', 'javascript': '📜',
        'json': '📋',
        'xml': '📄',
        'md': '📝', 'markdown': '📝',
        'txt': '📄',
        'png': '🖼️', 'jpg': '🖼️', 'jpeg': '🖼️', 'gif': '🖼️', 'svg': '🖼️', 'webp': '🖼️', 'ico': '🖼️',
        'woff': '🔤', 'woff2': '🔤', 'ttf': '🔤', 'eot': '🔤',
        'zip': '📦',
        'pdf': '📕'
    };
    return icons[ext] || '📄';
}

// Image preview function
function previewImage(path) {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.display = 'flex';
    modal.style.zIndex = '10000';
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 90vw; max-height: 90vh; padding: 1rem;">
            <div class="modal-header">
                <h2>${path.split('/').pop()}</h2>
                <button class="close-btn" onclick="this.closest('.modal').remove()">&times;</button>
            </div>
            <div class="modal-body" style="text-align: center; padding: 1rem;">
                <img src="/preview-assets/${encodeURIComponent(path)}" style="max-width: 100%; max-height: 70vh; border-radius: 4px;" alt="${path}">
            </div>
        </div>
    `;
    modal.onclick = (e) => {
        if (e.target === modal) modal.remove();
    };
    document.body.appendChild(modal);
}

// File upload functions
function showUploadFileDialog() {
    document.getElementById('upload-file-dialog').style.display = 'flex';
    document.getElementById('file-upload-path').value = currentPath || '';
}

function closeUploadFileDialog() {
    document.getElementById('upload-file-dialog').style.display = 'none';
    document.getElementById('file-input').value = '';
}

function uploadFile() {
    const fileInput = document.getElementById('file-input');
    const uploadPath = document.getElementById('file-upload-path').value;
    const progressDiv = document.getElementById('file-upload-progress');
    
    if (!fileInput.files || !fileInput.files[0]) {
        alert('Please select a file');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    if (uploadPath) {
        formData.append('path', uploadPath);
    }
    
    progressDiv.style.display = 'block';
    
    fetch(`${API_BASE}/api/upload-file`, {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        progressDiv.style.display = 'none';
        if (data.error) {
            alert('Error uploading file: ' + data.error);
        } else {
            alert('File uploaded successfully!');
            closeUploadFileDialog();
            loadFiles(currentPath);
        }
    })
    .catch(err => {
        progressDiv.style.display = 'none';
        alert('Error: ' + err.message);
    });
}

// Theme toggle
function toggleTheme() {
    const body = document.body;
    const currentTheme = body.getAttribute('data-theme') || 'dark';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    body.setAttribute('data-theme', newTheme);
    localStorage.setItem('way-cms-theme', newTheme);
    updateThemeButton(newTheme);
}

function loadTheme() {
    const savedTheme = localStorage.getItem('way-cms-theme') || 'dark';
    document.body.setAttribute('data-theme', savedTheme);
    updateThemeButton(savedTheme);
}

function updateThemeButton(theme) {
    const btn = document.getElementById('theme-toggle');
    if (btn) {
        btn.textContent = theme === 'dark' ? '☀️ Light' : '🌙 Dark';
    }
}

// Keyboard shortcuts
function showKeyboardShortcuts() {
    document.getElementById('keyboard-shortcuts-modal').style.display = 'flex';
}

function closeKeyboardShortcuts() {
    document.getElementById('keyboard-shortcuts-modal').style.display = 'none';
}

// Initialize theme on load
document.addEventListener('DOMContentLoaded', () => {
    loadTheme();
    
    // Global keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Esc to close modals
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal').forEach(modal => {
                if (modal.style.display === 'flex') {
                    modal.style.display = 'none';
                }
            });
        }
    });
});
