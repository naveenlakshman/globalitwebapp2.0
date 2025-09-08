# LMS Content Management Models - Admin Upload & Content Creation System
# Global IT Education Management System - Content Management Layer
# Purpose: Handle video/document uploads, quiz creation, assignment building, and content approval workflows
# Integration: Works with lms_model.py for complete LMS functionality

from init_db import db
from datetime import datetime, timedelta
from utils.timezone_helper import TimezoneAwareMixin, format_datetime_indian, get_current_ist_datetime
import json
import hashlib
import os
from enum import Enum

class UploadStatus(Enum):
    """Upload status enumeration"""
    PENDING = "pending"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class WorkflowStage(Enum):
    """Content workflow stages"""
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"
    ARCHIVED = "archived"

class VideoUpload(db.Model, TimezoneAwareMixin):
    """Video Upload Management - Track video upload process, encoding, and approval"""
    __tablename__ = 'video_uploads'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    module_id = db.Column(db.Integer, db.ForeignKey('course_modules.id'), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey('course_sections.id'), nullable=False)
    
    # File Information
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500))  # Original upload path
    processed_file_path = db.Column(db.String(500))  # Processed/encoded file path
    file_size = db.Column(db.BigInteger, default=0)  # in bytes
    file_format = db.Column(db.String(50))  # mp4, avi, mov, etc.
    file_hash = db.Column(db.String(64))  # SHA256 hash for integrity
    
    # Video Properties
    video_title = db.Column(db.String(200), nullable=False)
    video_description = db.Column(db.Text)
    duration_seconds = db.Column(db.Integer, default=0)
    resolution = db.Column(db.String(20))  # 1920x1080, 1280x720, etc.
    fps = db.Column(db.Integer, default=30)
    bitrate = db.Column(db.Integer)  # in kbps
    
    # Upload Process
    upload_status = db.Column(db.String(20), default='pending')  # pending, uploading, processing, completed, failed
    upload_progress = db.Column(db.Integer, default=0)  # 0-100
    encoding_status = db.Column(db.String(20), default='pending')  # pending, encoding, completed, failed
    encoding_progress = db.Column(db.Integer, default=0)  # 0-100
    
    # Security & Quality
    security_scan_status = db.Column(db.String(20), default='pending')  # pending, scanning, passed, failed
    quality_check_status = db.Column(db.String(20), default='pending')  # pending, checking, passed, failed
    watermark_applied = db.Column(db.Boolean, default=False)
    drm_protection_applied = db.Column(db.Boolean, default=False)
    
    # Workflow Management
    workflow_stage = db.Column(db.String(20), default='draft')  # draft, review, approved, published, rejected
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Timestamps
    upload_started_at = db.Column(db.DateTime, default=get_current_ist_datetime)
    upload_completed_at = db.Column(db.DateTime)
    processing_started_at = db.Column(db.DateTime)
    processing_completed_at = db.Column(db.DateTime)
    reviewed_at = db.Column(db.DateTime)
    approved_at = db.Column(db.DateTime)
    published_at = db.Column(db.DateTime)
    
    # Comments & Notes
    upload_notes = db.Column(db.Text)
    reviewer_comments = db.Column(db.Text)
    rejection_reason = db.Column(db.Text)
    
    # Error Handling
    error_message = db.Column(db.Text)
    retry_count = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=3)
    
    # Relationships
    course = db.relationship('Course', backref='video_uploads')
    module = db.relationship('CourseModule', backref='video_uploads')
    section = db.relationship('CourseSection', backref='video_uploads')
    uploader = db.relationship('User', foreign_keys=[uploaded_by], backref='uploaded_videos')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by], backref='reviewed_videos')
    approver = db.relationship('User', foreign_keys=[approved_by], backref='approved_videos')
    
    def __repr__(self):
        return f'<VideoUpload {self.video_title} - {self.upload_status}>'
    
    def update_upload_progress(self, progress):
        """Update upload progress"""
        self.upload_progress = min(100, max(0, progress))
        if progress >= 100:
            self.upload_status = 'processing'
            self.upload_completed_at = get_current_ist_datetime()
        db.session.commit()
    
    def update_encoding_progress(self, progress):
        """Update encoding progress"""
        self.encoding_progress = min(100, max(0, progress))
        if progress >= 100:
            self.encoding_status = 'completed'
            self.processing_completed_at = get_current_ist_datetime()
            self.upload_status = 'completed'
        db.session.commit()
    
    def submit_for_review(self):
        """Submit video for review"""
        if self.upload_status == 'completed':
            self.workflow_stage = 'review'
            db.session.commit()
            return True
        return False
    
    def approve_video(self, approver_id, comments=None):
        """Approve video for publishing"""
        self.workflow_stage = 'approved'
        self.approved_by = approver_id
        self.approved_at = get_current_ist_datetime()
        if comments:
            self.reviewer_comments = comments
        db.session.commit()
        return self.create_course_video()
    
    def reject_video(self, reviewer_id, reason):
        """Reject video with reason"""
        self.workflow_stage = 'rejected'
        self.reviewed_by = reviewer_id
        self.reviewed_at = get_current_ist_datetime()
        self.rejection_reason = reason
        db.session.commit()
    
    def create_course_video(self):
        """Create CourseVideo record from approved upload"""
        from models.lms_model import CourseVideo
        
        if self.workflow_stage == 'approved':
            video = CourseVideo(
                section_id=self.section_id,
                video_title=self.video_title,
                video_url=self.processed_file_path or self.file_path,
                video_duration=self.duration_seconds,
                video_description=self.video_description,
                video_type='local',
                file_size=self.file_size,
                quality=self.resolution,
                is_active=True,
                is_downloadable=False,  # Always False for security
                streaming_only=True,
                drm_protected=self.drm_protection_applied,
                watermark_enabled=self.watermark_applied,
                copy_protection=True
            )
            db.session.add(video)
            self.workflow_stage = 'published'
            self.published_at = get_current_ist_datetime()
            db.session.commit()
            return video
        return None
    
    def get_upload_size_formatted(self):
        """Format file size in human readable format"""
        if not self.file_size:
            return "Unknown"
        
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
    
    def get_duration_formatted(self):
        """Format duration in HH:MM:SS"""
        if not self.duration_seconds:
            return "00:00"
        
        hours = self.duration_seconds // 3600
        minutes = (self.duration_seconds % 3600) // 60
        seconds = self.duration_seconds % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

