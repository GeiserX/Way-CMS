// File browser navigation
function navigateTo(path) {
    currentPath = path;
    loadFiles(path);
    updateBreadcrumb(path);
}

function updateBreadcrumb(path) {
    const breadcrumbEl = document.getElementById('breadcrumb');
    const parts = path.split('/').filter(p => p);
    
    breadcrumbEl.innerHTML = '<span class="breadcrumb-item" onclick="navigateTo(\'\')">Root</span>';
    
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
                    <span>${escapeHtml(dir.name)}</span>
                `;
                item.onclick = () => navigateTo(dir.path);
                fileListEl.appendChild(item);
            });
            
            // Add files
            data.files.forEach(file => {
                const item = document.createElement('div');
                item.className = 'file-item';
                item.innerHTML = `
                    <span class="file-icon">📄</span>
                    <span>${escapeHtml(file.name)}</span>
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
            container.innerHTML = '<textarea id="editor"></textarea>';
            
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
            });
            
            // Keyboard shortcut for save (Ctrl+S or Cmd+S)
            currentEditor.on('keydown', (cm, e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                    e.preventDefault();
                    saveFile();
                }
            });
        })
        .catch(err => {
            alert('Error loading file: ' + err.message);
        });
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
            content: content
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            alert('Error saving file: ' + data.error);
        } else {
            document.getElementById('file-status').textContent = 'Saved';
            document.getElementById('file-status').className = 'status saved';
            setTimeout(() => {
                document.getElementById('file-status').textContent = '';
            }, 2000);
        }
    })
    .catch(err => {
        alert('Error saving file: ' + err.message);
    });
}

function closeEditor() {
    currentEditor = null;
    currentFilePath = null;
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

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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
});
