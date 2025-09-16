from init_db import db
from datetime import datetime, timezone
from utils.timezone_helper import utc_to_ist  # ✅ Centralized IST converter
from sqlalchemy import Enum
from werkzeug.security import check_password_hash, generate_password_hash

class Student(db.Model):
    __tablename__ = 'students'

    student_id = db.Column(db.String(50), primary_key=True)
    student_reg_no  = db.Column(db.String(50), nullable=False, unique=True, index=True)  # NEW
    full_name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(10))
    dob = db.Column(db.Date)
    mobile = db.Column(db.String(15))
    email = db.Column(db.String(100))
    address = db.Column(db.String(200))
    guardian_name = db.Column(db.String(100))            # ✅ Newly added
    guardian_mobile = db.Column(db.String(15))           # ✅ Guardian contact
    qualification = db.Column(db.String(50))             # ✅ Educational qualification
    admission_mode = db.Column(db.String(20))            # ✅ Newly added
    referred_by = db.Column(db.String(100))              # ✅ Newly added
    
    # ✅ Enhanced lead tracking fields (consistent with Lead model)
    lead_source = db.Column(db.Enum("Walk-in","Referral","Phone","Instagram","Facebook","Google","College Visit","Tally","Other", name="student_lead_source"), index=True)
    auto_created_lead = db.Column(db.Boolean, default=False)  # Flag to track if lead was auto-created
    auto_created_lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'))  # Reference to auto-created lead
    photo_filename = db.Column(db.String(200))           # ✅ Newly added
    id_proof_filename = db.Column(db.String(200))        # ✅ ID proof document
    registered_by = db.Column(db.String(100))            # ✅ Optional for audit
    admission_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'))
    course_name = db.Column(db.String(100))               # ✅ Course name for easy access
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'))  # ✅ Branch reference
    original_lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'))  # ✅ Track lead conversion
    status = db.Column(db.String(20), default='Active')  # ✅ Student status (Active, Hold, Inactive, Dropout, Completed)
    is_deleted = db.Column(db.Integer, default=0)
    
    # ✅ Internal LMS Integration fields
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))  # ✅ Course foreign key for LMS
    lms_enrolled = db.Column(db.Boolean, default=False)             # ✅ LMS enrollment status
    lms_enrollment_date = db.Column(db.DateTime)                     # ✅ LMS enrollment timestamp
    
    # ✅ Student Portal Authentication fields
    password_hash = db.Column(db.String(200))                        # ✅ Password for student portal login
    last_portal_login = db.Column(db.DateTime)                       # ✅ Last login to student portal
    portal_access_enabled = db.Column(db.Boolean, default=True)      # ✅ Portal access control

    def set_password(self, password):
        """Set password hash for student portal login"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if provided password matches the stored hash"""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def enroll_in_lms(self):
        """Enroll student in the internal LMS"""
        from utils.timezone_helper import get_current_ist_datetime
        
        if not self.lms_enrolled and self.course_id:
            self.lms_enrolled = True
            self.lms_enrollment_date = get_current_ist_datetime()
            db.session.commit()
            return True
        return False
    
    def update_portal_login(self):
        """Update last portal login timestamp"""
        from utils.timezone_helper import get_current_ist_datetime
        
        self.last_portal_login = get_current_ist_datetime()
        db.session.commit()
    
    def can_access_portal(self):
        """Check if student can access the portal"""
        return (self.portal_access_enabled and 
                self.status in ['Active', 'Hold'] and 
                self.password_hash is not None)
    
    def get_lms_progress(self):
        """Get student's progress in the internal LMS"""
        if not self.lms_enrolled or not self.course_id:
            return {
                'enrolled': False,
                'progress': 0,
                'modules_completed': 0,
                'total_modules': 0
            }
        
        try:
            from models.lms_model import CourseModule, StudentModuleProgress
            
            # Get all modules for the student's course
            modules = CourseModule.query.filter_by(
                course_id=self.course_id,
                is_published=True
            ).all()
            
            total_modules = len(modules)
            completed_modules = 0
            
            if total_modules > 0:
                for module in modules:
                    if module.is_completed_by_student(self.student_id):
                        completed_modules += 1
                
                progress = (completed_modules / total_modules) * 100
            else:
                progress = 0
            
            return {
                'enrolled': True,
                'progress': round(progress, 1),
                'modules_completed': completed_modules,
                'total_modules': total_modules,
                'enrollment_date': self.lms_enrollment_date
            }
            
        except Exception as e:
            return {
                'enrolled': True,
                'progress': 0,
                'modules_completed': 0,
                'total_modules': 0,
                'error': str(e)
            }

    def to_dict(self):
        return {
            "student_id": self.student_id,
            "full_name": self.full_name,
            "gender": self.gender,
            "dob": self.dob.strftime("%Y-%m-%d") if self.dob else None,
            "mobile": self.mobile,
            "email": self.email,
            "address": self.address,
            "guardian_name": self.guardian_name,
            "guardian_mobile": self.guardian_mobile,
            "qualification": self.qualification,
            "admission_mode": self.admission_mode,
            "referred_by": self.referred_by,
            "lead_source": self.lead_source,
            "auto_created_lead": self.auto_created_lead,
            "auto_created_lead_id": self.auto_created_lead_id,
            "photo_filename": self.photo_filename,
            "id_proof_filename": self.id_proof_filename,
            "registered_by": self.registered_by,
            "admission_date": utc_to_ist(self.admission_date),
            "batch_id": self.batch_id,
            "course_name": self.course_name,
            "branch_id": self.branch_id,
            "original_lead_id": self.original_lead_id,
            "status": self.status,
            "course_id": self.course_id,
            "lms_enrolled": self.lms_enrolled,
            "lms_enrollment_date": utc_to_ist(self.lms_enrollment_date) if self.lms_enrollment_date else None,
            "portal_access_enabled": self.portal_access_enabled
        }

    def get_attendance_rate(self, batch_id=None):
        """Get attendance rate for this student in a specific batch"""
        try:
            from models.student_attendance_model import StudentAttendance
            
            query = StudentAttendance.query.filter_by(student_id=self.student_id)
            if batch_id:
                query = query.filter_by(batch_id=batch_id)
            
            attendance_records = query.all()
            if not attendance_records:
                return 0
            
            present_count = sum(1 for record in attendance_records if record.status == 'Present')
            total_count = len(attendance_records)
            
            return round((present_count / total_count) * 100, 1) if total_count > 0 else 0
        except:
            return 0

    def get_sessions_attended(self, batch_id=None):
        """Get number of sessions attended by this student"""
        try:
            from models.student_attendance_model import StudentAttendance
            
            query = StudentAttendance.query.filter_by(student_id=self.student_id, status='Present')
            if batch_id:
                query = query.filter_by(batch_id=batch_id)
            
            return query.count()
        except:
            return 0
    
    def create_lead_from_admission(self, created_by_user_id, course_interest=None):
        """
        Create a lead record when student is directly admitted (walk-in scenario)
        This ensures we don't lose lead tracking data for direct admissions
        """
        try:
            from models.lead_model import Lead
            from utils.timezone_helper import get_current_ist_datetime
            import random
            import string
            
            # Check if lead already exists to avoid duplicates
            if self.auto_created_lead_id:
                existing_lead = Lead.query.get(self.auto_created_lead_id)
                if existing_lead:
                    return existing_lead
            
            # Generate lead serial number (similar to existing leads)
            # Format: BranchCode + YYYYMMDD + sequence
            from models.branch_model import Branch
            branch = Branch.query.get(self.branch_id) if self.branch_id else None
            branch_code = branch.branch_code if branch else "UNK"
            
            # Get current date for serial number
            from datetime import datetime
            today = datetime.now()
            date_str = today.strftime("%Y%m%d")
            
            # Find next sequence number for today
            existing_leads_today = Lead.query.filter(
                Lead.lead_sl_number.like(f"{branch_code}{date_str}-%")
            ).count()
            
            next_sequence = existing_leads_today + 1
            lead_sl_number = f"{branch_code}{date_str}-{next_sequence:03d}"
            
            # Create new lead record
            new_lead = Lead(
                lead_sl_number=lead_sl_number,
                lead_generation_date=self.admission_date,  # Use admission date as lead generation date
                branch_id=self.branch_id,
                assigned_to_user_id=created_by_user_id,
                
                # Student information
                name=self.full_name,
                mobile=self.mobile,
                email=self.email,
                qualification=self.qualification,
                address=self.address,
                
                # Guardian information
                guardian_name=self.guardian_name,
                guardian_mobile=self.guardian_mobile,
                
                # Lead specifics
                course_interest=course_interest or self.course_name,
                lead_source=self.lead_source or "Walk-in",  # Default to walk-in if not specified
                
                # Status and stage for converted lead
                lead_status="Converted",
                lead_stage="Closed Won",
                lead_closed_at=self.admission_date,
                
                # Additional fields for direct admission
                employment_type="Student",  # Assuming student for direct admission
                priority="Hot",  # Direct admission shows high intent
                lead_score=200,  # High score for converted leads
                
                # Conversion tracking
                converted_student_id=self.student_id,
                
                # Consent defaults (can be updated later)
                whatsapp_consent=True,
                sms_consent=True,
                email_consent=True,
                
                # Special notes for auto-created leads
                special_notes=f"Auto-created lead from direct admission on {today.strftime('%Y-%m-%d')}. Student admitted immediately.",
                tags="Direct Admission,Auto Created",
                
                # Timestamps
                created_at=self.admission_date,
                updated_at=self.admission_date
            )
            
            # Save the lead
            db.session.add(new_lead)
            db.session.flush()  # Get the ID without committing
            
            # Update student with auto-created lead reference
            self.auto_created_lead = True
            self.auto_created_lead_id = new_lead.id
            
            # Update original lead linkage in student record
            if not self.original_lead_id:
                self.original_lead_id = new_lead.id
            
            # Create a follow-up record for the admission
            from models.lead_model import LeadFollowUp
            admission_followup = LeadFollowUp(
                lead_id=new_lead.id,
                note=f"Direct admission completed for {self.full_name}. Student ID: {self.student_id}",
                channel="Admission Visit",
                created_by_user_id=created_by_user_id,
                is_completed=True,
                completed_at=self.admission_date,
                outcome_category="Admission Completed",
                outcome_notes=f"Student directly admitted and enrolled in {self.course_name}",
                created_at=self.admission_date
            )
            
            db.session.add(admission_followup)
            
            return new_lead
            
        except Exception as e:
            # Log error but don't fail student creation
            print(f"Error creating lead from admission: {str(e)}")
            return None

    def get_last_attendance(self, batch_id=None):
        """Get the last attendance record for this student"""
        try:
            from models.student_attendance_model import StudentAttendance
            
            query = StudentAttendance.query.filter_by(student_id=self.student_id)
            if batch_id:
                query = query.filter_by(batch_id=batch_id)
            
            return query.order_by(StudentAttendance.attendance_date.desc()).first()
        except:
            return None

    @property
    def date_of_birth(self):
        """Alias for dob for template compatibility"""
        return self.dob
    
    @property
    def status_display(self):
        """Get status with color and description"""
        status_map = {
            'Active': {'color': 'success', 'description': 'Currently enrolled and attending classes'},
            'Hold': {'color': 'warning', 'description': 'Temporarily paused (fees pending, personal reasons, etc.)'},
            'Inactive': {'color': 'secondary', 'description': 'Not attending for a longer period'},
            'Dropout': {'color': 'danger', 'description': 'Officially left/discontinued'},
            'Completed': {'color': 'primary', 'description': 'Successfully finished the course'}
        }
        return status_map.get(self.status, {'color': 'light', 'description': 'Unknown status'})
    
    def get_fee_status(self):
        """Get comprehensive fee status for the student"""
        try:
            from models.invoice_model import Invoice
            from models.installment_model import Installment
            from datetime import date
            
            # Get all invoices for this student
            invoices = Invoice.query.filter_by(student_id=self.student_id, is_deleted=0).all()
            
            if not invoices:
                return {
                    'status': 'No Invoice',
                    'color': 'secondary',
                    'description': 'Invoice not yet created',
                    'details': 'No financial records found'
                }
            
            total_amount = sum(inv.total_amount for inv in invoices)
            total_paid = sum(inv.paid_amount for inv in invoices)
            total_due = sum(inv.due_amount for inv in invoices)
            
            # Get installment details for more accurate status
            overdue_installments = 0
            pending_installments = 0
            
            for invoice in invoices:
                installments = Installment.query.filter_by(
                    invoice_id=invoice.id, 
                    is_deleted=0
                ).all()
                
                for installment in installments:
                    if installment.status == 'overdue':
                        overdue_installments += 1
                    elif installment.status == 'pending' and installment.due_date < date.today():
                        overdue_installments += 1
                    elif installment.status == 'pending':
                        pending_installments += 1
            
            # Determine status based on payment completion and overdue installments
            if total_due <= 0:
                return {
                    'status': 'Paid',
                    'color': 'success',
                    'description': 'All fees paid',
                    'details': f'₹{total_paid:,.0f} paid'
                }
            elif overdue_installments > 0:
                return {
                    'status': 'Overdue',
                    'color': 'danger',
                    'description': f'{overdue_installments} installment(s) overdue',
                    'details': f'₹{total_due:,.0f} pending'
                }
            elif pending_installments > 0 or total_paid > 0:
                return {
                    'status': 'Partial',
                    'color': 'warning',
                    'description': 'Partially paid',
                    'details': f'₹{total_paid:,.0f} paid, ₹{total_due:,.0f} due'
                }
            else:
                return {
                    'status': 'Pending',
                    'color': 'info',
                    'description': 'Payment pending',
                    'details': f'₹{total_amount:,.0f} total'
                }
                
        except Exception as e:
            return {
                'status': 'Error',
                'color': 'secondary',
                'description': 'Unable to fetch fee status',
                'details': str(e)
            }
    
    def get_total_sessions(self, batch_id):
        """Get total number of attendance sessions for this student in a batch"""
        try:
            from models.student_attendance_model import StudentAttendance
            
            total_sessions = StudentAttendance.query.filter_by(
                student_id=self.student_id,
                batch_id=batch_id
            ).count()
            
            return total_sessions
        except:
            return 0
    
    def get_present_count(self, batch_id):
        """Get count of present attendance records for this student in a batch"""
        try:
            from models.student_attendance_model import StudentAttendance
            
            present_count = StudentAttendance.query.filter_by(
                student_id=self.student_id,
                batch_id=batch_id,
                status='Present'
            ).count()
            
            return present_count
        except:
            return 0
    
    def get_late_count(self, batch_id):
        """Get count of late attendance records for this student in a batch"""
        try:
            from models.student_attendance_model import StudentAttendance
            
            late_count = StudentAttendance.query.filter_by(
                student_id=self.student_id,
                batch_id=batch_id,
                status='Late'
            ).count()
            
            return late_count
        except:
            return 0
    
    def get_absent_count(self, batch_id):
        """Get count of absent attendance records for this student in a batch"""
        try:
            from models.student_attendance_model import StudentAttendance
            
            absent_count = StudentAttendance.query.filter_by(
                student_id=self.student_id,
                batch_id=batch_id,
                status='Absent'
            ).count()
            
            return absent_count
        except:
            return 0
    
    def get_attendance_percentage(self, batch_id):
        """Get attendance percentage for this student in a batch"""
        try:
            total_sessions = self.get_total_sessions(batch_id)
            if total_sessions == 0:
                return 0
            
            present_count = self.get_present_count(batch_id)
            late_count = self.get_late_count(batch_id)
            
            # Count both present and late as attended
            attended_sessions = present_count + late_count
            percentage = (attended_sessions / total_sessions) * 100
            
            return round(percentage, 1)
        except:
            return 0
    
    def get_practical_hours(self, batch_id):
        """Get total practical hours for this student in a batch"""
        try:
            from models.student_attendance_model import StudentAttendance
            
            # Count attendance records where session_type is 'Practical'
            practical_sessions = StudentAttendance.query.filter_by(
                student_id=self.student_id,
                batch_id=batch_id,
                session_type='Practical'
            ).filter(StudentAttendance.status.in_(['Present', 'Late'])).count()
            
            # Assuming each practical session is 1 hour
            return practical_sessions
        except:
            return 0
    
    def get_theory_hours(self, batch_id):
        """Get total theory hours for this student in a batch"""
        try:
            from models.student_attendance_model import StudentAttendance
            
            # Count attendance records where session_type is 'Theory'
            theory_sessions = StudentAttendance.query.filter_by(
                student_id=self.student_id,
                batch_id=batch_id,
                session_type='Theory'
            ).filter(StudentAttendance.status.in_(['Present', 'Late'])).count()
            
            # Assuming each theory session is 1 hour
            return theory_sessions
        except:
            return 0

    # Relationships
    branch = db.relationship('Branch', backref='students')
    batch = db.relationship('Batch', backref='students')
