# LMS Models - Learning Management System (this model is for course delivery)
# Global IT Education Management System - Internal LMS Models
# Business Logic: Course → Module → Section → (Video + PDF Material)
# Example: CCOM Course → 5 Modules → 6 Sections each → 1 Video + 1 PDF per Section
# Security Features: DRM protection, watermarking, access logging, anti-piracy measures

from init_db import db
from datetime import datetime, timedelta
from utils.timezone_helper import TimezoneAwareMixin, format_datetime_indian, format_date_indian, get_current_ist_datetime
import json
import hashlib

class CourseModule(db.Model, TimezoneAwareMixin):
    """Course Module Model - Represents major learning modules within courses"""
    __tablename__ = 'course_modules'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    module_name = db.Column(db.String(200), nullable=False)  # e.g., "Introduction to Office Management"
    module_description = db.Column(db.Text)
    module_order = db.Column(db.Integer, default=0)
    estimated_duration_hours = db.Column(db.Integer, default=0)  # Total estimated hours for module
    is_mandatory = db.Column(db.Boolean, default=True)
    # Removed publishing workflow - all modules are active by default
    is_published = db.Column(db.Boolean, default=True)  # Always True for admin-created content
    prerequisites = db.Column(db.Text)  # JSON string of prerequisite module IDs
    learning_objectives = db.Column(db.Text)  # Learning goals for this module
    created_at = db.Column(db.DateTime, default=get_current_ist_datetime)
    updated_at = db.Column(db.DateTime, default=get_current_ist_datetime, onupdate=get_current_ist_datetime)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    course = db.relationship('Course', backref='modules')
    sections = db.relationship('CourseSection', backref='module', cascade='all, delete-orphan', order_by='CourseSection.section_order')
    student_progress = db.relationship('StudentModuleProgress', backref='module', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<CourseModule {self.module_name}>'
    
    def get_progress_for_student(self, student_id):
        """Get progress for specific student"""
        progress = StudentModuleProgress.query.filter_by(
            student_id=student_id, 
            module_id=self.id
        ).first()
        return progress.progress_percentage if progress else 0
    
    def is_completed_by_student(self, student_id):
        """Check if module is completed by student"""
        progress = StudentModuleProgress.query.filter_by(
            student_id=student_id, 
            module_id=self.id
        ).first()
        return progress.is_completed if progress else False
    
    def get_total_sections(self):
        """Get total number of sections in this module"""
        return len(self.sections)
    
    def get_completion_percentage(self, student_id):
        """Calculate module completion based on section completion"""
        if not self.sections:
            return 0
        
        completed_sections = 0
        for section in self.sections:
            if section.is_completed_by_student(student_id):
                completed_sections += 1
        
        return int((completed_sections / len(self.sections)) * 100)
    
    def is_ready_for_module_assessments(self, student_id):
        """Check if student has completed all sections and is ready for module-level quiz/assignments"""
        if not self.sections:
            return False
        
        # Check if all mandatory sections are completed
        for section in self.sections:
            if section.is_mandatory and not section.is_completed_by_student(student_id):
                return False
        
        return True
    
    def get_module_quizzes(self):
        """Get module-level quizzes (business logic: quizzes after completing all sections)"""
        from models.lms_content_management_model import Quiz
        return Quiz.query.filter_by(
            module_id=self.id, 
            quiz_placement='module'
        ).order_by(Quiz.placement_order).all()
    
    def get_module_assignments(self):
        """Get module-level assignments (business logic: assignments after completing all sections)"""
        from models.lms_content_management_model import AssignmentCreator
        return AssignmentCreator.query.filter_by(
            module_id=self.id, 
            assignment_placement='module'
        ).order_by(AssignmentCreator.placement_order).all()
    
    def get_created_at_formatted(self):
        """Get formatted creation date in IST"""
        return format_datetime_indian(self.created_at, include_time=True, include_seconds=False)
    
    def get_updated_at_formatted(self):
        """Get formatted update date in IST"""
        return format_datetime_indian(self.updated_at, include_time=True, include_seconds=False)

class CourseSection(db.Model, TimezoneAwareMixin):
    """Course Section Model - Represents chapters/sections within modules (Business Logic Layer)"""
    __tablename__ = 'course_sections'
    
    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey('course_modules.id'), nullable=False)
    section_name = db.Column(db.String(200), nullable=False)  # e.g., "Chapter 1: Introduction"
    section_description = db.Column(db.Text)
    section_order = db.Column(db.Integer, default=0)
    estimated_duration_minutes = db.Column(db.Integer, default=30)
    is_mandatory = db.Column(db.Boolean, default=True)
    # Removed publishing workflow - all sections are active by default
    is_published = db.Column(db.Boolean, default=True)  # Always True for admin-created content
    section_type = db.Column(db.String(50), default='content')  # content, quiz, assignment, project
    learning_outcomes = db.Column(db.Text)  # What student should learn from this section
    created_at = db.Column(db.DateTime, default=get_current_ist_datetime)
    updated_at = db.Column(db.DateTime, default=get_current_ist_datetime, onupdate=get_current_ist_datetime)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships - Each section has 1 video + 1 PDF (your business requirement)
    videos = db.relationship('CourseVideo', backref='section', cascade='all, delete-orphan')
    materials = db.relationship('CourseMaterial', backref='section', cascade='all, delete-orphan')
    student_progress = db.relationship('StudentSectionProgress', backref='section', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<CourseSection {self.section_name}>'
    
    def get_video(self):
        """Get the primary video for this section"""
        return self.videos[0] if self.videos else None
    
    def get_material(self):
        """Get the primary PDF material for this section"""
        return self.materials[0] if self.materials else None
    
    def has_complete_content(self):
        """Check if section has both video and PDF as per business requirement"""
        has_video = len(self.videos) > 0
        has_pdf = len([m for m in self.materials if m.material_type.lower() == 'pdf']) > 0
        return has_video and has_pdf
    
    def get_progress_for_student(self, student_id):
        """Get progress for specific student"""
        progress = StudentSectionProgress.query.filter_by(
            student_id=student_id, 
            section_id=self.id
        ).first()
        return progress.progress_percentage if progress else 0
    
    def is_completed_by_student(self, student_id):
        """Check if section is completed by student"""
        progress = StudentSectionProgress.query.filter_by(
            student_id=student_id, 
            section_id=self.id
        ).first()
        return progress.is_completed if progress else False
    
    def get_created_at_formatted(self):
        """Get formatted creation date in IST"""
        return format_datetime_indian(self.created_at, include_time=True, include_seconds=False)
    
    def get_updated_at_formatted(self):
        """Get formatted update date in IST"""
        return format_datetime_indian(self.updated_at, include_time=True, include_seconds=False)

class CourseVideo(db.Model, TimezoneAwareMixin):
    """Course Video Model - Represents video content in sections"""
    __tablename__ = 'course_videos'
    
    id = db.Column(db.Integer, primary_key=True)
    # Backward compatibility: keep module_id for existing data
    module_id = db.Column(db.Integer, db.ForeignKey('course_modules.id'), nullable=True)  # Legacy relationship
    section_id = db.Column(db.Integer, db.ForeignKey('course_sections.id'), nullable=True)  # New relationship
    video_title = db.Column(db.String(200), nullable=False)
    video_url = db.Column(db.String(500), nullable=False)
    video_duration = db.Column(db.Integer, default=0)  # in seconds
    video_description = db.Column(db.Text)
    thumbnail_url = db.Column(db.String(500))
    video_type = db.Column(db.String(50), default='youtube')  # youtube, mp4, local, streaming
    video_id = db.Column(db.String(100))  # YouTube ID or file identifier
    file_size = db.Column(db.Integer, default=0)
    quality = db.Column(db.String(20), default='720p')  # 480p, 720p, 1080p
    is_active = db.Column(db.Boolean, default=True)
    upload_date = db.Column(db.DateTime, default=get_current_ist_datetime)
    
    # Enhanced Security Features
    is_downloadable = db.Column(db.Boolean, default=False)  # Block all downloads
    streaming_only = db.Column(db.Boolean, default=True)  # Force streaming mode
    drm_protected = db.Column(db.Boolean, default=True)  # DRM protection enabled
    watermark_enabled = db.Column(db.Boolean, default=True)  # Show student watermark
    copy_protection = db.Column(db.Boolean, default=True)  # Disable right-click, copy
    session_token = db.Column(db.String(255))  # Session-based access token
    max_concurrent_viewers = db.Column(db.Integer, default=1)  # Limit concurrent access
    
    # Video Analytics
    view_count = db.Column(db.Integer, default=0)
    average_completion_rate = db.Column(db.Float, default=0.0)
    
    # Relationships
    student_progress = db.relationship('StudentVideoProgress', backref='video', cascade='all, delete-orphan')
    access_logs = db.relationship('VideoAccessLog', backref='video', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<CourseVideo {self.video_title}>'
    
    def get_watch_progress_for_student(self, student_id):
        """Get video watch progress for specific student"""
        progress = StudentVideoProgress.query.filter_by(
            student_id=student_id, 
            video_id=self.id
        ).first()
        return progress if progress else None
    
    def format_duration(self):
        """Format duration in HH:MM:SS"""
        if not self.video_duration:
            return "00:00"
        
        hours = self.video_duration // 3600
        minutes = (self.video_duration % 3600) // 60
        seconds = self.video_duration % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
    
    def get_secure_embed_url(self, student_id, ip_address=None):
        """Get secure embeddable URL with session token for video player"""
        import uuid
        import hashlib
        from datetime import timedelta
        
        # Generate session token
        token_data = f"{student_id}:{self.id}:{get_current_ist_datetime().timestamp()}"
        session_token = hashlib.sha256(token_data.encode()).hexdigest()[:32]
        
        # Log access attempt
        self.log_access(student_id, ip_address, 'embed_request')
        
        if self.video_type == 'youtube' and self.video_id:
            # YouTube with additional security parameters
            return f"https://www.youtube.com/embed/{self.video_id}?autoplay=1&controls=1&disablekb=1&fs=0&modestbranding=1&rel=0&showinfo=0&iv_load_policy=3"
        elif self.video_type == 'streaming':
            # Custom secure streaming URL
            return f"/secure-video/{self.id}/{session_token}"
        
        return None  # No direct file access allowed
    
    def can_student_access(self, student_id):
        """Check if student can access this video"""
        from datetime import datetime, timedelta
        
        # Check concurrent viewers limit
        active_sessions = VideoAccessLog.query.filter(
            VideoAccessLog.video_id == self.id,
            VideoAccessLog.session_end_time.is_(None),
            VideoAccessLog.created_at >= get_current_ist_datetime() - timedelta(hours=2)
        ).count()
        
        if active_sessions >= self.max_concurrent_viewers:
            return False, "Maximum concurrent viewers reached"
        
        # Check if student is enrolled in course
        section = db.session.get(CourseSection, self.section_id)
        if section and section.module:
            # Add enrollment check logic here
            pass
        
        return True, "Access granted"
    
    def log_access(self, student_id, ip_address=None, action='view'):
        """Log video access for security tracking"""
        log = VideoAccessLog(
            video_id=self.id,
            student_id=student_id,
            ip_address=ip_address,
            action=action,
            created_at=get_current_ist_datetime()
        )
        db.session.add(log)
        db.session.commit()
    
    def increment_view_count(self):
        """Increment view count"""
        self.view_count += 1
        db.session.commit()
    
    def is_download_blocked(self):
        """Check if video download is blocked (always True for security)"""
        return not self.is_downloadable  # Always block downloads
    
    def get_security_config(self):
        """Get video security configuration for frontend"""
        return {
            'downloadable': False,  # Never allow downloads
            'copy_protection': self.copy_protection,
            'watermark': self.watermark_enabled,
            'streaming_only': self.streaming_only,
            'drm_protected': self.drm_protected,
            'right_click_disabled': True,
            'developer_tools_blocked': True,
            'screenshot_blocked': True
        }
    
    def get_upload_date_formatted(self):
        """Get formatted upload date in IST"""
        return format_datetime_indian(self.upload_date, include_time=True, include_seconds=False)

class CourseMaterial(db.Model, TimezoneAwareMixin):
    """Course Material Model - Represents protected downloadable materials (PDF, docs) in sections"""
    __tablename__ = 'course_materials'
    
    id = db.Column(db.Integer, primary_key=True)
    # Backward compatibility: keep module_id for existing data
    module_id = db.Column(db.Integer, db.ForeignKey('course_modules.id'), nullable=True)  # Legacy relationship
    section_id = db.Column(db.Integer, db.ForeignKey('course_sections.id'), nullable=True)  # New relationship
    material_name = db.Column(db.String(200), nullable=False)
    material_type = db.Column(db.String(50), nullable=False)  # pdf, doc, ppt, image, zip
    file_url = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(255))  # Store original uploaded filename
    file_size = db.Column(db.Integer, default=0)
    download_count = db.Column(db.Integer, default=0)
    is_downloadable = db.Column(db.Boolean, default=True)  # Can be downloaded (with protection)
    is_active = db.Column(db.Boolean, default=True)
    upload_date = db.Column(db.DateTime, default=get_current_ist_datetime)
    description = db.Column(db.Text)
    
    # Enhanced Content Protection Features
    copy_protection = db.Column(db.Boolean, default=True)  # Disable text selection/copy
    print_protection = db.Column(db.Boolean, default=True)  # Disable printing
    watermark_enabled = db.Column(db.Boolean, default=True)  # Add student watermark
    view_only_mode = db.Column(db.Boolean, default=False)  # View only, no download
    session_timeout = db.Column(db.Integer, default=3600)  # Session timeout in seconds
    max_view_duration = db.Column(db.Integer, default=7200)  # Max view time per session
    
    # File Security
    access_level = db.Column(db.String(20), default='student')  # student, premium, admin
    requires_completion = db.Column(db.Boolean, default=False)  # Requires video completion to access
    encryption_enabled = db.Column(db.Boolean, default=True)  # File encryption
    secure_viewer_only = db.Column(db.Boolean, default=True)  # Must use secure viewer
    
    # Relationships
    download_logs = db.relationship('MaterialDownloadLog', backref='material', cascade='all, delete-orphan')
    access_logs = db.relationship('MaterialAccessLog', backref='material', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<CourseMaterial {self.material_name}>'
    
    def format_file_size(self):
        """Format file size in human readable format"""
        if not self.file_size:
            return "Unknown"
        
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def can_student_access(self, student_id, action='view'):
        """Check if student can access this material"""
        if not self.is_active:
            return False, "Material not available"
        
        if self.requires_completion:
            # Check if student completed the video in same section
            video = self.section.get_video()
            if video:
                progress = video.get_watch_progress_for_student(student_id)
                if not (progress and progress.is_completed):
                    return False, "Complete the video first to access material"
        
        # Check download vs view permissions
        if action == 'download' and self.view_only_mode:
            return False, "Material is view-only, download not allowed"
        
        if action == 'download' and not self.is_downloadable:
            return False, "Download not permitted for this material"
        
        return True, "Access granted"
    
    def get_secure_access_url(self, student_id, action='view', ip_address=None):
        """Generate secure access URL with session token"""
        import uuid
        import hashlib
        
        # Generate session token
        token_data = f"{student_id}:{self.id}:{action}:{get_current_ist_datetime().timestamp()}"
        session_token = hashlib.sha256(token_data.encode()).hexdigest()[:32]
        
        # Log access attempt
        self.log_access(student_id, action, ip_address)
        
        if action == 'view':
            return f"/secure-viewer/{self.id}/{session_token}"
        elif action == 'download' and self.is_downloadable and not self.view_only_mode:
            return f"/secure-download/{self.id}/{session_token}"
        
        return None
    
    def log_access(self, student_id, action='view', ip_address=None):
        """Log material access for security tracking"""
        log = MaterialAccessLog(
            material_id=self.id,
            student_id=student_id,
            action=action,
            ip_address=ip_address,
            created_at=get_current_ist_datetime()
        )
        db.session.add(log)
        db.session.commit()
    
    def increment_download_count(self, student_id=None):
        """Increment download count and log"""
        self.download_count += 1
        
        if student_id:
            # Log the download
            log = MaterialDownloadLog(
                material_id=self.id,
                student_id=student_id,
                download_timestamp=get_current_ist_datetime()
            )
            db.session.add(log)
        
        db.session.commit()
    
    def get_security_config(self):
        """Get material security configuration for frontend"""
        return {
            'copy_protection': self.copy_protection,
            'print_protection': self.print_protection,
            'watermark': self.watermark_enabled,
            'view_only': self.view_only_mode,
            'downloadable': self.is_downloadable and not self.view_only_mode,
            'secure_viewer_required': self.secure_viewer_only,
            'session_timeout': self.session_timeout,
            'right_click_disabled': True,
            'text_selection_disabled': self.copy_protection,
            'developer_tools_blocked': True,
            'screenshot_blocked': True
        }
    
    def get_watermark_text(self, student_id):
        """Generate watermark text for student"""
        timestamp = format_datetime_indian(get_current_ist_datetime(), include_time=True, include_seconds=False)
        return f"Licensed to: {student_id} | Access Time: {timestamp} | Global IT Education"
    
    def get_upload_date_formatted(self):
        """Get formatted upload date in IST"""
        return format_datetime_indian(self.upload_date, include_time=True, include_seconds=False)

class MaterialDownloadLog(db.Model, TimezoneAwareMixin):
    """Material Download Log - Track who downloaded what and when"""
    __tablename__ = 'material_download_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey('course_materials.id'), nullable=False)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'), nullable=False)
    download_timestamp = db.Column(db.DateTime, default=get_current_ist_datetime)
    ip_address = db.Column(db.String(45))  # Support IPv6
    user_agent = db.Column(db.String(500))
    file_hash = db.Column(db.String(64))  # SHA256 hash of downloaded file
    
    # Relationships
    student = db.relationship('Student', backref='download_logs')
    
    def __repr__(self):
        return f'<MaterialDownloadLog {self.student_id}-{self.material_id}>'

