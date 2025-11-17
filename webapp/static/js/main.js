// Global state
let allJobs = [];
let filteredJobs = [];
let currentSort = { column: 'fit_score', order: 'desc' };
let expandedJobId = null;
let editMode = false;
let editedJobs = {}; // Track edited jobs: {job_id: {field: value}}
let selectedJobs = new Set(); // Track selected job IDs for bulk operations
let lastSelectedRowIndex = null; // Track last selected row for shift+click range selection

const PROGRESS_POLL_INTERVAL_MS = 1000;
let progressPollInterval = null;
const activeProgressOps = new Set();

// Column configuration
const COLUMN_DEFINITIONS = [
    { id: 'checkbox', label: 'Select', defaultWidth: 50, resizable: false },
    { id: 'fit_score', label: 'Fit Score', defaultWidth: 100, resizable: true },
    { id: 'position_track', label: 'Position Track', defaultWidth: 160, resizable: true },
    { id: 'difficulty_score', label: 'Difficulty', defaultWidth: 110, resizable: true },
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

function showProgressPanel(operation) {
    activeProgressOps.add(operation);
    const panel = document.getElementById('progressPanel');
    if (panel) {
        panel.classList.remove('hidden');
    }
    if (!progressPollInterval) {
        fetchProgressStatus();
        progressPollInterval = setInterval(fetchProgressStatus, PROGRESS_POLL_INTERVAL_MS);
    }
}

function hideProgressPanel(operation) {
    activeProgressOps.delete(operation);
    if (activeProgressOps.size === 0) {
        if (progressPollInterval) {
            clearInterval(progressPollInterval);
            progressPollInterval = null;
        }
        const panel = document.getElementById('progressPanel');
        if (panel) {
            panel.classList.add('hidden');
        }
    }
}

async function fetchProgressStatus() {
    if (activeProgressOps.size === 0) {
        return;
    }
    try {
        const response = await fetch('/api/progress');
        const data = await response.json();
        if (data && data.success) {
            updateProgressPanelContent(data.process, data.match);
        }
    } catch (error) {
        console.debug('Progress polling failed:', error);
    }
}

function updateProgressPanelContent(processStatus, matchStatus) {
    renderProgressItem('progressProcess', processStatus, 'LLM Processing', activeProgressOps.has('process'));
    renderProgressItem('progressMatch', matchStatus, 'Matching Scores', activeProgressOps.has('match'));

    const panel = document.getElementById('progressPanel');
    if (!panel) {
        return;
    }
    const processEl = document.getElementById('progressProcess');
    const matchEl = document.getElementById('progressMatch');
    if (processEl && matchEl) {
        const hasVisibleItem = !processEl.classList.contains('hidden') || !matchEl.classList.contains('hidden');
        if (!hasVisibleItem && activeProgressOps.size === 0) {
            panel.classList.add('hidden');
        }
    }
}

function renderProgressItem(elementId, progress, label, shouldDisplay) {
    const el = document.getElementById(elementId);
    if (!el) {
        return;
    }
    if (!shouldDisplay || !progress) {
        el.classList.add('hidden');
        el.innerHTML = '';
        return;
    }

    const total = Number(progress.total) || 0;
    const processed = Number(progress.processed) || 0;
    const errors = Number(progress.errors) || 0;
    const status = progress.status || 'idle';
    const message = progress.message || '';

    let percent = 0;
    if (total > 0) {
        percent = Math.min(100, Math.round((processed / total) * 100));
    } else if (status === 'completed') {
        percent = 100;
    }

    let headline = `${label}: ${percent}%`;
    if (status === 'completed' && percent < 100) {
        headline = `${label}: Completed`;
    } else if (status === 'completed') {
        headline = `${label}: 100%`;
    } else if (status === 'error') {
        headline = `${label}: Error`;
    }

    let body = '';
    if (total > 0) {
        body += `<span class="subtext">${processed} / ${total} processed</span>`;
    } else if (status === 'completed') {
        body += `<span class="subtext">Completed</span>`;
    }
    if (errors > 0) {
        body += `<span class="subtext error">Errors: ${errors}</span>`;
    }
    if (message) {
        body += `<span class="subtext">${escapeHtml(message)}</span>`;
    }

    el.innerHTML = `<strong>${headline}</strong>${body}`;
    el.classList.remove('hidden');
}

async function callProcessApi(limit = null) {
    const response = await fetch('/api/process', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ limit })
    });

    const data = await response.json();
    if (!response.ok || !data.success) {
        throw new Error(data.error || 'Failed to process jobs');
    }
    return data;
}