class DocumentUpload(db.Model, TimezoneAwareMixin):
    """Document Upload Management - Track document upload, processing, and security"""
    __tablename__ = 'document_uploads'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    module_id = db.Column(db.Integer, db.ForeignKey('course_modules.id'), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey('course_sections.id'), nullable=False)
    
    # File Information
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500))  # Original upload path
    processed_file_path = db.Column(db.String(500))  # Processed/watermarked file
    preview_file_path = db.Column(db.String(500))  # Preview/thumbnail file
    file_size = db.Column(db.BigInteger, default=0)
    file_format = db.Column(db.String(50))  # pdf, doc, docx, ppt, etc.
    file_hash = db.Column(db.String(64))  # SHA256 hash
    
    # Document Properties
    document_title = db.Column(db.String(200), nullable=False)
    document_description = db.Column(db.Text)
    page_count = db.Column(db.Integer, default=0)
    word_count = db.Column(db.Integer, default=0)
    
    # Upload Process
    upload_status = db.Column(db.String(20), default='pending')
    upload_progress = db.Column(db.Integer, default=0)
    processing_status = db.Column(db.String(20), default='pending')
    processing_progress = db.Column(db.Integer, default=0)
    
    # Security & Processing
    security_scan_status = db.Column(db.String(20), default='pending')
    virus_scan_status = db.Column(db.String(20), default='pending')
    content_scan_status = db.Column(db.String(20), default='pending')  # Check for inappropriate content
    watermark_applied = db.Column(db.Boolean, default=False)
    copy_protection_applied = db.Column(db.Boolean, default=False)
    print_protection_applied = db.Column(db.Boolean, default=False)
    
    # Document Settings
    is_downloadable = db.Column(db.Boolean, default=True)
    view_only_mode = db.Column(db.Boolean, default=False)
    requires_video_completion = db.Column(db.Boolean, default=False)
    access_level = db.Column(db.String(20), default='student')
    
    # Workflow Management
    workflow_stage = db.Column(db.String(20), default='draft')
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Timestamps
    upload_started_at = db.Column(db.DateTime, default=get_current_ist_datetime)
    upload_completed_at = db.Column(db.DateTime)
    processing_started_at = db.Column(db.DateTime)
    processing_completed_at = db.Column(db.DateTime)
    reviewed_at = db.Column(db.DateTime)
    approved_at = db.Column(db.DateTime)
    published_at = db.Column(db.DateTime)
    
    # Comments & Notes
    upload_notes = db.Column(db.Text)
    reviewer_comments = db.Column(db.Text)
    rejection_reason = db.Column(db.Text)
    
    # Error Handling
    error_message = db.Column(db.Text)
    retry_count = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=3)
    
    # Relationships
    course = db.relationship('Course', backref='document_uploads')
    module = db.relationship('CourseModule', backref='document_uploads')
    section = db.relationship('CourseSection', backref='document_uploads')
    uploader = db.relationship('User', foreign_keys=[uploaded_by], backref='uploaded_documents')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by], backref='reviewed_documents')
    approver = db.relationship('User', foreign_keys=[approved_by], backref='approved_documents')
    
    def __repr__(self):
        return f'<DocumentUpload {self.document_title} - {self.upload_status}>'
    
    def get_upload_size_formatted(self):
        """Format file size in human readable format"""
        if not self.file_size:
            return "Unknown"
        
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
    
    def update_upload_progress(self, progress):
        """Update upload progress"""
        self.upload_progress = min(100, max(0, progress))
        if progress >= 100:
            self.upload_status = 'processing'
            self.upload_completed_at = get_current_ist_datetime()
            self.start_processing()
        db.session.commit()
    
    def start_processing(self):
        """Start document processing"""
        self.processing_status = 'processing'
        self.processing_started_at = get_current_ist_datetime()
        # Here you would trigger document processing tasks
        db.session.commit()
    
    def complete_processing(self):
        """Mark processing as completed"""
        self.processing_status = 'completed'
        self.processing_completed_at = get_current_ist_datetime()
        self.upload_status = 'completed'
        db.session.commit()
    
    def approve_document(self, approver_id, comments=None):
        """Approve document for publishing"""
        self.workflow_stage = 'approved'
        self.approved_by = approver_id
        self.approved_at = get_current_ist_datetime()
        if comments:
            self.reviewer_comments = comments
        db.session.commit()
        return self.create_course_material()
    
    def create_course_material(self):
        """Create CourseMaterial record from approved upload"""
        from models.lms_model import CourseMaterial
        
        if self.workflow_stage == 'approved':
            material = CourseMaterial(
                section_id=self.section_id,
                material_name=self.document_title,
                material_type=self.file_format.lower(),
                file_url=self.processed_file_path or self.file_path,
                original_filename=self.original_filename,
                file_size=self.file_size,
                description=self.document_description,
                is_downloadable=self.is_downloadable,
                is_active=True,
                copy_protection=self.copy_protection_applied,
                print_protection=self.print_protection_applied,
                watermark_enabled=self.watermark_applied,
                view_only_mode=self.view_only_mode,
                access_level=self.access_level,
                requires_completion=self.requires_video_completion,
                encryption_enabled=True,
                secure_viewer_only=True
            )
            db.session.add(material)
            self.workflow_stage = 'published'
            self.published_at = get_current_ist_datetime()
            db.session.commit()
            return material
        return None

