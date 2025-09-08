/**
 * Enhanced Follow-up Completion with Dynamic Outcome Options
 * Provides context-aware outcome selection for each follow-up type
 */

// Import outcome categories from backend
const OUTCOME_CATEGORIES = {
    "Demo Session": {
        "success": [
            {"value": "Demo Completed Successfully", "icon": "✅", "color": "success", "description": "Demo went well, lead is satisfied"},
            {"value": "Very Interested After Demo", "icon": "😍", "color": "success", "description": "Lead showed high interest"},
            {"value": "Ready for Fee Discussion", "icon": "💰", "color": "success", "description": "Lead wants to discuss pricing"},
        ],
        "neutral": [
            {"value": "Demo Completed - Neutral Response", "icon": "😐", "color": "warning", "description": "Demo completed but neutral feedback"},
            {"value": "Needs More Information", "icon": "❓", "color": "warning", "description": "Lead needs additional details"},
            {"value": "Wants to Think About It", "icon": "🤔", "color": "warning", "description": "Lead needs time to consider"},
            {"value": "Technical Questions Raised", "icon": "🔧", "color": "warning", "description": "Lead has technical concerns"},
        ],
        "negative": [
            {"value": "Not Interested After Demo", "icon": "❌", "color": "danger", "description": "Lead lost interest after demo"},
            {"value": "Found Too Difficult", "icon": "😰", "color": "danger", "description": "Course seems too challenging"},
            {"value": "Budget Concerns Raised", "icon": "💸", "color": "danger", "description": "Pricing is an issue"},
            {"value": "Timing Not Right", "icon": "⏰", "color": "warning", "description": "Not the right time for training"},
        ],
        "followup": [
            {"value": "Demo Rescheduled", "icon": "📅", "color": "info", "description": "Demo moved to different time"},
            {"value": "Parent Involvement Needed", "icon": "👨‍👩‍👧", "color": "info", "description": "Need to involve parents/family"},
        ]
    },
    
    "Outbound Call": {
        "success": [
            {"value": "Interested - Demo Scheduled", "icon": "📅", "color": "success", "description": "Lead interested and demo booked"},
            {"value": "Very Enthusiastic", "icon": "🎉", "color": "success", "description": "Lead very excited about courses"},
            {"value": "Ready to Visit Branch", "icon": "🏢", "color": "success", "description": "Lead wants to visit center"},
            {"value": "Wants Course Details", "icon": "📚", "color": "success", "description": "Lead requesting course information"},
        ],
        "neutral": [
            {"value": "Spoke Briefly - Call Back Later", "icon": "📞", "color": "warning", "description": "Short conversation, will call back"},
            {"value": "Some Interest - Need More Info", "icon": "🤷", "color": "warning", "description": "Mild interest, needs details"},
            {"value": "Comparing Options", "icon": "⚖️", "color": "warning", "description": "Lead comparing with other institutes"},
        ],
        "negative": [
            {"value": "Not Interested", "icon": "❌", "color": "danger", "description": "Lead not interested in courses"},
            {"value": "Wrong Number", "icon": "📵", "color": "danger", "description": "Incorrect contact number"},
            {"value": "Do Not Call Again", "icon": "🚫", "color": "danger", "description": "Lead requested no more calls"},
        ],
        "followup": [
            {"value": "No Response - Try Again", "icon": "📞", "color": "info", "description": "No answer, will retry"},
            {"value": "Busy - Call Back Later", "icon": "⏳", "color": "info", "description": "Lead was busy, call later"},
            {"value": "Voicemail Left", "icon": "📧", "color": "info", "description": "Left voicemail message"},
        ]
    },
    
    "Fee Discussion": {
        "success": [
            {"value": "Agreed to Fees", "icon": "✅", "color": "success", "description": "Lead accepted the pricing"},
            {"value": "Negotiated Successfully", "icon": "🤝", "color": "success", "description": "Reached mutually acceptable price"},
            {"value": "Payment Plan Accepted", "icon": "💳", "color": "success", "description": "Installment plan agreed upon"},
            {"value": "Ready to Pay", "icon": "💰", "color": "success", "description": "Lead ready to make payment"},
        ],
        "neutral": [
            {"value": "Considering Fee Options", "icon": "🤔", "color": "warning", "description": "Lead thinking about pricing"},
            {"value": "Discussing with Family", "icon": "👨‍👩‍👧", "color": "warning", "description": "Need family consultation"},
            {"value": "Comparing with Other Institutes", "icon": "📊", "color": "warning", "description": "Comparing prices elsewhere"},
        ],
        "negative": [
            {"value": "Too Expensive", "icon": "💸", "color": "danger", "description": "Fees are too high for lead"},
            {"value": "Budget Not Available", "icon": "💰", "color": "danger", "description": "Lead cannot afford training"},
            {"value": "Found Cheaper Alternative", "icon": "🔍", "color": "danger", "description": "Lead found lower cost option"},
        ],
        "followup": [
            {"value": "Need to Discuss with Parents", "icon": "👨‍👩‍👧", "color": "info", "description": "Parent approval required"},
            {"value": "Will Decide Next Week", "icon": "📅", "color": "info", "description": "Lead needs more time"},
            {"value": "Wants EMI Options", "icon": "💳", "color": "info", "description": "Interested in installment plans"},
        ]
    }
    // Add more follow-up types as needed
};

// Next action suggestions based on outcomes
const NEXT_ACTION_SUGGESTIONS = {
    "Demo Completed Successfully": ["Fee Discussion", "Course Counseling"],
    "Very Interested After Demo": ["Fee Discussion", "Document Collection"],
    "Ready for Fee Discussion": ["Fee Discussion"],
    "Interested - Demo Scheduled": ["Demo Session"],
    "Agreed to Fees": ["Document Collection", "Admission Visit"],
    "Too Expensive": ["Fee Discussion", "Parent Meeting"],
    "Needs More Information": ["Course Counseling", "Email"],
    "No Response - Try Again": ["Outbound Call", "WhatsApp"],
    // Add more mappings
};

