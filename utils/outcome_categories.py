"""
Outcome Categories Configuration for Lead Follow-ups
Provides structured outcome options for different follow-up types
"""

def get_outcome_categories_for_channel(channel):
    """Get available outcome categories for a specific follow-up channel"""
    
    outcome_categories = {
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
        },
        
        "Course Counseling": {
            "success": [
                {"value": "Course Matches Goals", "icon": "🎯", "color": "success", "description": "Perfect course for lead's objectives"},
                {"value": "Very Interested in Program", "icon": "😍", "color": "success", "description": "Lead loves the course structure"},
                {"value": "Career Path Clarified", "icon": "🛤️", "color": "success", "description": "Clear career direction identified"},
            ],
            "neutral": [
                {"value": "Understanding Requirements", "icon": "📖", "color": "warning", "description": "Lead learning about course needs"},
                {"value": "Exploring Options", "icon": "🔍", "color": "warning", "description": "Lead considering different courses"},
                {"value": "Questions Answered", "icon": "❓", "color": "warning", "description": "Provided clarifications"},
            ],
            "negative": [
                {"value": "Course Not Suitable", "icon": "❌", "color": "danger", "description": "Course doesn't match lead's needs"},
                {"value": "Wrong Career Choice", "icon": "🚫", "color": "danger", "description": "Lead realizes different career path"},
                {"value": "Not Ready for Training", "icon": "⏳", "color": "danger", "description": "Lead not prepared for course"},
            ],
            "followup": [
                {"value": "Need More Details", "icon": "📚", "color": "info", "description": "Lead wants additional information"},
                {"value": "Want to See Curriculum", "icon": "📋", "color": "info", "description": "Lead wants detailed syllabus"},
                {"value": "Discuss with Family", "icon": "👨‍👩‍👧", "color": "info", "description": "Family consultation needed"},
            ]
        },
        
        "WhatsApp": {
            "success": [
                {"value": "Responded Positively", "icon": "👍", "color": "success", "description": "Positive response received"},
                {"value": "Expressed Interest", "icon": "😊", "color": "success", "description": "Lead showed interest"},
                {"value": "Asked Questions", "icon": "❓", "color": "success", "description": "Lead engaged with questions"},
            ],
            "neutral": [
                {"value": "Message Delivered", "icon": "✅", "color": "warning", "description": "Message delivered successfully"},
                {"value": "Message Read - No Reply", "icon": "👁️", "color": "warning", "description": "Seen but no response"},
                {"value": "Shared with Family", "icon": "👨‍👩‍👧", "color": "warning", "description": "Lead sharing with family"},
            ],
            "followup": [
                {"value": "No Response", "icon": "📵", "color": "info", "description": "No response yet"},
                {"value": "Requested Call Back", "icon": "📞", "color": "info", "description": "Lead wants phone call"},
            ]
        },
        
        "Email": {
            "success": [
                {"value": "Responded Positively", "icon": "📧", "color": "success", "description": "Positive email response"},
                {"value": "Asked Questions", "icon": "❓", "color": "success", "description": "Lead replied with questions"},
            ],
            "neutral": [
                {"value": "Message Delivered", "icon": "✅", "color": "warning", "description": "Email delivered successfully"},
                {"value": "No Response", "icon": "📧", "color": "info", "description": "No email response yet"},
            ]
        },
        
        "Document Collection": {
            "success": [
                {"value": "Documents Collected", "icon": "📄", "color": "success", "description": "All required documents received"},
                {"value": "Partial Documents Received", "icon": "📋", "color": "warning", "description": "Some documents received"},
            ],
            "followup": [
                {"value": "Documents Pending", "icon": "⏳", "color": "info", "description": "Still waiting for documents"},
                {"value": "Additional Documents Needed", "icon": "📄", "color": "info", "description": "More documents required"},
                {"value": "Document Verification Required", "icon": "🔍", "color": "info", "description": "Need to verify documents"},
            ],
            "negative": [
                {"value": "Unable to Provide Documents", "icon": "❌", "color": "danger", "description": "Lead cannot provide required docs"},
            ]
        },
        
        "Parent Meeting": {
            "success": [
                {"value": "Parents Supportive", "icon": "👨‍👩‍👧", "color": "success", "description": "Family supports the decision"},
                {"value": "Family Approved", "icon": "✅", "color": "success", "description": "Family gave approval"},
                {"value": "Financial Approval Received", "icon": "💰", "color": "success", "description": "Family will fund the training"},
            ],
            "neutral": [
                {"value": "Parents Have Concerns", "icon": "🤔", "color": "warning", "description": "Family has some reservations"},
                {"value": "Need More Convincing", "icon": "💬", "color": "warning", "description": "Family needs more information"},
            ],
            "followup": [
                {"value": "Financial Discussion Needed", "icon": "💰", "color": "info", "description": "Need to discuss funding"},
            ],
            "negative": [
                {"value": "Parents Not Supportive", "icon": "❌", "color": "danger", "description": "Family against the training"},
                {"value": "Family Decided Against", "icon": "🚫", "color": "danger", "description": "Family decided not to proceed"},
                {"value": "Permission Denied", "icon": "⛔", "color": "danger", "description": "Family denied permission"},
            ]
        },
        
        "Admission Visit": {
            "success": [
                {"value": "Admission Completed", "icon": "🎓", "color": "success", "description": "Successfully enrolled"},
                {"value": "Enrollment Successful", "icon": "✅", "color": "success", "description": "Lead enrolled in course"},
                {"value": "Payment Made", "icon": "💰", "color": "success", "description": "Payment completed"},
                {"value": "Batch Assigned", "icon": "👥", "color": "success", "description": "Lead assigned to batch"},
            ],
            "followup": [
                {"value": "Visit Scheduled", "icon": "📅", "color": "info", "description": "Admission visit scheduled"},
                {"value": "Documents Submitted", "icon": "📄", "color": "info", "description": "Submitted required documents"},
                {"value": "Admission Pending", "icon": "⏳", "color": "info", "description": "Admission process in progress"},
                {"value": "Visit Postponed", "icon": "📅", "color": "info", "description": "Visit rescheduled"},
            ]
        }
    }
    
    # Generic outcomes for channels not specifically defined
    generic_outcomes = {
        "success": [
            {"value": "Positive Response", "icon": "👍", "color": "success", "description": "Positive outcome"},
        ],
        "neutral": [
            {"value": "Neutral Response", "icon": "😐", "color": "warning", "description": "Neutral outcome"},
        ],
        "negative": [
            {"value": "Negative Response", "icon": "👎", "color": "danger", "description": "Negative outcome"},
        ],
        "followup": [
            {"value": "Follow-up Required", "icon": "🔄", "color": "info", "description": "Needs follow-up action"},
            {"value": "Other", "icon": "📝", "color": "info", "description": "Custom outcome"},
        ]
    }
    
    return outcome_categories.get(channel, generic_outcomes)

