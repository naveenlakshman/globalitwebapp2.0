from init_db import db
from sqlalchemy import Enum, ForeignKey, Index, UniqueConstraint
from sqlalchemy.sql import func
from utils.timezone_helper import format_datetime_indian
from datetime import datetime

class Lead(db.Model):
    __tablename__ = "leads"

    id = db.Column(db.Integer, primary_key=True)
    lead_sl_number = db.Column(db.String(32), unique=True, nullable=False)  # e.g., MUM20241023-001
    lead_generation_date = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

    branch_id = db.Column(db.Integer, ForeignKey("branches.id"), nullable=False, index=True)
    assigned_to_user_id = db.Column(db.Integer, ForeignKey("users.id"), nullable=True, index=True)  # was lead_headed_by

    name = db.Column(db.String(120), nullable=False)
    mobile = db.Column(db.String(15), nullable=False, index=True)
    email = db.Column(db.String(255))  # optional but useful
    qualification = db.Column(db.String(80))
    employment_type = db.Column(Enum("Student","Employed","Self-Employed","Unemployed","Other", name="employment_type"))
    address = db.Column(db.String(255))

    course_interest = db.Column(db.String(120))  # or ForeignKey("courses.id")

    # Enhanced lead management fields - Updated for Phase 1
    # Lead Status - Current state of the lead (6 statuses)
    lead_status = db.Column(Enum("Open","In Progress","Follow-up Scheduled","Demo Scheduled","Converted","Not Interested", name="lead_status"), nullable=False, index=True, default="Open")
    # Lead Stage - Sales funnel step (8 stages)
    lead_stage = db.Column(Enum("New","Contacted","Qualified","Demo","Proposal","Negotiation","Closed Won","Closed Lost", name="lead_stage"), nullable=False, index=True, default="New")
    lead_closed_at = db.Column(db.DateTime(timezone=True))
    reason_for_lost = db.Column(db.Text)

    priority = db.Column(Enum("Low","Medium","High","Hot", name="lead_priority"), nullable=False, server_default="Medium", index=True)
    lead_score = db.Column(db.Integer, default=0, nullable=False)
    next_follow_up_at = db.Column(db.DateTime(timezone=True), index=True)

    lead_source = db.Column(Enum("Walk-in","Referral","Phone","Instagram","Facebook","Google","College Visit","Tally","Other", name="lead_source"), index=True)
    
    # Additional contact and preference fields
    alt_mobile = db.Column(db.String(15))
    preferred_language = db.Column(Enum("English","Hindi","Kannada","Tamil","Telugu","Marathi","Other", name="preferred_language"), default="English")
    availability_window = db.Column(db.String(100))  # e.g., "10 AM - 6 PM weekdays"
    decision_maker = db.Column(Enum("Self","Parent","Employer","Other", name="decision_maker"), nullable=False, default="Self")
    budget_comfort = db.Column(db.String(50))  # e.g., "10K-20K", "Flexible"
    mode_preference = db.Column(Enum("Offline","Online","Hybrid", name="mode_preference"), default="Offline")
    branch_preference = db.Column(db.String(100))
    distance_to_branch = db.Column(db.Float)  # in KM
    join_timeline = db.Column(Enum("Immediate","This Week","This Month","After Exams","Not Sure", name="join_timeline"), default="Not Sure")
    objections = db.Column(db.Text)  # time/fees/location/permission concerns
    
    # Guardian/Parent information (for students)
    guardian_name = db.Column(db.String(120))
    guardian_mobile = db.Column(db.String(15))
    guardian_email = db.Column(db.String(255))
    guardian_relation = db.Column(Enum("Father","Mother","Guardian","Relative","Other", name="guardian_relation"), nullable=True)
    
    # Goal and notes
    career_goal = db.Column(db.Text)  # job/marks/internship goals
    special_notes = db.Column(db.Text)
    
    # Document tracking
    documents_received = db.Column(db.Text)  # JSON or comma-separated list
    documents_pending = db.Column(db.Text)  # JSON or comma-separated list
    
    # Contact verification and preferences
    mobile_verified = db.Column(db.Boolean, default=False)
    email_verified = db.Column(db.Boolean, default=False)
    whatsapp_consent = db.Column(db.Boolean, default=True)
    sms_consent = db.Column(db.Boolean, default=True)
    email_consent = db.Column(db.Boolean, default=True)
    
    # Tags for quick identification
    tags = db.Column(db.Text)  # JSON array or comma-separated: "Tally,1st PUC,Prefers Kannada,Parent Decision"
    
    # Competitor and conversion tracking
    competitor_mention = db.Column(db.String(100))
    competitor_notes = db.Column(db.Text)
    
    # Lead age calculation helper (computed field)
    @property
    def lead_age_days(self):
        if self.lead_generation_date:
            from datetime import datetime
            return (datetime.now() - self.lead_generation_date.replace(tzinfo=None)).days
        return 0
    
    @property
    def display_priority(self):
        """Property to get the display priority for templates"""
        return self.get_effective_priority()

    def calculate_lead_score(self):
        """Calculate lead score based on available data points"""
        score = 0
        
        # 1. Lead Source scoring (25 points max)
        source_scores = {
            "Referral": 25,
            "Walk-in": 20,
            "Phone": 15,
            "Instagram": 10,
            "Facebook": 10,
            "Google": 12,
            "College Visit": 18,
            "Tally": 8,
            "Other": 5
        }
        if self.lead_source:
            score += source_scores.get(self.lead_source, 5)
        
        # 2. Qualification scoring (25 points max)
        if self.qualification:
            qual_lower = self.qualification.lower()
            if any(word in qual_lower for word in ['phd', 'doctorate', 'post graduate', 'pg', 'masters', 'mba', 'mca']):
                score += 25
            elif any(word in qual_lower for word in ['graduate', 'degree', 'bachelor', 'btech', 'be', 'bcom', 'bsc', 'ba']):
                score += 20
            elif any(word in qual_lower for word in ['diploma', 'certificate', 'professional']):
                score += 15
            elif any(word in qual_lower for word in ['12th', 'puc', 'hsc', '+2']):
                score += 10
            else:
                score += 5
        
        # 3. Employment Type scoring (20 points max)
        employment_scores = {
            "Employed": 20,
            "Self-Employed": 18,
            "Student": 12,
            "Unemployed": 8,
            "Other": 5
        }
        if self.employment_type:
            score += employment_scores.get(self.employment_type, 5)
        
        # 4. Budget Comfort scoring (25 points max)
        if self.budget_comfort:
            budget_lower = self.budget_comfort.lower()
            if 'flexible' in budget_lower or 'no limit' in budget_lower:
                score += 25
            elif any(indicator in budget_lower for indicator in ['50k', '40k', '30k', '25k']):
                score += 22
            elif any(indicator in budget_lower for indicator in ['20k', '15k']):
                score += 18
            elif any(indicator in budget_lower for indicator in ['10k', '12k']):
                score += 15
            elif any(indicator in budget_lower for indicator in ['5k', '8k']):
                score += 10
            else:
                score += 5
        
        # 5. Lead Stage progression scoring (30 points max)
        stage_scores = {
            "Won": 50,  # Bonus for converted leads
            "Negotiation": 30,
            "Demo Booked": 25,
            "Contacted": 15,
            "New": 10,
            "Lost": -10,
            "Not Interested": -5
        }
        if self.lead_stage:
            score += stage_scores.get(self.lead_stage, 5)
        
        # 6. Lead Status scoring (20 points max)
        status_scores = {
            "Converted": 40,
            "Demo Scheduled": 25,
            "Demo Booked": 25,
            "Negotiation": 22,
            "Follow-up Scheduled": 18,
            "In Progress": 15,
            "Contacted": 12,
            "Open": 8,
            "New": 5,
            "Not Interested": -5,
            "Lost": -10
        }
        if self.lead_status:
            score += status_scores.get(self.lead_status, 5)
        
        # 7. Follow-up engagement scoring (25 points max)
        if hasattr(self, 'followups') and self.followups:
            followup_count = len(self.followups)
            completed_followups = len([f for f in self.followups if f.is_completed])
            
            # Points for follow-up activity
            if followup_count >= 5:
                score += 15
            elif followup_count >= 3:
                score += 12
            elif followup_count >= 1:
                score += 8
            
            # Points for completion rate
            if followup_count > 0:
                completion_rate = completed_followups / followup_count
                if completion_rate >= 0.8:
                    score += 10
                elif completion_rate >= 0.5:
                    score += 7
                elif completion_rate >= 0.3:
                    score += 4
        
        # 8. Decision maker scoring (15 points max)
        decision_scores = {
            "Self": 15,
            "Employer": 12,
            "Parent": 8,
            "Other": 5
        }
        if self.decision_maker:
            score += decision_scores.get(self.decision_maker, 5)
        
        # 9. Join timeline urgency scoring (15 points max)
        timeline_scores = {
            "Immediate": 15,
            "This Week": 12,
            "This Month": 10,
            "After Exams": 8,
            "Not Sure": 3
        }
        if self.join_timeline:
            score += timeline_scores.get(self.join_timeline, 3)
        
        # 10. Lead age factor (10 points max, fresher leads score higher)
        age_days = self.lead_age_days
        if age_days <= 1:
            score += 10  # Very fresh
        elif age_days <= 3:
            score += 8   # Fresh
        elif age_days <= 7:
            score += 6   # Recent
        elif age_days <= 14:
            score += 4   # Week old
        elif age_days <= 30:
            score += 2   # Month old
        else:
            score += 0   # Old leads
        
        # 11. Contact verification bonus (10 points max)
        if self.mobile_verified:
            score += 5
        if self.email_verified:
            score += 5
        
        # 12. Course interest specificity (10 points max)
        if self.course_interest and self.course_interest.strip() and self.course_interest != "Not specified":
            score += 10
        
        # 13. Priority factor (5 points max)
        priority_scores = {
            "Hot": 5,
            "High": 4,
            "Warm": 2,
            "Low": 0
        }
        if self.priority:
            score += priority_scores.get(self.priority, 1)
        
        # Ensure score is not negative
        return max(0, score)

    def update_lead_score(self):
        """Update the lead score and save to database"""
        self.lead_score = self.calculate_lead_score()
        return self.lead_score
    
    def get_effective_priority(self):
        """Get the effective priority for display purposes"""
        # For converted leads, show as converted regardless of stored priority
        if self.lead_status == "Converted" or self.lead_stage == "Closed Won":
            return "Converted"
        
        # For lost leads, show as lost regardless of stored priority
        if self.lead_status == "Not Interested" or self.lead_stage == "Closed Lost":
            return "Lost"
        
        # For active leads, use the stored priority or calculate from score
        if self.priority and self.priority in ["Low", "Medium", "High", "Hot"]:
            return self.priority
        else:
            # Fallback to score-based calculation for active leads only
            score = self.lead_score or 0
            if score >= 150:
                return "Hot"
            elif score >= 120:
                return "High" 
            elif score >= 80:
                return "Medium"
            else:
                return "Low"
    
    def get_priority_from_score(self):
        """Determine priority based on lead score"""
        # For converted leads, priority is no longer relevant
        if self.lead_status == "Converted" or self.lead_stage == "Closed Won":
            return "Converted"
        
        # For lost leads, priority is no longer relevant
        if self.lead_status == "Not Interested" or self.lead_stage == "Closed Lost":
            return "Lost"
        
        score = self.lead_score or 0
        if score >= 150:
            return "Hot"
        elif score >= 120:
            return "High" 
        elif score >= 80:
            return "Medium"  # Changed from "Warm" to match database enum
        else:
            return "Low"
    
    def get_priority_display(self):
        """Get priority with emoji and color class"""
        priority = self.get_effective_priority()
        priority_config = {
            "Hot": {"emoji": "🔥", "class": "hot", "text": "Hot"},
            "High": {"emoji": "⭐", "class": "high", "text": "High"},
            "Medium": {"emoji": "👍", "class": "medium", "text": "Medium"},
            "Low": {"emoji": "📈", "class": "low", "text": "Low"},
            "Converted": {"emoji": "✅", "class": "converted", "text": "Converted"},
            "Lost": {"emoji": "❌", "class": "lost", "text": "Lost"}
        }
        return priority_config.get(priority, priority_config["Low"])

    # =====================================
    # AI LOGIC RULES - Phase 1 Enhancement
    # =====================================
    
    def apply_ai_stage_status_rules(self):
        """Apply AI logic rules to ensure Stage and Status consistency"""
        
        # Rule 0: Initialize NULL/None stage to "New" if not closed
        if self.lead_stage is None:
            if self.lead_status in ["Converted"]:
                self.lead_stage = "Closed Won"
            elif self.lead_status in ["Not Interested"]:
                self.lead_stage = "Closed Lost"
            else:
                self.lead_stage = "New"
        
        # Rule 1: If Stage = Closed Won → Status must be Converted
        if self.lead_stage == "Closed Won" and self.lead_status != "Converted":
            self.lead_status = "Converted"
            
        # Rule 2: If Stage = Closed Lost → Status must be Not Interested  
        elif self.lead_stage == "Closed Lost" and self.lead_status != "Not Interested":
            self.lead_status = "Not Interested"
            
        # Rule 3: If Status = Converted → Stage must be Closed Won
        elif self.lead_status == "Converted" and self.lead_stage != "Closed Won":
            self.lead_stage = "Closed Won"
            
        # Rule 4: If Status = Not Interested → Stage must be Closed Lost
        elif self.lead_status == "Not Interested" and self.lead_stage != "Closed Lost":
            self.lead_stage = "Closed Lost"
    
    def suggest_next_stage(self, follow_up_type):
        """AI suggests next stage based on follow-up type and current stage"""
        stage_progression = {
            "New": {
                "Outbound Call": "Contacted",
                "WhatsApp": "Contacted", 
                "Email": "Contacted"
            },
            "Contacted": {
                "Demo Session": "Demo",
                "Course Counseling": "Qualified",
                "Outbound Call": "Qualified"
            },
            "Qualified": {
                "Demo Session": "Demo",
                "Fee Discussion": "Proposal"
            },
            "Demo": {
                "Fee Discussion": "Proposal",
                "Course Counseling": "Proposal"
            },
            "Proposal": {
                "Fee Discussion": "Negotiation",
                "Parent Meeting": "Negotiation",
                "Document Collection": "Negotiation"
            },
            "Negotiation": {
                "Document Collection": "Closed Won",
                "Admission Visit": "Closed Won"
            }
        }
        
        current_options = stage_progression.get(self.lead_stage, {})
        return current_options.get(follow_up_type, self.lead_stage)
    
    def suggest_next_status(self, follow_up_outcome):
        """AI suggests next status based on follow-up outcome"""
        outcome_status_map = {
            "Interested": "In Progress",
            "Wants Demo": "Demo Scheduled", 
            "Price Concern": "Follow-up Scheduled",
            "Needs Time": "Follow-up Scheduled",
            "Parent Approval Needed": "Follow-up Scheduled",
            "Ready to Join": "Converted",
            "Enrolled": "Converted",
            "Not Interested": "Not Interested",
            "Budget Issue": "Not Interested",
            "Timing Issue": "Follow-up Scheduled",
            "Demo Completed": "In Progress"
        }
        
        return outcome_status_map.get(follow_up_outcome, self.lead_status)
    
    def get_valid_status_options(self):
        """Get valid status options based on current stage"""
        stage_status_map = {
            "New": ["Open", "In Progress"],
            "Contacted": ["In Progress", "Follow-up Scheduled", "Demo Scheduled"],
            "Qualified": ["In Progress", "Follow-up Scheduled", "Demo Scheduled"],
            "Demo": ["In Progress", "Follow-up Scheduled"],
            "Proposal": ["In Progress", "Follow-up Scheduled"],
            "Negotiation": ["In Progress", "Follow-up Scheduled"],
            "Closed Won": ["Converted"],
            "Closed Lost": ["Not Interested"]
        }
        
        return stage_status_map.get(self.lead_stage, ["Open", "In Progress"])
    
    def validate_stage_status_combination(self):
        """Validate if current stage-status combination is valid"""
        valid_statuses = self.get_valid_status_options()
        return self.lead_status in valid_statuses
    
    def auto_advance_stage_from_followup(self, follow_up_type, outcome_category=None):
        """Auto-advance stage based on completed follow-up with structured outcomes"""
        old_stage = self.lead_stage
        
        # Define successful completion outcomes for each follow-up type
        demo_success_outcomes = [
            "Demo Completed Successfully", "Very Interested After Demo", "Ready for Fee Discussion"
        ]
        
        counseling_success_outcomes = [
            "Course Matches Goals", "Very Interested in Program", "Career Path Clarified"
        ]
        
        fee_success_outcomes = [
            "Agreed to Fees", "Negotiated Successfully", "Payment Plan Accepted", "Ready to Pay"
        ]
        
        document_success_outcomes = [
            "Documents Collected", "Documents Submitted", "Document Verification Required"
        ]
        
        admission_success_outcomes = [
            "Admission Completed", "Enrollment Successful", "Payment Made"
        ]
        
        # Auto-advance based on follow-up completion with structured outcomes
        if follow_up_type in ["Outbound Call", "Inbound Call"]:
            if outcome_category and "Demo Scheduled" in outcome_category:
                # Call resulted in demo scheduling - advance to Demo stage
                if self.lead_stage in ["New", "Contacted"]:
                    self.lead_stage = "Demo"
            elif outcome_category and any(word in outcome_category for word in ["Interested", "Enthusiastic", "Visit"]):
                # Call showed interest - advance to Contacted
                if self.lead_stage == "New":
                    self.lead_stage = "Contacted"
                    
        elif follow_up_type == "Demo Session":
            if (outcome_category in demo_success_outcomes or 
                (outcome_category and "demo completed" in outcome_category.lower())):
                if self.lead_stage in ["New", "Contacted", "Qualified"]:
                    self.lead_stage = "Demo"
                    
        elif follow_up_type == "Course Counseling":
            if outcome_category in counseling_success_outcomes:
                if self.lead_stage == "Contacted":
                    self.lead_stage = "Qualified"
                    
        elif follow_up_type == "Fee Discussion":
            if outcome_category in fee_success_outcomes:
                if self.lead_stage == "Demo":
                    self.lead_stage = "Proposal"
                elif self.lead_stage == "Proposal":
                    self.lead_stage = "Negotiation"
            elif outcome_category and any(word in outcome_category for word in ["Too Expensive", "Budget Not Available"]):
                # Pricing rejection - close as lost
                self.lead_stage = "Closed Lost"
                    
        elif follow_up_type == "Document Collection":
            if outcome_category in document_success_outcomes:
                if self.lead_stage == "Negotiation":
                    self.lead_stage = "Closed Won"
                    
        elif follow_up_type == "Admission Visit":
            if outcome_category in admission_success_outcomes:
                self.lead_stage = "Closed Won"
                
        # Fallback for legacy data or unstructured outcomes
        elif outcome_category:
            outcome_lower = outcome_category.lower()
            
            if follow_up_type == "Demo Session" and any(word in outcome_lower for word in ["completed", "successful", "interested"]):
                if self.lead_stage in ["New", "Contacted", "Qualified"]:
                    self.lead_stage = "Demo"
                    
            elif follow_up_type == "Fee Discussion" and any(word in outcome_lower for word in ["agreed", "negotiated", "accepted"]):
                if self.lead_stage == "Demo":
                    self.lead_stage = "Proposal"
                elif self.lead_stage == "Proposal":
                    self.lead_stage = "Negotiation"
        
        # Apply consistency rules after stage change
        self.apply_ai_stage_status_rules()
        
        return old_stage != self.lead_stage  # Return True if stage changed

    def auto_update_stage_from_status(self):
        """Auto-update stage when status changes - Phase 2 Smart Automation"""
        old_stage = self.lead_stage
        
        # Initialize None stage first
        if self.lead_stage is None:
            if self.lead_status in ["Converted"]:
                self.lead_stage = "Closed Won"
            elif self.lead_status in ["Not Interested"]:
                self.lead_stage = "Closed Lost"
            else:
                self.lead_stage = "New"
        
        # Check if we have any contact activity (inbound or outbound)
        has_contact_activity = False
        if hasattr(self, 'followups') and self.followups:
            contact_channels = ['Outbound Call', 'Inbound Call', 'WhatsApp', 'Email', 'Video Call']
            has_contact_activity = any(
                f.channel in contact_channels and f.is_completed 
                for f in self.followups
            )
        
        # Status-driven stage updates
        if self.lead_status == "Converted":
            self.lead_stage = "Closed Won"
            
        elif self.lead_status == "Not Interested":
            self.lead_stage = "Closed Lost"
            
        elif self.lead_status == "Demo Scheduled":
            # Only advance if not already past demo stage
            if self.lead_stage in ["New", "Contacted", "Qualified", None]:
                self.lead_stage = "Demo"
                
        elif self.lead_status == "In Progress":
            # Advance from New to Contacted if in progress
            if self.lead_stage in ["New", None]:
                self.lead_stage = "Contacted"
                
        elif self.lead_status == "Follow-up Scheduled":
            # Ensure at least contacted if follow-up is scheduled and we have contact activity
            if self.lead_stage in ["New", None] and has_contact_activity:
                self.lead_stage = "Contacted"
            elif self.lead_stage in ["New", None]:
                # No contact yet, but follow-up scheduled, stay as New
                self.lead_stage = "New"
        
        # If we have contact activity but still in New stage, advance to Contacted
        if has_contact_activity and self.lead_stage in ["New", None]:
            self.lead_stage = "Contacted"
        
        # Apply consistency rules after stage change
        self.apply_ai_stage_status_rules()
        
        return old_stage != self.lead_stage  # Return True if stage changed

    def auto_update_status_from_followup_completion(self, follow_up_type, outcome_category, next_action_scheduled=False):
        """Auto-update status when follow-up is completed - Phase 2 Smart Automation with Structured Outcomes"""
        old_status = self.lead_status
        
        # Define outcome categories for better automation
        success_outcomes = [
            "Demo Completed Successfully", "Very Interested After Demo", "Ready for Fee Discussion",
            "Interested - Demo Scheduled", "Very Enthusiastic", "Ready to Visit Branch",
            "Agreed to Fees", "Negotiated Successfully", "Payment Plan Accepted", "Ready to Pay",
            "Course Matches Goals", "Very Interested in Program", "Career Path Clarified",
            "Responded Positively", "Expressed Interest", "Documents Collected",
            "Parents Supportive", "Family Approved", "Financial Approval Received",
            "Admission Completed", "Enrollment Successful", "Payment Made"
        ]
        
        neutral_outcomes = [
            "Demo Completed - Neutral Response", "Needs More Information", "Wants to Think About It",
            "Technical Questions Raised", "Spoke Briefly - Call Back Later", "Some Interest - Need More Info",
            "Comparing Options", "Considering Fee Options", "Discussing with Family",
            "Understanding Requirements", "Exploring Options", "Questions Answered",
            "Message Delivered", "Asked Questions", "Partial Documents Received",
            "Parents Have Concerns", "Need More Convincing", "Visit Scheduled"
        ]
        
        negative_outcomes = [
            "Not Interested After Demo", "Found Too Difficult", "Budget Concerns Raised",
            "Not Interested", "Wrong Number", "Do Not Call Again",
            "Too Expensive", "Budget Not Available", "Found Cheaper Alternative",
            "Course Not Suitable", "Wrong Career Choice", "Not Ready for Training",
            "Unable to Provide Documents", "Parents Not Supportive", "Family Decided Against"
        ]
        
        followup_required_outcomes = [
            "Timing Not Right", "Demo Rescheduled", "Parent Involvement Needed",
            "Busy - Call Back Later", "Voicemail Left", "Need to Discuss with Parents",
            "Will Decide Next Week", "Wants EMI Options", "Need More Details",
            "Want to See Curriculum", "No Response", "Requested Call Back",
            "Documents Pending", "Financial Discussion Needed", "Visit Postponed"
        ]
        
        # Apply automation based on outcome category
        if outcome_category in success_outcomes:
            # Positive outcomes - advance the lead
            if follow_up_type == "Demo Session":
                self.lead_status = "In Progress"
            elif "Demo Scheduled" in outcome_category:
                # Special case: when a call results in demo scheduling
                self.lead_status = "Demo Scheduled"
            elif follow_up_type == "Fee Discussion" and "Agreed" in outcome_category:
                # Fee agreement doesn't mean converted - need to complete enrollment
                self.lead_status = "In Progress"
            elif follow_up_type == "Admission Visit" and "Completed" in outcome_category:
                self.lead_status = "Converted"
            elif "Payment" in outcome_category or "Enrollment" in outcome_category:
                self.lead_status = "Converted"
            else:
                self.lead_status = "In Progress"
                
        elif outcome_category in neutral_outcomes:
            # Neutral outcomes - keep engaged
            if next_action_scheduled:
                self.lead_status = "Follow-up Scheduled"
            else:
                self.lead_status = "In Progress"
                
        elif outcome_category in negative_outcomes:
            # Negative outcomes - mark appropriately
            if "Not Interested" in outcome_category or "Wrong Number" in outcome_category or "Do Not Call" in outcome_category:
                self.lead_status = "Not Interested"
            elif "Too Expensive" in outcome_category or "Budget Not Available" in outcome_category:
                # Strong financial objections - likely not salvageable
                self.lead_status = "Not Interested"
            elif "Budget Concerns" in outcome_category:
                # Mild budget concerns - still salvageable with different approach
                self.lead_status = "Follow-up Scheduled"
            else:
                self.lead_status = "Not Interested"
                
        elif outcome_category in followup_required_outcomes:
            # Outcomes that explicitly require follow-up
            self.lead_status = "Follow-up Scheduled"
            
        else:
            # Fallback for unrecognized outcomes or legacy data
            # Try to parse from the outcome text (backward compatibility)
            outcome_lower = (outcome_category or "").lower()
            
            if any(word in outcome_lower for word in ["completed", "successful", "interested", "ready", "agreed", "enrolled"]):
                self.lead_status = "In Progress"
            elif any(word in outcome_lower for word in ["not interested", "budget", "expensive", "difficult"]):
                self.lead_status = "Not Interested"
            elif any(word in outcome_lower for word in ["reschedule", "later", "think", "discuss", "time"]):
                self.lead_status = "Follow-up Scheduled"
            else:
                # No change for unrecognizable outcomes
                pass
        
        # Apply consistency rules after status change
        self.apply_ai_stage_status_rules()
        
        return old_status != self.lead_status  # Return True if status changed

    def validate_business_logic(self):
        """Validate business logic consistency - Phase 2 Enhancement"""
        from utils.timezone_helper import get_current_ist_datetime
        issues = []
        
        # Rule 0: Stage should not be None/NULL
        if self.lead_stage is None:
            issues.append("Lead stage is not set (NULL) - should be initialized")
        
        # Rule 1: "In Progress" status should have follow-up activity or be recently created
        if self.lead_status == "In Progress":
            if len(self.followups) == 0 and self.lead_age_days > 1:
                issues.append("Lead marked as 'In Progress' but has no follow-up activity and is more than 1 day old")
        
        # Rule 2: "Follow-up Scheduled" status should have next_follow_up_at set
        if self.lead_status == "Follow-up Scheduled" and not self.next_follow_up_at:
            issues.append("Lead marked as 'Follow-up Scheduled' but no follow-up time is set")
        
        # Rule 2.5: "Follow-up Scheduled" status with no follow-up records
        if self.lead_status == "Follow-up Scheduled" and len(self.followups) == 0:
            issues.append("Lead marked as 'Follow-up Scheduled' but has no follow-up records - inconsistent data")
        
        # Rule 3: "Demo Scheduled" status should have a demo-type follow-up scheduled
        if self.lead_status == "Demo Scheduled":
            demo_followups = [f for f in self.followups if f.channel == "Demo Session"]
            if not demo_followups and not self.next_follow_up_at:
                issues.append("Lead marked as 'Demo Scheduled' but no demo session is scheduled")
        
        # Rule 3.5: Stage progression based on contact activity
        if hasattr(self, 'followups') and self.followups:
            contact_channels = ['Outbound Call', 'Inbound Call', 'WhatsApp', 'Email', 'Video Call']
            has_contact_activity = any(
                f.channel in contact_channels and f.is_completed 
                for f in self.followups
            )
            
            if has_contact_activity and self.lead_stage == "New":
                issues.append("Lead has completed contact activity but stage is still 'New' - should be 'Contacted'")
        
        # Rule 3.6: Stage consistency - no follow-ups should mean "New" stage
        if len(self.followups) == 0 and self.lead_stage not in ["New", "Closed Won", "Closed Lost"]:
            issues.append(f"Lead has no follow-up activity but stage is '{self.lead_stage}' - should be 'New'")
        
        # Rule 4: Leads older than 30 days without activity should be reviewed
        if self.lead_age_days > 30 and len(self.followups) == 0:
            issues.append(f"Lead is {self.lead_age_days} days old with no follow-up activity")
        
        # Rule 5: High priority leads should have recent activity
        if self.priority in ["High", "Hot"] and self.lead_age_days > 3:
            from datetime import datetime, timezone
            current_time = datetime.now(timezone.utc)  # Get timezone-aware current time
            recent_activity = any(
                f.created_at and abs((current_time - (f.created_at.replace(tzinfo=timezone.utc) if f.created_at.tzinfo is None else f.created_at)).days) <= 3 
                for f in self.followups
            )
            if not recent_activity:
                issues.append(f"{self.priority} priority lead has no activity in the last 3 days")
        
        return issues
    
    def auto_suggest_status_correction(self):
        """Auto-suggest status corrections based on current state"""
        suggestions = []
        
        # If stage is None, suggest initialization
        if self.lead_stage is None:
            # Check if we have contact activity to determine appropriate stage
            has_contact_activity = False
            if hasattr(self, 'followups') and self.followups:
                contact_channels = ['Outbound Call', 'Inbound Call', 'WhatsApp', 'Email', 'Video Call']
                has_contact_activity = any(
                    f.channel in contact_channels and f.is_completed 
                    for f in self.followups
                )
            
            if has_contact_activity:
                suggestions.append({
                    "current_stage": self.lead_stage,
                    "suggested_stage": "Contacted",
                    "reason": "Lead has contact activity but stage is not set"
                })
            else:
                suggestions.append({
                    "current_stage": self.lead_stage,
                    "suggested_stage": "New", 
                    "reason": "Lead stage is not set and should be initialized"
                })
        
        # If stage is "New" but has contact activity, suggest "Contacted"
        if self.lead_stage == "New" and hasattr(self, 'followups') and self.followups:
            contact_channels = ['Outbound Call', 'Inbound Call', 'WhatsApp', 'Email', 'Video Call']
            has_contact_activity = any(
                f.channel in contact_channels and f.is_completed 
                for f in self.followups
            )
            
            if has_contact_activity:
                suggestions.append({
                    "current_stage": self.lead_stage,
                    "suggested_stage": "Contacted",
                    "reason": "Lead has completed contact activity and should progress to 'Contacted' stage"
                })
        
        # If stage is not "New" but has no follow-ups, suggest "New"
        if (len(self.followups) == 0 and 
            self.lead_stage not in ["New", "Closed Won", "Closed Lost"] and 
            self.lead_status not in ["Converted", "Not Interested"]):
            suggestions.append({
                "current_stage": self.lead_stage,
                "suggested_stage": "New",
                "reason": "Lead has no follow-up activity and should be in 'New' stage"
            })
        
        # If "Follow-up Scheduled" but no follow-up records, suggest "Open"
        if self.lead_status == "Follow-up Scheduled" and len(self.followups) == 0:
            # Has next action scheduled but no follow-up records - data inconsistency
            suggestions.append({
                "current_status": self.lead_status,
                "suggested_status": "Open",
                "reason": "Status shows 'Follow-up Scheduled' but no follow-up records exist - data inconsistency",
                "clear_next_followup": True  # Flag to clear next_follow_up_at
            })
        
        # If Open but has next_follow_up_at scheduled and no follow-ups, check if it's valid
        elif (self.lead_status == "Open" and self.next_follow_up_at and 
              len(self.followups) == 0):
            # Check if the date is valid and in the future
            is_valid_future_date = False
            try:
                next_time = datetime.strptime(self.next_follow_up_at, "%d-%b-%Y %H:%M")
                if next_time > datetime.now():
                    is_valid_future_date = True
            except:
                pass
            
            if is_valid_future_date:
                suggestions.append({
                    "current_status": self.lead_status,
                    "suggested_status": "Follow-up Scheduled",
                    "reason": "Follow-up is scheduled, status should reflect this"
                })
            else:
                # Invalid or past date - clear it
                suggestions.append({
                    "current_status": self.lead_status,
                    "suggested_status": "Open",
                    "reason": "Invalid or past due follow-up date - clearing stale data",
                    "clear_next_followup": True
                })
        
        # If "In Progress" with no activity, suggest "Open" 
        if self.lead_status == "In Progress" and len(self.followups) == 0 and self.lead_age_days > 1:
            suggestions.append({
                "current_status": self.lead_status,
                "suggested_status": "Open",
                "reason": "No follow-up activity recorded, should be marked as 'Open' until engagement begins"
            })
        
        # If next_follow_up_at is set but status is not "Follow-up Scheduled" (exclude converted/closed leads)
        if (self.next_follow_up_at and 
            self.lead_status not in ["Follow-up Scheduled", "Demo Scheduled", "Converted", "Not Interested", "Lost"] and
            self.lead_stage not in ["Closed Won", "Closed Lost"]):
            suggestions.append({
                "current_status": self.lead_status,
                "suggested_status": "Follow-up Scheduled",
                "reason": "Follow-up is scheduled, status should reflect this"
            })
        
        return suggestions

    def check_duplicate_followup(self, follow_up_type, next_action_at):
        """Check for duplicate follow-ups - Phase 2 Smart Automation"""
        from datetime import timedelta
        
        if not next_action_at:
            return None
            
        # Check for existing follow-ups within 1 hour window
        time_window_start = next_action_at - timedelta(hours=1)
        time_window_end = next_action_at + timedelta(hours=1)
        
        existing_followups = [f for f in self.followups if 
                            f.next_action_at and 
                            f.channel == follow_up_type and
                            not f.is_completed and
                            time_window_start <= f.next_action_at <= time_window_end]
        
        return existing_followups[0] if existing_followups else None
    
    def get_conflicting_followups(self, next_action_at):
        """Get all follow-ups that conflict with the proposed time - Phase 2 Smart Automation"""
        from datetime import timedelta
        import pytz
        
        if not next_action_at:
            return []
        
        # Ensure next_action_at is timezone-aware (UTC)
        if next_action_at.tzinfo is None:
            next_action_at = pytz.UTC.localize(next_action_at)
            
        # Check for any follow-ups within 30 minutes
        time_window_start = next_action_at - timedelta(minutes=30)
        time_window_end = next_action_at + timedelta(minutes=30)
        
        conflicting_followups = []
        for f in self.followups:
            if f.next_action_at and not f.is_completed:
                # Ensure comparison datetime is timezone-aware
                followup_time = f.next_action_at
                if followup_time.tzinfo is None:
                    followup_time = pytz.UTC.localize(followup_time)
                    
                if time_window_start <= followup_time <= time_window_end:
                    conflicting_followups.append(f)
        
        return conflicting_followups
    
    def suggest_alternative_followup_time(self, preferred_time):
        """Suggest alternative time if conflicts exist - Phase 2 Smart Automation"""
        from datetime import timedelta
        import pytz
        
        # Ensure preferred_time is timezone-aware
        if preferred_time.tzinfo is None:
            preferred_time = pytz.UTC.localize(preferred_time)
        
        conflicts = self.get_conflicting_followups(preferred_time)
        if not conflicts:
            return preferred_time
            
        # Try 1 hour later
        alternative_time = preferred_time + timedelta(hours=1)
        if not self.get_conflicting_followups(alternative_time):
            return alternative_time
            
        # Try 2 hours later
        alternative_time = preferred_time + timedelta(hours=2)
        if not self.get_conflicting_followups(alternative_time):
            return alternative_time
            
        # Try next day same time
        alternative_time = preferred_time + timedelta(days=1)
        return alternative_time

    def suggest_smart_next_actions(self, last_follow_up_type=None, last_outcome=None):
        """AI-powered suggestions for next actions - Phase 2 Smart Automation"""
        from datetime import datetime, timedelta
        
        suggestions = []
        current_time = datetime.now()
        
        # Base suggestions on current stage and status
        stage_action_map = {
            "New": [
                {"action": "Outbound Call", "priority": "High", "time_offset": timedelta(hours=2), 
                 "reason": "Initial contact to qualify lead"},
                {"action": "WhatsApp", "priority": "Medium", "time_offset": timedelta(hours=1),
                 "reason": "Quick introduction message"},
                {"action": "Email", "priority": "Low", "time_offset": timedelta(hours=4),
                 "reason": "Send course information"}
            ],
            
            "Contacted": [
                {"action": "Course Counseling", "priority": "High", "time_offset": timedelta(days=1),
                 "reason": "Understand course requirements"},
                {"action": "Demo Session", "priority": "High", "time_offset": timedelta(days=2),
                 "reason": "Show practical training approach"},
                {"action": "Outbound Call", "priority": "Medium", "time_offset": timedelta(hours=8),
                 "reason": "Follow up on initial conversation"}
            ],
            
            "Qualified": [
                {"action": "Demo Session", "priority": "High", "time_offset": timedelta(days=1),
                 "reason": "Demonstrate course value"},
                {"action": "Fee Discussion", "priority": "Medium", "time_offset": timedelta(days=2),
                 "reason": "Discuss investment options"},
                {"action": "Parent Meeting", "priority": "Medium", "time_offset": timedelta(days=3),
                 "reason": "Get family buy-in"}
            ],
            
            "Demo": [
                {"action": "Fee Discussion", "priority": "High", "time_offset": timedelta(hours=4),
                 "reason": "Strike while demo impact is fresh"},
                {"action": "Course Counseling", "priority": "Medium", "time_offset": timedelta(days=1),
                 "reason": "Address any questions from demo"},
                {"action": "Parent Meeting", "priority": "Medium", "time_offset": timedelta(days=1),
                 "reason": "Get decision maker involved"}
            ],
            
            "Proposal": [
                {"action": "Fee Discussion", "priority": "High", "time_offset": timedelta(hours=6),
                 "reason": "Negotiate terms and pricing"},
                {"action": "Parent Meeting", "priority": "High", "time_offset": timedelta(days=1),
                 "reason": "Get final approval"},
                {"action": "Document Collection", "priority": "Medium", "time_offset": timedelta(days=2),
                 "reason": "Prepare for enrollment"}
            ],
            
            "Negotiation": [
                {"action": "Fee Discussion", "priority": "High", "time_offset": timedelta(hours=4),
                 "reason": "Close the deal"},
                {"action": "Document Collection", "priority": "High", "time_offset": timedelta(days=1),
                 "reason": "Finalize enrollment process"},
                {"action": "Admission Visit", "priority": "Medium", "time_offset": timedelta(days=1),
                 "reason": "Complete admission formalities"}
            ]
        }
        
        # Get base suggestions for current stage
        base_suggestions = stage_action_map.get(self.lead_stage, [])
        
        # Refine based on last follow-up outcome
        if last_outcome:
            if "interested" in last_outcome.lower():
                # Increase priority and reduce time offset
                for suggestion in base_suggestions:
                    suggestion["priority"] = "High"
                    suggestion["time_offset"] = suggestion["time_offset"] / 2
                    
            elif "not interested" in last_outcome.lower():
                # Add re-engagement strategies
                base_suggestions = [
                    {"action": "WhatsApp", "priority": "Low", "time_offset": timedelta(days=7),
                     "reason": "Re-engagement after cooling period"},
                    {"action": "Email", "priority": "Low", "time_offset": timedelta(days=14),
                     "reason": "Share success stories"}
                ]
                
            elif "needs time" in last_outcome.lower():
                # Extend time offsets
                for suggestion in base_suggestions:
                    suggestion["time_offset"] = suggestion["time_offset"] * 2
                    suggestion["reason"] += " (giving time to decide)"
        
        # Refine based on lead age
        lead_age = self.lead_age_days
        if lead_age > 7:
            # Add urgency for old leads
            for suggestion in base_suggestions:
                suggestion["reason"] += f" (Lead is {lead_age} days old - needs attention)"
                if suggestion["priority"] == "Medium":
                    suggestion["priority"] = "High"
        
        # Convert to final format with actual times
        for suggestion in base_suggestions:
            suggested_time = current_time + suggestion["time_offset"]
            
            # Check for conflicts and suggest alternative if needed
            alternative_time = self.suggest_alternative_followup_time(suggested_time)
            
            suggestions.append({
                "action": suggestion["action"],
                "priority": suggestion["priority"],
                "suggested_time": alternative_time,
                "reason": suggestion["reason"],
                "conflicts": len(self.get_conflicting_followups(suggested_time)) > 0
            })
        
        # Sort by priority (High -> Medium -> Low)
        priority_order = {"High": 3, "Medium": 2, "Low": 1}
        suggestions.sort(key=lambda x: priority_order.get(x["priority"], 0), reverse=True)
        
        return suggestions[:3]  # Return top 3 suggestions
    
    def get_smart_followup_templates(self, follow_up_type):
        """Get smart templates for different follow-up types - Phase 2 Smart Automation"""
        
        templates = {
            "Outbound Call": {
                "script": f"Hi {self.name}, this is from Global IT. I wanted to discuss your interest in {self.course_interest or 'our computer courses'}. When would be a good time to talk?",
                "duration": "15 minutes",
                "objectives": ["Qualify interest", "Understand timeline", "Schedule demo"]
            },
            
            "WhatsApp": {
                "script": f"Hello {self.name}! 👋 Thank you for your interest in Global IT courses. I'd love to help you find the perfect course. When can we chat? 📞",
                "duration": "Immediate",
                "objectives": ["Quick engagement", "Schedule call", "Share course info"]
            },
            
            "Demo Session": {
                "script": f"Hi {self.name}, let's schedule your free demo session for {self.course_interest or 'computer training'}. You'll see our teaching methodology and facilities firsthand.",
                "duration": "45 minutes",
                "objectives": ["Show course value", "Address concerns", "Build confidence"]
            },
            
            "Fee Discussion": {
                "script": f"Hi {self.name}, I'd like to discuss our flexible payment options for {self.course_interest or 'the course'}. We have several plans that might work for your budget.",
                "duration": "30 minutes", 
                "objectives": ["Present pricing", "Handle objections", "Offer flexibility"]
            },
            
            "Course Counseling": {
                "script": f"Hello {self.name}, let's discuss which course path would be best for your career goals. I'll help you choose the right program.",
                "duration": "30 minutes",
                "objectives": ["Understand goals", "Recommend courses", "Create learning path"]
            },
            
            "Parent Meeting": {
                "script": f"Hello, I'd like to meet with {self.name}'s family to discuss the course investment and benefits. Your support is important for their success.",
                "duration": "45 minutes",
                "objectives": ["Get family buy-in", "Address concerns", "Secure approval"]
            }
        }
        
        return templates.get(follow_up_type, {
            "script": f"Hi {self.name}, following up on our previous conversation.",
            "duration": "15 minutes",
            "objectives": ["Continue conversation", "Move forward"]
        })

    # conversion linkage (optional) - Temporarily disabled until students table is verified
    converted_student_id = db.Column(db.Integer)  # ForeignKey("students.id") commented out

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())
    is_deleted = db.Column(db.Boolean, nullable=False, server_default="0")
    
    # Enhanced deletion tracking fields
    deletion_reason = db.Column(db.String(50))  # duplicate_lead, spam_invalid, test_data, etc.
    deletion_notes = db.Column(db.Text)  # Additional context for deletion
    deleted_by_user_id = db.Column(db.Integer, ForeignKey("users.id"), nullable=True)
    deleted_at = db.Column(db.DateTime(timezone=True))

    __table_args__ = (
        Index("ix_leads_branch_status_next", "branch_id", "lead_status", "next_follow_up_at"),
    )

    # Relationships
    branch = db.relationship('Branch', backref='leads')
    assigned_to = db.relationship('User', foreign_keys=[assigned_to_user_id], backref='assigned_leads')
    deleted_by = db.relationship('User', foreign_keys=[deleted_by_user_id], backref='deleted_leads')
    followups = db.relationship('LeadFollowUp', back_populates='lead', cascade='all, delete-orphan')

    def to_dict(self):
        """Convert Lead object to dictionary"""
        return {
            'id': self.id,
            'lead_sl_number': self.lead_sl_number,
            'lead_generation_date': format_datetime_indian(self.lead_generation_date, include_time=True) if self.lead_generation_date else None,
            'branch_id': self.branch_id,
            'assigned_to_user_id': self.assigned_to_user_id,
            'name': self.name,
            'mobile': self.mobile,
            'email': self.email,
            'qualification': self.qualification,
            'employment_type': self.employment_type,
            'address': self.address,
            'course_interest': self.course_interest,
            'lead_status': self.lead_status,
            'lead_stage': self.lead_stage,
            'lead_closed_at': format_datetime_indian(self.lead_closed_at, include_time=True) if self.lead_closed_at else None,
            'reason_for_lost': self.reason_for_lost,
            'priority': self.priority,
            'lead_score': self.lead_score,
            'next_follow_up_at': format_datetime_indian(self.next_follow_up_at, include_time=True) if self.next_follow_up_at else None,
            'lead_source': self.lead_source,
            'alt_mobile': self.alt_mobile,
            'preferred_language': self.preferred_language,
            'availability_window': self.availability_window,
            'decision_maker': self.decision_maker,
            'budget_comfort': self.budget_comfort,
            'mode_preference': self.mode_preference,
            'branch_preference': self.branch_preference,
            'distance_to_branch': self.distance_to_branch,
            'join_timeline': self.join_timeline,
            'objections': self.objections,
            'guardian_name': self.guardian_name,
            'guardian_mobile': self.guardian_mobile,
            'guardian_email': self.guardian_email,
            'guardian_relation': self.guardian_relation,
            'career_goal': self.career_goal,
            'special_notes': self.special_notes,
            'documents_received': self.documents_received,
            'documents_pending': self.documents_pending,
            'mobile_verified': self.mobile_verified,
            'email_verified': self.email_verified,
            'whatsapp_consent': self.whatsapp_consent,
            'sms_consent': self.sms_consent,
            'email_consent': self.email_consent,
            'tags': self.tags,
            'competitor_mention': self.competitor_mention,
            'competitor_notes': self.competitor_notes,
            'converted_student_id': self.converted_student_id,
            'created_at': format_datetime_indian(self.created_at, include_time=True) if self.created_at else None,
            'updated_at': format_datetime_indian(self.updated_at, include_time=True) if self.updated_at else None,
            'is_deleted': self.is_deleted,
            'lead_age_days': self.lead_age_days
        }

    def __repr__(self):
        return f"<Lead {self.lead_sl_number}: {self.name}>"

