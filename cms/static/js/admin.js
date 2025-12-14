/**
 * Admin Panel JavaScript for Way-CMS Multi-Tenant
 */

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    loadUsers();
    loadProjects();
    loadAssignments();
    loadSettings();
});

// ============== Tab Navigation ==============

function initTabs() {
    const tabs = document.querySelectorAll('.admin-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active class from all tabs
            tabs.forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            // Add active to clicked tab
            tab.classList.add('active');
            const tabId = 'tab-' + tab.dataset.tab;
            document.getElementById(tabId).classList.add('active');
        });
    });
}

// ============== Toast Notifications ==============

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// ============== Modal Functions ==============

function openModal(modalId) {
    document.getElementById(modalId).classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

// Close modal on background click
document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('active');
        }
    });
});

// ============== User Management ==============

let usersData = [];
let projectsData = [];

async function loadUsers() {
    try {
        const response = await fetch('/admin/users');
        const data = await response.json();
        usersData = data.users;
        renderUsers();
    } catch (error) {
        showToast('Error loading users: ' + error.message, 'error');
    }
}

function renderUsers() {
    const tbody = document.getElementById('users-tbody');
    tbody.innerHTML = usersData.map(user => `
        <tr>
            <td>${escapeHtml(user.email)}</td>
            <td>${escapeHtml(user.name || '-')}</td>
            <td><span class="badge ${user.is_admin ? 'badge-admin' : 'badge-user'}">${user.is_admin ? 'Admin' : 'User'}</span></td>
            <td><span class="badge ${user.has_password ? 'badge-yes' : 'badge-no'}">${user.has_password ? 'Yes' : 'No'}</span></td>
            <td>${user.last_login ? new Date(user.last_login).toLocaleString() : 'Never'}</td>
            <td class="actions">
                <button class="btn btn-secondary btn-sm" onclick="editUser(${user.id})">Edit</button>
                <button class="btn btn-warning btn-sm" onclick="sendMagicLink(${user.id})">Send Link</button>
                <button class="btn btn-danger btn-sm" onclick="deleteUser(${user.id})">Delete</button>
            </td>
        </tr>
    `).join('');
}

function togglePasswordField() {
    const sendWelcome = document.getElementById('send-welcome-email').checked;
    const passwordGroup = document.getElementById('password-group');
    const passwordInput = document.getElementById('user-password');
    
    if (sendWelcome) {
        passwordGroup.style.display = 'none';
        passwordInput.removeAttribute('required');
    } else {
        passwordGroup.style.display = 'block';
        passwordInput.setAttribute('required', 'required');
    }
}

function showCreateUserModal() {
    // Reset form
    document.getElementById('user-email').value = '';
    document.getElementById('user-name').value = '';
    document.getElementById('user-is-admin').checked = false;
    document.getElementById('send-welcome-email').checked = true;
    document.getElementById('user-password').value = '';
    
    // Reset password field visibility
    togglePasswordField();
    
    // Populate projects select
    const select = document.getElementById('user-projects');
    select.innerHTML = projectsData.map(p => 
        `<option value="${p.id}">${escapeHtml(p.name)}</option>`
    ).join('');
    
    openModal('create-user-modal');
}

async function createUser() {
    const email = document.getElementById('user-email').value.trim();
    const name = document.getElementById('user-name').value.trim();
    const isAdmin = document.getElementById('user-is-admin').checked;
    const sendWelcome = document.getElementById('send-welcome-email').checked;
    const password = document.getElementById('user-password').value;
    
    const projectSelect = document.getElementById('user-projects');
    const projectIds = Array.from(projectSelect.selectedOptions).map(o => parseInt(o.value));
    
    if (!email) {
        showToast('Email is required', 'error');
        return;
    }
    
    // Require password if not sending welcome email
    if (!sendWelcome && !password) {
        showToast('Password is required when not sending welcome email', 'error');
        return;
    }
    
    try {
        const response = await fetch('/admin/users', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email,
                name,
                password: password || undefined,
                is_admin: isAdmin,
                project_ids: projectIds,
                send_welcome_email: sendWelcome
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast('User created successfully', 'success');
            if (data.warning) {
                showToast(data.warning, 'error');
            }
            closeModal('create-user-modal');
            loadUsers();
            loadAssignments();
        } else {
            showToast(data.error || 'Error creating user', 'error');
        }
    } catch (error) {
        showToast('Error creating user: ' + error.message, 'error');
    }
}

function editUser(userId) {
    const user = usersData.find(u => u.id === userId);
    if (!user) return;
    
    document.getElementById('edit-user-id').value = user.id;
    document.getElementById('edit-user-email').value = user.email;
    document.getElementById('edit-user-name').value = user.name || '';
    document.getElementById('edit-user-is-admin').checked = user.is_admin;
    
    openModal('edit-user-modal');
}

