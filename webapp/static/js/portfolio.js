// Portfolio Management JavaScript

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadPortfolioStatus();
    setupEventListeners();
});

// Setup event listeners
function setupEventListeners() {
    document.getElementById('uploadForm').addEventListener('submit', handleUpload);
}

// Load portfolio status
async function loadPortfolioStatus() {
    try {
        const response = await fetch('/api/portfolio');
        const data = await response.json();
        
        if (data.success) {
            displayPortfolioStatus(data);
        } else {
            showError('Failed to load portfolio status: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error loading portfolio status:', error);
        showError('Error loading portfolio status: ' + error.message);
    }
}

// Display portfolio status
function displayPortfolioStatus(data) {
    // Update status info
    document.getElementById('portfolioPath').textContent = data.portfolio_path;
    document.getElementById('combinedTextLength').textContent = 
        data.portfolio_status.combined_text_length.toLocaleString() + ' characters';
    
    // Display files
    const filesList = document.getElementById('filesList');
    
    if (data.files.length === 0 && data.other_files.length === 0) {
        filesList.innerHTML = '<div class="loading">No portfolio files found</div>';
        return;
    }
    
    let html = '';
    
    // Expected files
    data.files.forEach(file => {
        const statusClass = file.exists ? 'exists' : 'missing';
        const statusText = file.exists ? 'Available' : 'Missing';
        const statusBadgeClass = file.exists ? 'status-exists' : 'status-missing';
        
        html += `
            <div class="file-card ${statusClass}">
                <div class="file-info">
                    <div class="file-name">${escapeHtml(file.display_name)}</div>
                    <div class="file-details">
                        <span>File: ${escapeHtml(file.filename)}</span>
                        ${file.exists ? `<span>Size: ${file.size_mb} MB</span>` : ''}
                    </div>
                    <span class="file-status ${statusBadgeClass}">${statusText}</span>
                </div>
                <div class="file-actions">
                    ${file.exists ? `
                        <button class="btn-file btn-view" onclick="viewFile('${escapeHtml(file.filename)}')">View</button>
                        <button class="btn-file btn-delete" onclick="deleteFile('${escapeHtml(file.filename)}')">Delete</button>
                    ` : `
                        <span style="color: #999; font-size: 0.9em;">Upload to add</span>
                    `}
                </div>
            </div>
        `;
    });
    
    // Other files
    if (data.other_files.length > 0) {
        html += '<h3 style="margin-top: 30px; margin-bottom: 15px; color: #667eea;">Other Files</h3>';
        data.other_files.forEach(file => {
            html += `
                <div class="file-card exists">
                    <div class="file-info">
                        <div class="file-name">${escapeHtml(file.display_name)}</div>
                        <div class="file-details">
                            <span>Size: ${file.size_mb} MB</span>
                        </div>
                        <span class="file-status status-exists">Available</span>
                    </div>
                    <div class="file-actions">
                        <button class="btn-file btn-view" onclick="viewFile('${escapeHtml(file.filename)}')">View</button>
                        <button class="btn-file btn-delete" onclick="deleteFile('${escapeHtml(file.filename)}')">Delete</button>
                    </div>
                </div>
            `;
        });
    }
    
    filesList.innerHTML = html;
}

// Handle file upload
async function handleUpload(e) {
    e.preventDefault();
    
    const fileInput = document.getElementById('fileInput');
    const targetFilename = document.getElementById('targetFilename');
    const uploadButton = document.getElementById('uploadButton');
    
    if (!fileInput.files || fileInput.files.length === 0) {
        alert('Please select a file to upload');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    if (targetFilename.value) {
        formData.append('target_filename', targetFilename.value);
    }
    
    // Disable button
    uploadButton.disabled = true;
    uploadButton.textContent = 'Uploading...';
    
    try {
        const response = await fetch('/api/portfolio/upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            showSuccess(`File uploaded successfully: ${data.filename}`);
            // Reset form
            fileInput.value = '';
            targetFilename.value = '';
            // Reload portfolio status
            await loadPortfolioStatus();
        } else {
            showError('Upload failed: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error uploading file:', error);
        showError('Error uploading file: ' + error.message);
    } finally {
        uploadButton.disabled = false;
        uploadButton.textContent = 'Upload';
    }
}

// View file
function viewFile(filename) {
    window.open(`/api/portfolio/${encodeURIComponent(filename)}`, '_blank');
}

// Delete file
async function deleteFile(filename) {
    if (!confirm(`Are you sure you want to delete "${filename}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/portfolio/${encodeURIComponent(filename)}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showSuccess(`File deleted: ${filename}`);
            await loadPortfolioStatus();
        } else {
            showError('Delete failed: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error deleting file:', error);
        showError('Error deleting file: ' + error.message);
    }
}

// Utility functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showError(message) {
    const filesList = document.getElementById('filesList');
    filesList.innerHTML = `<div class="error-message">${escapeHtml(message)}</div>`;
    setTimeout(() => {
        loadPortfolioStatus();
    }, 3000);
}

function showSuccess(message) {
    const filesList = document.getElementById('filesList');
    const existingHtml = filesList.innerHTML;
    filesList.innerHTML = `<div class="success-message">${escapeHtml(message)}</div>` + existingHtml;
    setTimeout(() => {
        const successMsg = filesList.querySelector('.success-message');
        if (successMsg) {
            successMsg.remove();
        }
    }, 3000);
}