class Quiz(db.Model, TimezoneAwareMixin):
    """Quiz Management - Create and manage quizzes for sections"""
    __tablename__ = 'quizzes'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    module_id = db.Column(db.Integer, db.ForeignKey('course_modules.id'), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey('course_sections.id'), nullable=True)  # Made optional for module-level quizzes
    
    # Quiz Placement - New field to support your business logic
    quiz_placement = db.Column(db.String(20), default='section')  # 'section', 'module', 'course'
    placement_order = db.Column(db.Integer, default=0)  # Order within placement (e.g., 1st quiz after module)
    
    # Quiz Information
    quiz_title = db.Column(db.String(200), nullable=False)
    quiz_description = db.Column(db.Text)
    instructions = db.Column(db.Text)
    
    # Quiz Settings
    total_questions = db.Column(db.Integer, default=0)
    max_score = db.Column(db.Integer, default=100)
    passing_score = db.Column(db.Integer, default=70)
    time_limit_minutes = db.Column(db.Integer, default=30)
    max_attempts = db.Column(db.Integer, default=3)
    
    # Quiz Behavior
    shuffle_questions = db.Column(db.Boolean, default=True)
    shuffle_options = db.Column(db.Boolean, default=True)
    show_results_immediately = db.Column(db.Boolean, default=False)
    show_correct_answers = db.Column(db.Boolean, default=False)
    allow_review = db.Column(db.Boolean, default=True)
    
    # Access Control
    is_mandatory = db.Column(db.Boolean, default=True)
    is_published = db.Column(db.Boolean, default=False)
    requires_video_completion = db.Column(db.Boolean, default=True)
    available_from = db.Column(db.DateTime)
    available_until = db.Column(db.DateTime)
    
    # Workflow
    workflow_stage = db.Column(db.String(20), default='draft')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=get_current_ist_datetime)
    updated_at = db.Column(db.DateTime, default=get_current_ist_datetime, onupdate=get_current_ist_datetime)
    reviewed_at = db.Column(db.DateTime)
    approved_at = db.Column(db.DateTime)
    published_at = db.Column(db.DateTime)
    
    # Comments
    creator_notes = db.Column(db.Text)
    reviewer_comments = db.Column(db.Text)
    
    # Relationships
    course = db.relationship('Course', backref='quizzes')
    module = db.relationship('CourseModule', backref='quizzes')
    section = db.relationship('CourseSection', backref='quizzes')
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_quizzes')
    questions = db.relationship('QuizQuestion', backref='quiz', cascade='all, delete-orphan', order_by='QuizQuestion.question_order')
    attempts = db.relationship('QuizAttempt', backref='quiz', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Quiz {self.quiz_title}>'
    
    def add_question(self, question_text, question_type='multiple_choice', options=None, correct_answer=None, points=1):
        """Add a question to the quiz"""
        question_order = len(self.questions) + 1
        question = QuizQuestion(
            quiz_id=self.id,
            question_text=question_text,
            question_type=question_type,
            question_order=question_order,
            points=points,
            correct_answer=correct_answer
        )
        
        if options and question_type in ['multiple_choice', 'single_choice']:
            question.options = json.dumps(options)
        
        db.session.add(question)
        self.total_questions = len(self.questions) + 1
        db.session.commit()
        return question
    
    def calculate_total_score(self):
        """Calculate total possible score for quiz"""
        total = sum(q.points for q in self.questions)
        self.max_score = total
        db.session.commit()
        return total
    
    def is_available_for_student(self, student_id):
        """Check if quiz is available for student"""
        if not self.is_published:
            return False
        
        current_time = get_current_ist_datetime()
        if self.available_from and current_time < self.available_from:
            return False
        
        if self.available_until and current_time > self.available_until:
            return False
        
        if self.requires_video_completion:
            # Check if student completed video in same section
            video = self.section.get_video()  # From lms_model
            if video:
                progress = video.get_watch_progress_for_student(student_id)
                if not (progress and progress.is_completed):
                    return False
        
        return True
    
    def get_student_attempts(self, student_id):
        """Get all attempts by a student"""
        return QuizAttempt.query.filter_by(
            quiz_id=self.id,
            student_id=student_id
        ).order_by(QuizAttempt.attempt_number).all()
    
    def can_student_attempt(self, student_id):
        """Check if student can make another attempt"""
        attempts = self.get_student_attempts(student_id)
        return len(attempts) < self.max_attempts

class QuizQuestion(db.Model, TimezoneAwareMixin):
    """Quiz Questions - Individual questions within quizzes"""
    __tablename__ = 'quiz_questions'
    
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    
    # Question Content
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(50), default='multiple_choice')  # multiple_choice, single_choice, true_false, short_answer, essay
    question_order = db.Column(db.Integer, default=0)
    points = db.Column(db.Integer, default=1)
    
    # Answer Options (JSON for multiple choice)
    options = db.Column(db.Text)  # JSON array of options
    correct_answer = db.Column(db.Text)  # Correct answer or answer key
    explanation = db.Column(db.Text)  # Explanation for the answer
    
    # Question Settings
    is_required = db.Column(db.Boolean, default=True)
    allow_partial_credit = db.Column(db.Boolean, default=False)
    case_sensitive = db.Column(db.Boolean, default=False)  # For text answers
    
    # Media
    image_url = db.Column(db.String(500))  # Optional question image
    audio_url = db.Column(db.String(500))  # Optional audio clip
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=get_current_ist_datetime)
    updated_at = db.Column(db.DateTime, default=get_current_ist_datetime, onupdate=get_current_ist_datetime)
    
    def __repr__(self):
        return f'<QuizQuestion {self.id}: {self.question_text[:50]}...>'
    
    def get_options_list(self):
        """Get options as list"""
        if self.options:
            return json.loads(self.options)
        return []
    
    def get_options(self):
        """Alias for get_options_list for template compatibility"""
        return self.get_options_list()
    
    def set_options_list(self, options_list):
        """Set options from list"""
        self.options = json.dumps(options_list)
    
    def get_correct_option_indexes(self):
        """Get correct option indexes as list"""
        if self.question_type in ['multiple_choice', 'multiple_select']:
            if self.correct_answer:
                try:
                    # Handle both single index and multiple indexes
                    if '[' in self.correct_answer:
                        return json.loads(self.correct_answer)
                    else:
                        return [int(self.correct_answer)]
                except (ValueError, json.JSONDecodeError):
                    return []
        return []
    
    def check_answer(self, student_answer):
        """Check if student answer is correct"""
        if self.question_type == 'multiple_choice':
            return str(student_answer).strip() == str(self.correct_answer).strip()
        elif self.question_type == 'true_false':
            return str(student_answer).lower() == str(self.correct_answer).lower()
        elif self.question_type == 'short_answer':
            if self.case_sensitive:
                return student_answer.strip() == self.correct_answer.strip()
            else:
                return student_answer.strip().lower() == self.correct_answer.strip().lower()
        elif self.question_type == 'essay':
            # Essay questions require manual grading
            return None
        
        return False

