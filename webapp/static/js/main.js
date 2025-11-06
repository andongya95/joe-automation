// Global state
let allJobs = [];
let filteredJobs = [];
let currentSort = { column: 'fit_score', order: 'desc' };
let expandedJobId = null;
let editMode = false;
let editedJobs = {}; // Track edited jobs: {job_id: {field: value}}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    loadFields();
    loadLevels();
    loadJobs();
    setupEventListeners();
});

// Setup event listeners
function setupEventListeners() {
    // Filters
    document.getElementById('filterStatus').addEventListener('change', applyFilters);
    document.getElementById('filterField').addEventListener('change', applyFilters);
    document.getElementById('filterLevel').addEventListener('change', applyFilters);
    document.getElementById('filterMinScore').addEventListener('input', applyFilters);
    document.getElementById('searchInput').addEventListener('input', debounce(applyFilters, 300));
    document.getElementById('clearFilters').addEventListener('click', clearFilters);
    document.getElementById('scrapeButton').addEventListener('click', triggerScrape);
    document.getElementById('processButton').addEventListener('click', triggerProcess);
    document.getElementById('saveButton').addEventListener('click', saveEdits);
    document.getElementById('cancelEditButton').addEventListener('click', cancelEdit);
    
    // Sortable columns
    document.querySelectorAll('.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const column = th.dataset.sort;
            if (currentSort.column === column) {
                currentSort.order = currentSort.order === 'asc' ? 'desc' : 'asc';
            } else {
                currentSort.column = column;
                currentSort.order = 'desc';
            }
            updateSortIndicators();
            applyFilters();
        });
    });
    
    // Action buttons (delegated event listener)
    document.addEventListener('click', (e) => {
        if (e.target.dataset.action === 'view') {
            viewJobDetails(e.target.dataset.jobId);
        } else if (e.target.dataset.action === 'status') {
            updateStatus(e.target.dataset.jobId);
        } else if (e.target.dataset.action === 'edit') {
            enterEditMode(e.target.dataset.jobId);
        }
    });
    
    // Modal close
    document.querySelector('.close').addEventListener('click', closeModal);
    window.addEventListener('click', (e) => {
        const modal = document.getElementById('jobDetailsModal');
        if (e.target === modal) {
            closeModal();
        }
    });
}