class MaterialAccessLog(db.Model, TimezoneAwareMixin):
    """Material Access Log - Track all material access attempts"""
    __tablename__ = 'material_access_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey('course_materials.id'), nullable=False)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # view, download, copy_attempt, print_attempt
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    session_token = db.Column(db.String(255))
    success = db.Column(db.Boolean, default=True)
    failure_reason = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=get_current_ist_datetime)
    
    # Relationships
    student = db.relationship('Student', backref='material_access_logs')
    
    def __repr__(self):
        return f'<MaterialAccessLog {self.student_id}-{self.action}>'

class VideoAccessLog(db.Model, TimezoneAwareMixin):
    """Video Access Log - Track all video access attempts and sessions"""
    __tablename__ = 'video_access_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey('course_videos.id'), nullable=False)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # view, embed_request, download_attempt, copy_attempt
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    session_token = db.Column(db.String(255))
    session_start_time = db.Column(db.DateTime, default=get_current_ist_datetime)
    session_end_time = db.Column(db.DateTime)
    watch_duration = db.Column(db.Integer, default=0)  # in seconds
    success = db.Column(db.Boolean, default=True)
    failure_reason = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=get_current_ist_datetime)
    
    # Security flags
    suspicious_activity = db.Column(db.Boolean, default=False)
    multiple_tabs_detected = db.Column(db.Boolean, default=False)
    screen_recording_detected = db.Column(db.Boolean, default=False)
    
    # Relationships
    student = db.relationship('Student', backref='video_access_logs')
    
    def __repr__(self):
        return f'<VideoAccessLog {self.student_id}-{self.action}>'
    
    def end_session(self, watch_duration=0):
        """End video watching session"""
        self.session_end_time = get_current_ist_datetime()
        self.watch_duration = watch_duration
        db.session.commit()