class QuizAttempt(db.Model, TimezoneAwareMixin):
    """Quiz Attempts - Track student quiz attempts and results"""
    __tablename__ = 'quiz_attempts'
    
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'), nullable=False)
    
    # Attempt Information
    attempt_number = db.Column(db.Integer, default=1)
    status = db.Column(db.String(20), default='in_progress')  # in_progress, completed, timed_out, abandoned
    
    # Scoring
    total_questions = db.Column(db.Integer, default=0)
    questions_answered = db.Column(db.Integer, default=0)
    correct_answers = db.Column(db.Integer, default=0)
    score = db.Column(db.Integer, default=0)
    percentage = db.Column(db.Float, default=0.0)
    is_passed = db.Column(db.Boolean, default=False)
    
    # Timing
    time_limit_minutes = db.Column(db.Integer)
    time_spent_minutes = db.Column(db.Integer, default=0)
    time_remaining_seconds = db.Column(db.Integer)
    
    # Student Answers (JSON)
    answers = db.Column(db.Text)  # JSON object with question_id: answer pairs
    
    # Timestamps
    started_at = db.Column(db.DateTime, default=get_current_ist_datetime)
    completed_at = db.Column(db.DateTime)
    last_activity_at = db.Column(db.DateTime, default=get_current_ist_datetime)
    
    # Additional Info
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    
    # Relationships
    student = db.relationship('Student', backref='quiz_attempts')
    
    __table_args__ = (db.UniqueConstraint('quiz_id', 'student_id', 'attempt_number'),)
    
    def __repr__(self):
        return f'<QuizAttempt {self.student_id} - Quiz {self.quiz_id} - Attempt {self.attempt_number}>'
    
    def get_answers_dict(self):
        """Get answers as dictionary"""
        if self.answers:
            return json.loads(self.answers)
        return {}
    
    def set_answers_dict(self, answers_dict):
        """Set answers from dictionary"""
        self.answers = json.dumps(answers_dict)
    
    def submit_answer(self, question_id, answer):
        """Submit answer for a question"""
        answers_dict = self.get_answers_dict()
        answers_dict[str(question_id)] = answer
        self.set_answers_dict(answers_dict)
        self.questions_answered = len(answers_dict)
        self.last_activity_at = get_current_ist_datetime()
        db.session.commit()
    
    def calculate_score(self):
        """Calculate final score for the attempt"""
        if self.status != 'completed':
            return 0
        
        correct_count = 0
        total_points = 0
        earned_points = 0
        
        answers_dict = self.get_answers_dict()
        
        for question in self.quiz.questions:
            total_points += question.points
            question_id_str = str(question.id)
            
            if question_id_str in answers_dict:
                student_answer = answers_dict[question_id_str]
                if question.check_answer(student_answer):
                    correct_count += 1
                    earned_points += question.points
        
        self.correct_answers = correct_count
        self.score = earned_points
        self.total_questions = len(self.quiz.questions)
        
        if total_points > 0:
            self.percentage = (earned_points / total_points) * 100
        else:
            self.percentage = 0
        
        self.is_passed = self.percentage >= self.quiz.passing_score
        db.session.commit()
        
        return self.score
    
    def complete_attempt(self):
        """Mark attempt as completed and calculate score"""
        self.status = 'completed'
        self.completed_at = get_current_ist_datetime()
        
        # Calculate time spent
        if self.started_at:
            time_diff = self.completed_at - self.started_at
            self.time_spent_minutes = int(time_diff.total_seconds() / 60)
        
        # Calculate final score
        self.calculate_score()
        
        db.session.commit()
        return self.score