// Load statistics
async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();
        
        if (data.success) {
            const stats = data.stats;
            document.getElementById('statTotal').textContent = stats.total;
            document.getElementById('statNew').textContent = stats.by_status.new || 0;
            document.getElementById('statApplied').textContent = stats.by_status.applied || 0;
            document.getElementById('statAvgScore').textContent = stats.avg_fit_score.toFixed(1);
        }
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Load fields for filter
async function loadFields() {
    try {
        const response = await fetch('/api/fields');
        const data = await response.json();
        
        if (data.success) {
            const select = document.getElementById('filterField');
            data.fields.forEach(field => {
                const option = document.createElement('option');
                option.value = field;
                option.textContent = field;
                select.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading fields:', error);
    }
}

// Load levels for filter
async function loadLevels() {
    try {
        const response = await fetch('/api/levels');
        const data = await response.json();
        
        if (data.success) {
            const select = document.getElementById('filterLevel');
            data.levels.forEach(level => {
                const option = document.createElement('option');
                option.value = level;
                option.textContent = level;
                select.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading levels:', error);
    }
}

// Load jobs
async function loadJobs() {
    try {
        const params = new URLSearchParams({
            sort_by: currentSort.column,
            order: currentSort.order
        });
        
        const response = await fetch(`/api/jobs?${params}`);
        const data = await response.json();
        
        if (data.success) {
            allJobs = data.jobs;
            applyFilters();
        } else {
            showError('Failed to load jobs');
        }
    } catch (error) {
        console.error('Error loading jobs:', error);
        showError('Error loading jobs: ' + error.message);
    }
}

// Apply filters
function applyFilters() {
    const status = document.getElementById('filterStatus').value;
    const field = document.getElementById('filterField').value;
    const level = document.getElementById('filterLevel').value;
    const minScore = document.getElementById('filterMinScore').value;
    const search = document.getElementById('searchInput').value.toLowerCase();
    
    filteredJobs = allJobs.filter(job => {
        if (status && job.application_status !== status) return false;
        if (field && job.field !== field) return false;
        if (level && job.level !== level) return false;
        if (minScore && (job.fit_score || 0) < parseFloat(minScore)) return false;
        if (search) {
            const searchText = search.toLowerCase();
            const title = (job.title || '').toLowerCase();
            const institution = (job.institution || '').toLowerCase();
            const description = (job.description || '').toLowerCase();
            if (!title.includes(searchText) && !institution.includes(searchText) && !description.includes(searchText)) {
                return false;
            }
        }
        return true;
    });
    
    // Sort
    sortJobs(filteredJobs);
    renderJobs();
}

// Sort jobs
function sortJobs(jobs) {
    const { column, order } = currentSort;
    const reverse = order === 'desc';
    
    jobs.sort((a, b) => {
        let aVal, bVal;
        
        switch (column) {
            case 'fit_score':
                aVal = a.fit_score || 0;
                bVal = b.fit_score || 0;
                break;
            case 'deadline':
                aVal = a.deadline || '';
                bVal = b.deadline || '';
                break;
            case 'institution':
                aVal = (a.institution || '').toLowerCase();
                bVal = (b.institution || '').toLowerCase();
                break;
            case 'title':
                aVal = (a.title || '').toLowerCase();
                bVal = (b.title || '').toLowerCase();
                break;
            default:
                return 0;
        }
        
        if (aVal < bVal) return reverse ? 1 : -1;
        if (aVal > bVal) return reverse ? -1 : 1;
        return 0;
    });
}

// Update sort indicators
function updateSortIndicators() {
    document.querySelectorAll('.sortable').forEach(th => {
        th.classList.remove('asc', 'desc');
        if (th.dataset.sort === currentSort.column) {
            th.classList.add(currentSort.order);
        }
    });
}

// Render jobs table
function renderJobs() {
    const tbody = document.getElementById('jobsTableBody');
    
    if (filteredJobs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="loading">No jobs found</td></tr>';
        return;
    }
    
    tbody.innerHTML = filteredJobs.map(job => {
        const fitScore = job.fit_score || 0;
        const fitScoreClass = fitScore >= 70 ? 'fit-score-high' : fitScore >= 40 ? 'fit-score-medium' : 'fit-score-low';
        const statusClass = `status-${job.application_status || 'new'}`;
        
        return `
            <tr data-job-id="${job.job_id}">
                <td><span class="fit-score ${fitScoreClass}">${fitScore.toFixed(1)}</span></td>
                <td>${escapeHtml(job.title || 'N/A')}</td>
                <td>${escapeHtml(job.institution || 'N/A')}</td>
                <td>${escapeHtml(job.field || 'N/A')}</td>
                <td>${escapeHtml(job.level || 'N/A')}</td>
                <td>${formatDate(job.deadline)}</td>
                <td>${escapeHtml(job.location || 'N/A')}</td>
                <td><span class="status-badge ${statusClass}">${job.application_status || 'new'}</span></td>
                <td>
                    <a href="https://www.aeaweb.org/joe/listing/${job.job_id}" target="_blank" class="joe-link">View on JOE</a>
                </td>
                <td>
                    <div class="action-buttons">
                        <button class="btn btn-view" data-action="view" data-job-id="${job.job_id}">View</button>
                        <button class="btn btn-status" data-action="status" data-job-id="${job.job_id}">Status</button>
                        <button class="btn btn-edit" data-action="edit" data-job-id="${job.job_id}">Edit</button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

// View job details
async function viewJobDetails(jobId) {
    try {
        const response = await fetch(`/api/jobs/${jobId}`);
        const data = await response.json();
        
        if (data.success) {
            const job = data.job;
            const modal = document.getElementById('jobDetailsModal');
            const modalTitle = document.getElementById('modalTitle');
            const modalBody = document.getElementById('modalBody');
            
            modalTitle.textContent = job.title || 'Job Details';
            modalBody.innerHTML = `
                <div class="modal-section">
                    <h3>Basic Information</h3>
                    <p><strong>Institution:</strong> ${escapeHtml(job.institution || 'N/A')}</p>
                    <p><strong>Position Type:</strong> ${escapeHtml(job.position_type || 'N/A')}</p>
                    <p><strong>Field:</strong> ${escapeHtml(job.field || 'N/A')}</p>
                    <p><strong>Level:</strong> ${escapeHtml(job.level || 'N/A')}</p>
                    <p><strong>Location:</strong> ${escapeHtml(job.location || 'N/A')}</p>
                    <p><strong>Deadline:</strong> ${formatDate(job.deadline)}</p>
                    <p><strong>Posted Date:</strong> ${formatDate(job.posted_date)}</p>
                    <p><strong>Fit Score:</strong> ${(job.fit_score || 0).toFixed(1)}</p>
                    <p><strong>Status:</strong> <span class="status-badge status-${job.application_status || 'new'}">${job.application_status || 'new'}</span></p>
                </div>
                ${job.description ? `
                <div class="modal-section">
                    <h3>Description</h3>
                    <p>${escapeHtml(job.description).replace(/\n/g, '<br>')}</p>
                </div>
                ` : ''}
                ${job.requirements ? `
                <div class="modal-section">
                    <h3>Requirements</h3>
                    <p>${escapeHtml(job.requirements).replace(/\n/g, '<br>')}</p>
                </div>
                ` : ''}
                ${job.contact_info ? `
                <div class="modal-section">
                    <h3>Contact Information</h3>
                    <p>${escapeHtml(job.contact_info).replace(/\n/g, '<br>')}</p>
                </div>
                ` : ''}
            `;
            
            modal.style.display = 'block';
        }
    } catch (error) {
        console.error('Error loading job details:', error);
        alert('Error loading job details');
    }
}

// Update job status
async function updateStatus(jobId) {
    const currentStatus = allJobs.find(j => j.job_id === jobId)?.application_status || 'new';
    const statuses = ['new', 'applied', 'expired', 'rejected'];
    const currentIndex = statuses.indexOf(currentStatus);
    const nextStatus = statuses[(currentIndex + 1) % statuses.length];
    
    if (confirm(`Change status from "${currentStatus}" to "${nextStatus}"?`)) {
        try {
            const response = await fetch(`/api/jobs/${jobId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    application_status: nextStatus
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Update local data
                const job = allJobs.find(j => j.job_id === jobId);
                if (job) {
                    job.application_status = nextStatus;
                }
                applyFilters();
                loadStats();
            } else {
                alert('Failed to update status: ' + (data.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error updating status:', error);
            alert('Error updating status: ' + error.message);
        }
    }
}

// Close modal
function closeModal() {
    document.getElementById('jobDetailsModal').style.display = 'none';
}

// Clear filters
function clearFilters() {
    document.getElementById('filterStatus').value = '';
    document.getElementById('filterField').value = '';
    document.getElementById('filterLevel').value = '';
    document.getElementById('filterMinScore').value = '';
    document.getElementById('searchInput').value = '';
    applyFilters();
}

// Utility functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    try {
        const date = new Date(dateString);
        return date.toLocaleDateString();
    } catch {
        return dateString;
    }
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Trigger scraping
async function triggerScrape() {
    const button = document.getElementById('scrapeButton');
    const originalText = button.textContent;
    
    // Disable button and show loading state
    button.disabled = true;
    button.classList.add('scraping');
    button.textContent = 'Scraping...';
    
    try {
        const response = await fetch('/api/scrape', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Show success message
            alert(`Scraping complete!\n${data.message}\n\nNew jobs: ${data.new_count}\nUpdated jobs: ${data.updated_count}\nTotal scraped: ${data.total_scraped}`);
            
            // Reload jobs and stats
            await loadJobs();
            await loadStats();
            await loadFields();
            await loadLevels();
        } else {
            alert('Scraping failed: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error triggering scrape:', error);
        alert('Error triggering scrape: ' + error.message);
    } finally {
        // Re-enable button
        button.disabled = false;
        button.classList.remove('scraping');
        button.textContent = originalText;
    }
}

// Trigger LLM processing
async function triggerProcess() {
    const button = document.getElementById('processButton');
    const originalText = button.textContent;
    
    // Disable button and show loading state
    button.disabled = true;
    button.classList.add('processing');
    button.textContent = 'Processing...';
    
    try {
        const response = await fetch('/api/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ limit: null })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`LLM Processing complete!\n${data.message}\n\nProcessed: ${data.processed_count}\nErrors: ${data.error_count}\nTotal: ${data.total_processed}`);
            
            // Reload jobs and stats
            await loadJobs();
            await loadStats();
            await loadFields();
            await loadLevels();
        } else {
            alert('Processing failed: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error triggering process:', error);
        alert('Error triggering process: ' + error.message);
    } finally {
        // Re-enable button
        button.disabled = false;
        button.classList.remove('processing');
        button.textContent = originalText;
    }
}

// Enter edit mode for a job
function enterEditMode(jobId) {
    // Check if this row is already in edit mode
    const row = document.querySelector(`tr[data-job-id="${jobId}"]`);
    if (!row) return;
    
    // If row is already editable, do nothing
    if (row.querySelector('td.editable')) {
        return;
    }
    
    // Enable edit mode if not already enabled
    if (!editMode) {
        editMode = true;
        document.getElementById('editControls').style.display = 'flex';
    }
    
    // Make editable fields
    // Column order: fit_score(0), title(1), institution(2), field(3), level(4), deadline(5), location(6), status(7), link(8), actions(9)
    const editableFields = ['title', 'institution', 'field', 'level', 'deadline', 'location', 'application_status'];
    const editableIndices = [1, 2, 3, 4, 5, 6, 7]; // Corresponding cell indices
    const cells = row.querySelectorAll('td');
    
    editableFields.forEach((field, index) => {
        const cellIndex = editableIndices[index];
        if (cells[cellIndex]) {
            const cell = cells[cellIndex];
            let currentValue = cell.textContent.trim();
            
            // For status, extract from badge
            if (field === 'application_status') {
                const badge = cell.querySelector('.status-badge');
                if (badge) {
                    currentValue = badge.textContent.trim().toLowerCase();
                }
            }
            
            cell.classList.add('editable');
            
            if (field === 'application_status') {
                // Status dropdown
                cell.innerHTML = `
                    <select data-field="${field}" data-job-id="${jobId}">
                        <option value="new" ${currentValue === 'new' ? 'selected' : ''}>new</option>
                        <option value="applied" ${currentValue === 'applied' ? 'selected' : ''}>applied</option>
                        <option value="expired" ${currentValue === 'expired' ? 'selected' : ''}>expired</option>
                        <option value="rejected" ${currentValue === 'rejected' ? 'selected' : ''}>rejected</option>
                    </select>
                `;
            } else if (field === 'deadline') {
                // Date input
                const dateValue = currentValue !== 'N/A' ? currentValue : '';
                cell.innerHTML = `<input type="date" data-field="${field}" data-job-id="${jobId}" value="${dateValue}">`;
            } else {
                // Text input
                cell.innerHTML = `<input type="text" data-field="${field}" data-job-id="${jobId}" value="${escapeHtml(currentValue)}">`;
            }
            
            // Track changes
            const input = cell.querySelector('input, select');
            input.addEventListener('change', function() {
                const jobId = this.dataset.jobId;
                const field = this.dataset.field;
                const value = this.value;
                
                if (!editedJobs[jobId]) {
                    editedJobs[jobId] = {};
                }
                editedJobs[jobId][field] = value;
                
                cell.classList.add('edited');
                updateEditStatus();
            });
        }
    });
    
    // Update edit status
    updateEditStatus();
}

// Update edit status message
function updateEditStatus() {
    const statusEl = document.getElementById('editStatus');
    const count = Object.keys(editedJobs).length;
    if (count > 0) {
        statusEl.textContent = `${count} job(s) with unsaved changes`;
    } else {
        statusEl.textContent = '';
    }
}

// Save edits
async function saveEdits() {
    if (Object.keys(editedJobs).length === 0) {
        alert('No changes to save');
        return;
    }
    
    if (!confirm(`Save changes to ${Object.keys(editedJobs).length} job(s)?`)) {
        return;
    }
    
    try {
        const response = await fetch('/api/jobs/batch', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ updates: editedJobs })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`Changes saved!\n${data.message}`);
            
            // Exit edit mode and reload
            cancelEdit();
            await loadJobs();
            await loadStats();
        } else {
            alert('Failed to save: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error saving edits:', error);
        alert('Error saving edits: ' + error.message);
    }
}

// Cancel edit mode
function cancelEdit() {
    editMode = false;
    editedJobs = {};
    document.getElementById('editControls').style.display = 'none';
    
    // Reload jobs to reset table
    renderJobs();
}

function showError(message) {
    const tbody = document.getElementById('jobsTableBody');
    tbody.innerHTML = `<tr><td colspan="10" class="loading" style="color: #ef4444;">${escapeHtml(message)}</td></tr>`;
}