async function runProcessAfterScrape(autoTriggered = false) {
    showProgressPanel('process');
    try {
        const data = await callProcessApi();
        const message = `LLM Processing complete!\n${data.message}\n\nProcessed: ${data.processed_count}\nErrors: ${data.error_count}\nTotal: ${data.total_processed}`;
        if (autoTriggered) {
            alert(`Auto processing finished.\n\n${message}`);
        } else {
            alert(message);
        }
        await loadJobs();
        await loadStats();
        await loadFilters();
        return true;
    } catch (error) {
        console.error('Auto LLM processing failed:', error);
        alert('Auto LLM processing failed: ' + error.message);
        return false;
    } finally {
        hideProgressPanel('process');
    }
}

async function callMatchApi(force = false) {
    const response = await fetch('/api/match', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ force })
    });

    const data = await response.json();
    if (!response.ok || !data.success) {
        throw new Error(data.error || 'Failed to match fit scores');
    }
    return data;
}

async function runMatchAfterScrape(autoTriggered = false, force = false) {
    showProgressPanel('match');
    try {
        const data = await callMatchApi(force);
        let message = `Fit scores updated!\n${data.message}`;
        if (typeof data.recomputed === 'number') {
            message += `\nRecomputed: ${data.recomputed}`;
        }
        if (typeof data.skipped === 'number') {
            message += `\nSkipped: ${data.skipped}`;
        }
        if (autoTriggered) {
            alert(`Auto matching finished.\n\n${message}`);
        } else {
            alert(message);
        }
        await loadStats();
        await loadJobs();
        await loadFilters();
        const forceToggle = document.getElementById('forceMatchToggle');
        if (forceToggle && !force) {
            forceToggle.checked = false;
        }
        return true;
    } catch (error) {
        console.error('Auto matching failed:', error);
        alert('Auto matching failed: ' + error.message);
        return false;
    } finally {
        hideProgressPanel('match');
    }
}