class LeadFollowUp(db.Model):
    __tablename__ = "lead_followups"
    
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    note = db.Column(db.Text, nullable=False)
    # Follow-up types updated for computer training institute workflow (includes legacy values for migration)
    channel = db.Column(Enum("Outbound Call","WhatsApp","Email","Demo Session","Fee Discussion","Course Counseling","Document Collection","Admission Visit","Parent Meeting","Video Call","SMS","Inbound Call","Site Visit","Other","Call","Visit","Meeting","Admission Visit Scheduled", name="followup_channel"))
    created_by_user_id = db.Column(db.Integer, ForeignKey("users.id"))
    next_action_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Additional followup completion tracking
    is_completed = db.Column(db.Boolean, default=False, nullable=False)
    completed_at = db.Column(db.DateTime(timezone=True))
    
    # Structured outcome system - Phase 2 Enhancement
    outcome_category = db.Column(Enum(
        # Demo Session Outcomes
        "Demo Completed Successfully", "Very Interested After Demo", "Ready for Fee Discussion",
        "Demo Completed - Neutral Response", "Needs More Information", "Wants to Think About It",
        "Technical Questions Raised", "Not Interested After Demo", "Found Too Difficult", 
        "Budget Concerns Raised", "Timing Not Right", "Demo Rescheduled", "Parent Involvement Needed",
        
        # Call Outcomes (Outbound/Inbound)
        "Interested - Demo Scheduled", "Very Enthusiastic", "Ready to Visit Branch", 
        "Wants Course Details", "Spoke Briefly - Call Back Later", "Some Interest - Need More Info",
        "Comparing Options", "Not Interested", "Wrong Number", "Do Not Call Again",
        "No Response - Try Again", "Busy - Call Back Later", "Voicemail Left",
        
        # Fee Discussion Outcomes
        "Agreed to Fees", "Negotiated Successfully", "Payment Plan Accepted", "Ready to Pay",
        "Considering Fee Options", "Discussing with Family", "Comparing with Other Institutes",
        "Too Expensive", "Budget Not Available", "Found Cheaper Alternative",
        "Need to Discuss with Parents", "Will Decide Next Week", "Wants EMI Options",
        
        # Course Counseling Outcomes
        "Course Matches Goals", "Very Interested in Program", "Career Path Clarified",
        "Understanding Requirements", "Exploring Options", "Questions Answered",
        "Course Not Suitable", "Wrong Career Choice", "Not Ready for Training",
        "Need More Details", "Want to See Curriculum", "Discuss with Family",
        
        # WhatsApp/Email Outcomes
        "Message Delivered", "Responded Positively", "Expressed Interest", "Asked Questions",
        "No Response", "Message Read - No Reply", "Requested Call Back", "Shared with Family",
        
        # Document Collection Outcomes
        "Documents Collected", "Partial Documents Received", "Documents Pending",
        "Unable to Provide Documents", "Document Verification Required", "Additional Documents Needed",
        
        # Parent Meeting Outcomes
        "Parents Supportive", "Family Approved", "Financial Approval Received",
        "Parents Have Concerns", "Need More Convincing", "Financial Discussion Needed",
        "Parents Not Supportive", "Family Decided Against", "Permission Denied",
        
        # Admission Visit Outcomes
        "Admission Completed", "Enrollment Successful", "Payment Made", "Batch Assigned",
        "Visit Scheduled", "Documents Submitted", "Admission Pending", "Visit Postponed",
        
        # Generic/Other
        "Positive Response", "Neutral Response", "Negative Response", "Follow-up Required", "Other",
        
        name="followup_outcome_category"
    ), index=True)
    
    # Keep free text for additional context and legacy data
    outcome_notes = db.Column(db.Text)  # Additional details about the outcome
    next_action = db.Column(db.Text)

    # Relationships
    lead = db.relationship('Lead', back_populates='followups')
    created_by = db.relationship('User', backref='lead_followups')

    def to_dict(self):
        """Convert LeadFollowUp object to dictionary"""
        return {
            'id': self.id,
            'lead_id': self.lead_id,
            'note': self.note,
            'channel': self.channel,
            'created_by_user_id': self.created_by_user_id,
            'next_action_at': format_datetime_indian(self.next_action_at, include_time=True) if self.next_action_at else None,
            'created_at': format_datetime_indian(self.created_at, include_time=True) if self.created_at else None,
            'is_completed': self.is_completed,
            'completed_at': format_datetime_indian(self.completed_at, include_time=True) if self.completed_at else None,
            'outcome_category': self.outcome_category,
            'outcome_notes': self.outcome_notes,
            'next_action': self.next_action
        }

    def __repr__(self):
        return f"<LeadFollowUp {self.id}: Lead {self.lead_id}>"
