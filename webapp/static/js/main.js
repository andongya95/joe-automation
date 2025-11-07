// Global state
let allJobs = [];
let filteredJobs = [];
let currentSort = { column: 'fit_score', order: 'desc' };
let expandedJobId = null;
let editMode = false;
let editedJobs = {}; // Track edited jobs: {job_id: {field: value}}
let selectedJobs = new Set(); // Track selected job IDs for bulk operations

// Column configuration
const COLUMN_DEFINITIONS = [
    { id: 'checkbox', label: 'Select', defaultWidth: 50, resizable: false },
    { id: 'fit_score', label: 'Fit Score', defaultWidth: 100, resizable: true },
    { id: 'title', label: 'Title', defaultWidth: 200, resizable: true },
    { id: 'institution', label: 'Institution', defaultWidth: 180, resizable: true },
    { id: 'field', label: 'Field', defaultWidth: 150, resizable: true },
    { id: 'level', label: 'Level', defaultWidth: 120, resizable: true },
    { id: 'deadline', label: 'Deadline', defaultWidth: 110, resizable: true },
    { id: 'extracted_deadline', label: 'Extracted Deadline', defaultWidth: 140, resizable: true },
    { id: 'location', label: 'Location', defaultWidth: 150, resizable: true },
    { id: 'country', label: 'Country', defaultWidth: 120, resizable: true },
    { id: 'status', label: 'Status', defaultWidth: 100, resizable: true },
    { id: 'application_materials', label: 'Application Materials', defaultWidth: 250, resizable: true },
    { id: 'references_separate_email', label: 'Refs Separate Email', defaultWidth: 140, resizable: true },
    { id: 'application_portal', label: 'Application Portal', defaultWidth: 150, resizable: true },
    { id: 'link', label: 'Link', defaultWidth: 80, resizable: true },
    { id: 'actions', label: 'Actions', defaultWidth: 150, resizable: true }
];

let columnConfig = loadColumnConfig();

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    loadFilters();
    loadJobs();
    setupEventListeners();
});