class SecurityViolationLog(db.Model, TimezoneAwareMixin):
    """Security Violation Log - Track all security violation attempts"""
    __tablename__ = 'security_violation_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'), nullable=False)
    violation_type = db.Column(db.String(100), nullable=False)  # copy_attempt, download_attempt, screenshot, dev_tools, etc.
    resource_type = db.Column(db.String(50))  # video, material, page
    resource_id = db.Column(db.Integer)  # video_id or material_id
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    violation_details = db.Column(db.Text)  # Additional details about the violation
    severity = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    action_taken = db.Column(db.String(100))  # warning, session_terminated, account_suspended
    created_at = db.Column(db.DateTime, default=get_current_ist_datetime)
    
    # Relationships
    student = db.relationship('Student', backref='security_violations')
    
    def __repr__(self):
        return f'<SecurityViolationLog {self.student_id}-{self.violation_type}>'
    
    @staticmethod
    def log_violation(student_id, violation_type, resource_type=None, resource_id=None, 
                     ip_address=None, user_agent=None, details=None, severity='medium'):
        """Log a security violation"""
        violation = SecurityViolationLog(
            student_id=student_id,
            violation_type=violation_type,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            violation_details=details,
            severity=severity
        )
        db.session.add(violation)
        db.session.commit()
        return violation