class AssignmentCreator(db.Model, TimezoneAwareMixin):
    """Assignment Creator - Enhanced assignment creation and management"""
    __tablename__ = 'assignment_creators'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    module_id = db.Column(db.Integer, db.ForeignKey('course_modules.id'), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey('course_sections.id'), nullable=True)  # Made optional for module-level assignments
    
    # Assignment Placement - New field to support your business logic
    assignment_placement = db.Column(db.String(20), default='section')  # 'section', 'module', 'course'
    placement_order = db.Column(db.Integer, default=0)  # Order within placement (e.g., 1st assignment after module)
    
    # Assignment Information
    assignment_title = db.Column(db.String(200), nullable=False)
    assignment_description = db.Column(db.Text)
    detailed_instructions = db.Column(db.Text)
    assignment_type = db.Column(db.String(50), default='project')  # project, essay, practical, presentation, research
    
    # Submission Requirements
    submission_format = db.Column(db.String(100))  # pdf, doc, video, url, text, zip
    max_file_size_mb = db.Column(db.Integer, default=50)
    allowed_file_types = db.Column(db.String(200))  # JSON array of allowed extensions
    min_word_count = db.Column(db.Integer)
    max_word_count = db.Column(db.Integer)
    
    # Scoring & Grading
    max_score = db.Column(db.Integer, default=100)
    grading_rubric = db.Column(db.Text)  # JSON grading criteria
    auto_grading_enabled = db.Column(db.Boolean, default=False)
    peer_review_enabled = db.Column(db.Boolean, default=False)
    
    # Timing & Availability
    is_mandatory = db.Column(db.Boolean, default=True)
    due_date = db.Column(db.DateTime)
    late_submission_allowed = db.Column(db.Boolean, default=False)
    late_penalty_percent = db.Column(db.Integer, default=10)  # per day
    
    # Access Control
    requires_video_completion = db.Column(db.Boolean, default=True)
    requires_material_download = db.Column(db.Boolean, default=False)
    group_assignment = db.Column(db.Boolean, default=False)
    max_group_size = db.Column(db.Integer, default=1)
    
    # Workflow
    workflow_stage = db.Column(db.String(20), default='draft')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=get_current_ist_datetime)
    updated_at = db.Column(db.DateTime, default=get_current_ist_datetime, onupdate=get_current_ist_datetime)
    reviewed_at = db.Column(db.DateTime)
    approved_at = db.Column(db.DateTime)
    published_at = db.Column(db.DateTime)
    
    # Post-publication edit tracking
    last_published_edit = db.Column(db.DateTime)
    edit_count_post_publish = db.Column(db.Integer, default=0)
    
    # Unpublish functionality
    unpublished_at = db.Column(db.DateTime)
    unpublished_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    unpublish_reason = db.Column(db.Text)
    
    # Revision tracking
    parent_assignment_id = db.Column(db.Integer, db.ForeignKey('assignment_creators.id'))
    revision_notes = db.Column(db.Text)
    revision_number = db.Column(db.Integer, default=1)
    is_current_revision = db.Column(db.Boolean, default=True)
    
    # Assignment editing metadata
    editing_locked = db.Column(db.Boolean, default=False)
    locked_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    locked_at = db.Column(db.DateTime)
    lock_reason = db.Column(db.Text)
    
    # Comments
    creator_notes = db.Column(db.Text)
    reviewer_comments = db.Column(db.Text)
    rejection_reason = db.Column(db.Text)
    
    # Relationships
    course = db.relationship('Course', backref='assignment_creators')
    module = db.relationship('CourseModule', backref='assignment_creators')
    section = db.relationship('CourseSection', backref='assignment_creators')
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_assignments')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by], backref='reviewed_assignments')
    approver = db.relationship('User', foreign_keys=[approved_by], backref='approved_assignments')
    unpublisher = db.relationship('User', foreign_keys=[unpublished_by], backref='unpublished_assignments')
    locker = db.relationship('User', foreign_keys=[locked_by], backref='locked_assignments')
    parent_assignment = db.relationship('AssignmentCreator', foreign_keys=[parent_assignment_id], remote_side='AssignmentCreator.id', backref='revisions')
    
    def __repr__(self):
        return f'<AssignmentCreator {self.assignment_title}>'
    
    def get_allowed_file_types_list(self):
        """Get allowed file types as list"""
        if self.allowed_file_types and self.allowed_file_types.strip() and self.allowed_file_types not in ['None', 'null']:
            try:
                return json.loads(self.allowed_file_types)
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    
    def set_allowed_file_types_list(self, types_list):
        """Set allowed file types from list"""
        self.allowed_file_types = json.dumps(types_list)
    
    def get_grading_rubric_dict(self):
        """Get grading rubric as dictionary"""
        if self.grading_rubric and self.grading_rubric.strip() and self.grading_rubric not in ['None', 'null']:
            try:
                return json.loads(self.grading_rubric)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}
    
    def set_grading_rubric_dict(self, rubric_dict):
        """Set grading rubric from dictionary"""
        self.grading_rubric = json.dumps(rubric_dict)
    
    def approve_assignment(self, approver_id, comments=None):
        """Approve assignment for publishing"""
        self.workflow_stage = 'approved'
        self.approved_by = approver_id
        self.approved_at = get_current_ist_datetime()
        if comments:
            self.reviewer_comments = comments
        db.session.commit()
        return self.create_student_assignment()
    
    def create_student_assignment(self):
        """Create StudentAssignment record from approved assignment"""
        from models.lms_model import StudentAssignment
        
        if self.workflow_stage == 'approved':
            assignment = StudentAssignment(
                section_id=self.section_id,
                assignment_title=self.assignment_title,
                assignment_description=self.assignment_description,
                assignment_type=self.assignment_type,
                max_score=self.max_score,
                due_date=self.due_date,
                submission_format=self.submission_format,
                is_mandatory=self.is_mandatory,
                is_published=True,
                created_by=self.created_by
            )
            db.session.add(assignment)
            self.workflow_stage = 'published'
            self.published_at = get_current_ist_datetime()
            db.session.commit()
            return assignment
        return None
    
    def is_overdue(self):
        """Check if assignment is overdue"""
        if self.due_date:
            return get_current_ist_datetime() > self.due_date
        return False

