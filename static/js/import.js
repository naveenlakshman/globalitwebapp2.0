// Import Module JavaScript

let currentStep = 1;
let importType = '';
let uploadedFile = null;
let fileData = null;

// Initialize import functionality
function initializeImport(type) {
    importType = type;
    setupFileUpload();
    setupDragAndDrop();
}

// Setup file upload functionality
function setupFileUpload() {
    const fileInput = document.getElementById('file-input');
    if (fileInput) {
        fileInput.addEventListener('change', handleFileSelect);
    }
}

// Setup drag and drop functionality
function setupDragAndDrop() {
    const uploadArea = document.getElementById('upload-area');
    if (!uploadArea) return;

    uploadArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });

    uploadArea.addEventListener('click', function() {
        document.getElementById('file-input').click();
    });
}

// Handle file selection
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        handleFile(file);
    }
}

// Handle file processing
function handleFile(file) {
    // Validate file type
    if (!file.name.toLowerCase().endsWith('.csv')) {
        showAlert('Please select a CSV file.', 'error');
        return;
    }

    // Validate file size (10MB limit)
    if (file.size > 10 * 1024 * 1024) {
        showAlert('File size should not exceed 10MB.', 'error');
        return;
    }

    uploadedFile = file;
    displayFileInfo(file);
    enableUploadButton();
}

// Display file information
function displayFileInfo(file) {
    const fileInfo = document.getElementById('file-info');
    const fileName = document.getElementById('file-name');
    const fileSize = document.getElementById('file-size');
    const uploadArea = document.getElementById('upload-area');

    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);
    
    fileInfo.style.display = 'block';
    uploadArea.style.display = 'none';
}

// Remove selected file
function removeFile() {
    uploadedFile = null;
    fileData = null;
    
    const fileInfo = document.getElementById('file-info');
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('file-input');
    
    fileInfo.style.display = 'none';
    uploadArea.style.display = 'block';
    fileInput.value = '';
    
    disableUploadButton();
}

// Enable upload button
function enableUploadButton() {
    const uploadBtn = document.getElementById('upload-btn');
    if (uploadBtn) {
        uploadBtn.disabled = false;
    }
}

// Disable upload button
function disableUploadButton() {
    const uploadBtn = document.getElementById('upload-btn');
    if (uploadBtn) {
        uploadBtn.disabled = true;
    }
}