# Additional LMS Models for Comprehensive Functionality

class CourseAnnouncement(db.Model, TimezoneAwareMixin):
    """Course Announcements - For course-specific notifications"""
    __tablename__ = 'course_announcements'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), default='normal')  # low, normal, high, urgent
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=get_current_ist_datetime)
    expires_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    course = db.relationship('Course', backref='announcements')
    
    def __repr__(self):
        return f'<CourseAnnouncement {self.title}>'
    
    def is_active(self):
        """Check if announcement is still active"""
        if self.expires_at:
            return get_current_ist_datetime() <= self.expires_at
        return True

class StudentAssignment(db.Model, TimezoneAwareMixin):
    """Student Assignments - For section-based assignments"""
    __tablename__ = 'student_assignments'
    
    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey('course_sections.id'), nullable=False)
    assignment_title = db.Column(db.String(200), nullable=False)
    assignment_description = db.Column(db.Text)
    assignment_type = db.Column(db.String(50), default='project')  # quiz, project, essay, practical
    max_score = db.Column(db.Integer, default=100)
    due_date = db.Column(db.DateTime)
    submission_format = db.Column(db.String(100))  # pdf, doc, video, url, text
    is_mandatory = db.Column(db.Boolean, default=True)
    is_published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=get_current_ist_datetime)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    section = db.relationship('CourseSection', backref='assignments')
    submissions = db.relationship('AssignmentSubmission', backref='assignment', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<StudentAssignment {self.assignment_title}>'
    
    def is_overdue(self):
        """Check if assignment is overdue"""
        if self.due_date:
            return get_current_ist_datetime() > self.due_date
        return False
    
    def get_submission_by_student(self, student_id):
        """Get student's submission for this assignment"""
        return AssignmentSubmission.query.filter_by(
            assignment_id=self.id,
            student_id=student_id
        ).first()

class AssignmentSubmission(db.Model, TimezoneAwareMixin):
    """Assignment Submissions - Student assignment submissions"""
    __tablename__ = 'assignment_submissions'
    
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('student_assignments.id'), nullable=False)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'), nullable=False)
    submission_content = db.Column(db.Text)  # Text content or file description
    submission_url = db.Column(db.String(500))  # File URL or external link
    submitted_at = db.Column(db.DateTime, default=get_current_ist_datetime)
    status = db.Column(db.String(20), default='submitted')  # submitted, graded, returned
    score = db.Column(db.Integer)
    feedback = db.Column(db.Text)
    graded_at = db.Column(db.DateTime)
    graded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    student = db.relationship('Student', backref='assignment_submissions')
    
    __table_args__ = (db.UniqueConstraint('assignment_id', 'student_id'),)
    
    def __repr__(self):
        return f'<AssignmentSubmission {self.student_id}-{self.assignment_id}>'
    
    def is_graded(self):
        """Check if submission is graded"""
        return self.status == 'graded' and self.score is not None