class ContentWorkflow(db.Model, TimezoneAwareMixin):
    """Content Workflow Management - Track approval workflows for all content types"""
    __tablename__ = 'content_workflows'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Content Reference
    content_type = db.Column(db.String(50), nullable=False)  # video, document, quiz, assignment
    content_id = db.Column(db.Integer, nullable=False)  # ID of the content record
    
    # Workflow Information
    workflow_stage = db.Column(db.String(20), default='draft')
    priority = db.Column(db.String(20), default='normal')  # low, normal, high, urgent
    
    # People Involved
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'))  # Current reviewer
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Workflow Actions
    workflow_actions = db.Column(db.Text)  # JSON array of workflow history
    current_action = db.Column(db.String(100))
    next_action = db.Column(db.String(100))
    
    # Comments & Feedback
    creator_notes = db.Column(db.Text)
    reviewer_feedback = db.Column(db.Text)
    final_comments = db.Column(db.Text)
    
    # Timing
    created_at = db.Column(db.DateTime, default=get_current_ist_datetime)
    assigned_at = db.Column(db.DateTime)
    reviewed_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    due_date = db.Column(db.DateTime)
    
    # Status Tracking
    is_urgent = db.Column(db.Boolean, default=False)
    requires_revision = db.Column(db.Boolean, default=False)
    revision_count = db.Column(db.Integer, default=0)
    
    # Relationships
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_workflows')
    reviewer = db.relationship('User', foreign_keys=[assigned_to], backref='assigned_workflows')
    approver = db.relationship('User', foreign_keys=[approved_by], backref='approved_workflows')
    
    def __repr__(self):
        return f'<ContentWorkflow {self.content_type}-{self.content_id} - {self.workflow_stage}>'
    
    def get_content_title(self):
        """Get the title of the associated content"""
        try:
            if self.content_type == 'video':
                video = VideoUpload.query.get(self.content_id)
                return video.video_title if video else 'Unknown Video'
            elif self.content_type == 'document':
                document = DocumentUpload.query.get(self.content_id)
                return document.document_title if document else 'Unknown Document'
            elif self.content_type == 'quiz':
                quiz = Quiz.query.get(self.content_id)
                return quiz.quiz_title if quiz else 'Unknown Quiz'
            elif self.content_type == 'assignment':
                assignment = AssignmentCreator.query.get(self.content_id)
                return assignment.assignment_title if assignment else 'Unknown Assignment'
            else:
                return f'Unknown {self.content_type.title()}'
        except:
            return f'Content #{self.content_id}'
    
    def get_workflow_actions_list(self):
        """Get workflow actions as list"""
        if self.workflow_actions:
            return json.loads(self.workflow_actions)
        return []
    
    def add_workflow_action(self, action, user_id, comments=None):
        """Add an action to workflow history"""
        actions = self.get_workflow_actions_list()
        action_entry = {
            'action': action,
            'user_id': user_id,
            'timestamp': get_current_ist_datetime().isoformat(),
            'comments': comments
        }
        actions.append(action_entry)
        self.workflow_actions = json.dumps(actions)
        self.current_action = action
        db.session.commit()
    
    def assign_to_reviewer(self, reviewer_id, due_date=None):
        """Assign workflow to a reviewer"""
        self.assigned_to = reviewer_id
        self.assigned_at = get_current_ist_datetime()
        self.workflow_stage = 'review'
        if due_date:
            self.due_date = due_date
        self.add_workflow_action('assigned_for_review', reviewer_id)
        db.session.commit()
    
    def approve_content(self, approver_id, comments=None):
        """Approve content workflow"""
        self.workflow_stage = 'approved'
        self.approved_by = approver_id
        self.completed_at = get_current_ist_datetime()
        self.final_comments = comments
        self.add_workflow_action('approved', approver_id, comments)
        db.session.commit()
    
    def reject_content(self, reviewer_id, reason, requires_revision=True):
        """Reject content with feedback"""
        if requires_revision:
            self.workflow_stage = 'revision_required'
            self.requires_revision = True
            self.revision_count += 1
        else:
            self.workflow_stage = 'rejected'
            self.completed_at = get_current_ist_datetime()
        
        self.reviewer_feedback = reason
        self.add_workflow_action('rejected', reviewer_id, reason)
        db.session.commit()

