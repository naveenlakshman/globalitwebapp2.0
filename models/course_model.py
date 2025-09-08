from init_db import db
from datetime import datetime, timezone
from utils.timezone_helper import format_datetime_indian, format_date_indian, utc_to_ist
from utils.model_helpers import standardize_model_datetime_fields
from sqlalchemy import Enum, Text, String, Integer, Float, DateTime, Boolean

class Course(db.Model):
    __tablename__ = 'courses'

    id = db.Column(Integer, primary_key=True)
    
    # Basic Course Information
    course_name = db.Column(String(120), nullable=False, unique=True)
    course_code = db.Column(String(20), unique=True)  # Short code like "MSO-ADV", "PYTHON-FUL"
    category = db.Column(Enum("Programming", "Office Suite", "Web Development", "Data Science", 
                             "Digital Marketing", "Graphic Design", "Hardware", "Networking", 
                             "Cloud Computing", "Mobile Development", "Digital Foundations",
                             "Programming & AI", "Finance & Accounting", "Communication & Soft Skills", 
                             "Other", name="course_category"), 
                        default="Programming")
    
    # Duration and Timing
    duration = db.Column(String(50), nullable=False)  # e.g., "3 Months", "120 Hours"
    duration_in_hours = db.Column(Integer)  # Total course hours for calculation
    duration_in_days = db.Column(Integer)   # Total course days
    
    # Pricing Information
    fee = db.Column(Float, nullable=False)
    registration_fee = db.Column(Float, default=0.0)  # One-time registration fee
    material_fee = db.Column(Float, default=0.0)      # Books, materials fee
    certification_fee = db.Column(Float, default=0.0) # Certificate fee
    early_bird_discount = db.Column(Float, default=0.0)  # Early bird discount percentage
    group_discount = db.Column(Float, default=0.0)       # Group enrollment discount
    
    # Course Content and Structure
    description = db.Column(Text)
    course_outline = db.Column(Text)        # Detailed syllabus
    prerequisites = db.Column(Text)         # Required prior knowledge
    learning_outcomes = db.Column(Text)     # What students will learn
    software_requirements = db.Column(Text) # Required software/tools
    
    # Target Audience and Career
    target_audience = db.Column(Text)       # Who should take this course
    career_opportunities = db.Column(Text)  # Job opportunities after course
    difficulty_level = db.Column(Enum("Beginner", "Intermediate", "Advanced", "Expert", name="difficulty_level"), 
                                default="Beginner")
    
    # Course Delivery and Format
    delivery_mode = db.Column(Enum("Classroom", "Online", "Hybrid", "Offline", "Offline/Hybrid", name="delivery_mode"), default="Classroom")
    batch_size_min = db.Column(Integer, default=5)   # Minimum students to start batch
    batch_size_max = db.Column(Integer, default=30)  # Maximum students per batch
    
    # Certification and Assessment
    has_certification = db.Column(Boolean, default=True)
    certification_body = db.Column(String(100))  # Issuing authority
    assessment_type = db.Column(Enum("Project", "Exam", "Both", "Continuous", name="assessment_type"), 
                               default="Both")
    passing_criteria = db.Column(String(100))  # e.g., "60% in exam + project completion"
    
    # Scheduling Information
    typical_schedule = db.Column(String(200))  # e.g., "Mon-Fri 10AM-12PM" or "Weekends 9AM-1PM"
    flexible_timing = db.Column(Boolean, default=True)  # Can timing be adjusted
    
    # Marketing and Visibility
    is_featured = db.Column(Boolean, default=False)    # Show on homepage
    is_popular = db.Column(Boolean, default=False)     # Mark as popular course
    display_order = db.Column(Integer, default=100)    # For sorting in lists
    course_image = db.Column(String(200))              # Course thumbnail/image
    brochure_path = db.Column(String(200))             # PDF brochure path
    
    # Administrative
    status = db.Column(Enum("Active", "Inactive", "Draft", "Archived", name="course_status"), default='Active')
    is_deleted = db.Column(Integer, default=0)
    created_at = db.Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by = db.Column(Integer, db.ForeignKey('users.id'))  # Who created the course
    
    # Enrollment tracking (computed properties)
    @property
    def total_enrollments(self):
        """Get total number of students enrolled in this course"""
        from models.student_model import Student
        return Student.query.filter_by(course_name=self.course_name, is_deleted=0).count()
    
    @property
    def active_batches_count(self):
        """Get number of active batches for this course"""
        from models.batch_model import Batch
        return Batch.query.filter_by(course_id=self.id, is_deleted=0).filter(
            Batch.status.in_(['Active', 'In Progress'])
        ).count()
    
    @property
    def total_revenue(self):
        """Get total revenue generated from this course"""
        from models.invoice_model import Invoice
        result = db.session.query(db.func.sum(Invoice.paid_amount)).filter_by(
            course_id=self.id, is_deleted=0
        ).scalar()
        return result or 0.0

    def to_dict(self, include_stats=False):
        """Convert course to dictionary with optional statistics"""
        base_dict = {
            "id": self.id,
            "course_name": self.course_name,
            "course_code": self.course_code,
            "category": self.category,
            "duration": self.duration,
            "duration_in_hours": self.duration_in_hours,
            "duration_in_days": self.duration_in_days,
            "fee": self.fee,
            "registration_fee": self.registration_fee,
            "material_fee": self.material_fee,
            "certification_fee": self.certification_fee,
            "early_bird_discount": self.early_bird_discount,
            "group_discount": self.group_discount,
            "description": self.description,
            "course_outline": self.course_outline,
            "prerequisites": self.prerequisites,
            "learning_outcomes": self.learning_outcomes,
            "software_requirements": self.software_requirements,
            "target_audience": self.target_audience,
            "career_opportunities": self.career_opportunities,
            "difficulty_level": self.difficulty_level,
            "delivery_mode": self.delivery_mode,
            "batch_size_min": self.batch_size_min,
            "batch_size_max": self.batch_size_max,
            "has_certification": self.has_certification,
            "certification_body": self.certification_body,
            "assessment_type": self.assessment_type,
            "passing_criteria": self.passing_criteria,
            "typical_schedule": self.typical_schedule,
            "flexible_timing": self.flexible_timing,
            "is_featured": self.is_featured,
            "is_popular": self.is_popular,
            "display_order": self.display_order,
            "course_image": self.course_image,
            "brochure_path": self.brochure_path,
            "status": self.status,
            "created_at": format_datetime_indian(utc_to_ist(self.created_at)) if self.created_at else None,
            "updated_at": format_datetime_indian(utc_to_ist(self.updated_at)) if self.updated_at else None
        }
        
        if include_stats:
            base_dict.update({
                "total_enrollments": self.total_enrollments,
                "active_batches_count": self.active_batches_count,
                "total_revenue": self.total_revenue
            })
        
        return base_dict
    
    def __repr__(self):
        return f'<Course {self.course_name} - {self.category}>'