// Setup event listeners
function setupEventListeners() {
    // Filters
    document.getElementById('filterStatus').addEventListener('change', applyFilters);
    document.getElementById('filterField').addEventListener('change', applyFilters);
    document.getElementById('filterPositionTrack').addEventListener('change', applyFilters);
    document.getElementById('filterLevel').addEventListener('change', applyFilters);
    document.getElementById('filterCountry').addEventListener('change', applyFilters);
    document.getElementById('filterMinScore').addEventListener('input', applyFilters);
    document.getElementById('searchInput').addEventListener('input', debounce(applyFilters, 300));
    document.getElementById('clearFilters').addEventListener('click', clearFilters);
    document.getElementById('scrapeButton').addEventListener('click', triggerScrape);
    document.getElementById('processButton').addEventListener('click', triggerProcess);
    const matchButton = document.getElementById('matchButton');
    matchButton.addEventListener('click', () => {
        const forceToggle = document.getElementById('forceMatchToggle');
        const force = forceToggle ? forceToggle.checked : false;
        triggerMatch(force);
    });
    document.getElementById('saveButton').addEventListener('click', saveEdits);
    document.getElementById('cancelEditButton').addEventListener('click', cancelEdit);
    
    // Bulk selection
    document.getElementById('selectAllCheckbox').addEventListener('change', toggleSelectAll);
    document.getElementById('selectAllBtn').addEventListener('click', selectAllVisible);
    document.getElementById('deselectAllBtn').addEventListener('click', deselectAll);
    document.getElementById('bulkUpdateBtn').addEventListener('click', bulkUpdateStatus);
    document.getElementById('processSelectedBtn').addEventListener('click', processSelectedJobs);
    document.getElementById('matchSelectedBtn').addEventListener('click', matchSelectedJobs);
    
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
            document.getElementById('statPending').textContent = stats.by_status.pending || 0;
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
        const [fieldsRes, levelsRes, tracksRes, countriesRes] = await Promise.all([
            fetch('/api/fields'),
            fetch('/api/levels'),
            fetch('/api/position-tracks'),
            fetch('/api/countries')
        ]);
        
        const fieldsData = await fieldsRes.json();
        const levelsData = await levelsRes.json();
        const tracksData = await tracksRes.json();
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

        if (tracksData.success) {
            const filterTrack = document.getElementById('filterPositionTrack');
            if (filterTrack) {
                while (filterTrack.options.length > 1) {
                    filterTrack.remove(1);
                }
                tracksData.tracks.forEach(track => {
                    const option = document.createElement('option');
                    option.value = track;
                    option.textContent = track;
                    filterTrack.appendChild(option);
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
    const positionTrack = document.getElementById('filterPositionTrack').value;
    const level = document.getElementById('filterLevel').value;
    const country = document.getElementById('filterCountry').value;
    const minScore = document.getElementById('filterMinScore').value;
    const search = document.getElementById('searchInput').value.toLowerCase();
    
    filteredJobs = allJobs.filter(job => {
        // By default, exclude "unrelated" jobs unless explicitly filtered
        if (!status && job.application_status === 'unrelated') return false;
        if (status && job.application_status !== status) return false;
        if (field && job.field !== field) return false;
        if (positionTrack && (job.position_track || '').toLowerCase() !== positionTrack.toLowerCase()) return false;
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
        let isEmptyA = false;
        let isEmptyB = false;
        
        switch (column) {
            case 'fit_score':
                aVal = a.fit_score || 0;
                bVal = b.fit_score || 0;
                break;
            case 'difficulty_score':
                aVal = typeof a.difficulty_score === 'number' ? a.difficulty_score : Number.POSITIVE_INFINITY;
                bVal = typeof b.difficulty_score === 'number' ? b.difficulty_score : Number.POSITIVE_INFINITY;
                break;
            case 'deadline':
            case 'extracted_deadline':
                // Handle date sorting - convert to comparable format
                aVal = a[column] || '';
                bVal = b[column] || '';
                isEmptyA = !aVal;
                isEmptyB = !bVal;
                // Empty dates should sort last (regardless of sort order)
                if (isEmptyA && isEmptyB) return 0;
                if (isEmptyA) return 1;  // a is empty, sort to end
                if (isEmptyB) return -1; // b is empty, sort to end
                // Extract date part if it's a datetime string
                if (typeof aVal === 'string' && aVal.includes(' ')) aVal = aVal.split(' ')[0];
                if (typeof bVal === 'string' && bVal.includes(' ')) bVal = bVal.split(' ')[0];
                // Dates in YYYY-MM-DD format can be compared as strings for chronological sorting
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
        
        // Handle empty values for date columns - always sort to end
        if (isEmptyA || isEmptyB) {
            // This should have been handled above, but just in case
            if (isEmptyA && isEmptyB) return 0;
            if (isEmptyA) return 1;
            if (isEmptyB) return -1;
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
        tbody.innerHTML = '<tr><td colspan="19" class="loading">No jobs found</td></tr>';
        return;
    }
    
    tbody.innerHTML = filteredJobs.map(job => {
        const fitScore = job.fit_score || 0;
        const fitScoreClass = fitScore >= 70 ? 'fit-score-high' : fitScore >= 40 ? 'fit-score-medium' : 'fit-score-low';
        const statusClass = `status-${job.application_status || 'new'}`;
        const isSelected = selectedJobs.has(job.job_id);
        const positionTrack = (job.position_track || 'N/A');
        const difficultyScore = typeof job.difficulty_score === 'number' ? job.difficulty_score : null;
        const difficultyDisplay = difficultyScore !== null ? difficultyScore.toFixed(1) : 'N/A';
        const difficultyClass = difficultyScore !== null ?
            (difficultyScore <= 15 ? 'difficulty-high' : difficultyScore <= 40 ? 'difficulty-medium' : 'difficulty-low') :
            'difficulty-unknown';
        const currentStatus = job.application_status || 'new';
        
        return `
            <tr data-job-id="${job.job_id}">
                <td data-column="checkbox"><input type="checkbox" class="job-checkbox" data-job-id="${job.job_id}" ${isSelected ? 'checked' : ''}></td>
                <td data-column="job_id">${escapeHtml(job.job_id || 'N/A')}</td>
                <td data-column="fit_score"><span class="fit-score ${fitScoreClass}">${fitScore.toFixed(1)}</span></td>
                <td data-column="position_track">${escapeHtml(positionTrack)}</td>
                <td data-column="difficulty_score"><span class="difficulty-chip ${difficultyClass}">${difficultyDisplay}</span></td>
                <td data-column="title">${escapeHtml(job.title || 'N/A')}</td>
                <td data-column="institution">${escapeHtml(job.institution || 'N/A')}</td>
                <td data-column="field">${escapeHtml(job.field || 'N/A')}</td>
                <td data-column="level">${escapeHtml(job.level || 'N/A')}</td>
                <td data-column="deadline">${formatDate(job.deadline)}</td>
                <td data-column="extracted_deadline">${formatDate(job.extracted_deadline)}</td>
                <td data-column="location">${escapeHtml(job.location || 'N/A')}</td>
                <td data-column="country">${escapeHtml(job.country || 'N/A')}</td>
                <td data-column="status">
                    <select class="status-dropdown" data-job-id="${job.job_id}">
                        <option value="pending" ${currentStatus === 'pending' ? 'selected' : ''}>pending</option>
                        <option value="new" ${currentStatus === 'new' ? 'selected' : ''}>new</option>
                        <option value="applied" ${currentStatus === 'applied' ? 'selected' : ''}>applied</option>
                        <option value="expired" ${currentStatus === 'expired' ? 'selected' : ''}>expired</option>
                        <option value="rejected" ${currentStatus === 'rejected' ? 'selected' : ''}>rejected</option>
                        <option value="unrelated" ${currentStatus === 'unrelated' ? 'selected' : ''}>unrelated</option>
                    </select>
                </td>
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
        checkbox.addEventListener('click', function(e) {
            // Prevent default to handle shift+click properly
            if (e.shiftKey) {
                e.preventDefault();
                this.checked = !this.checked;
                handleJobSelection(e);
            }
        });
    });
    
    // Also support clicking on the row itself (not just checkbox) for shift+click
    document.querySelectorAll('#jobsTableBody tr[data-job-id]').forEach(row => {
        row.addEventListener('click', function(e) {
            // Only handle if clicking on the row itself, not on interactive elements
            if (e.target.tagName !== 'INPUT' && 
                e.target.tagName !== 'SELECT' && 
                e.target.tagName !== 'BUTTON' && 
                e.target.tagName !== 'A' &&
                !e.target.closest('button') &&
                !e.target.closest('a') &&
                !e.target.closest('select')) {
                const checkbox = this.querySelector('.job-checkbox');
                if (checkbox) {
                    if (e.shiftKey && lastSelectedRowIndex !== null) {
                        e.preventDefault();
                        const allRows = Array.from(document.querySelectorAll('#jobsTableBody tr[data-job-id]'));
                        const currentRowIndex = allRows.indexOf(this);
                        const startIndex = Math.min(lastSelectedRowIndex, currentRowIndex);
                        const endIndex = Math.max(lastSelectedRowIndex, currentRowIndex);
                        const rangeRows = allRows.slice(startIndex, endIndex + 1);
                        
                        rangeRows.forEach(rangeRow => {
                            const rangeJobId = rangeRow.dataset.jobId;
                            const rangeCheckbox = rangeRow.querySelector('.job-checkbox');
                            if (rangeCheckbox) {
                                rangeCheckbox.checked = true;
                                selectedJobs.add(rangeJobId);
                            }
                        });
                        lastSelectedRowIndex = currentRowIndex;
                    } else {
                        checkbox.checked = !checkbox.checked;
                        const jobId = checkbox.dataset.jobId;
                        if (checkbox.checked) {
                            selectedJobs.add(jobId);
                        } else {
                            selectedJobs.delete(jobId);
                        }
                        const allRows = Array.from(document.querySelectorAll('#jobsTableBody tr[data-job-id]'));
                        lastSelectedRowIndex = allRows.indexOf(this);
                    }
                    updateBulkActionsVisibility();
                    updateSelectAllCheckbox();
                }
            }
        });
    });
    
    // Attach status dropdown event listeners
    document.querySelectorAll('.status-dropdown').forEach(dropdown => {
        dropdown.addEventListener('change', handleStatusChange);
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

// Update job status via dropdown
async function handleStatusChange(event) {
    const dropdown = event.target;
    const jobId = dropdown.dataset.jobId;
    const newStatus = dropdown.value;
    
    try {
        const response = await fetch(`/api/jobs/${jobId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                application_status: newStatus
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Update local data
            const job = allJobs.find(j => j.job_id === jobId);
            if (job) {
                job.application_status = newStatus;
            }
            applyFilters();
            loadStats();
        } else {
            // Revert dropdown on error
            dropdown.value = allJobs.find(j => j.job_id === jobId)?.application_status || 'new';
            alert('Failed to update status: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error updating status:', error);
        // Revert dropdown on error
        dropdown.value = allJobs.find(j => j.job_id === jobId)?.application_status || 'new';
        alert('Error updating status: ' + error.message);
    }
}

// Update job status
async function updateStatus(jobId) {
    const currentStatus = allJobs.find(j => j.job_id === jobId)?.application_status || 'new';
    const statuses = ['pending', 'new', 'applied', 'expired', 'rejected'];
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
    document.getElementById('filterPositionTrack').value = '';
    document.getElementById('filterLevel').value = '';
    document.getElementById('filterCountry').value = '';
    document.getElementById('filterMinScore').value = '';
    document.getElementById('searchInput').value = '';
    applyFilters();
}

// Bulk selection functions
function handleJobSelection(event) {
    const checkbox = event.target;
    const jobId = checkbox.dataset.jobId;
    const row = checkbox.closest('tr');
    const allRows = Array.from(document.querySelectorAll('#jobsTableBody tr[data-job-id]'));
    const currentRowIndex = allRows.indexOf(row);
    
    // Handle shift+click for range selection
    if (event.shiftKey && lastSelectedRowIndex !== null && currentRowIndex !== -1) {
        event.preventDefault();
        const startIndex = Math.min(lastSelectedRowIndex, currentRowIndex);
        const endIndex = Math.max(lastSelectedRowIndex, currentRowIndex);
        const rangeRows = allRows.slice(startIndex, endIndex + 1);
        
        // Select all rows in range
        rangeRows.forEach(rangeRow => {
            const rangeJobId = rangeRow.dataset.jobId;
            const rangeCheckbox = rangeRow.querySelector('.job-checkbox');
            if (rangeCheckbox) {
                rangeCheckbox.checked = true;
                selectedJobs.add(rangeJobId);
            }
        });
    } else {
        // Normal click - toggle single selection
        if (checkbox.checked) {
            selectedJobs.add(jobId);
        } else {
            selectedJobs.delete(jobId);
        }
        // Update last selected row index
        lastSelectedRowIndex = currentRowIndex;
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
    lastSelectedRowIndex = null;
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

// Process selected jobs with LLM
async function processSelectedJobs() {
    const jobIds = Array.from(selectedJobs);
    
    if (jobIds.length === 0) {
        alert('No jobs selected');
        return;
    }
    
    const forceToggle = document.getElementById('forceProcessToggle');
    const force = forceToggle ? forceToggle.checked : false;
    
    if (!confirm(`Process ${jobIds.length} selected job(s) with LLM${force ? ' (force re-process)' : ''}?`)) {
        return;
    }
    
    try {
        showProgressPanel('process');
        const response = await fetch('/api/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                job_ids: jobIds,
                force: force
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`Successfully processed ${data.processed_count} job(s)`);
            // Refresh display
            await loadJobs();
            applyFilters();
            loadStats();
        } else {
            alert('Failed to process jobs: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error processing jobs:', error);
        alert('Error processing jobs: ' + error.message);
    } finally {
        hideProgressPanel('process');
    }
}

// Match selected jobs
async function matchSelectedJobs() {
    const jobIds = Array.from(selectedJobs);
    
    if (jobIds.length === 0) {
        alert('No jobs selected');
        return;
    }
    
    const forceToggle = document.getElementById('forceMatchSelectedToggle');
    const force = forceToggle ? forceToggle.checked : false;
    
    if (!confirm(`Match fit scores for ${jobIds.length} selected job(s)${force ? ' (force recompute)' : ''}?`)) {
        return;
    }
    
    try {
        showProgressPanel('match');
        const response = await fetch('/api/match', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                job_ids: jobIds,
                force: force
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`Successfully matched ${data.updated_count} job(s)`);
            // Refresh display
            await loadJobs();
            applyFilters();
            loadStats();
        } else {
            alert('Failed to match jobs: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error matching jobs:', error);
        alert('Error matching jobs: ' + error.message);
    } finally {
        hideProgressPanel('match');
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
            let alertMessage = `Scraping complete!\n${data.message}\n\nNew jobs: ${data.new_count}\nUpdated jobs: ${data.updated_count}\nTotal scraped: ${data.total_scraped}`;
            if (typeof data.pending_llm === 'number' && data.pending_llm > 100) {
                alertMessage += `\n\n⚠️ ${data.pending_llm} postings still need LLM processing. Run "Process with LLM" to parse them.`;
            }
            alert(alertMessage);
            
            // Reload jobs and stats
            let processHandled = false;
            let matchHandled = false;
            if (typeof data.new_count === 'number' && data.new_count > 0) {
                if (data.new_count > 100) {
                    const userWantsProcess = confirm(`There are ${data.new_count} new postings.\nDo you want to run LLM processing now?`);
                    if (userWantsProcess) {
                        processHandled = await runProcessAfterScrape(false);
                        if (processHandled) {
                            const userWantsMatch = confirm('Run Match Fit Scores now?');
                            if (userWantsMatch) {
                                matchHandled = await runMatchAfterScrape(false);
                            }
                        }
                    } else {
                        const userWantsMatchOnly = confirm('Skip LLM processing but run Match Fit Scores now?');
                        if (userWantsMatchOnly) {
                            matchHandled = await runMatchAfterScrape(false);
                        }
                    }
                } else {
                    processHandled = await runProcessAfterScrape(true);
                    matchHandled = await runMatchAfterScrape(true);
                }
            }

            if (!processHandled && !matchHandled) {
                await loadJobs();
                await loadStats();
                await loadFilters();
            }
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
    showProgressPanel('process');
    
    try {
        const data = await callProcessApi();
        alert(`LLM Processing complete!\n${data.message}\n\nProcessed: ${data.processed_count}\nErrors: ${data.error_count}\nTotal: ${data.total_processed}`);
        await loadJobs();
        await loadStats();
        await loadFilters();
    } catch (error) {
        console.error('Error triggering process:', error);
        alert('Error triggering process: ' + error.message);
    } finally {
        // Re-enable button
        button.disabled = false;
        button.classList.remove('processing');
        button.textContent = originalText;
        hideProgressPanel('process');
    }
}

// Trigger fit score matching
async function triggerMatch(forceFull = false) {
    const button = document.getElementById('matchButton');
    const originalText = button.textContent;

    button.disabled = true;
    button.textContent = 'Matching...';
    button.classList.add('processing');
    showProgressPanel('match');

    try {
        const data = await callMatchApi(forceFull);

        let message = data.message || 'Fit scores updated successfully';
        if (typeof data.heuristic_fallbacks === 'number' && data.heuristic_fallbacks > 0) {
            message += `\nUsed heuristic fallback for ${data.heuristic_fallbacks} job(s).`;
        }
        if (typeof data.recomputed === 'number') {
            message += `\nRecomputed: ${data.recomputed}`;
        }
        if (typeof data.skipped === 'number') {
            message += `\nSkipped: ${data.skipped}`;
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
        await loadFilters();

        const forceToggle = document.getElementById('forceMatchToggle');
        if (forceToggle && !forceFull) {
            forceToggle.checked = false;
        }
    } catch (error) {
        console.error('Error matching fit scores:', error);
        showError('Error matching fit scores: ' + error.message);
    } finally {
        button.disabled = false;
        button.textContent = originalText;
        button.classList.remove('processing');
        hideProgressPanel('match');
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
    // Column order reference:
    // checkbox(0), job_id(1), fit_score(2), position_track(3), difficulty_score(4), title(5), institution(6), field(7), level(8), deadline(9),
    // extracted_deadline(10), location(11), country(12), status(13), application_materials(14), references_separate_email(15),
    // application_portal(16), link(17), actions(18)
    const editableFields = ['title', 'institution', 'field', 'level', 'deadline', 'extracted_deadline', 'location', 'country', 'application_status', 'application_materials', 'application_portal_url'];
    const editableIndices = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16]; // Corresponding cell indices
    const cells = row.querySelectorAll('td');
    
    // Get the original job data for accurate field values
    const job = filteredJobs.find(j => j.job_id === jobId) || allJobs.find(j => j.job_id === jobId);
    
    editableFields.forEach((field, index) => {
        const cellIndex = editableIndices[index];
        if (cells[cellIndex]) {
            const cell = cells[cellIndex];
            let currentValue = cell.textContent.trim();
            
            // For date fields, use original value from job data (YYYY-MM-DD format)
            if (field === 'deadline' || field === 'extracted_deadline') {
                if (job && job[field]) {
                    // Extract date part if it's a datetime string
                    const dateStr = job[field].includes(' ') ? job[field].split(' ')[0] : job[field];
                    currentValue = dateStr;
                } else {
                    currentValue = '';
                }
            }
            // For status, extract from select dropdown
            else if (field === 'application_status') {
                const select = cell.querySelector('select.status-dropdown');
                if (select) {
                    currentValue = select.value || 'new';
                } else if (job) {
                    currentValue = job.application_status || 'new';
                }
            }
            // For application portal, extract from link or badge
            else if (field === 'application_portal_url') {
                const link = cell.querySelector('.btn-portal');
                if (link) {
                    currentValue = link.href || '';
                } else if (job) {
                    currentValue = job.application_portal_url || '';
                } else {
                    currentValue = '';
                }
            }
            // For other fields, use job data if available, otherwise use cell text
            else if (job && job[field] !== undefined && job[field] !== null) {
                currentValue = String(job[field]);
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
                        <option value="pending" ${currentValue === 'pending' ? 'selected' : ''}>pending</option>
                        <option value="new" ${currentValue === 'new' ? 'selected' : ''}>new</option>
                        <option value="applied" ${currentValue === 'applied' ? 'selected' : ''}>applied</option>
                        <option value="expired" ${currentValue === 'expired' ? 'selected' : ''}>expired</option>
                        <option value="rejected" ${currentValue === 'rejected' ? 'selected' : ''}>rejected</option>
                        <option value="unrelated" ${currentValue === 'unrelated' ? 'selected' : ''}>unrelated</option>
                    </select>
                `;
            } else if (field === 'deadline' || field === 'extracted_deadline') {
                // Date input - currentValue is already in YYYY-MM-DD format
                cell.innerHTML = `<input type="date" data-field="${field}" data-job-id="${jobId}" value="${currentValue}">`;
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