class FileStorage(db.Model, TimezoneAwareMixin):
    """File Storage Management - Track file storage, CDN, and backup status"""
    __tablename__ = 'file_storage'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # File Information
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.BigInteger, default=0)
    file_type = db.Column(db.String(50))  # video, document, image, audio
    mime_type = db.Column(db.String(100))
    file_hash = db.Column(db.String(64))  # SHA256 hash
    
    # Storage Locations
    local_storage_path = db.Column(db.String(500))
    cdn_url = db.Column(db.String(500))
    backup_location = db.Column(db.String(500))
    cloud_storage_url = db.Column(db.String(500))
    
    # Storage Status
    storage_status = db.Column(db.String(20), default='local')  # local, cdn, cloud, backed_up
    cdn_sync_status = db.Column(db.String(20), default='pending')  # pending, syncing, synced, failed
    backup_status = db.Column(db.String(20), default='pending')  # pending, backing_up, backed_up, failed
    
    # File Integrity
    integrity_check_status = db.Column(db.String(20), default='pending')  # pending, verified, failed
    last_integrity_check = db.Column(db.DateTime)
    compression_status = db.Column(db.String(20), default='none')  # none, compressing, compressed
    encryption_status = db.Column(db.String(20), default='none')  # none, encrypting, encrypted
    
    # Access & Usage
    access_count = db.Column(db.Integer, default=0)
    last_accessed = db.Column(db.DateTime)
    bandwidth_usage_mb = db.Column(db.Integer, default=0)
    
    # Associated Content
    content_type = db.Column(db.String(50))  # video_upload, document_upload, etc.
    content_id = db.Column(db.Integer)  # ID of associated content
    
    # Management
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=get_current_ist_datetime)
    updated_at = db.Column(db.DateTime, default=get_current_ist_datetime, onupdate=get_current_ist_datetime)
    
    # Cleanup
    is_temporary = db.Column(db.Boolean, default=False)
    cleanup_after = db.Column(db.DateTime)  # Auto-delete after this date
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime)
    
    # Relationships
    uploader = db.relationship('User', backref='uploaded_files')
    
    def __repr__(self):
        return f'<FileStorage {self.original_filename}>'
    
    def get_file_size_formatted(self):
        """Format file size in human readable format"""
        if not self.file_size:
            return "Unknown"
        
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
    
    def get_best_url(self):
        """Get the best available URL for the file"""
        if self.cdn_url and self.cdn_sync_status == 'synced':
            return self.cdn_url
        elif self.cloud_storage_url:
            return self.cloud_storage_url
        elif self.local_storage_path:
            return f"/files/{self.id}/{self.stored_filename}"
        return None
    
    def verify_integrity(self):
        """Verify file integrity using hash"""
        if os.path.exists(self.file_path):
            import hashlib
            sha256_hash = hashlib.sha256()
            with open(self.file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            
            calculated_hash = sha256_hash.hexdigest()
            if calculated_hash == self.file_hash:
                self.integrity_check_status = 'verified'
                self.last_integrity_check = get_current_ist_datetime()
                db.session.commit()
                return True
            else:
                self.integrity_check_status = 'failed'
                db.session.commit()
                return False
        return False
    
    def mark_for_cleanup(self, days_from_now=30):
        """Mark file for automatic cleanup"""
        self.is_temporary = True
        self.cleanup_after = get_current_ist_datetime() + timedelta(days=days_from_now)
        db.session.commit()
    
    def increment_access(self):
        """Increment access count and update last accessed"""
        self.access_count += 1
        self.last_accessed = get_current_ist_datetime()
        db.session.commit()

# Initialize default settings when module is imported
def initialize_lms_content_settings():
    """Initialize default settings for LMS content management"""
    from models.lms_model import LMSSettings
    
    default_settings = [
        # Upload Settings
        ('max_video_file_size_mb', 2048, 'int', 'Maximum video file size in MB'),
        ('max_document_file_size_mb', 100, 'int', 'Maximum document file size in MB'),
        ('allowed_video_formats', ['mp4', 'avi', 'mov', 'wmv', 'flv'], 'json', 'Allowed video file formats'),
        ('allowed_document_formats', ['pdf', 'doc', 'docx', 'ppt', 'pptx'], 'json', 'Allowed document formats'),
        
        # Processing Settings
        ('auto_video_encoding', True, 'bool', 'Automatically encode uploaded videos'),
        ('video_quality_levels', ['480p', '720p', '1080p'], 'json', 'Available video quality levels'),
        ('auto_document_watermarking', True, 'bool', 'Automatically watermark documents'),
        ('auto_virus_scanning', True, 'bool', 'Automatically scan uploaded files for viruses'),
        
        # Workflow Settings
        ('content_approval_required', True, 'bool', 'Require approval before publishing content'),
        ('auto_approval_for_admins', False, 'bool', 'Auto-approve content uploaded by admins'),
        ('workflow_notification_enabled', True, 'bool', 'Send notifications for workflow actions'),
        
        # Storage Settings
        ('cdn_enabled', False, 'bool', 'Enable CDN for file distribution'),
        ('auto_backup_enabled', True, 'bool', 'Automatically backup uploaded files'),
        ('file_retention_days', 2555, 'int', 'Days to retain uploaded files (7 years)'),
        ('cleanup_temporary_files', True, 'bool', 'Automatically cleanup temporary files'),
        
        # Quiz Settings
        ('default_quiz_time_limit', 30, 'int', 'Default quiz time limit in minutes'),
        ('max_quiz_attempts', 3, 'int', 'Maximum quiz attempts per student'),
        ('auto_grade_objective_questions', True, 'bool', 'Automatically grade objective questions'),
        
        # Assignment Settings
        ('default_assignment_due_days', 7, 'int', 'Default days for assignment due date'),
        ('late_submission_penalty', 10, 'int', 'Late submission penalty percentage per day'),
        ('max_assignment_file_size_mb', 50, 'int', 'Maximum assignment file size in MB'),
    ]
    
    for key, value, setting_type, description in default_settings:
        existing = LMSSettings.query.filter_by(setting_key=key).first()
        if not existing:
            LMSSettings.set_setting(key, value, setting_type, description)