let currentFollowupId = null;
let currentFollowupType = null;

/**
 * Open the enhanced follow-up completion modal
 */
function openFollowupCompletionModal(followupId, followupType, followupDate, followupNotes) {
    currentFollowupId = followupId;
    currentFollowupType = followupType;
    
    // Update display information
    document.getElementById('followupTypeDisplay').textContent = followupType;
    document.getElementById('followupDateDisplay').textContent = new Date(followupDate).toLocaleString();
    document.getElementById('followupNotesDisplay').textContent = followupNotes || 'No specific notes';
    
    // Generate outcome options for this follow-up type
    generateOutcomeOptions(followupType);
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('completeFollowupModal'));
    modal.show();
}

/**
 * Generate dynamic outcome options based on follow-up type
 */
function generateOutcomeOptions(followupType) {
    const container = document.getElementById('outcomeCategories');
    container.innerHTML = '';
    
    const categories = OUTCOME_CATEGORIES[followupType] || OUTCOME_CATEGORIES["Outbound Call"]; // Fallback
    
    Object.keys(categories).forEach(categoryType => {
        const outcomes = categories[categoryType];
        
        outcomes.forEach(outcome => {
            const col = document.createElement('div');
            col.className = 'col-md-6 col-lg-4';
            
            col.innerHTML = `
                <div class="card outcome-option ${outcome.color}" 
                     data-outcome="${outcome.value}"
                     onclick="selectOutcome('${outcome.value}', '${outcome.description}')">
                    <div class="card-body text-center p-3">
                        <div class="fs-2 mb-2">${outcome.icon}</div>
                        <h6 class="card-title mb-1">${outcome.value}</h6>
                        <p class="card-text small text-muted">${outcome.description}</p>
                    </div>
                </div>
            `;
            
            container.appendChild(col);
        });
    });
}

/**
 * Handle outcome selection
 */
function selectOutcome(outcomeValue, outcomeDescription) {
    // Remove previous selection
    document.querySelectorAll('.outcome-option').forEach(option => {
        option.classList.remove('selected');
    });
    
    // Mark current selection
    const selectedOption = document.querySelector(`[data-outcome="${outcomeValue}"]`);
    selectedOption.classList.add('selected');
    
    // Update hidden input and display
    document.getElementById('selectedOutcomeCategory').value = outcomeValue;
    document.getElementById('selectedOutcomeText').textContent = outcomeValue;
    document.getElementById('selectedOutcome').classList.remove('d-none');
    
    // Generate next action suggestions
    generateNextActionSuggestions(outcomeValue);
    
    // Auto-populate outcome notes placeholder based on selection
    const notesField = document.getElementById('outcomeNotes');
    notesField.placeholder = `Add specific details about "${outcomeValue}"...`;
}

/**
 * Generate suggested next actions based on outcome
 */
function generateNextActionSuggestions(outcomeValue) {
    const nextActionSelect = document.getElementById('nextActionType');
    nextActionSelect.innerHTML = '<option value="">Select Type</option>';
    
    const suggestions = NEXT_ACTION_SUGGESTIONS[outcomeValue] || [];
    
    suggestions.forEach(suggestion => {
        const option = document.createElement('option');
        option.value = suggestion;
        option.textContent = suggestion;
        nextActionSelect.appendChild(option);
    });
    
    // Auto-check schedule next action for followup-required outcomes
    const followupRequiredOutcomes = [
        "Demo Rescheduled", "Parent Involvement Needed", "No Response - Try Again",
        "Busy - Call Back Later", "Need to Discuss with Parents", "Will Decide Next Week",
        "Wants EMI Options", "Needs More Information"
    ];
    
    if (followupRequiredOutcomes.includes(outcomeValue)) {
        document.getElementById('scheduleNextAction').checked = true;
        document.getElementById('nextActionSection').classList.remove('d-none');
    }
}

/**
 * Toggle next action section
 */
document.getElementById('scheduleNextAction').addEventListener('change', function() {
    const section = document.getElementById('nextActionSection');
    if (this.checked) {
        section.classList.remove('d-none');
    } else {
        section.classList.add('d-none');
    }
});

/**
 * Submit follow-up completion
 */
async function submitFollowupCompletion() {
    const selectedOutcome = document.getElementById('selectedOutcomeCategory').value;
    
    if (!selectedOutcome) {
        alert('Please select an outcome for this follow-up');
        return;
    }
    
    const formData = {
        followup_id: currentFollowupId,
        outcome_category: selectedOutcome,
        outcome_notes: document.getElementById('outcomeNotes').value,
        schedule_next: document.getElementById('scheduleNextAction').checked,
        next_action_type: document.getElementById('nextActionType').value,
        next_action_date: document.getElementById('nextActionDate').value,
        next_action_notes: document.getElementById('nextActionNotes').value
    };
    
    try {
        const response = await fetch('/leads/complete-followup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });
        
        if (response.ok) {
            const result = await response.json();
            
            // Show success message
            showNotification('Follow-up completed successfully!', 'success');
            
            // Close modal
            bootstrap.Modal.getInstance(document.getElementById('completeFollowupModal')).hide();
            
            // Refresh page or update UI
            location.reload();
        } else {
            throw new Error('Failed to complete follow-up');
        }
    } catch (error) {
        console.error('Error completing follow-up:', error);
        showNotification('Error completing follow-up. Please try again.', 'error');
    }
}

/**
 * Show notification
 */
function showNotification(message, type) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type === 'success' ? 'success' : 'danger'} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}
