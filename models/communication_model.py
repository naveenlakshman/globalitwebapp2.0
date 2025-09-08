# Communication and Analytics Models
# Global IT Education Management System - Phase 3 Support and Analytics Models

from init_db import db
from datetime import datetime, timedelta
import json

class StudentNotification(db.Model):
    """Student Notification Model - System notifications for students"""
    __tablename__ = 'student_notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'), nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)  # announcement, assignment, grade, system
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text)
    action_url = db.Column(db.String(500))  # optional link for action
    is_read = db.Column(db.Boolean, default=False)
    priority = db.Column(db.String(20), default='normal')  # low, normal, high, urgent
    expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime)
    
    # Relationships
    student = db.relationship('Student', backref='notifications')
    
    def __repr__(self):
        return f'<StudentNotification {self.title}>'
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()
            db.session.commit()
    
    def is_expired(self):
        """Check if notification is expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def get_priority_color(self):
        """Get color class for priority"""
        priority_colors = {
            'low': 'text-muted',
            'normal': 'text-info',
            'high': 'text-warning',
            'urgent': 'text-danger'
        }
        return priority_colors.get(self.priority, 'text-info')
    
    def get_type_icon(self):
        """Get icon for notification type"""
        type_icons = {
            'announcement': 'fas fa-bullhorn',
            'assignment': 'fas fa-tasks',
            'grade': 'fas fa-star',
            'system': 'fas fa-cog',
            'course': 'fas fa-book',
            'payment': 'fas fa-credit-card',
            'attendance': 'fas fa-calendar-check'
        }
        return type_icons.get(self.notification_type, 'fas fa-bell')
    
    @staticmethod
    def create_notification(student_id, notification_type, title, message, 
                          action_url=None, priority='normal', expires_in_days=30):
        """Create a new notification for student"""
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days) if expires_in_days else None
        
        notification = StudentNotification(
            student_id=student_id,
            notification_type=notification_type,
            title=title,
            message=message,
            action_url=action_url,
            priority=priority,
            expires_at=expires_at
        )
        
        db.session.add(notification)
        db.session.commit()
        return notification

class StudentSupportTicket(db.Model):
    """Student Support Ticket Model - Help desk tickets from students"""
    __tablename__ = 'student_support_tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(50), unique=True)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'), nullable=False)
    category = db.Column(db.String(50), default='general')  # technical, academic, financial, general
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='open')  # open, in_progress, resolved, closed
    priority = db.Column(db.String(20), default='normal')  # low, normal, high, urgent
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    
    # Relationships
    student = db.relationship('Student', backref='support_tickets')
    assigned_user = db.relationship('User', foreign_keys=[assigned_to])
    
    def __repr__(self):
        return f'<StudentSupportTicket {self.ticket_number}>'
    
    def generate_ticket_number(self):
        """Generate unique ticket number"""
        import random
        import string
        
        # Format: SPT-YYYYMMDD-XXXX (SPT = Student Portal Ticket)
        date_part = datetime.utcnow().strftime('%Y%m%d')
        random_part = ''.join(random.choices(string.digits, k=4))
        self.ticket_number = f"SPT-{date_part}-{random_part}"
        
        # Ensure uniqueness
        while StudentSupportTicket.query.filter_by(ticket_number=self.ticket_number).first():
            random_part = ''.join(random.choices(string.digits, k=4))
            self.ticket_number = f"SPT-{date_part}-{random_part}"
    
    def get_status_color(self):
        """Get color class for status"""
        status_colors = {
            'open': 'text-primary',
            'in_progress': 'text-warning',
            'resolved': 'text-success',
            'closed': 'text-secondary'
        }
        return status_colors.get(self.status, 'text-primary')
    
    def get_priority_color(self):
        """Get color class for priority"""
        priority_colors = {
            'low': 'text-muted',
            'normal': 'text-info',
            'high': 'text-warning',
            'urgent': 'text-danger'
        }
        return priority_colors.get(self.priority, 'text-info')
    
    def get_category_icon(self):
        """Get icon for category"""
        category_icons = {
            'technical': 'fas fa-cogs',
            'academic': 'fas fa-graduation-cap',
            'financial': 'fas fa-credit-card',
            'general': 'fas fa-question-circle'
        }
        return category_icons.get(self.category, 'fas fa-ticket-alt')
    
    def close_ticket(self, resolved_by=None):
        """Close the ticket"""
        self.status = 'resolved'
        self.resolved_at = datetime.utcnow()
        if resolved_by:
            self.assigned_to = resolved_by
        db.session.commit()

class StudentPortalSession(db.Model):
    """Student Portal Session Model - Track student portal usage"""
    __tablename__ = 'student_portal_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'), nullable=False)
    session_token = db.Column(db.String(200))
    login_time = db.Column(db.DateTime, default=datetime.utcnow)
    logout_time = db.Column(db.DateTime)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    device_type = db.Column(db.String(50))  # desktop, mobile, tablet
    session_duration = db.Column(db.Integer, default=0)  # in minutes
    pages_visited = db.Column(db.Integer, default=0)
    actions_performed = db.Column(db.Integer, default=0)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    student = db.relationship('Student', backref='portal_sessions')
    
    def __repr__(self):
        return f'<StudentPortalSession {self.student_id}-{self.login_time}>'
    
    def end_session(self):
        """End the session and calculate duration"""
        self.logout_time = datetime.utcnow()
        if self.login_time:
            duration = self.logout_time - self.login_time
            self.session_duration = int(duration.total_seconds() / 60)  # in minutes
        db.session.commit()
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.utcnow()
        db.session.commit()
    
    def is_active(self, timeout_minutes=30):
        """Check if session is still active"""
        if not self.last_activity:
            return False
        
        timeout_delta = timedelta(minutes=timeout_minutes)
        return datetime.utcnow() - self.last_activity < timeout_delta

class StudentLearningAnalytics(db.Model):
    """Student Learning Analytics Model - Daily learning statistics"""
    __tablename__ = 'student_learning_analytics'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    total_study_time = db.Column(db.Integer, default=0)  # minutes studied
    modules_accessed = db.Column(db.Integer, default=0)
    videos_watched = db.Column(db.Integer, default=0)
    materials_downloaded = db.Column(db.Integer, default=0)
    quizzes_attempted = db.Column(db.Integer, default=0)
    assignments_submitted = db.Column(db.Integer, default=0)
    forum_posts = db.Column(db.Integer, default=0)
    login_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    student = db.relationship('Student', backref='learning_analytics')
    course = db.relationship('Course', backref='learning_analytics')
    
    __table_args__ = (db.UniqueConstraint('student_id', 'course_id', 'date'),)
    
    def __repr__(self):
        return f'<StudentLearningAnalytics {self.student_id}-{self.date}>'
    
    @staticmethod
    def get_or_create_today(student_id, course_id):
        """Get or create today's analytics record"""
        today = datetime.utcnow().date()
        analytics = StudentLearningAnalytics.query.filter_by(
            student_id=student_id,
            course_id=course_id,
            date=today
        ).first()
        
        if not analytics:
            analytics = StudentLearningAnalytics(
                student_id=student_id,
                course_id=course_id,
                date=today
            )
            db.session.add(analytics)
            db.session.commit()
        
        return analytics
    
    def add_study_time(self, minutes):
        """Add study time to today's record"""
        self.total_study_time += minutes
        db.session.commit()
    
    def increment_module_access(self):
        """Increment modules accessed count"""
        self.modules_accessed += 1
        db.session.commit()
    
    def increment_video_watched(self):
        """Increment videos watched count"""
        self.videos_watched += 1
        db.session.commit()
    
    def increment_material_download(self):
        """Increment materials downloaded count"""
        self.materials_downloaded += 1
        db.session.commit()
    
    def increment_quiz_attempt(self):
        """Increment quizzes attempted count"""
        self.quizzes_attempted += 1
        db.session.commit()
    
    def increment_assignment_submission(self):
        """Increment assignments submitted count"""
        self.assignments_submitted += 1
        db.session.commit()
    
    def increment_login(self):
        """Increment login count"""
        self.login_count += 1
        db.session.commit()
    
    @staticmethod
    def get_weekly_stats(student_id, course_id):
        """Get weekly learning statistics"""
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=7)
        
        weekly_data = StudentLearningAnalytics.query.filter(
            StudentLearningAnalytics.student_id == student_id,
            StudentLearningAnalytics.course_id == course_id,
            StudentLearningAnalytics.date.between(start_date, end_date)
        ).all()
        
        total_study_time = sum(record.total_study_time for record in weekly_data)
        total_modules = sum(record.modules_accessed for record in weekly_data)
        total_videos = sum(record.videos_watched for record in weekly_data)
        total_logins = sum(record.login_count for record in weekly_data)
        
        return {
            'total_study_time': total_study_time,
            'total_modules': total_modules,
            'total_videos': total_videos,
            'total_logins': total_logins,
            'average_daily_time': total_study_time / 7,
            'days_active': len(weekly_data)
        }
    
    @staticmethod
    def get_monthly_stats(student_id, course_id):
        """Get monthly learning statistics"""
        end_date = datetime.utcnow().date()
        start_date = end_date.replace(day=1)  # First day of current month
        
        monthly_data = StudentLearningAnalytics.query.filter(
            StudentLearningAnalytics.student_id == student_id,
            StudentLearningAnalytics.course_id == course_id,
            StudentLearningAnalytics.date.between(start_date, end_date)
        ).all()
        
        total_study_time = sum(record.total_study_time for record in monthly_data)
        total_modules = sum(record.modules_accessed for record in monthly_data)
        total_videos = sum(record.videos_watched for record in monthly_data)
        total_materials = sum(record.materials_downloaded for record in monthly_data)
        total_quizzes = sum(record.quizzes_attempted for record in monthly_data)
        total_assignments = sum(record.assignments_submitted for record in monthly_data)
        
        days_in_month = (end_date - start_date).days + 1
        
        return {
            'total_study_time': total_study_time,
            'total_modules': total_modules,
            'total_videos': total_videos,
            'total_materials': total_materials,
            'total_quizzes': total_quizzes,
            'total_assignments': total_assignments,
            'average_daily_time': total_study_time / days_in_month,
            'days_active': len(monthly_data),
            'activity_percentage': (len(monthly_data) / days_in_month) * 100
        }