class StudentNotes(db.Model, TimezoneAwareMixin):
    """Student Notes - Personal notes for sections"""
    __tablename__ = 'student_notes'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey('course_sections.id'), nullable=False)
    note_title = db.Column(db.String(200))
    note_content = db.Column(db.Text, nullable=False)
    is_private = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=get_current_ist_datetime)
    updated_at = db.Column(db.DateTime, default=get_current_ist_datetime, onupdate=get_current_ist_datetime)
    
    # Relationships
    student = db.relationship('Student', backref='notes')
    section = db.relationship('CourseSection', backref='student_notes')
    
    def __repr__(self):
        return f'<StudentNotes {self.student_id}-{self.section_id}>'

class LMSSettings(db.Model, TimezoneAwareMixin):
    """LMS Settings - System-wide LMS configuration"""
    __tablename__ = 'lms_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text)
    setting_type = db.Column(db.String(50), default='string')  # string, int, bool, json
    description = db.Column(db.Text)
    is_user_configurable = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=get_current_ist_datetime)
    updated_at = db.Column(db.DateTime, default=get_current_ist_datetime, onupdate=get_current_ist_datetime)
    
    def __repr__(self):
        return f'<LMSSettings {self.setting_key}>'
    
    @staticmethod
    def get_setting(key, default=None):
        """Get setting value by key"""
        setting = LMSSettings.query.filter_by(setting_key=key).first()
        if setting:
            if setting.setting_type == 'int':
                return int(setting.setting_value) if setting.setting_value else default
            elif setting.setting_type == 'bool':
                return setting.setting_value.lower() == 'true' if setting.setting_value else default
            elif setting.setting_type == 'json':
                return json.loads(setting.setting_value) if setting.setting_value else default
            return setting.setting_value or default
        return default
    
    @staticmethod
    def set_setting(key, value, setting_type='string', description=None):
        """Set or update setting"""
        setting = LMSSettings.query.filter_by(setting_key=key).first()
        if not setting:
            setting = LMSSettings(setting_key=key, setting_type=setting_type, description=description)
            db.session.add(setting)
        
        if setting_type == 'json':
            setting.setting_value = json.dumps(value)
        else:
            setting.setting_value = str(value)
        
        setting.setting_type = setting_type
        if description:
            setting.description = description
        
        db.session.commit()
        return setting
    
    @staticmethod
    def initialize_default_security_settings():
        """Initialize default security settings for LMS"""
        default_settings = [
            ('video_downloads_enabled', False, 'bool', 'Allow video downloads (always False for security)'),
            ('material_copy_protection', True, 'bool', 'Enable copy protection for materials'),
            ('video_watermark_enabled', True, 'bool', 'Show watermark on videos'),
            ('material_watermark_enabled', True, 'bool', 'Add watermark to materials'),
            ('max_concurrent_video_sessions', 1, 'int', 'Maximum concurrent video sessions per student'),
            ('session_timeout_minutes', 60, 'int', 'Session timeout in minutes'),
            ('security_logging_enabled', True, 'bool', 'Enable comprehensive security logging'),
            ('right_click_protection', True, 'bool', 'Disable right-click context menu'),
            ('developer_tools_detection', True, 'bool', 'Detect and block developer tools'),
            ('screenshot_protection', True, 'bool', 'Attempt to block screenshots'),
            ('video_drm_protection', True, 'bool', 'Enable DRM protection for videos'),
            ('material_print_protection', True, 'bool', 'Disable printing of materials'),
            ('automatic_violation_response', True, 'bool', 'Automatically respond to security violations'),
            ('violation_warning_threshold', 3, 'int', 'Number of violations before warning'),
            ('violation_suspension_threshold', 10, 'int', 'Number of violations before suspension'),
        ]
        
        for key, value, setting_type, description in default_settings:
            existing = LMSSettings.query.filter_by(setting_key=key).first()
            if not existing:
                LMSSettings.set_setting(key, value, setting_type, description)