def get_all_outcome_categories():
    """Get all available outcome categories across all channels"""
    all_categories = set()
    
    channels = [
        "Demo Session", "Outbound Call", "Fee Discussion", "Course Counseling",
        "WhatsApp", "Email", "Document Collection", "Parent Meeting", "Admission Visit"
    ]
    
    for channel in channels:
        categories = get_outcome_categories_for_channel(channel)
        for category_type in categories.values():
            for outcome in category_type:
                all_categories.add(outcome["value"])
    
    # Add generic outcomes
    all_categories.update(["Positive Response", "Neutral Response", "Negative Response", "Follow-up Required", "Other"])
    
    return sorted(list(all_categories))

def get_outcome_impact(outcome_category):
    """Get the impact level of an outcome (success, neutral, negative, followup)"""
    success_outcomes = [
        "Demo Completed Successfully", "Very Interested After Demo", "Ready for Fee Discussion",
        "Interested - Demo Scheduled", "Very Enthusiastic", "Ready to Visit Branch",
        "Agreed to Fees", "Negotiated Successfully", "Payment Plan Accepted", "Ready to Pay",
        "Course Matches Goals", "Very Interested in Program", "Career Path Clarified",
        "Responded Positively", "Expressed Interest", "Documents Collected",
        "Parents Supportive", "Family Approved", "Financial Approval Received",
        "Admission Completed", "Enrollment Successful", "Payment Made", "Batch Assigned",
        "Positive Response"
    ]
    
    negative_outcomes = [
        "Not Interested After Demo", "Found Too Difficult", "Budget Concerns Raised",
        "Not Interested", "Wrong Number", "Do Not Call Again",
        "Too Expensive", "Budget Not Available", "Found Cheaper Alternative",
        "Course Not Suitable", "Wrong Career Choice", "Not Ready for Training",
        "Unable to Provide Documents", "Parents Not Supportive", "Family Decided Against",
        "Permission Denied", "Negative Response"
    ]
    
    if outcome_category in success_outcomes:
        return "success"
    elif outcome_category in negative_outcomes:
        return "negative"
    elif "Follow-up" in outcome_category or "Rescheduled" in outcome_category or "Pending" in outcome_category:
        return "followup"
    else:
        return "neutral"