// Upload file and preview
async function uploadFile() {
    if (!uploadedFile) {
        showAlert('Please select a file first.', 'error');
        return;
    }

    showLoading(true);

    const formData = new FormData();
    formData.append('file', uploadedFile);
    formData.append('import_type', importType);

    try {
        const response = await fetch('/import/upload', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            fileData = result.data;
            displayPreview(result.data);
            goToStep(2);
        } else {
            showAlert(result.message, 'error');
        }
    } catch (error) {
        showAlert('Error uploading file: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

// Display data preview and column mapping
function displayPreview(data) {
    displayColumnMapping(data.columns, data.column_suggestions, data.required_columns);
    displayDataPreview(data.sample_data);
}

// Display column mapping interface
function displayColumnMapping(csvColumns, suggestions, requiredColumns) {
    const mappingContainer = document.getElementById('column-mapping');
    
    let html = '<h3>Column Mapping</h3>';
    html += '<p>Map your CSV columns to database fields:</p>';
    html += '<div class="mapping-grid">';

    csvColumns.forEach(csvCol => {
        const suggested = suggestions[csvCol] || '';
        const isRequired = requiredColumns.includes(csvCol.toLowerCase());
        
        html += `
            <div class="mapping-row">
                <div class="csv-column">
                    ${csvCol} ${isRequired ? '<span class="field-tag required">required</span>' : ''}
                </div>
                <div class="mapping-arrow">→</div>
                <div class="db-field">
                    <select id="mapping-${csvCol}" class="form-control">
                        <option value="">-- Skip Column --</option>
                        ${getFieldOptions(importType, suggested)}
                    </select>
                </div>
            </div>
        `;
    });

    html += '</div>';
    mappingContainer.innerHTML = html;
}

// Get field options for select dropdown
function getFieldOptions(type, selectedValue = '') {
    const fieldOptions = {
        students: [
            'student_id', 'full_name', 'gender', 'dob', 'mobile', 'email', 'address',
            'guardian_name', 'guardian_mobile', 'qualification', 'course_name', 
            'batch_id', 'branch_id', 'lead_source', 'status', 'admission_date'
        ],
        invoices: [
            'student_id', 'course_id', 'total_amount', 'paid_amount', 'due_amount',
            'discount', 'enrollment_date', 'invoice_date', 'due_date', 'payment_terms'
        ],
        installments: [
            'invoice_id', 'installment_number', 'due_date', 'amount', 'paid_amount',
            'status', 'late_fee', 'discount_amount', 'notes'
        ],
        payments: [
            'invoice_id', 'installment_id', 'amount', 'mode', 'utr_number',
            'notes', 'payment_date', 'discount_amount'
        ]
    };

    const fields = fieldOptions[type] || [];
    return fields.map(field => 
        `<option value="${field}" ${field === selectedValue ? 'selected' : ''}>${field}</option>`
    ).join('');
}

// Display data preview table
function displayDataPreview(sampleData) {
    const previewContainer = document.getElementById('preview-table');
    
    if (!sampleData || sampleData.length === 0) {
        previewContainer.innerHTML = '<p>No data to preview</p>';
        return;
    }

    const columns = Object.keys(sampleData[0]);
    
    let html = '<table class="table">';
    html += '<thead><tr>';
    columns.forEach(col => {
        html += `<th>${col}</th>`;
    });
    html += '</tr></thead>';
    
    html += '<tbody>';
    sampleData.forEach(row => {
        html += '<tr>';
        columns.forEach(col => {
            const value = row[col] || '';
            html += `<td title="${value}">${value}</td>`;
        });
        html += '</tr>';
    });
    html += '</tbody></table>';
    
    previewContainer.innerHTML = html;
}

// Start import process
async function startImport() {
    const columnMapping = getColumnMapping();
    const duplicateHandling = document.getElementById('duplicate-handling').value;
    const notes = document.getElementById('import-notes').value;

    // Validate required mappings
    if (!validateColumnMapping(columnMapping)) {
        return;
    }

    goToStep(3);

    try {
        const response = await fetch('/import/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                column_mapping: columnMapping,
                duplicate_handling: duplicateHandling,
                notes: notes
            })
        });

        const result = await response.json();

        if (result.success) {
            displayResults(result);
        } else {
            displayError(result.message);
        }
    } catch (error) {
        displayError('Error processing import: ' + error.message);
    }

    goToStep(4);
}

// Get column mapping from form
function getColumnMapping() {
    const mapping = {};
    const mappingSelects = document.querySelectorAll('[id^="mapping-"]');
    
    mappingSelects.forEach(select => {
        const csvColumn = select.id.replace('mapping-', '');
        const dbField = select.value;
        
        if (dbField) {
            mapping[csvColumn] = dbField;
        }
    });

    return mapping;
}

// Validate column mapping
function validateColumnMapping(mapping) {
    const requiredFields = getRequiredFields(importType);
    const mappedFields = Object.values(mapping);
    
    const missingFields = requiredFields.filter(field => !mappedFields.includes(field));
    
    if (missingFields.length > 0) {
        showAlert(`Please map the following required fields: ${missingFields.join(', ')}`, 'error');
        return false;
    }

    return true;
}

// Get required fields for import type
function getRequiredFields(type) {
    const requirements = {
        students: ['full_name', 'mobile'],
        invoices: ['student_id', 'total_amount', 'enrollment_date'],
        installments: ['invoice_id', 'due_date', 'amount'],
        payments: ['amount', 'mode']
    };
    return requirements[type] || [];
}

