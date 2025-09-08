"""
LMS Routes for Global IT Education Web App
Handles Internal Learning Management System - Course Delivery Platform
Business Logic: Course → Module → Section → (Video + PDF Material)
Security Features: DRM protection, watermarking, access logging, anti-piracy measures
"""

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash, current_app, send_file, abort
from functools import wraps
import logging
from datetime import datetime, timedelta
import os
import hashlib
import uuid
from io import BytesIO

# Import database
from init_db import db

# Import LMS models
from models.lms_model import (
    CourseModule, CourseSection, CourseVideo, CourseMaterial,
    StudentModuleProgress, StudentSectionProgress, StudentVideoProgress,
    MaterialDownloadLog, MaterialAccessLog, VideoAccessLog, SecurityViolationLog,
    CourseAnnouncement, StudentAssignment, AssignmentSubmission, StudentNotes, LMSSettings
)

# Import existing models
from models.student_model import Student
from models.course_model import Course
from models.user_model import User
from models.batch_model import Batch

# Import timezone helper
from utils.timezone_helper import get_current_ist_datetime, format_datetime_indian

# Set up logging
logger = logging.getLogger(__name__)

# Create Blueprint
lms_bp = Blueprint('lms', __name__, url_prefix='/lms')

def login_required(f):
    """Decorator to require login for LMS routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access the Learning Management System.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    """Decorator to require student role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'student':
            flash('This area is for students only.', 'error')
            return redirect(url_for('lms.admin_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') not in ['admin', 'super_admin']:
            flash('Administrator access required.', 'error')
            return redirect(url_for('lms.admin_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_student():
    """Get current student object if logged in as student"""
    if session.get('role') == 'student':
        student_id = session.get('student_id')
        return Student.query.filter_by(student_id=student_id).first()
    return None

def log_security_violation(violation_type, resource_type=None, resource_id=None, details=None):
    """Log security violation"""
    student = get_current_student()
    if student:
        SecurityViolationLog.log_violation(
            student_id=student.student_id,
            violation_type=violation_type,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            details=details
        )

def validate_session_token(token, resource_id, action='view'):
    """Validate session token for secure access"""
    try:
        student = get_current_student()
        if not student:
            return False
        
        # Basic token validation (implement more sophisticated validation as needed)
        expected_token_data = f"{student.student_id}:{resource_id}:{action}"
        expected_token = hashlib.sha256(expected_token_data.encode()).hexdigest()[:32]
        
        return token == expected_token
    except:
        return False

# =====================================
# MAIN LMS ROUTES - STUDENT INTERFACE
# =====================================

@lms_bp.route('/')
@login_required
def lms_index():
    """LMS Index - redirects to appropriate dashboard"""
    if session.get('role') == 'student':
        return redirect(url_for('lms.student_dashboard'))
    else:
        return redirect(url_for('lms.admin_dashboard'))

@lms_bp.route('/dashboard')
@login_required
@student_required
def student_dashboard():
    """Student Dashboard - Shows enrolled courses and learning progress"""
    try:
        student = get_current_student()
        if not student:
            flash('Student profile not found.', 'error')
            return redirect(url_for('index'))
        
        # Get student's enrolled course
        course = None
        if student.course_id:
            course = Course.query.get(student.course_id)
        
        if not course:
            flash('No course assigned. Please contact your administrator.', 'warning')
            return render_template('lms/student/no_course.html', student=student)
        
        # Get course modules and progress
        modules = CourseModule.query.filter_by(
            course_id=course.id
        ).order_by(CourseModule.module_order).all()
        
        # Calculate overall progress
        total_modules = len(modules)
        completed_modules = 0
        total_progress = 0
        
        for module in modules:
            progress = module.get_progress_for_student(student.student_id)
            if progress >= 100:
                completed_modules += 1
            total_progress += progress
        
        overall_progress = total_progress / total_modules if total_modules > 0 else 0
        
        # Get recent announcements
        announcements = CourseAnnouncement.query.filter_by(
            course_id=course.id
        ).filter(
            (CourseAnnouncement.expires_at.is_(None)) | 
            (CourseAnnouncement.expires_at >= get_current_ist_datetime())
        ).order_by(CourseAnnouncement.created_at.desc()).limit(5).all()
        
        # Get recent activity
        recent_progress = StudentSectionProgress.query.filter_by(
            student_id=student.student_id
        ).order_by(StudentSectionProgress.last_accessed.desc()).limit(10).all()
        
        return render_template('lms/student/dashboard.html',
                             student=student,
                             course=course,
                             modules=modules,
                             total_modules=total_modules,
                             completed_modules=completed_modules,
                             overall_progress=overall_progress,
                             announcements=announcements,
                             recent_progress=recent_progress)
                             
    except Exception as e:
        logger.error(f"Error loading student dashboard: {e}")
        flash('Error loading dashboard. Please try again.', 'error')
        return redirect(url_for('index'))

@lms_bp.route('/course/<int:course_id>')
@login_required
@student_required
def course_content(course_id):
    """Display course content structure for students"""
    try:
        student = get_current_student()
        if not student:
            flash('Student profile not found.', 'error')
            return redirect(url_for('lms.student_dashboard'))
        
        # Verify student is enrolled in this course
        if student.course_id != course_id:
            flash('You are not enrolled in this course.', 'error')
            return redirect(url_for('lms.student_dashboard'))
        
        course = Course.query.get_or_404(course_id)
        
        # Get course modules with sections
        modules = CourseModule.query.filter_by(
            course_id=course_id
        ).order_by(CourseModule.module_order).all()
        
        # Prepare modules with progress and sections
        modules_data = []
        for module in modules:
            module_progress = module.get_progress_for_student(student.student_id)
            
            # Get sections for this module
            sections = []
            for section in module.sections:
                section_progress = section.get_progress_for_student(student.student_id)
                section_data = {
                    'section': section,
                    'progress': section_progress,
                    'completed': section.is_completed_by_student(student.student_id),
                    'has_video': len(section.videos) > 0,
                    'has_material': len(section.materials) > 0
                }
                sections.append(section_data)
            
            modules_data.append({
                'module': module,
                'progress': module_progress,
                'completed': module.is_completed_by_student(student.student_id),
                'sections': sections
            })
        
        return render_template('lms/student/course_content.html',
                             course=course,
                             modules_data=modules_data,
                             student=student)
                             
    except Exception as e:
        logger.error(f"Error loading course content: {e}")
        flash('Error loading course content. Please try again.', 'error')
        return redirect(url_for('lms.student_dashboard'))

@lms_bp.route('/module/<int:module_id>')
@login_required
@student_required
def module_content(module_id):
    """Display module content with sections"""
    try:
        student = get_current_student()
        if not student:
            flash('Student profile not found.', 'error')
            return redirect(url_for('lms.student_dashboard'))
        
        module = CourseModule.query.get_or_404(module_id)
        
        # Verify student access to this module
        if module.course_id != student.course_id:
            flash('Access denied to this module.', 'error')
            return redirect(url_for('lms.student_dashboard'))
        
        # Get sections with progress
        sections_data = []
        for section in module.sections:
            section_progress = section.get_progress_for_student(student.student_id)
            video = section.get_video()
            material = section.get_material()
            
            sections_data.append({
                'section': section,
                'progress': section_progress,
                'completed': section.is_completed_by_student(student.student_id),
                'video': video,
                'material': material,
                'can_access': True  # Add access logic if needed
            })
        
        # Get or create module progress
        module_progress = StudentModuleProgress.query.filter_by(
            student_id=student.student_id,
            module_id=module_id
        ).first()
        
        if not module_progress:
            module_progress = StudentModuleProgress(
                student_id=student.student_id,
                module_id=module_id,
                started_at=get_current_ist_datetime()
            )
            db.session.add(module_progress)
            db.session.commit()
        
        return render_template('lms/student/module_content.html',
                             module=module,
                             sections_data=sections_data,
                             module_progress=module_progress,
                             student=student)
                             
    except Exception as e:
        logger.error(f"Error loading module content: {e}")
        flash('Error loading module content. Please try again.', 'error')
        return redirect(url_for('lms.student_dashboard'))
@lms_bp.route('/section/<int:section_id>')
@login_required
@student_required
def section_content(section_id):
    """Display section content with video and materials"""
    try:
        student = get_current_student()
        if not student:
            flash('Student profile not found.', 'error')
            return redirect(url_for('lms.student_dashboard'))
        
        section = CourseSection.query.get_or_404(section_id)
        
        # Verify student access
        if section.module.course_id != student.course_id:
            log_security_violation('unauthorized_access', 'section', section_id)
            flash('Access denied to this section.', 'error')
            return redirect(url_for('lms.student_dashboard'))
        
        # Get or create section progress
        section_progress = StudentSectionProgress.query.filter_by(
            student_id=student.student_id,
            section_id=section_id
        ).first()
        
        if not section_progress:
            section_progress = StudentSectionProgress(
                student_id=student.student_id,
                section_id=section_id,
                started_at=get_current_ist_datetime()
            )
            db.session.add(section_progress)
            db.session.commit()
        else:
            # Update last accessed time
            section_progress.last_accessed = get_current_ist_datetime()
            db.session.commit()
        
        # Get video and materials
        video = section.get_video()
        material = section.get_material()
        
        # Get video progress if video exists
        video_progress = None
        if video:
            video_progress = video.get_watch_progress_for_student(student.student_id)
        
        # Get student notes for this section
        notes = StudentNotes.query.filter_by(
            student_id=student.student_id,
            section_id=section_id
        ).first()
        
        # Get assignments for this section
        assignments = StudentAssignment.query.filter_by(
            section_id=section_id
        ).all()
        
        return render_template('lms/student/section_content.html',
                             section=section,
                             section_progress=section_progress,
                             video=video,
                             video_progress=video_progress,
                             material=material,
                             notes=notes,
                             assignments=assignments,
                             student=student)
                             
    except Exception as e:
        logger.error(f"Error loading section content: {e}")
        flash('Error loading section content. Please try again.', 'error')
        return redirect(url_for('lms.student_dashboard'))

# =====================================
# VIDEO STREAMING AND SECURITY ROUTES
# =====================================

@lms_bp.route('/video/<int:video_id>/embed')
@login_required
@student_required
def video_embed(video_id):
    """Secure video embed endpoint with DRM protection"""
    try:
        student = get_current_student()
        if not student:
            abort(403)
        
        video = CourseVideo.query.get_or_404(video_id)
        
        # Verify student access
        if video.section.module.course_id != student.course_id:
            log_security_violation('unauthorized_video_access', 'video', video_id)
            abort(403)
        
        # Check if student can access this video
        can_access, message = video.can_student_access(student.student_id)
        if not can_access:
            log_security_violation('video_access_denied', 'video', video_id, message)
            return jsonify({'error': message}), 403
        
        # Get secure embed URL
        secure_url = video.get_secure_embed_url(student.student_id, request.remote_addr)
        if not secure_url:
            abort(404)
        
        # Log access
        video.log_access(student.student_id, request.remote_addr, 'embed_request')
        
        # Get security configuration
        security_config = video.get_security_config()
        
        return render_template('lms/student/video_embed.html',
                             video=video,
                             secure_url=secure_url,
                             security_config=security_config,
                             student=student)
                             
    except Exception as e:
        logger.error(f"Error loading video embed: {e}")
        abort(500)

@lms_bp.route('/video/<int:video_id>/progress', methods=['POST'])
@login_required
@student_required
def update_video_progress():
    """Update video watch progress via AJAX"""
    try:
        data = request.get_json()
        video_id = data.get('video_id')
        current_position = data.get('current_position', 0)
        total_duration = data.get('total_duration', 0)
        
        student = get_current_student()
        if not student:
            return jsonify({'error': 'Student not found'}), 403
        
        video = CourseVideo.query.get_or_404(video_id)
        
        # Verify access
        if video.section.module.course_id != student.course_id:
            log_security_violation('unauthorized_progress_update', 'video', video_id)
            return jsonify({'error': 'Access denied'}), 403
        
        # Get or create video progress
        video_progress = StudentVideoProgress.query.filter_by(
            student_id=student.student_id,
            video_id=video_id
        ).first()
        
        if not video_progress:
            video_progress = StudentVideoProgress(
                student_id=student.student_id,
                video_id=video_id,
                first_watched=get_current_ist_datetime()
            )
            db.session.add(video_progress)
        
        # Update progress
        video_progress.update_watch_progress(current_position, total_duration)
        
        # Update section progress if video is completed
        if video_progress.is_completed:
            section_progress = StudentSectionProgress.query.filter_by(
                student_id=student.student_id,
                section_id=video.section_id
            ).first()
            
            if section_progress:
                section_progress.video_completed = True
                section_progress.check_auto_completion()
        
        return jsonify({
            'success': True,
            'completion_percentage': video_progress.completion_percentage,
            'is_completed': video_progress.is_completed
        })
        
    except Exception as e:
        logger.error(f"Error updating video progress: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@lms_bp.route('/secure-video/<int:video_id>/<token>')
@login_required
@student_required
def secure_video_stream(video_id, token):
    """Secure video streaming endpoint with token validation"""
    try:
        student = get_current_student()
        if not student:
            abort(403)
        
        # Validate token
        if not validate_session_token(token, video_id, 'stream'):
            log_security_violation('invalid_video_token', 'video', video_id)
            abort(403)
        
        video = CourseVideo.query.get_or_404(video_id)
        
        # Additional security checks
        can_access, message = video.can_student_access(student.student_id)
        if not can_access:
            log_security_violation('video_stream_denied', 'video', video_id, message)
            abort(403)
        
        # Log streaming session start
        video.log_access(student.student_id, request.remote_addr, 'stream_start')
        video.increment_view_count()
        
        # For security, redirect to actual video URL or serve from secure location
        # This is a placeholder - implement your actual video serving logic
        if video.video_type == 'youtube':
            return redirect(f"https://www.youtube.com/watch?v={video.video_id}")
        else:
            # Serve from secure local storage
            return send_file(video.file_url, as_attachment=False)
            
    except Exception as e:
        logger.error(f"Error streaming video: {e}")
        abort(500)

# =====================================
# MATERIAL ACCESS AND SECURITY ROUTES
# =====================================

@lms_bp.route('/material/<int:material_id>/view')
@login_required
@student_required
def view_material(material_id):
    """Secure material viewer with copy protection"""
    try:
        student = get_current_student()
        if not student:
            flash('Student profile not found.', 'error')
            return redirect(url_for('lms.student_dashboard'))
        
        material = CourseMaterial.query.get_or_404(material_id)
        
        # Verify student access
        if material.section.module.course_id != student.course_id:
            log_security_violation('unauthorized_material_access', 'material', material_id)
            flash('Access denied to this material.', 'error')
            return redirect(url_for('lms.student_dashboard'))
        
        # Check access permissions
        can_access, message = material.can_student_access(student.student_id, 'view')
        if not can_access:
            log_security_violation('material_access_denied', 'material', material_id, message)
            flash(message, 'error')
            return redirect(url_for('lms.section_content', section_id=material.section_id))
        
        # Log access
        material.log_access(student.student_id, 'view', request.remote_addr)
        
        # Get security configuration
        security_config = material.get_security_config()
        watermark_text = material.get_watermark_text(student.student_id)
        
        # Get secure access URL
        secure_url = material.get_secure_access_url(student.student_id, 'view', request.remote_addr)
        
        return render_template('lms/student/material_viewer.html',
                             material=material,
                             security_config=security_config,
                             watermark_text=watermark_text,
                             secure_url=secure_url,
                             student=student)
                             
    except Exception as e:
        logger.error(f"Error viewing material: {e}")
        flash('Error loading material. Please try again.', 'error')
        return redirect(url_for('lms.student_dashboard'))

@lms_bp.route('/material/<int:material_id>/download')
@login_required
@student_required
def download_material(material_id):
    """Secure material download with logging"""
    try:
        student = get_current_student()
        if not student:
            abort(403)
        
        material = CourseMaterial.query.get_or_404(material_id)
        
        # Verify student access
        if material.section.module.course_id != student.course_id:
            log_security_violation('unauthorized_download_attempt', 'material', material_id)
            abort(403)
        
        # Check download permissions
        can_access, message = material.can_student_access(student.student_id, 'download')
        if not can_access:
            log_security_violation('material_download_denied', 'material', material_id, message)
            flash(message, 'error')
            return redirect(url_for('lms.section_content', section_id=material.section_id))
        
        # Log download
        material.log_access(student.student_id, 'download', request.remote_addr)
        material.increment_download_count(student.student_id)
        
        # Update section progress
        section_progress = StudentSectionProgress.query.filter_by(
            student_id=student.student_id,
            section_id=material.section_id
        ).first()
        
        if section_progress:
            section_progress.material_downloaded = True
            section_progress.check_auto_completion()
            db.session.commit()
        
        # Serve file with security headers
        try:
            response = send_file(
                material.file_url,
                as_attachment=True,
                download_name=material.original_filename or material.material_name
            )
            
            # Add security headers
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            
            return response
            
        except FileNotFoundError:
            flash('File not found. Please contact support.', 'error')
            return redirect(url_for('lms.section_content', section_id=material.section_id))
            
    except Exception as e:
        logger.error(f"Error downloading material: {e}")
        abort(500)

@lms_bp.route('/secure-viewer/<int:material_id>/<token>')
@login_required
@student_required
def secure_material_viewer(material_id, token):
    """Secure material viewer with token validation"""
    try:
        student = get_current_student()
        if not student:
            abort(403)
        
        # Validate token
        if not validate_session_token(token, material_id, 'view'):
            log_security_violation('invalid_material_token', 'material', material_id)
            abort(403)
        
        material = CourseMaterial.query.get_or_404(material_id)
        
        # Additional security checks
        can_access, message = material.can_student_access(student.student_id, 'view')
        if not can_access:
            log_security_violation('secure_viewer_denied', 'material', material_id, message)
            abort(403)
        
        # For PDF files, render in secure viewer
        if material.material_type.lower() == 'pdf':
            return render_template('lms/student/pdf_viewer.html',
                                 material=material,
                                 student=student,
                                 watermark=material.get_watermark_text(student.student_id))
        else:
            # For other file types, serve directly with security headers
            return send_file(material.file_url, as_attachment=False)
            
    except Exception as e:
        logger.error(f"Error in secure viewer: {e}")
        abort(500)

# =====================================
# STUDENT PROGRESS AND NOTES ROUTES
# =====================================

@lms_bp.route('/notes/save', methods=['POST'])
@login_required
@student_required
def save_notes():
    """Save student notes for a section"""
    try:
        data = request.get_json()
        section_id = data.get('section_id')
        note_content = data.get('content', '').strip()
        
        student = get_current_student()
        if not student:
            return jsonify({'error': 'Student not found'}), 403
        
        section = CourseSection.query.get_or_404(section_id)
        
        # Verify access
        if section.module.course_id != student.course_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get or create notes
        notes = StudentNotes.query.filter_by(
            student_id=student.student_id,
            section_id=section_id
        ).first()
        
        if not notes:
            notes = StudentNotes(
                student_id=student.student_id,
                section_id=section_id,
                note_content=note_content
            )
            db.session.add(notes)
        else:
            notes.note_content = note_content
            notes.updated_at = get_current_ist_datetime()
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Notes saved successfully'})
        
    except Exception as e:
        logger.error(f"Error saving notes: {e}")
        return jsonify({'error': 'Failed to save notes'}), 500

@lms_bp.route('/progress/overview')
@login_required
@student_required
def progress_overview():
    """Student progress overview page"""
    try:
        student = get_current_student()
        if not student:
            flash('Student profile not found.', 'error')
            return redirect(url_for('lms.student_dashboard'))
        
        # Get course and modules
        course = Course.query.get(student.course_id) if student.course_id else None
        if not course:
            flash('No course assigned.', 'warning')
            return redirect(url_for('lms.student_dashboard'))
        
        modules = CourseModule.query.filter_by(
            course_id=course.id
        ).order_by(CourseModule.module_order).all()
        
        # Calculate detailed progress
        progress_data = []
        total_completion = 0
        total_time_spent = 0
        
        for module in modules:
            module_progress = StudentModuleProgress.query.filter_by(
                student_id=student.student_id,
                module_id=module.id
            ).first()
            
            sections_progress = []
            for section in module.sections:
                section_progress = StudentSectionProgress.query.filter_by(
                    student_id=student.student_id,
                    section_id=section.id
                ).first()
                
                sections_progress.append({
                    'section': section,
                    'progress': section_progress.progress_percentage if section_progress else 0,
                    'time_spent': section_progress.time_spent if section_progress else 0,
                    'completed': section_progress.is_completed if section_progress else False
                })
            
            module_data = {
                'module': module,
                'progress': module_progress.progress_percentage if module_progress else 0,
                'time_spent': module_progress.time_spent if module_progress else 0,
                'completed': module_progress.is_completed if module_progress else False,
                'sections': sections_progress
            }
            
            progress_data.append(module_data)
            
            if module_progress:
                total_completion += module_progress.progress_percentage
                total_time_spent += module_progress.time_spent
        
        overall_completion = total_completion / len(modules) if modules else 0
        
        return render_template('lms/student/progress_overview.html',
                             course=course,
                             progress_data=progress_data,
                             overall_completion=overall_completion,
                             total_time_spent=total_time_spent,
                             student=student)
                             
    except Exception as e:
        logger.error(f"Error loading progress overview: {e}")
        flash('Error loading progress overview.', 'error')
        return redirect(url_for('lms.student_dashboard'))

# =====================================
# ADMIN DASHBOARD AND MANAGEMENT
# =====================================

@lms_bp.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    """Admin dashboard for LMS management"""
    try:
        # Get overall statistics
        total_courses = Course.query.count()
        total_modules = CourseModule.query.count()
        total_sections = CourseSection.query.count()
        total_videos = CourseVideo.query.count()
        total_materials = CourseMaterial.query.count()
        
        # Get student statistics
        total_students = Student.query.filter_by(is_deleted=0, status='Active').count()
        active_students = StudentSectionProgress.query.filter(
            StudentSectionProgress.last_accessed >= get_current_ist_datetime() - timedelta(days=7)
        ).distinct(StudentSectionProgress.student_id).count()
        
        # Get recent activity
        recent_progress = StudentSectionProgress.query.order_by(
            StudentSectionProgress.last_accessed.desc()
        ).limit(10).all()
        
        # Get security violations
        recent_violations = SecurityViolationLog.query.order_by(
            SecurityViolationLog.created_at.desc()
        ).limit(10).all()
        
        # Get popular content
        popular_videos = CourseVideo.query.order_by(
            CourseVideo.view_count.desc()
        ).limit(5).all()
        
        return render_template('lms/lms_dashboard.html',
                             total_courses=total_courses,
                             total_modules=total_modules,
                             total_sections=total_sections,
                             total_videos=total_videos,
                             total_materials=total_materials,
                             total_students=total_students,
                             active_students=active_students,
                             recent_progress=recent_progress,
                             recent_violations=recent_violations,
                             popular_videos=popular_videos,
                             is_admin_view=True)
                             
    except Exception as e:
        logger.error(f"Error loading admin dashboard: {e}")
        flash('Error loading admin dashboard.', 'error')
        return redirect(url_for('index'))

@lms_bp.route('/admin/courses')
@login_required
@admin_required
def admin_courses():
    """Admin course management"""
    try:
        courses = Course.query.all()
        
        # Get course statistics
        course_stats = []
        for course in courses:
            modules_count = CourseModule.query.filter_by(course_id=course.id).count()
            students_count = Student.query.filter_by(course_id=course.id, is_deleted=0).count()
            
            course_stats.append({
                'course': course,
                'modules_count': modules_count,
                'students_count': students_count
            })
        
        return render_template('lms/admin/courses.html', course_stats=course_stats)
        
    except Exception as e:
        logger.error(f"Error loading admin courses: {e}")
        flash('Error loading courses.', 'error')
        return redirect(url_for('lms.admin_dashboard'))

@lms_bp.route('/admin/course/<int:course_id>/modules')
@login_required
@admin_required
def admin_course_modules(course_id):
    """Admin module management for a course"""
    try:
        course = Course.query.get_or_404(course_id)
        modules = CourseModule.query.filter_by(course_id=course_id).order_by(CourseModule.module_order).all()
        
        # Get module statistics
        module_stats = []
        for module in modules:
            sections_count = CourseSection.query.filter_by(module_id=module.id).count()
            students_progress = StudentModuleProgress.query.filter_by(module_id=module.id).all()
            avg_progress = sum([p.progress_percentage for p in students_progress]) / len(students_progress) if students_progress else 0
            
            module_stats.append({
                'module': module,
                'sections_count': sections_count,
                'students_count': len(students_progress),
                'avg_progress': avg_progress
            })
        
        return render_template('lms/admin/course_modules.html',
                             course=course,
                             module_stats=module_stats)
        
    except Exception as e:
        logger.error(f"Error loading course modules: {e}")
        flash('Error loading modules.', 'error')
        return redirect(url_for('lms.admin_courses'))

@lms_bp.route('/admin/security/violations')
@login_required
@admin_required
def admin_security_violations():
    """Admin security violations monitoring"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        violations = SecurityViolationLog.query.order_by(
            SecurityViolationLog.created_at.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)
        
        # Get violation statistics
        total_violations = SecurityViolationLog.query.count()
        today_violations = SecurityViolationLog.query.filter(
            SecurityViolationLog.created_at >= get_current_ist_datetime().replace(hour=0, minute=0, second=0)
        ).count()
        
        # Get violation types count
        violation_types = db.session.query(
            SecurityViolationLog.violation_type,
            db.func.count(SecurityViolationLog.id).label('count')
        ).group_by(SecurityViolationLog.violation_type).all()
        
        return render_template('lms/admin/security_violations.html',
                             violations=violations,
                             total_violations=total_violations,
                             today_violations=today_violations,
                             violation_types=violation_types)
        
    except Exception as e:
        logger.error(f"Error loading security violations: {e}")
        flash('Error loading security violations.', 'error')
        return redirect(url_for('lms.admin_dashboard'))

@lms_bp.route('/admin/settings')
@login_required
@admin_required
def admin_settings():
    """Admin LMS settings management"""
    try:
        # Initialize default settings if not exists
        LMSSettings.initialize_default_security_settings()
        
        # Get all settings grouped by category
        security_settings = [
            'video_downloads_enabled',
            'material_copy_protection',
            'video_watermark_enabled',
            'material_watermark_enabled',
            'right_click_protection',
            'developer_tools_detection',
            'screenshot_protection',
            'video_drm_protection',
            'material_print_protection'
        ]
        
        session_settings = [
            'max_concurrent_video_sessions',
            'session_timeout_minutes'
        ]
        
        violation_settings = [
            'security_logging_enabled',
            'automatic_violation_response',
            'violation_warning_threshold',
            'violation_suspension_threshold'
        ]
        
        settings_data = {
            'security': {setting: LMSSettings.get_setting(setting) for setting in security_settings},
            'session': {setting: LMSSettings.get_setting(setting) for setting in session_settings},
            'violation': {setting: LMSSettings.get_setting(setting) for setting in violation_settings}
        }
        
        return render_template('lms/admin/settings.html', settings_data=settings_data)
        
    except Exception as e:
        logger.error(f"Error loading admin settings: {e}")
        flash('Error loading settings.', 'error')
        return redirect(url_for('lms.admin_dashboard'))

@lms_bp.route('/admin/settings/update', methods=['POST'])
@login_required
@admin_required
def update_admin_settings():
    """Update LMS admin settings"""
    try:
        data = request.get_json()
        
        for setting_key, setting_value in data.items():
            # Determine setting type
            if isinstance(setting_value, bool):
                setting_type = 'bool'
            elif isinstance(setting_value, int):
                setting_type = 'int'
            else:
                setting_type = 'string'
            
            LMSSettings.set_setting(setting_key, setting_value, setting_type)
        
        return jsonify({'success': True, 'message': 'Settings updated successfully'})
        
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        return jsonify({'error': 'Failed to update settings'}), 500

# =====================================
# API ROUTES FOR AJAX OPERATIONS
# =====================================

@lms_bp.route('/api/student/progress/<int:course_id>')
@login_required
@student_required
def api_student_progress(course_id):
    """API endpoint for student progress data"""
    try:
        student = get_current_student()
        if not student or student.course_id != course_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get overall progress
        modules = CourseModule.query.filter_by(course_id=course_id).all()
        progress_data = []
        
        for module in modules:
            module_progress = module.get_progress_for_student(student.student_id)
            progress_data.append({
                'module_id': module.id,
                'module_name': module.module_name,
                'progress': module_progress,
                'completed': module.is_completed_by_student(student.student_id)
            })
        
        return jsonify({
            'success': True,
            'progress_data': progress_data
        })
        
    except Exception as e:
        logger.error(f"Error getting student progress: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@lms_bp.route('/api/security/report', methods=['POST'])
@login_required
def api_report_security_violation():
    """API endpoint for reporting security violations from frontend"""
    try:
        data = request.get_json()
        violation_type = data.get('violation_type')
        resource_type = data.get('resource_type')
        resource_id = data.get('resource_id')
        details = data.get('details')
        
        log_security_violation(violation_type, resource_type, resource_id, details)
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error reporting security violation: {e}")
        return jsonify({'error': 'Failed to report violation'}), 500

# =====================================
# ERROR HANDLERS
# =====================================

@lms_bp.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors in LMS"""
    return render_template('lms/errors/404.html'), 404

@lms_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors in LMS"""
    return render_template('lms/errors/500.html'), 500

@lms_bp.errorhandler(403)
def forbidden_error(error):
    """Handle 403 errors in LMS"""
    return render_template('lms/errors/403.html'), 403
