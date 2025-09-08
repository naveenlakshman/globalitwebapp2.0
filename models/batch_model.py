from init_db import db
from datetime import datetime, timezone
from utils.timezone_helper import utc_to_ist  # ✅ Centralized IST time

class Batch(db.Model):
    __tablename__ = 'batches'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    
    # Course relationship - proper foreign key
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    course_name = db.Column(db.String(100), nullable=True)  # Keep for backward compatibility during migration
    
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=False)  # Added for franchise scaling
    start_date = db.Column(db.Text)  # Changed to TEXT to match schema
    end_date = db.Column(db.Text)    # Changed to TEXT to match schema
    timing = db.Column(db.Text)      # Deprecated - keeping for backward compatibility
    
    # New time fields for attendance tracking
    checkin_time = db.Column(db.Time)    # Daily batch check-in time (e.g., 09:00)
    checkout_time = db.Column(db.Time)   # Daily batch check-out time (e.g., 12:00)
    
    max_capacity = db.Column(db.Integer, default=30)  # Maximum student capacity
    
    # Batch Lifecycle Management
    status = db.Column(db.String(20), default='Active')  # Active, Completed, Archived, Suspended, Cancelled
    completion_date = db.Column(db.Text)  # When batch was completed
    archived_at = db.Column(db.DateTime)  # When batch was archived
    archived_by = db.Column(db.Integer)   # User who archived the batch
    
    # Suspension tracking
    suspended_at = db.Column(db.DateTime)  # When batch was suspended
    suspended_by = db.Column(db.Integer)   # User who suspended the batch
    suspension_reason = db.Column(db.String(100))  # Reason for suspension
    suspension_notes = db.Column(db.Text)  # Additional notes for suspension
    expected_resume_date = db.Column(db.Date)  # Expected resume date
    
    # Cancellation tracking
    cancelled_at = db.Column(db.DateTime)  # When batch was cancelled
    cancelled_by = db.Column(db.Integer)   # User who cancelled the batch
    cancellation_reason = db.Column(db.String(100))  # Reason for cancellation
    cancellation_notes = db.Column(db.Text)  # Additional notes for cancellation
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_deleted = db.Column(db.Integer, default=0)  # Keep for backward compatibility

    # Relationships
    branch = db.relationship('Branch', backref='batches')
    # Note: Course relationship managed manually via course_id foreign key

    def to_dict(self):
        # Get course name manually if needed
        course_name = self.course_name
        if not course_name and self.course_id:
            from models.course_model import Course
            course = Course.query.get(self.course_id)
            course_name = course.course_name if course else 'Unknown Course'
            
        return {
            "batch_id": self.id,
            "name": self.name,
            "course_id": self.course_id,
            "course_name": course_name,
            "branch_id": self.branch_id,
            "timing": self.get_formatted_timing_display(),  # Use new formatted timing
            "checkin_time": self.get_formatted_checkin_time(),
            "checkout_time": self.get_formatted_checkout_time(),
            "start_date": self.start_date,
            "end_date": self.end_date,
            "start_date_formatted": self.get_formatted_start_date(),
            "end_date_formatted": self.get_formatted_end_date(),
            "status": self.status,
            "completion_date": self.completion_date,
            "created_at": utc_to_ist(self.created_at),  # Convert to IST
            "student_count": self.get_student_count(),
            "trainer_count": self.get_trainer_count(),
            "attendance_rate": self.get_attendance_rate()
        }

    def get_formatted_start_date(self):
        """Get formatted start date"""
        if not self.start_date:
            return 'Not set'
        try:
            from datetime import datetime
            if isinstance(self.start_date, str):
                date_obj = datetime.strptime(self.start_date, '%Y-%m-%d')
                return date_obj.strftime('%d %b %Y')
            else:
                return self.start_date.strftime('%d %b %Y')
        except:
            return self.start_date

    def get_formatted_end_date(self):
        """Get formatted end date"""
        if not self.end_date:
            return 'Not set'
        try:
            from datetime import datetime
            if isinstance(self.end_date, str):
                date_obj = datetime.strptime(self.end_date, '%Y-%m-%d')
                return date_obj.strftime('%d %b %Y')
            else:
                return self.end_date.strftime('%d %b %Y')
        except:
            return self.end_date

    def get_formatted_checkin_time(self):
        """Get formatted check-in time in 12-hour format"""
        if not self.checkin_time:
            return 'Not set'
        try:
            from datetime import datetime, time
            if isinstance(self.checkin_time, str):
                time_obj = datetime.strptime(self.checkin_time, '%H:%M').time()
                return time_obj.strftime('%I:%M %p')
            elif isinstance(self.checkin_time, time):
                return self.checkin_time.strftime('%I:%M %p')
            else:
                return str(self.checkin_time)
        except:
            return str(self.checkin_time) if self.checkin_time else 'Not set'

    def get_formatted_checkout_time(self):
        """Get formatted check-out time in 12-hour format"""
        if not self.checkout_time:
            return 'Not set'
        try:
            from datetime import datetime, time
            if isinstance(self.checkout_time, str):
                time_obj = datetime.strptime(self.checkout_time, '%H:%M').time()
                return time_obj.strftime('%I:%M %p')
            elif isinstance(self.checkout_time, time):
                return self.checkout_time.strftime('%I:%M %p')
            else:
                return str(self.checkout_time)
        except:
            return str(self.checkout_time) if self.checkout_time else 'Not set'

    def get_formatted_timing_display(self):
        """Get formatted timing display for backward compatibility and display"""
        checkin = self.get_formatted_checkin_time()
        checkout = self.get_formatted_checkout_time()
        
        if checkin != 'Not set' and checkout != 'Not set':
            return f"{checkin} - {checkout}"
        elif self.timing:
            return self.timing  # Fallback to old timing field
        else:
            return 'Timing not set'

    def get_student_count(self):
        """Get count of active students in this batch"""
        from models.student_model import Student
        return Student.query.filter_by(batch_id=self.id, is_deleted=0).count()

    def get_trainer_count(self):
        """Get count of active trainers assigned to this batch"""
        from models.batch_trainer_assignment_model import BatchTrainerAssignment
        return BatchTrainerAssignment.query.filter_by(batch_id=self.id, is_active=1).count()

    def get_attendance_rate(self):
        """Get overall attendance rate for this batch"""
        from models.student_attendance_model import StudentAttendance
        stats = StudentAttendance.get_attendance_stats(self.id)
        return round(stats.get('attendance_rate', 0), 2)

    def get_active_trainers(self):
        """Get list of active trainers for this batch"""
        from models.batch_trainer_assignment_model import BatchTrainerAssignment
        from models.user_model import User
        assignments = BatchTrainerAssignment.query.filter_by(batch_id=self.id, is_active=1).all()
        trainer_ids = [assignment.trainer_id for assignment in assignments]
        return User.query.filter(User.id.in_(trainer_ids)).all()

    def get_students(self):
        """Get list of active students in this batch"""
        from models.student_model import Student
        return Student.query.filter_by(batch_id=self.id, is_deleted=0).all()

    def get_progress_percentage(self):
        """Calculate batch progress based on start and end dates"""
        if not self.start_date or not self.end_date:
            return 0
        
        try:
            from datetime import datetime
            start = datetime.strptime(self.start_date, '%Y-%m-%d')
            end = datetime.strptime(self.end_date, '%Y-%m-%d')
            today = datetime.now()
            
            if today < start:
                return 0
            elif today > end:
                return 100
            else:
                total_days = (end - start).days
                elapsed_days = (today - start).days
                return round((elapsed_days / total_days) * 100, 1) if total_days > 0 else 0
        except:
            return 0

    @property
    def is_active(self):
        """Check if batch is currently active"""
        return self.status == 'Active' and self.is_deleted == 0

    @property 
    def is_completed(self):
        """Check if batch is completed"""
        return self.status == 'Completed'
    
    @property
    def is_archived(self):
        """Check if batch is archived"""
        return self.status == 'Archived'
    
    @property
    def is_suspended(self):
        """Check if batch is suspended"""
        return self.status == 'Suspended'
    
    def can_be_completed(self):
        """Check if batch can be marked as completed"""
        return self.status == 'Active'
    
    def can_be_archived(self):
        """Check if batch can be archived"""
        return self.status == 'Completed'
    
    def can_be_suspended(self):
        """Check if batch can be suspended"""
        return self.status == 'Active'
    
    def can_be_reactivated(self):
        """Check if batch can be reactivated"""
        return self.status == 'Suspended'
    
    def can_be_cancelled(self):
        """Check if batch can be cancelled"""
        return self.status in ['Active', 'Suspended']
    
    def complete_batch(self, user_id=None):
        """Mark batch as completed"""
        if self.can_be_completed():
            self.status = 'Completed'
            self.completion_date = datetime.now().strftime('%Y-%m-%d')
            return True
        return False
    
    def archive_batch(self, user_id=None):
        """Archive the batch"""
        if self.can_be_archived():
            self.status = 'Archived'
            self.archived_at = datetime.now(timezone.utc)
            self.archived_by = user_id
            return True
        return False
    
    def suspend_batch(self, user_id=None, reason=None, notes=None, expected_resume_date=None):
        """Suspend the batch with reason tracking"""
        if self.can_be_suspended():
            self.status = 'Suspended'
            self.suspended_at = datetime.now(timezone.utc)
            self.suspended_by = user_id
            self.suspension_reason = reason
            self.suspension_notes = notes
            
            # Handle expected_resume_date conversion
            if expected_resume_date:
                if isinstance(expected_resume_date, str):
                    try:
                        from datetime import datetime as dt
                        self.expected_resume_date = dt.strptime(expected_resume_date, '%Y-%m-%d').date()
                    except ValueError:
                        self.expected_resume_date = None
                else:
                    self.expected_resume_date = expected_resume_date
            
            return True
        return False
    
    def reactivate_batch(self, user_id=None):
        """Reactivate suspended batch"""
        if self.can_be_reactivated():
            self.status = 'Active'
            return True
        return False
    
    def cancel_batch(self, user_id=None, reason=None, notes=None):
        """Cancel the batch permanently"""
        if self.can_be_cancelled():
            self.status = 'Cancelled'
            self.cancelled_at = datetime.now(timezone.utc)
            self.cancelled_by = user_id
            self.cancellation_reason = reason
            self.cancellation_notes = notes
            return True
        return False