// Setup event listeners
function setupEventListeners() {
    // Filters
    document.getElementById('filterStatus').addEventListener('change', applyFilters);
    document.getElementById('filterField').addEventListener('change', applyFilters);
    document.getElementById('filterLevel').addEventListener('change', applyFilters);
    document.getElementById('filterCountry').addEventListener('change', applyFilters);
    document.getElementById('filterMinScore').addEventListener('input', applyFilters);
    document.getElementById('searchInput').addEventListener('input', debounce(applyFilters, 300));
    document.getElementById('clearFilters').addEventListener('click', clearFilters);
    document.getElementById('scrapeButton').addEventListener('click', triggerScrape);
    document.getElementById('processButton').addEventListener('click', triggerProcess);
    document.getElementById('matchButton').addEventListener('click', triggerMatch);
    document.getElementById('saveButton').addEventListener('click', saveEdits);
    document.getElementById('cancelEditButton').addEventListener('click', cancelEdit);
    
    // Bulk selection
    document.getElementById('selectAllCheckbox').addEventListener('change', toggleSelectAll);
    document.getElementById('selectAllBtn').addEventListener('click', selectAllVisible);
    document.getElementById('deselectAllBtn').addEventListener('click', deselectAll);
    document.getElementById('bulkUpdateBtn').addEventListener('click', bulkUpdateStatus);
    
    // Column settings
    document.getElementById('columnSettingsBtn').addEventListener('click', openColumnSettings);
    document.getElementById('closeColumnSettings').addEventListener('click', closeColumnSettings);
    document.getElementById('saveColumnSettings').addEventListener('click', saveColumnSettings);
    document.getElementById('resetColumnSettings').addEventListener('click', resetColumnSettings);
    
    // Close modal when clicking outside
    window.addEventListener('click', (e) => {
        const modal = document.getElementById('columnSettingsModal');
        if (e.target === modal) {
            closeColumnSettings();
        }
    });
    
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

// Load filters (fields, levels, countries)
async function loadFilters() {
    try {
        const [fieldsRes, levelsRes, countriesRes] = await Promise.all([
            fetch('/api/fields'),
            fetch('/api/levels'),
            fetch('/api/countries')
        ]);
        
        const fieldsData = await fieldsRes.json();
        const levelsData = await levelsRes.json();
        const countriesData = await countriesRes.json();
        
        if (fieldsData.success) {
            const filterField = document.getElementById('filterField');
            if (filterField) {
                while (filterField.options.length > 1) {
                    filterField.remove(1);
                }
                fieldsData.fields.forEach(field => {
                    const option = document.createElement('option');
                    option.value = field;
                    option.textContent = field;
                    filterField.appendChild(option);
                });
            }
        }
        
        if (levelsData.success) {
            const filterLevel = document.getElementById('filterLevel');
            if (filterLevel) {
                while (filterLevel.options.length > 1) {
                    filterLevel.remove(1);
                }
                levelsData.levels.forEach(level => {
                    const option = document.createElement('option');
                    option.value = level;
                    option.textContent = level;
                    filterLevel.appendChild(option);
                });
            }
        }
        
        if (countriesData.success) {
            const filterCountry = document.getElementById('filterCountry');
            if (filterCountry) {
                while (filterCountry.options.length > 1) {
                    filterCountry.remove(1);
                }
                countriesData.countries.forEach(country => {
                    const option = document.createElement('option');
                    option.value = country;
                    option.textContent = country;
                    filterCountry.appendChild(option);
                });
            }
        }
    } catch (error) {
        console.error('Error loading filters:', error);
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
    const country = document.getElementById('filterCountry').value;
    const minScore = document.getElementById('filterMinScore').value;
    const search = document.getElementById('searchInput').value.toLowerCase();
    
    filteredJobs = allJobs.filter(job => {
        // By default, exclude "unrelated" jobs unless explicitly filtered
        if (!status && job.application_status === 'unrelated') return false;
        if (status && job.application_status !== status) return false;
        if (field && job.field !== field) return false;
        if (level && job.level !== level) return false;
        if (country && job.country !== country) return false;
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
        tbody.innerHTML = '<tr><td colspan="16" class="loading">No jobs found</td></tr>';
        return;
    }
    
    tbody.innerHTML = filteredJobs.map(job => {
        const fitScore = job.fit_score || 0;
        const fitScoreClass = fitScore >= 70 ? 'fit-score-high' : fitScore >= 40 ? 'fit-score-medium' : 'fit-score-low';
        const statusClass = `status-${job.application_status || 'new'}`;
        const isSelected = selectedJobs.has(job.job_id);
        
        return `
            <tr data-job-id="${job.job_id}">
                <td data-column="checkbox"><input type="checkbox" class="job-checkbox" data-job-id="${job.job_id}" ${isSelected ? 'checked' : ''}></td>
                <td data-column="fit_score"><span class="fit-score ${fitScoreClass}">${fitScore.toFixed(1)}</span></td>
                <td data-column="title">${escapeHtml(job.title || 'N/A')}</td>
                <td data-column="institution">${escapeHtml(job.institution || 'N/A')}</td>
                <td data-column="field">${escapeHtml(job.field || 'N/A')}</td>
                <td data-column="level">${escapeHtml(job.level || 'N/A')}</td>
                <td data-column="deadline">${formatDate(job.deadline)}</td>
                <td data-column="extracted_deadline">${formatDate(job.extracted_deadline)}</td>
                <td data-column="location">${escapeHtml(job.location || 'N/A')}</td>
                <td data-column="country">${escapeHtml(job.country || 'N/A')}</td>
                <td data-column="status"><span class="status-badge ${statusClass}">${job.application_status || 'new'}</span></td>
                <td data-column="application_materials">${formatApplicationMaterials(job.application_materials)}</td>
                <td data-column="references_separate_email">${job.references_separate_email ? '<span class="portal-badge">Yes</span>' : '<span style="color: #999;">No</span>'}</td>
                <td data-column="application_portal">
                    ${job.requires_separate_application ? 
                        (job.application_portal_url ? 
                            `<a href="${escapeHtml(job.application_portal_url)}" target="_blank" class="btn-portal">Apply</a>` : 
                            '<span class="portal-badge">Yes</span>') : 
                        '<span style="color: #999;">No</span>'
                    }
                </td>
                <td data-column="link">
                    ${job.job_id && /^\d+$/.test(job.job_id) ? 
                        `<a href="https://www.aeaweb.org/joe/listing.php?JOE_ID=${job.job_id}" target="_blank" class="btn-view-joe">View</a>` : 
                        '<span style="color: #999;">N/A</span>'
                    }
                </td>
                <td data-column="actions">
                    <div class="action-buttons">
                        <button class="btn btn-view" data-action="view" data-job-id="${job.job_id}">View</button>
                        <button class="btn btn-status" data-action="status" data-job-id="${job.job_id}">Status</button>
                        <button class="btn btn-edit" data-action="edit" data-job-id="${job.job_id}">Edit</button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
    
    // Update bulk actions visibility
    updateBulkActionsVisibility();
    
    // Attach checkbox event listeners after rendering
    document.querySelectorAll('.job-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', handleJobSelection);
    });
    
    // Update select all checkbox state
    updateSelectAllCheckbox();
    
    // Apply column configuration after rendering
    applyColumnConfig();
    setupColumnResizing();
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
    document.getElementById('filterCountry').value = '';
    document.getElementById('filterMinScore').value = '';
    document.getElementById('searchInput').value = '';
    applyFilters();
}

// Bulk selection functions
function handleJobSelection(event) {
    const jobId = event.target.dataset.jobId;
    if (event.target.checked) {
        selectedJobs.add(jobId);
    } else {
        selectedJobs.delete(jobId);
    }
    updateBulkActionsVisibility();
    updateSelectAllCheckbox();
}

function toggleSelectAll(event) {
    const checked = event.target.checked;
    document.querySelectorAll('.job-checkbox').forEach(checkbox => {
        checkbox.checked = checked;
        const jobId = checkbox.dataset.jobId;
        if (checked) {
            selectedJobs.add(jobId);
        } else {
            selectedJobs.delete(jobId);
        }
    });
    updateBulkActionsVisibility();
}

function selectAllVisible() {
    filteredJobs.forEach(job => {
        selectedJobs.add(job.job_id);
    });
    document.querySelectorAll('.job-checkbox').forEach(checkbox => {
        checkbox.checked = true;
    });
    updateBulkActionsVisibility();
    updateSelectAllCheckbox();
}

function deselectAll() {
    selectedJobs.clear();
    document.querySelectorAll('.job-checkbox').forEach(checkbox => {
        checkbox.checked = false;
    });
    document.getElementById('selectAllCheckbox').checked = false;
    updateBulkActionsVisibility();
}

function updateBulkActionsVisibility() {
    const bulkActions = document.getElementById('bulkActions');
    const selectedCount = document.getElementById('selectedCount');
    const count = selectedJobs.size;
    
    if (count > 0) {
        bulkActions.style.display = 'flex';
        selectedCount.textContent = `${count} selected`;
    } else {
        bulkActions.style.display = 'none';
    }
}

function updateSelectAllCheckbox() {
    const checkboxes = document.querySelectorAll('.job-checkbox');
    const allChecked = checkboxes.length > 0 && Array.from(checkboxes).every(cb => cb.checked);
    const someChecked = Array.from(checkboxes).some(cb => cb.checked);
    const selectAllCheckbox = document.getElementById('selectAllCheckbox');
    
    selectAllCheckbox.checked = allChecked;
    selectAllCheckbox.indeterminate = someChecked && !allChecked;
}

async function bulkUpdateStatus() {
    const status = document.getElementById('bulkStatusSelect').value;
    const jobIds = Array.from(selectedJobs);
    
    if (jobIds.length === 0) {
        alert('No jobs selected');
        return;
    }
    
    if (!confirm(`Update ${jobIds.length} job(s) to status "${status}"?`)) {
        return;
    }
    
    try {
        const updates = {};
        jobIds.forEach(jobId => {
            updates[jobId] = { application_status: status };
        });
        
        const response = await fetch('/api/jobs/batch', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ updates })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Update local state
            jobIds.forEach(jobId => {
                const job = allJobs.find(j => j.job_id === jobId);
                if (job) {
                    job.application_status = status;
                }
            });
            
            // Clear selection
            deselectAll();
            
            // Refresh display
            applyFilters();
            loadStats();
            
            alert(`Successfully updated ${data.updated_count} job(s) to "${status}"`);
        } else {
            alert('Failed to update jobs: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error updating jobs:', error);
        alert('Error updating jobs: ' + error.message);
    }
}

// Utility functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatApplicationMaterials(materials) {
    if (!materials) {
        return '<span style="color: #999;">N/A</span>';
    }
    
    // Handle both string (comma-separated) and array formats
    let items = [];
    if (typeof materials === 'string') {
        // Split by comma, clean up whitespace, filter empty strings
        items = materials.split(',').map(item => item.trim()).filter(item => item.length > 0);
    } else if (Array.isArray(materials)) {
        items = materials.map(item => typeof item === 'string' ? item.trim() : String(item)).filter(item => item.length > 0);
    } else {
        items = [String(materials)];
    }
    
    if (items.length === 0) {
        return '<span style="color: #999;">N/A</span>';
    }
    
    // Format as bulleted list with line breaks
    return '<ul style="margin: 0; padding-left: 20px; list-style-type: disc;">' +
           items.map(item => `<li style="margin: 2px 0;">${escapeHtml(item)}</li>`).join('') +
           '</ul>';
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

// Column configuration functions
function loadColumnConfig() {
    const saved = localStorage.getItem('columnConfig');
    if (saved) {
        try {
            return JSON.parse(saved);
        } catch (e) {
            console.error('Error loading column config:', e);
        }
    }
    // Default config: all columns visible with default widths
    const defaultConfig = {};
    COLUMN_DEFINITIONS.forEach(col => {
        defaultConfig[col.id] = {
            visible: true,
            width: col.defaultWidth
        };
    });
    return defaultConfig;
}

function saveColumnConfig() {
    localStorage.setItem('columnConfig', JSON.stringify(columnConfig));
}

function applyColumnConfig() {
    // Apply column widths
    COLUMN_DEFINITIONS.forEach(col => {
        const config = columnConfig[col.id];
        const width = config && config.width ? config.width : col.defaultWidth;
        const th = document.querySelector(`th[data-column="${col.id}"]`);
        if (th) {
            th.style.width = width + 'px';
            th.style.minWidth = width + 'px';
        }
        // Also apply to cells
        document.querySelectorAll(`td[data-column="${col.id}"]`).forEach(td => {
            td.style.width = width + 'px';
            td.style.minWidth = width + 'px';
        });
    });
    
    // Apply column visibility
    COLUMN_DEFINITIONS.forEach(col => {
        const config = columnConfig[col.id];
        const visible = config ? config.visible !== false : true;
        
        // Hide/show header
        const th = document.querySelector(`th[data-column="${col.id}"]`);
        if (th) {
            th.style.display = visible ? '' : 'none';
        }
        
        // Hide/show cells
        document.querySelectorAll(`td[data-column="${col.id}"]`).forEach(td => {
            td.style.display = visible ? '' : 'none';
        });
    });
}

function setupColumnResizing() {
    COLUMN_DEFINITIONS.forEach(col => {
        if (!col.resizable) return;
        
        const th = document.querySelector(`th[data-column="${col.id}"]`);
        if (!th) return;
        
        // Skip if resize handle already exists
        if (th.querySelector('.resize-handle')) return;
        
        let isResizing = false;
        let startX = 0;
        let startWidth = 0;
        
        const resizeHandle = document.createElement('div');
        resizeHandle.className = 'resize-handle';
        resizeHandle.style.cssText = 'position: absolute; right: 0; top: 0; width: 5px; height: 100%; cursor: col-resize; background: transparent; z-index: 10;';
        th.style.position = 'relative';
        th.appendChild(resizeHandle);
        
        resizeHandle.addEventListener('mousedown', (e) => {
            isResizing = true;
            startX = e.pageX;
            startWidth = th.offsetWidth;
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            e.preventDefault();
        });
        
        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;
            const diff = e.pageX - startX;
            const newWidth = Math.max(50, startWidth + diff);
            th.style.width = newWidth + 'px';
            th.style.minWidth = newWidth + 'px';
            
            // Update all cells in this column
            document.querySelectorAll(`td[data-column="${col.id}"]`).forEach(td => {
                td.style.width = newWidth + 'px';
                td.style.minWidth = newWidth + 'px';
            });
        });
        
        document.addEventListener('mouseup', () => {
            if (isResizing) {
                isResizing = false;
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
                
                // Save new width
                if (!columnConfig[col.id]) {
                    columnConfig[col.id] = {};
                }
                columnConfig[col.id].width = th.offsetWidth;
                saveColumnConfig();
            }
        });
    });
}

function openColumnSettings() {
    const modal = document.getElementById('columnSettingsModal');
    const controls = document.getElementById('columnVisibilityControls');
    
    controls.innerHTML = COLUMN_DEFINITIONS.map(col => {
        const config = columnConfig[col.id];
        const visible = config ? config.visible !== false : true;
        return `
            <label class="column-toggle">
                <input type="checkbox" data-column="${col.id}" ${visible ? 'checked' : ''}>
                <span>${col.label}</span>
            </label>
        `;
    }).join('');
    
    // Add event listeners
    controls.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            const colId = e.target.dataset.column;
            if (!columnConfig[colId]) {
                columnConfig[colId] = {};
            }
            columnConfig[colId].visible = e.target.checked;
        });
    });
    
    modal.style.display = 'block';
}

function closeColumnSettings() {
    document.getElementById('columnSettingsModal').style.display = 'none';
}

function saveColumnSettings() {
    saveColumnConfig();
    applyColumnConfig();
    renderJobs(); // Re-render to apply visibility changes
    closeColumnSettings();
    alert('Column settings saved!');
}

function resetColumnSettings() {
    if (confirm('Reset all column settings to default?')) {
        columnConfig = {};
        COLUMN_DEFINITIONS.forEach(col => {
            columnConfig[col.id] = {
                visible: true,
                width: col.defaultWidth
            };
        });
        saveColumnConfig();
        applyColumnConfig();
        renderJobs();
        openColumnSettings(); // Refresh the modal
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
            await loadFilters();
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
            await loadFilters();
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

// Trigger fit score matching
async function triggerMatch() {
    const button = document.getElementById('matchButton');
    const originalText = button.textContent;

    button.disabled = true;
    button.textContent = 'Matching...';

    try {
        const response = await fetch('/api/match', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Failed to match fit scores');
        }

        let message = data.message || 'Fit scores updated successfully';
        if (typeof data.heuristic_fallbacks === 'number' && data.heuristic_fallbacks > 0) {
            message += `\nUsed heuristic fallback for ${data.heuristic_fallbacks} job(s).`;
        }
        if (Array.isArray(data.sample) && data.sample.length > 0) {
            const sampleText = data.sample.map(sample => {
                const title = sample.title || 'Unknown title';
                const score = typeof sample.fit_score === 'number' ? sample.fit_score.toFixed(1) : 'N/A';
                const reasoning = sample.reasoning ? `Reasoning: ${sample.reasoning}` : 'Reasoning: (not provided)';
                return `• ${title} — Score: ${score}. ${reasoning}`;
            }).join('\n');
            message += `\n\nSample results:\n${sampleText}`;
        }

        alert(message);
        await loadStats();
        await loadJobs();
    } catch (error) {
        console.error('Error matching fit scores:', error);
        showError('Error matching fit scores: ' + error.message);
    } finally {
        button.disabled = false;
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
    // Column order: fit_score(0), title(1), institution(2), field(3), level(4), deadline(5), extracted_deadline(6), location(7), country(8), status(9), materials(10), refs_email(11), portal(12), link(13), actions(14)
    const editableFields = ['title', 'institution', 'field', 'level', 'deadline', 'extracted_deadline', 'location', 'country', 'application_status', 'application_materials', 'application_portal_url'];
    const editableIndices = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12]; // Corresponding cell indices
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
            
            // For application portal, extract from link or badge
            if (field === 'application_portal_url') {
                const link = cell.querySelector('.btn-portal');
                if (link) {
                    currentValue = link.href || '';
                } else {
                    currentValue = '';
                }
            }
            
            // For references_separate_email, extract from badge
            if (field === 'references_separate_email') {
                const badge = cell.querySelector('.portal-badge');
                currentValue = badge ? '1' : '0';
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
            } else if (field === 'deadline' || field === 'extracted_deadline') {
                // Date input
                const dateValue = currentValue !== 'N/A' ? currentValue : '';
                cell.innerHTML = `<input type="date" data-field="${field}" data-job-id="${jobId}" value="${dateValue}">`;
            } else if (field === 'references_separate_email') {
                // Boolean checkbox
                const isChecked = currentValue === '1' || currentValue === 'Yes' || currentValue.toLowerCase() === 'yes';
                cell.innerHTML = `<input type="checkbox" data-field="${field}" data-job-id="${jobId}" ${isChecked ? 'checked' : ''}>`;
            } else if (field === 'application_portal_url') {
                // URL input
                cell.innerHTML = `<input type="url" data-field="${field}" data-job-id="${jobId}" value="${escapeHtml(currentValue)}" placeholder="https://...">`;
            } else if (field === 'application_materials') {
                // Textarea for materials
                cell.innerHTML = `<textarea data-field="${field}" data-job-id="${jobId}" rows="2" style="width: 100%;">${escapeHtml(currentValue)}</textarea>`;
            } else {
                // Text input
                cell.innerHTML = `<input type="text" data-field="${field}" data-job-id="${jobId}" value="${escapeHtml(currentValue)}">`;
            }
            
            // Track changes
            const input = cell.querySelector('input, select, textarea');
            const eventType = input.type === 'checkbox' ? 'change' : 'change';
            input.addEventListener(eventType, function() {
                const jobId = this.dataset.jobId;
                const field = this.dataset.field;
                const value = this.type === 'checkbox' ? (this.checked ? 1 : 0) : this.value;
                
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