class StudentModuleProgress(db.Model, TimezoneAwareMixin):
    """Student Module Progress Model - Tracks student progress in modules"""
    __tablename__ = 'student_module_progress'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'), nullable=False)
    module_id = db.Column(db.Integer, db.ForeignKey('course_modules.id'), nullable=False)
    progress_percentage = db.Column(db.Integer, default=0)
    time_spent = db.Column(db.Integer, default=0)  # in minutes
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    last_accessed = db.Column(db.DateTime, default=get_current_ist_datetime)
    is_completed = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)  # student notes for this module
    
    # Relationships
    student = db.relationship('Student', backref='module_progress')
    
    __table_args__ = (db.UniqueConstraint('student_id', 'module_id'),)
    
    def __repr__(self):
        return f'<StudentModuleProgress {self.student_id}-{self.module_id}: {self.progress_percentage}%>'
    
    def mark_completed(self):
        """Mark module as completed"""
        self.is_completed = True
        self.progress_percentage = 100
        self.completed_at = get_current_ist_datetime()
        db.session.commit()
    
    def update_progress(self, percentage, time_spent_minutes=0):
        """Update progress percentage and time spent"""
        self.progress_percentage = min(100, max(0, percentage))
        self.time_spent += time_spent_minutes
        self.last_accessed = get_current_ist_datetime()
        
        if self.progress_percentage >= 100 and not self.is_completed:
            self.mark_completed()
        
        db.session.commit()
    
    def calculate_progress_from_sections(self):
        """Auto-calculate module progress based on completed sections"""
        module = db.session.get(CourseModule, self.module_id)
        if not module or not module.sections:
            return 0
        
        completed_sections = 0
        for section in module.sections:
            if section.is_completed_by_student(self.student_id):
                completed_sections += 1
        
        calculated_percentage = int((completed_sections / len(module.sections)) * 100)
        self.update_progress(calculated_percentage)
        return calculated_percentage