async function updateUser() {
    const userId = document.getElementById('edit-user-id').value;
    const name = document.getElementById('edit-user-name').value.trim();
    const isAdmin = document.getElementById('edit-user-is-admin').checked;
    
    try {
        const response = await fetch(`/admin/users/${userId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, is_admin: isAdmin })
        });
        
        if (response.ok) {
            showToast('User updated successfully', 'success');
            closeModal('edit-user-modal');
            loadUsers();
        } else {
            const data = await response.json();
            showToast(data.error || 'Error updating user', 'error');
        }
    } catch (error) {
        showToast('Error updating user: ' + error.message, 'error');
    }
}

async function deleteUser(userId) {
    if (!confirm('Are you sure you want to delete this user?')) return;
    
    try {
        const response = await fetch(`/admin/users/${userId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showToast('User deleted successfully', 'success');
            loadUsers();
            loadAssignments();
        } else {
            const data = await response.json();
            showToast(data.error || 'Error deleting user', 'error');
        }
    } catch (error) {
        showToast('Error deleting user: ' + error.message, 'error');
    }
}

async function sendMagicLink(userId) {
    try {
        const response = await fetch(`/admin/users/${userId}/send-link`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast(data.message || 'Magic link sent', 'success');
        } else {
            showToast(data.error || 'Error sending magic link', 'error');
        }
    } catch (error) {
        showToast('Error sending magic link: ' + error.message, 'error');
    }
}

// ============== Project Management ==============

async function loadProjects() {
    try {
        const response = await fetch('/admin/projects');
        const data = await response.json();
        projectsData = data.projects;
        renderProjects();
    } catch (error) {
        showToast('Error loading projects: ' + error.message, 'error');
    }
}

function renderProjects() {
    const tbody = document.getElementById('projects-tbody');
    tbody.innerHTML = projectsData.map(project => `
        <tr>
            <td>${escapeHtml(project.name)}</td>
            <td><code>${escapeHtml(project.slug)}</code></td>
            <td>${project.website_url ? `<a href="${escapeHtml(project.website_url)}" target="_blank">${escapeHtml(project.website_url)}</a>` : '-'}</td>
            <td>${new Date(project.created_at).toLocaleDateString()}</td>
            <td class="actions">
                <button class="btn btn-secondary btn-sm" onclick="editProject(${project.id})">Edit</button>
                <button class="btn btn-danger btn-sm" onclick="deleteProject(${project.id})">Delete</button>
            </td>
        </tr>
    `).join('');
}

function showCreateProjectModal() {
    document.getElementById('project-name').value = '';
    document.getElementById('project-slug').value = '';
    document.getElementById('project-url').value = '';
    openModal('create-project-modal');
}

// Auto-generate slug from name
document.getElementById('project-name')?.addEventListener('input', (e) => {
    const slugInput = document.getElementById('project-slug');
    if (!slugInput.value || slugInput.dataset.auto === 'true') {
        slugInput.value = e.target.value
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-|-$/g, '');
        slugInput.dataset.auto = 'true';
    }
});

document.getElementById('project-slug')?.addEventListener('input', () => {
    document.getElementById('project-slug').dataset.auto = 'false';
});

async function createProject() {
    const name = document.getElementById('project-name').value.trim();
    const slug = document.getElementById('project-slug').value.trim().toLowerCase();
    const websiteUrl = document.getElementById('project-url').value.trim();
    
    if (!name || !slug) {
        showToast('Name and slug are required', 'error');
        return;
    }
    
    if (!/^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$/.test(slug)) {
        showToast('Slug must contain only lowercase letters, numbers, and hyphens', 'error');
        return;
    }
    
    try {
        const response = await fetch('/admin/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, slug, website_url: websiteUrl || null })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast('Project created successfully', 'success');
            closeModal('create-project-modal');
            loadProjects();
        } else {
            showToast(data.error || 'Error creating project', 'error');
        }
    } catch (error) {
        showToast('Error creating project: ' + error.message, 'error');
    }
}

function editProject(projectId) {
    const project = projectsData.find(p => p.id === projectId);
    if (!project) return;
    
    document.getElementById('edit-project-id').value = project.id;
    document.getElementById('edit-project-name').value = project.name;
    document.getElementById('edit-project-slug').value = project.slug;
    document.getElementById('edit-project-url').value = project.website_url || '';
    
    openModal('edit-project-modal');
}

