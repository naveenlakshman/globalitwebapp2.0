from init_db import db
from datetime import datetime, timezone
from utils.timezone_helper import get_current_ist_datetime

class StaffProfile(db.Model):
    __tablename__ = 'staff_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    
    # Personal Information
    employee_id = db.Column(db.String(50), unique=True, nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(10), nullable=True)  # Male, Female, Other
    marital_status = db.Column(db.String(20), nullable=True)
    nationality = db.Column(db.String(50), nullable=True)
    blood_group = db.Column(db.String(5), nullable=True)
    
    # Contact Information
    primary_mobile = db.Column(db.String(15), nullable=True)
    secondary_mobile = db.Column(db.String(15), nullable=True)
    personal_email = db.Column(db.String(100), nullable=True)
    official_email = db.Column(db.String(100), nullable=True)
    
    # Address Information
    current_address = db.Column(db.Text, nullable=True)
    permanent_address = db.Column(db.Text, nullable=True)
    city = db.Column(db.String(50), nullable=True)
    state = db.Column(db.String(50), nullable=True)
    pincode = db.Column(db.String(10), nullable=True)
    country = db.Column(db.String(50), default='India')
    
    # Professional Information
    department = db.Column(db.String(100), nullable=True)
    designation = db.Column(db.String(100), nullable=True)
    joining_date = db.Column(db.Date, nullable=True)
    probation_period_months = db.Column(db.Integer, default=6)
    employment_type = db.Column(db.String(20), nullable=True)  # Full-time, Part-time, Contract
    work_location = db.Column(db.String(100), nullable=True)
    reporting_manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Salary & Benefits
    basic_salary = db.Column(db.Numeric(10, 2), nullable=True)
    gross_salary = db.Column(db.Numeric(10, 2), nullable=True)
    bank_account_number = db.Column(db.String(20), nullable=True)
    bank_name = db.Column(db.String(100), nullable=True)
    bank_ifsc = db.Column(db.String(11), nullable=True)
    pan_number = db.Column(db.String(10), nullable=True)
    aadhar_number = db.Column(db.String(12), nullable=True)
    
    # Education & Qualifications
    highest_qualification = db.Column(db.String(100), nullable=True)
    university_college = db.Column(db.String(200), nullable=True)
    graduation_year = db.Column(db.Integer, nullable=True)
    specialization = db.Column(db.String(100), nullable=True)
    additional_certifications = db.Column(db.Text, nullable=True)
    
    # Skills & Expertise
    technical_skills = db.Column(db.Text, nullable=True)  # JSON or comma-separated
    soft_skills = db.Column(db.Text, nullable=True)
    languages_known = db.Column(db.Text, nullable=True)
    teaching_subjects = db.Column(db.Text, nullable=True)  # For trainers
    years_of_experience = db.Column(db.Integer, nullable=True)
    previous_experience = db.Column(db.Text, nullable=True)
    
    # Emergency Contact
    emergency_contact_name = db.Column(db.String(100), nullable=True)
    emergency_contact_relation = db.Column(db.String(50), nullable=True)
    emergency_contact_mobile = db.Column(db.String(15), nullable=True)
    emergency_contact_address = db.Column(db.Text, nullable=True)
    
    # Documents & Files
    profile_photo = db.Column(db.String(255), nullable=True)
    resume_file = db.Column(db.String(255), nullable=True)
    id_proof_file = db.Column(db.String(255), nullable=True)
    address_proof_file = db.Column(db.String(255), nullable=True)
    educational_certificates = db.Column(db.Text, nullable=True)  # JSON array of file paths
    
    # Performance & Status
    performance_rating = db.Column(db.Float, nullable=True)
    last_appraisal_date = db.Column(db.Date, nullable=True)
    next_appraisal_date = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    notice_period_days = db.Column(db.Integer, default=30)
    
    # Additional Information
    notes = db.Column(db.Text, nullable=True)
    special_notes = db.Column(db.Text, nullable=True)
    hobbies_interests = db.Column(db.Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=get_current_ist_datetime)
    updated_at = db.Column(db.DateTime, default=get_current_ist_datetime, onupdate=get_current_ist_datetime)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='staff_profile')
    reporting_manager = db.relationship('User', foreign_keys=[reporting_manager_id])
    created_by = db.relationship('User', foreign_keys=[created_by_user_id])
    updated_by = db.relationship('User', foreign_keys=[updated_by_user_id])
    
    def __repr__(self):
        return f'<StaffProfile {self.user.full_name if self.user else self.user_id}>'
    
    def to_dict(self):
        """Convert staff profile to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'employee_id': self.employee_id,
            'user_name': self.user.full_name if self.user else None,
            'username': self.user.username if self.user else None,
            'role': self.user.role if self.user else None,
            'primary_mobile': self.primary_mobile,
            'personal_email': self.personal_email,
            'department': self.department,
            'designation': self.designation,
            'joining_date': self.joining_date.isoformat() if self.joining_date else None,
            'employment_type': self.employment_type,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def get_full_profile(self):
        """Get complete staff profile information"""
        profile_data = self.to_dict()
        
        # Add additional computed fields
        if self.user:
            # Get branch assignments
            from models.user_branch_assignment_model import UserBranchAssignment
            from models.branch_model import Branch
            
            assignments = UserBranchAssignment.query.filter_by(
                user_id=self.user_id, 
                is_active=1
            ).all()
            
            branches = []
            for assignment in assignments:
                branch = Branch.query.get(assignment.branch_id)
                if branch:
                    branches.append({
                        'id': branch.id,
                        'name': branch.branch_name,
                        'location': branch.location
                    })
            
            profile_data['branches'] = branches
            
        return profile_data
    
    @staticmethod
    def generate_employee_id():
        """Generate unique employee ID"""
        # Format: EMP-YYYY-NNNN (e.g., EMP-2025-0001)
        current_year = datetime.now().year
        
        # Get the last employee ID for current year
        last_profile = StaffProfile.query.filter(
            StaffProfile.employee_id.like(f'EMP-{current_year}-%')
        ).order_by(StaffProfile.employee_id.desc()).first()
        
        if last_profile and last_profile.employee_id:
            # Extract number and increment
            try:
                last_num = int(last_profile.employee_id.split('-')[-1])
                new_num = last_num + 1
            except:
                new_num = 1
        else:
            new_num = 1
        
        return f'EMP-{current_year}-{new_num:04d}'
    
    @staticmethod
    def get_staff_summary():
        """Get staff statistics summary"""
        from sqlalchemy import func
        from models.user_model import User
        
        total_staff = db.session.query(func.count(StaffProfile.id)).filter(
            StaffProfile.is_active == True
        ).scalar()
        
        # Group by role
        role_counts = db.session.query(
            User.role,
            func.count(StaffProfile.id)
        ).join(StaffProfile).filter(
            StaffProfile.is_active == True
        ).group_by(User.role).all()
        
        return {
            'total_staff': total_staff or 0,
            'role_breakdown': dict(role_counts) if role_counts else {}
        }