class StudentSectionProgress(db.Model, TimezoneAwareMixin):
    """Student Section Progress Model - Tracks student progress in sections/chapters"""
    __tablename__ = 'student_section_progress'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey('course_sections.id'), nullable=False)
    progress_percentage = db.Column(db.Integer, default=0)
    time_spent = db.Column(db.Integer, default=0)  # in minutes
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    last_accessed = db.Column(db.DateTime, default=get_current_ist_datetime)
    is_completed = db.Column(db.Boolean, default=False)
    
    # Section-specific tracking
    video_completed = db.Column(db.Boolean, default=False)
    material_downloaded = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)  # student notes for this section
    
    # Relationships
    student = db.relationship('Student', backref='section_progress')
    
    __table_args__ = (db.UniqueConstraint('student_id', 'section_id'),)
    
    def __repr__(self):
        return f'<StudentSectionProgress {self.student_id}-{self.section_id}: {self.progress_percentage}%>'
    
    def mark_completed(self):
        """Mark section as completed"""
        self.is_completed = True
        self.progress_percentage = 100
        self.completed_at = get_current_ist_datetime()
        db.session.commit()
        
        # Update module progress
        section = db.session.get(CourseSection, self.section_id)
        if section:
            module_progress = StudentModuleProgress.query.filter_by(
                student_id=self.student_id,
                module_id=section.module_id
            ).first()
            
            if module_progress:
                module_progress.calculate_progress_from_sections()
    
    def update_progress(self, percentage, time_spent_minutes=0):
        """Update progress percentage and time spent"""
        self.progress_percentage = min(100, max(0, percentage))
        self.time_spent += time_spent_minutes
        self.last_accessed = get_current_ist_datetime()
        
        if self.progress_percentage >= 100 and not self.is_completed:
            self.mark_completed()
        
        db.session.commit()
    
    def check_auto_completion(self):
        """Auto-complete section if both video and material requirements are met"""
        if self.video_completed and self.material_downloaded:
            if not self.is_completed:
                self.mark_completed()
            return True
        return False