async function updateProject() {
    const projectId = document.getElementById('edit-project-id').value;
    const name = document.getElementById('edit-project-name').value.trim();
    const websiteUrl = document.getElementById('edit-project-url').value.trim();
    
    if (!name) {
        showToast('Project name is required', 'error');
        return;
    }
    
    try {
        const response = await fetch(`/admin/projects/${projectId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, website_url: websiteUrl || null })
        });
        
        if (response.ok) {
            showToast('Project updated successfully', 'success');
            closeModal('edit-project-modal');
            loadProjects();
        } else {
            const data = await response.json();
            showToast(data.error || 'Error updating project', 'error');
        }
    } catch (error) {
        showToast('Error updating project: ' + error.message, 'error');
    }
}

async function deleteProject(projectId) {
    if (!confirm('Are you sure you want to delete this project? This will NOT delete the project files.')) return;
    
    try {
        const response = await fetch(`/admin/projects/${projectId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showToast('Project deleted successfully', 'success');
            loadProjects();
            loadAssignments();
        } else {
            const data = await response.json();
            showToast(data.error || 'Error deleting project', 'error');
        }
    } catch (error) {
        showToast('Error deleting project: ' + error.message, 'error');
    }
}

// ============== Assignments Management ==============

let assignmentsData = [];

async function loadAssignments() {
    try {
        const response = await fetch('/admin/assignments');
        const data = await response.json();
        assignmentsData = data.assignments;
        renderAssignments();
    } catch (error) {
        showToast('Error loading assignments: ' + error.message, 'error');
    }
}

function renderAssignments() {
    const grid = document.getElementById('assignments-grid');
    
    if (assignmentsData.length === 0) {
        grid.innerHTML = '<p style="color: var(--text-secondary);">No assignments yet. Assign users to projects to give them access.</p>';
        return;
    }
    
    grid.innerHTML = assignmentsData.map(a => `
        <div class="assignment-card">
            <div class="assignment-info">
                <span class="assignment-user">${escapeHtml(a.email)}</span>
                <span class="assignment-project">📁 ${escapeHtml(a.project_name)}</span>
            </div>
            <button class="btn btn-danger btn-sm" onclick="removeAssignment(${a.user_id}, ${a.project_id})">Remove</button>
        </div>
    `).join('');
}

function showAssignModal() {
    // Populate users select
    const userSelect = document.getElementById('assign-user');
    userSelect.innerHTML = usersData
        .filter(u => !u.is_admin) // Don't need to assign admins
        .map(u => `<option value="${u.id}">${escapeHtml(u.email)}</option>`)
        .join('');
    
    // Populate projects select
    const projectSelect = document.getElementById('assign-project');
    projectSelect.innerHTML = projectsData.map(p => 
        `<option value="${p.id}">${escapeHtml(p.name)}</option>`
    ).join('');
    
    openModal('assign-modal');
}

async function assignUserToProject() {
    const userId = document.getElementById('assign-user').value;
    const projectId = document.getElementById('assign-project').value;
    
    if (!userId || !projectId) {
        showToast('Please select both user and project', 'error');
        return;
    }
    
    try {
        const response = await fetch('/admin/assignments', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: parseInt(userId), project_id: parseInt(projectId) })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast('User assigned successfully', 'success');
            closeModal('assign-modal');
            loadAssignments();
        } else {
            showToast(data.error || 'Error assigning user', 'error');
        }
    } catch (error) {
        showToast('Error assigning user: ' + error.message, 'error');
    }
}

async function removeAssignment(userId, projectId) {
    if (!confirm('Remove this user from the project?')) return;
    
    try {
        const response = await fetch(`/admin/assignments?user_id=${userId}&project_id=${projectId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showToast('Assignment removed', 'success');
            loadAssignments();
        } else {
            const data = await response.json();
            showToast(data.error || 'Error removing assignment', 'error');
        }
    } catch (error) {
        showToast('Error removing assignment: ' + error.message, 'error');
    }
}

// ============== Settings ==============

async function loadSettings() {
    // Load email config
    try {
        const response = await fetch('/admin/email/config');
        const data = await response.json();
        
        const configInfo = document.getElementById('email-config-info');
        if (data.configured) {
            configInfo.innerHTML = `
                <strong>Status:</strong> Configured ✓<br>
                <strong>Host:</strong> ${escapeHtml(data.host)}:${data.port}<br>
                <strong>User:</strong> ${escapeHtml(data.user)}<br>
                <strong>From:</strong> ${escapeHtml(data.from_name)} &lt;${escapeHtml(data.from_email)}&gt;
            `;
        } else {
            configInfo.innerHTML = `
                <strong>Status:</strong> Not configured ✗<br>
                <small>Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, and SMTP_FROM environment variables.</small>
            `;
        }
    } catch (error) {
        document.getElementById('email-config-info').textContent = 'Error loading config';
    }
    
    // Load stats
    try {
        const response = await fetch('/admin/stats');
        const data = await response.json();
        
        document.getElementById('stats-grid').innerHTML = `
            <div class="stat-card">
                <div class="stat-value">${data.users}</div>
                <div class="stat-label">Users</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${data.projects}</div>
                <div class="stat-label">Projects</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${data.assignments}</div>
                <div class="stat-label">Assignments</div>
            </div>
        `;
    } catch (error) {
        document.getElementById('stats-grid').textContent = 'Error loading stats';
    }
}

async function testEmailConfig() {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = 'Testing...';
    
    try {
        const response = await fetch('/admin/email/test', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            showToast('Email connection successful!', 'success');
        } else {
            showToast('Email test failed: ' + data.message, 'error');
        }
    } catch (error) {
        showToast('Error testing email: ' + error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Test Connection';
    }
}

// ============== Utilities ==============

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