// Display import results
function displayResults(result) {
    const data = result.data;
    const isSuccess = data.failed === 0;
    const isPartial = data.failed > 0 && data.successful > 0;

    // Results header
    let headerHtml = '';
    if (isSuccess) {
        headerHtml = `
            <div class="results-icon success">
                <i class="fas fa-check"></i>
            </div>
            <h2>Import Completed Successfully!</h2>
            <p>All records have been imported successfully.</p>
        `;
    } else if (isPartial) {
        headerHtml = `
            <div class="results-icon warning">
                <i class="fas fa-exclamation-triangle"></i>
            </div>
            <h2>Import Completed with Issues</h2>
            <p>Some records could not be imported. Please review the errors below.</p>
        `;
    } else {
        headerHtml = `
            <div class="results-icon error">
                <i class="fas fa-times"></i>
            </div>
            <h2>Import Failed</h2>
            <p>The import could not be completed due to errors.</p>
        `;
    }

    document.getElementById('results-header').innerHTML = headerHtml;

    // Results summary
    const summaryHtml = `
        <div class="result-stat success">
            <div class="number">${data.successful}</div>
            <div class="label">Successful</div>
        </div>
        <div class="result-stat error">
            <div class="number">${data.failed}</div>
            <div class="label">Failed</div>
        </div>
        <div class="result-stat warning">
            <div class="number">${data.skipped}</div>
            <div class="label">Skipped</div>
        </div>
        <div class="result-stat info">
            <div class="number">${data.successful + data.failed + data.skipped}</div>
            <div class="label">Total</div>
        </div>
    `;

    document.getElementById('results-summary').innerHTML = summaryHtml;

    // Display errors if any
    if (data.errors && data.errors.length > 0) {
        const errorsContainer = document.getElementById('results-errors');
        
        let errorsHtml = '<h3>Import Errors</h3>';
        errorsHtml += '<div class="error-list">';
        
        data.errors.forEach(error => {
            errorsHtml += `<div class="error-item">${error}</div>`;
        });
        
        if (data.total_errors > data.errors.length) {
            errorsHtml += `<div class="error-item"><strong>... and ${data.total_errors - data.errors.length} more errors</strong></div>`;
        }
        
        errorsHtml += '</div>';
        errorsContainer.innerHTML = errorsHtml;
        errorsContainer.style.display = 'block';
    }
}

// Display error message
function displayError(message) {
    const headerHtml = `
        <div class="results-icon error">
            <i class="fas fa-times"></i>
        </div>
        <h2>Import Failed</h2>
        <p>${message}</p>
    `;

    document.getElementById('results-header').innerHTML = headerHtml;
    document.getElementById('results-summary').innerHTML = '';
}

// Navigate to specific step
function goToStep(step) {
    // Hide all steps
    for (let i = 1; i <= 4; i++) {
        const stepElement = document.getElementById(`step-${i}`);
        const contentElement = document.getElementById(`content-${i}`);
        
        if (stepElement && contentElement) {
            stepElement.classList.remove('active', 'completed');
            contentElement.style.display = 'none';
        }
    }

    // Show current step
    const currentStepElement = document.getElementById(`step-${step}`);
    const currentContentElement = document.getElementById(`content-${step}`);
    
    if (currentStepElement && currentContentElement) {
        currentStepElement.classList.add('active');
        currentContentElement.style.display = 'block';
    }

    // Mark previous steps as completed
    for (let i = 1; i < step; i++) {
        const stepElement = document.getElementById(`step-${i}`);
        if (stepElement) {
            stepElement.classList.add('completed');
        }
    }

    currentStep = step;
}

// Start new import
function startNewImport() {
    // Reset everything
    currentStep = 1;
    uploadedFile = null;
    fileData = null;
    
    // Reset file input
    const fileInput = document.getElementById('file-input');
    if (fileInput) {
        fileInput.value = '';
    }
    
    // Reset UI
    removeFile();
    
    // Go to step 1
    goToStep(1);
}

// Utility functions
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function showAlert(message, type = 'info') {
    // Create alert element
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible`;
    alert.innerHTML = `
        ${message}
        <button type="button" class="close" onclick="this.parentElement.remove()">
            <span>&times;</span>
        </button>
    `;
    
    // Insert at top of content
    const firstContent = document.querySelector('.wizard-content');
    if (firstContent) {
        firstContent.insertBefore(alert, firstContent.firstChild);
    }
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (alert.parentElement) {
            alert.remove();
        }
    }, 5000);
}

function showLoading(show) {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.display = show ? 'flex' : 'none';
    }
}

// Export functions for global access
window.initializeImport = initializeImport;
window.uploadFile = uploadFile;
window.startImport = startImport;
window.goToStep = goToStep;
window.startNewImport = startNewImport;
window.removeFile = removeFile;