class StudentVideoProgress(db.Model, TimezoneAwareMixin):
    """Student Video Progress Model - Tracks video watching progress"""
    __tablename__ = 'student_video_progress'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('course_videos.id'), nullable=False)
    watch_time = db.Column(db.Integer, default=0)  # in seconds
    total_duration = db.Column(db.Integer, default=0)
    last_position = db.Column(db.Integer, default=0)  # playback position in seconds
    completion_percentage = db.Column(db.Integer, default=0)
    watch_sessions = db.Column(db.Integer, default=0)  # number of times watched
    first_watched = db.Column(db.DateTime)
    last_watched = db.Column(db.DateTime, default=get_current_ist_datetime)
    is_completed = db.Column(db.Boolean, default=False)
    
    # Relationships
    student = db.relationship('Student', backref='video_progress')
    
    __table_args__ = (db.UniqueConstraint('student_id', 'video_id'),)
    
    def __repr__(self):
        return f'<StudentVideoProgress {self.student_id}-{self.video_id}: {self.completion_percentage}%>'
    
    def update_watch_progress(self, current_position, total_duration):
        """Update video watch progress"""
        self.last_position = current_position
        self.total_duration = total_duration
        self.last_watched = get_current_ist_datetime()
        self.watch_sessions += 1
        
        if not self.first_watched:
            self.first_watched = get_current_ist_datetime()
        
        # Calculate completion percentage
        if total_duration > 0:
            self.completion_percentage = min(100, int((current_position / total_duration) * 100))
            
            # Consider video completed if watched 90% or more
            if self.completion_percentage >= 90:
                self.is_completed = True
        
        # Update total watch time (avoid counting repeated watching of same section)
        if current_position > self.watch_time:
            self.watch_time = current_position
        
        db.session.commit()
    
    def format_watch_time(self):
        """Format watch time in HH:MM:SS"""
        if not self.watch_time:
            return "00:00"
        
        hours = self.watch_time // 3600
        minutes = (self.watch_time % 3600) // 60
        seconds = self.watch_time % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
