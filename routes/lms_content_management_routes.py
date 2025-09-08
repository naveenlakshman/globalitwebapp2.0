# LMS Content Management Routes - Admin Upload & Content Creation Routes
# Global IT Education Management System - Content Management Routes
# Purpose: Handle API endpoints for video/document uploads, quiz creation, assignment building, and workflows
# Integration: Works with lms_content_management_model.py for complete content management

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash, send_file, abort
from werkzeug.utils import secure_filename
import json
from models.lms_content_management_model import (
    VideoUpload, DocumentUpload, Quiz, QuizQuestion, QuizAttempt, 
    AssignmentCreator, ContentWorkflow, FileStorage, UploadStatus, WorkflowStage
)
from models.lms_model import CourseModule, CourseSection, LMSSettings
from models.course_model import Course
from models.user_model import User
from models.student_model import Student
from init_db import db
from utils.timezone_helper import get_current_ist_datetime, format_datetime_indian
import os
import json
import hashlib
import mimetypes
from datetime import datetime, timedelta
import uuid

# Create Blueprint
lms_content_management = Blueprint('lms_content_management', __name__, url_prefix='/admin/content')

# Helper Functions
def allowed_file(filename, allowed_extensions):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def get_file_hash(file_path):
    """Calculate SHA256 hash of file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def require_admin():
    """Decorator to require admin access"""
    def decorator(f):
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('auth.login'))
            
            user = User.query.get(session['user_id'])
            if not user or user.role not in ['admin', 'super_admin', 'content_manager']:
                flash('Access denied. Admin privileges required.', 'error')
                return redirect(url_for('index'))
            
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

# ==================== DASHBOARD & OVERVIEW ====================

@lms_content_management.route('/')
@require_admin()
def dashboard():
    """Content management dashboard"""
    # Get statistics
    stats = {
        'videos': {
            'total': VideoUpload.query.count(),
            'pending': VideoUpload.query.filter_by(workflow_stage='draft').count(),
            'processing': VideoUpload.query.filter_by(upload_status='processing').count(),
            'approved': VideoUpload.query.filter_by(workflow_stage='approved').count()
        },
        'documents': {
            'total': DocumentUpload.query.count(),
            'pending': DocumentUpload.query.filter_by(workflow_stage='draft').count(),
            'processing': DocumentUpload.query.filter_by(upload_status='processing').count(),
            'approved': DocumentUpload.query.filter_by(workflow_stage='approved').count()
        },
        'quizzes': {
            'total': Quiz.query.count(),
            'draft': Quiz.query.filter_by(workflow_stage='draft').count(),
            'published': Quiz.query.filter_by(is_published=True).count(),
            'total_attempts': QuizAttempt.query.count()
        },
        'assignments': {
            'total': AssignmentCreator.query.count(),
            'draft': AssignmentCreator.query.filter_by(workflow_stage='draft').count(),
            'published': AssignmentCreator.query.filter_by(workflow_stage='published').count()
        }
    }
    
    # Recent activities
    recent_videos = VideoUpload.query.order_by(VideoUpload.upload_started_at.desc()).limit(5).all()
    recent_documents = DocumentUpload.query.order_by(DocumentUpload.upload_started_at.desc()).limit(5).all()
    
    # Pending approvals
    pending_workflows = ContentWorkflow.query.filter_by(workflow_stage='review').limit(10).all()
    
    return render_template('admin/content/content_dashboard.html', 
                         stats=stats, 
                         recent_videos=recent_videos,
                         recent_documents=recent_documents,
                         pending_workflows=pending_workflows)

# ==================== VIDEO UPLOAD ROUTES ====================

@lms_content_management.route('/videos')
@require_admin()
def video_list():
    """List all video uploads"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')
    course_id = request.args.get('course_id', type=int)
    
    query = VideoUpload.query
    
    if status != 'all':
        query = query.filter_by(workflow_stage=status)
    
    if course_id:
        query = query.filter_by(course_id=course_id)
    
    videos = query.order_by(VideoUpload.upload_started_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    courses = Course.query.filter_by(status='Active').all()
    
    return render_template('admin/content/video_list.html', 
                         videos=videos, 
                         courses=courses,
                         current_status=status,
                         current_course_id=course_id)

@lms_content_management.route('/videos/upload')
@require_admin()
def video_upload_form():
    """Show video upload form"""
    courses = Course.query.filter_by(status='Active').all()
    max_file_size = LMSSettings.get_setting('max_video_file_size_mb', 2048)
    allowed_formats = LMSSettings.get_setting('allowed_video_formats', ['mp4', 'avi', 'mov'])
    
    return render_template('admin/content/video_upload.html', 
                         courses=courses,
                         max_file_size=max_file_size,
                         allowed_formats=allowed_formats)

@lms_content_management.route('/videos/upload', methods=['POST'])
@require_admin()
def video_upload_process():
    """Process video upload"""
    try:
        # Validate form data
        course_id = request.form.get('course_id', type=int)
        module_id = request.form.get('module_id', type=int)
        section_id = request.form.get('section_id', type=int)
        video_title = request.form.get('video_title')
        video_description = request.form.get('video_description', '')
        upload_type = request.form.get('upload_type', 'file')  # 'file' or 'youtube'
        
        if not all([course_id, module_id, section_id, video_title]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        if upload_type == 'youtube':
            return process_youtube_upload(course_id, module_id, section_id, video_title, video_description, request.form.get('upload_notes', ''))
        else:
            return process_file_upload(course_id, module_id, section_id, video_title, video_description)
            
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

def process_youtube_upload(course_id, module_id, section_id, video_title, video_description, upload_notes=None):
    """Process YouTube URL upload"""
    try:
        youtube_url = request.form.get('youtube_url')
        if not youtube_url:
            return jsonify({'error': 'YouTube URL is required'}), 400
        
        # Extract YouTube video ID
        import re
        youtube_patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]+)',
            r'youtube\.com\/embed\/([a-zA-Z0-9_-]+)'
        ]
        
        video_id = None
        for pattern in youtube_patterns:
            match = re.search(pattern, youtube_url)
            if match:
                video_id = match.group(1)
                break
        
        if not video_id:
            return jsonify({'error': 'Invalid YouTube URL'}), 400
        
        # Create VideoUpload record for YouTube video
        video_upload = VideoUpload(
            course_id=course_id,
            module_id=module_id,
            section_id=section_id,
            original_filename=f"youtube_{video_id}.mp4",
            file_path=youtube_url,  # Store YouTube URL in file_path
            file_size=0,  # YouTube videos don't have file size
            file_format='youtube',
            file_hash=f"youtube_{video_id}",
            video_title=video_title,
            video_description=video_description,
            upload_notes=upload_notes,
            upload_status='completed',
            encoding_status='completed',
            workflow_stage='approved',
            uploaded_by=session.get('user_id')
        )
        
        db.session.add(video_upload)
        db.session.commit()
        
        # For YouTube videos, create CourseVideo record directly since no processing is needed
        from models.lms_model import CourseVideo
        
        course_video = CourseVideo(
            section_id=section_id,
            video_title=video_title,
            video_url=youtube_url,
            video_description=video_description,
            video_type='youtube',
            video_id=video_id,  # Store YouTube video ID
            is_active=True,
            is_downloadable=False,
            streaming_only=True,
            drm_protected=True,
            watermark_enabled=True,
            copy_protection=True
        )
        
        db.session.add(course_video)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'YouTube video added successfully',
            'video_id': video_upload.id,
            'course_video_id': course_video.id
        })
        
    except Exception as e:
        return jsonify({'error': f'YouTube upload failed: {str(e)}'}), 500

def process_file_upload(course_id, module_id, section_id, video_title, video_description):
    """Process file upload"""
    try:
        # Validate file
        if 'video_file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['video_file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Check file extension
        allowed_formats = LMSSettings.get_setting('allowed_video_formats', ['mp4', 'avi', 'mov'])
        if not allowed_file(file.filename, allowed_formats):
            return jsonify({'error': f'File type not allowed. Allowed: {", ".join(allowed_formats)}'}), 400
        
        # Create upload directory
        upload_dir = os.path.join('uploads', 'videos', str(course_id), str(module_id))
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        # Save file
        file.save(file_path)
        file_size = os.path.getsize(file_path)
        file_hash = get_file_hash(file_path)
        
        # Create VideoUpload record
        video_upload = VideoUpload(
            course_id=course_id,
            module_id=module_id,
            section_id=section_id,
            original_filename=secure_filename(file.filename),
            file_path=file_path,
            file_size=file_size,
            file_format=file_extension,
            file_hash=file_hash,
            video_title=video_title,
            video_description=video_description,
            upload_status='uploading',
            workflow_stage='draft',
            uploaded_by=session['user_id']
        )
        
        db.session.add(video_upload)
        db.session.commit()
        
        # Create file storage record
        file_storage = FileStorage(
            original_filename=file.filename,
            stored_filename=unique_filename,
            file_path=file_path,
            file_size=file_size,
            file_type='video',
            mime_type=mimetypes.guess_type(file.filename)[0],
            file_hash=file_hash,
            content_type='video_upload',
            content_id=video_upload.id,
            uploaded_by=session['user_id']
        )
        
        db.session.add(file_storage)
        db.session.commit()
        
        # Update upload progress to completed
        video_upload.update_upload_progress(100)
        
        return jsonify({
            'success': True,
            'video_id': video_upload.id,
            'message': 'Video uploaded successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@lms_content_management.route('/videos/<int:video_id>')
@require_admin()
def video_detail(video_id):
    """Show video upload details"""
    video = VideoUpload.query.get_or_404(video_id)
    
    return render_template('admin/content/video_detail.html', video=video)

@lms_content_management.route('/videos/<int:video_id>/approve', methods=['POST'])
@require_admin()
def approve_video(video_id):
    """Approve video for publishing"""
    video = VideoUpload.query.get_or_404(video_id)
    comments = request.form.get('comments', '')
    
    try:
        course_video = video.approve_video(session['user_id'], comments)
        if course_video:
            flash('Video approved and published successfully!', 'success')
        else:
            flash('Failed to approve video. Please check video status.', 'error')
    except Exception as e:
        flash(f'Error approving video: {str(e)}', 'error')
    
    return redirect(url_for('lms_content_management.video_detail', video_id=video_id))

@lms_content_management.route('/videos/<int:video_id>/reject', methods=['POST'])
@require_admin()
def reject_video(video_id):
    """Reject video with reason"""
    video = VideoUpload.query.get_or_404(video_id)
    reason = request.form.get('reason', '')
    
    if not reason:
        flash('Rejection reason is required.', 'error')
        return redirect(url_for('lms_content_management.video_detail', video_id=video_id))
    
    try:
        video.reject_video(session['user_id'], reason)
        flash('Video rejected successfully.', 'info')
    except Exception as e:
        flash(f'Error rejecting video: {str(e)}', 'error')
    
    return redirect(url_for('lms_content_management.video_detail', video_id=video_id))

# ==================== DOCUMENT UPLOAD ROUTES ====================

@lms_content_management.route('/documents')
@require_admin()
def document_list():
    """List all document uploads"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')
    course_id = request.args.get('course_id', type=int)
    
    query = DocumentUpload.query
    
    if status != 'all':
        query = query.filter_by(workflow_stage=status)
    
    if course_id:
        query = query.filter_by(course_id=course_id)
    
    documents = query.order_by(DocumentUpload.upload_started_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    courses = Course.query.filter_by(status='Active').all()
    
    return render_template('admin/content/document_list.html', 
                         documents=documents, 
                         courses=courses,
                         current_status=status,
                         current_course_id=course_id)

@lms_content_management.route('/documents/upload')
@require_admin()
def document_upload_form():
    """Show document upload form"""
    courses = Course.query.filter_by(status='Active').all()
    max_file_size = LMSSettings.get_setting('max_document_file_size_mb', 100)
    allowed_formats = LMSSettings.get_setting('allowed_document_formats', ['pdf', 'doc', 'docx'])
    
    return render_template('admin/content/document_upload.html', 
                         courses=courses,
                         max_file_size=max_file_size,
                         allowed_formats=allowed_formats)

@lms_content_management.route('/documents/upload', methods=['POST'])
@require_admin()
def document_upload_process():
    """Process document upload"""
    try:
        # Validate form data
        course_id = request.form.get('course_id', type=int)
        module_id = request.form.get('module_id', type=int)
        section_id = request.form.get('section_id', type=int)
        document_title = request.form.get('document_title')
        document_description = request.form.get('document_description', '')
        is_downloadable = request.form.get('is_downloadable') == 'on'
        upload_type = request.form.get('upload_type', 'file')
        upload_notes = request.form.get('upload_notes', '')
        
        if not all([course_id, module_id, section_id, document_title]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        if upload_type == 'cloud':
            return process_cloud_document(course_id, module_id, section_id, document_title, 
                                        document_description, is_downloadable, upload_notes)
        else:
            return process_file_document(course_id, module_id, section_id, document_title, 
                                       document_description, is_downloadable, upload_notes)
            
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

def process_cloud_document(course_id, module_id, section_id, document_title, document_description, is_downloadable, upload_notes):
    """Process cloud document upload"""
    try:
        cloud_url = request.form.get('cloud_url')
        cloud_type = request.form.get('cloud_type')
        
        if not cloud_url or not cloud_type:
            return jsonify({'error': 'Cloud URL and type are required'}), 400
        
        # Create DocumentUpload record for cloud document
        document_upload = DocumentUpload(
            course_id=course_id,
            module_id=module_id,
            section_id=section_id,
            original_filename=f"cloud_{cloud_type}_document",
            file_path=cloud_url,  # Store cloud URL in file_path
            file_size=0,  # Cloud documents don't have file size
            file_format=cloud_type,
            file_hash=f"cloud_{cloud_type}_{hash(cloud_url)}",
            document_title=document_title,
            document_description=document_description,
            is_downloadable=is_downloadable,
            upload_notes=upload_notes,
            upload_status='completed',
            workflow_stage='approved',  # Cloud docs can be auto-approved
            uploaded_by=session.get('user_id')
        )
        
        db.session.add(document_upload)
        db.session.commit()
        
        # For cloud documents, create CourseMaterial record directly
        from models.lms_model import CourseMaterial
        
        course_material = CourseMaterial(
            section_id=section_id,
            material_name=document_title,
            material_type=cloud_type,
            file_url=cloud_url,
            original_filename=f"cloud_{cloud_type}_document",
            file_size=0,
            description=document_description,
            is_downloadable=is_downloadable,
            is_active=True,
            copy_protection=True,
            print_protection=True,
            watermark_enabled=True,
            encryption_enabled=False,  # Cloud docs don't need local encryption
            secure_viewer_only=False,  # Cloud docs open in their native viewers
            access_level='student'
        )
        
        db.session.add(course_material)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'document_id': document_upload.id,
            'course_material_id': course_material.id,
            'message': 'Cloud document added successfully'
        })
        
    except Exception as e:
        return jsonify({'error': f'Cloud document upload failed: {str(e)}'}), 500

def process_file_document(course_id, module_id, section_id, document_title, document_description, is_downloadable, upload_notes):
    """Process file document upload"""
    try:
        # Validate file
        if 'document_file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['document_file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Check file extension
        allowed_formats = LMSSettings.get_setting_value('allowed_document_formats', ['pdf', 'doc', 'docx'])
        if not allowed_file(file.filename, allowed_formats):
            return jsonify({'error': f'File type not allowed. Allowed: {", ".join(allowed_formats)}'}), 400
        
        # Create upload directory
        upload_dir = os.path.join('uploads', 'documents', str(course_id), str(module_id))
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        # Save file
        file.save(file_path)
        file_size = os.path.getsize(file_path)
        file_hash = get_file_hash(file_path)
        
        # Create DocumentUpload record
        document_upload = DocumentUpload(
            course_id=course_id,
            module_id=module_id,
            section_id=section_id,
            original_filename=secure_filename(file.filename),
            file_path=file_path,
            file_size=file_size,
            file_format=file_extension,
            file_hash=file_hash,
            document_title=document_title,
            document_description=document_description,
            is_downloadable=is_downloadable,
            upload_notes=upload_notes,
            upload_status='uploading',
            workflow_stage='draft',
            uploaded_by=session['user_id']
        )
        
        db.session.add(document_upload)
        db.session.commit()
        
        # Update upload progress
        document_upload.update_upload_progress(100)
        
        return jsonify({
            'success': True,
            'document_id': document_upload.id,
            'message': 'Document uploaded successfully'
        })
        
    except Exception as e:
        return jsonify({'error': f'File upload failed: {str(e)}'}), 500

@lms_content_management.route('/documents/<int:document_id>')
@require_admin()
def document_detail(document_id):
    """Show document upload details"""
    document = DocumentUpload.query.get_or_404(document_id)
    
    return render_template('admin/content/document_detail.html', document=document)

@lms_content_management.route('/documents/<int:document_id>/edit')
@require_admin()
def document_edit(document_id):
    """Edit document upload information"""
    document = DocumentUpload.query.get_or_404(document_id)
    
    # Only allow editing for draft or rejected documents
    if document.workflow_stage not in ['draft', 'rejected']:
        flash('Document cannot be edited in current stage.', 'error')
        return redirect(url_for('lms_content_management.document_detail', document_id=document_id))
    
    courses = Course.query.filter_by(status='Active').all()
    return render_template('admin/content/document_edit.html', document=document, courses=courses)

@lms_content_management.route('/documents/<int:document_id>/edit', methods=['POST'])
@require_admin()
def document_edit_process(document_id):
    """Process document edit form"""
    document = DocumentUpload.query.get_or_404(document_id)
    
    # Only allow editing for draft or rejected documents
    if document.workflow_stage not in ['draft', 'rejected']:
        flash('Document cannot be edited in current stage.', 'error')
        return redirect(url_for('lms_content_management.document_detail', document_id=document_id))
    
    try:
        # Update document information
        document.document_title = request.form.get('document_title', '').strip()
        document.document_description = request.form.get('document_description', '').strip()
        document.course_id = int(request.form.get('course_id'))
        document.module_id = int(request.form.get('module_id'))
        document.section_id = int(request.form.get('section_id'))
        document.is_downloadable = 'is_downloadable' in request.form
        document.view_only_mode = 'view_only_mode' in request.form
        document.requires_video_completion = 'requires_video_completion' in request.form
        document.access_level = request.form.get('access_level', 'student')
        document.upload_notes = request.form.get('upload_notes', '').strip()
        
        # Security settings
        document.copy_protection_applied = 'copy_protection' in request.form
        document.print_protection_applied = 'print_protection' in request.form
        document.watermark_applied = 'watermark_enabled' in request.form
        
        # Reset workflow stage to draft if it was rejected
        if document.workflow_stage == 'rejected':
            document.workflow_stage = 'draft'
            document.rejection_reason = None
        
        db.session.commit()
        flash('Document updated successfully!', 'success')
        return redirect(url_for('lms_content_management.document_detail', document_id=document_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating document: {str(e)}', 'error')
        return redirect(url_for('lms_content_management.document_edit', document_id=document_id))

@lms_content_management.route('/documents/<int:document_id>/approve', methods=['POST'])
@require_admin()
def approve_document(document_id):
    """Approve document for publishing"""
    document = DocumentUpload.query.get_or_404(document_id)
    comments = request.form.get('comments', '')
    
    try:
        course_material = document.approve_document(session['user_id'], comments)
        if course_material:
            flash('Document approved and published successfully!', 'success')
        else:
            flash('Failed to approve document. Please check document status.', 'error')
    except Exception as e:
        flash(f'Error approving document: {str(e)}', 'error')
    
    return redirect(url_for('lms_content_management.document_detail', document_id=document_id))

@lms_content_management.route('/documents/<int:document_id>/submit-review', methods=['POST'])
@require_admin()
def submit_document_for_review(document_id):
    """Submit document for review"""
    document = DocumentUpload.query.get_or_404(document_id)
    
    try:
        if document.upload_status == 'completed' and document.workflow_stage == 'draft':
            document.workflow_stage = 'review'
            document.reviewed_at = get_current_ist_datetime()
            db.session.commit()
            return jsonify({'success': True, 'message': 'Document submitted for review'})
        else:
            return jsonify({'success': False, 'error': 'Document not ready for review'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@lms_content_management.route('/documents/<int:document_id>/reject', methods=['POST'])
@require_admin()
def reject_document(document_id):
    """Reject document"""
    document = DocumentUpload.query.get_or_404(document_id)
    rejection_reason = request.form.get('rejection_reason', '')
    
    try:
        if rejection_reason:
            document.workflow_stage = 'rejected'
            document.rejection_reason = rejection_reason
            document.reviewed_at = get_current_ist_datetime()
            db.session.commit()
            flash('Document rejected successfully!', 'success')
        else:
            flash('Rejection reason is required!', 'error')
    except Exception as e:
        flash(f'Error rejecting document: {str(e)}', 'error')
    
    return redirect(url_for('lms_content_management.document_detail', document_id=document_id))

# ==================== QUIZ MANAGEMENT ROUTES ====================

@lms_content_management.route('/quizzes')
@require_admin()
def quiz_list():
    """List all quizzes"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')
    course_id = request.args.get('course_id', type=int)
    
    query = Quiz.query
    
    if status != 'all':
        if status == 'published':
            query = query.filter_by(is_published=True)
        else:
            query = query.filter_by(workflow_stage=status)
    
    if course_id:
        query = query.filter_by(course_id=course_id)
    
    quizzes = query.order_by(Quiz.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    courses = Course.query.filter_by(status='Active').all()
    
    return render_template('admin/content/quiz_list.html', 
                         quizzes=quizzes, 
                         courses=courses,
                         current_status=status,
                         current_course_id=course_id)

@lms_content_management.route('/quizzes/create')
@require_admin()
def quiz_create_form():
    """Show quiz creation form"""
    courses = Course.query.filter_by(status='Active').all()
    
    return render_template('admin/content/quiz_create.html', courses=courses)

@lms_content_management.route('/quizzes/create', methods=['POST'])
@require_admin()
def quiz_create_process():
    """Process quiz creation"""
    try:
        # Get form data
        course_id = request.form.get('course_id', type=int)
        module_id = request.form.get('module_id', type=int)
        section_id = request.form.get('section_id', type=int)
        quiz_placement = request.form.get('quiz_placement', 'section')  # New field
        placement_order = request.form.get('placement_order', 1, type=int)  # New field
        quiz_title = request.form.get('quiz_title')
        quiz_description = request.form.get('quiz_description', '')
        instructions = request.form.get('instructions', '')
        time_limit = request.form.get('time_limit_minutes', 30, type=int)
        max_attempts = request.form.get('max_attempts', 3, type=int)
        passing_score = request.form.get('passing_score', 70, type=int)
        
        # Validation based on placement type
        if quiz_placement == 'module':
            # Module-level quiz - section_id is optional
            if not all([course_id, module_id, quiz_title]):
                flash('Missing required fields for module-level quiz', 'error')
                return redirect(url_for('lms_content_management.quiz_create_form'))
            section_id = None  # Set to None for module-level quizzes
        else:
            # Section-level quiz - requires section_id
            if not all([course_id, module_id, section_id, quiz_title]):
                flash('Missing required fields for section-level quiz', 'error')
                return redirect(url_for('lms_content_management.quiz_create_form'))
        
        # Create quiz
        quiz = Quiz(
            course_id=course_id,
            module_id=module_id,
            section_id=section_id,
            quiz_placement=quiz_placement,
            placement_order=placement_order,
            quiz_title=quiz_title,
            quiz_description=quiz_description,
            instructions=instructions,
            time_limit_minutes=time_limit,
            max_attempts=max_attempts,
            passing_score=passing_score,
            created_by=session['user_id']
        )
        
        db.session.add(quiz)
        db.session.commit()
        
        flash('Quiz created successfully!', 'success')
        return redirect(url_for('lms_content_management.quiz_detail', quiz_id=quiz.id))
        
    except Exception as e:
        flash(f'Error creating quiz: {str(e)}', 'error')
        return redirect(url_for('lms_content_management.quiz_create_form'))

@lms_content_management.route('/quizzes/<int:quiz_id>')
@require_admin()
def quiz_detail(quiz_id):
    """Show quiz details and questions"""
    quiz = Quiz.query.get_or_404(quiz_id)
    
    return render_template('admin/content/quiz_detail.html', quiz=quiz)

@lms_content_management.route('/quizzes/<int:quiz_id>/questions/add')
@require_admin()
def quiz_add_question_form(quiz_id):
    """Show add question form"""
    quiz = Quiz.query.get_or_404(quiz_id)
    
    return render_template('admin/content/quiz_add_question.html', quiz=quiz)

@lms_content_management.route('/quizzes/<int:quiz_id>/questions/add', methods=['POST'])
@require_admin()
def quiz_add_question_process(quiz_id):
    """Process adding question to quiz"""
    quiz = Quiz.query.get_or_404(quiz_id)
    
    try:
        question_text = request.form.get('question_text')
        question_type = request.form.get('question_type', 'multiple_choice')
        points = request.form.get('points', 1, type=int)
        explanation = request.form.get('explanation', '')
        is_required = bool(request.form.get('is_required'))
        
        if not question_text:
            flash('Question text is required', 'error')
            return redirect(url_for('lms_content_management.quiz_add_question_form', quiz_id=quiz_id))
        
        # Handle different question types
        options = None
        correct_answer = None
        
        if question_type in ['multiple_choice', 'multiple_select']:
            # Get options from the form
            options_list = request.form.getlist('options[]')
            options_list = [opt.strip() for opt in options_list if opt.strip()]
            
            if len(options_list) < 2:
                flash('At least 2 options are required for multiple choice questions', 'error')
                return redirect(url_for('lms_content_management.quiz_add_question_form', quiz_id=quiz_id))
            
            options = json.dumps(options_list)
            
            if question_type == 'multiple_choice':
                correct_answer = request.form.get('correct_option')
            else:  # multiple_select
                correct_options = request.form.getlist('correct_options[]')
                correct_answer = json.dumps([int(opt) for opt in correct_options])
            
        elif question_type == 'true_false':
            options = json.dumps(['True', 'False'])
            correct_answer = request.form.get('true_false_answer')
            
        elif question_type in ['short_answer', 'essay']:
            correct_answer = request.form.get('correct_answer', '')
        
        # Create the question
        question = QuizQuestion(
            quiz_id=quiz.id,
            question_text=question_text,
            question_type=question_type,
            options=options,
            correct_answer=correct_answer,
            explanation=explanation,
            points=points,
            is_required=is_required,
            question_order=len(quiz.questions) + 1
        )
        
        db.session.add(question)
        
        # Update quiz total questions and score
        quiz.total_questions = len(quiz.questions) + 1
        quiz.max_score = sum(q.points for q in quiz.questions) + points
        
        db.session.commit()
        
        flash('Question added successfully!', 'success')
        
        # Check if user wants to add another question or finish
        action = request.form.get('action', 'add_another')
        if action == 'finish':
            return redirect(url_for('lms_content_management.quiz_detail', quiz_id=quiz_id))
        else:
            return redirect(url_for('lms_content_management.quiz_add_question_form', quiz_id=quiz_id))
        
    except Exception as e:
        flash(f'Error adding question: {str(e)}', 'error')
        return redirect(url_for('lms_content_management.quiz_add_question_form', quiz_id=quiz_id))

# Quiz and Question Editing Routes

@lms_content_management.route('/quizzes/<int:quiz_id>/edit')
@require_admin()
def quiz_edit_form(quiz_id):
    """Show quiz edit form"""
    quiz = Quiz.query.get_or_404(quiz_id)
    courses = Course.query.filter_by(status='Active').all()
    
    return render_template('admin/content/quiz_edit.html', quiz=quiz, courses=courses)

@lms_content_management.route('/quizzes/<int:quiz_id>/edit', methods=['POST'])
@require_admin()
def quiz_edit_process(quiz_id):
    """Process quiz editing"""
    quiz = Quiz.query.get_or_404(quiz_id)
    
    try:
        # Get form data
        quiz.quiz_title = request.form.get('quiz_title')
        quiz.quiz_description = request.form.get('quiz_description', '')
        quiz.instructions = request.form.get('instructions', '')
        quiz.time_limit_minutes = request.form.get('time_limit_minutes', 30, type=int)
        quiz.max_attempts = request.form.get('max_attempts', 3, type=int)
        quiz.passing_score = request.form.get('passing_score', 70, type=int)
        quiz.quiz_placement = request.form.get('quiz_placement', 'section')
        quiz.placement_order = request.form.get('placement_order', 1, type=int)
        
        # Handle placement changes
        if quiz.quiz_placement == 'module':
            quiz.section_id = None
        else:
            quiz.section_id = request.form.get('section_id', type=int)
        
        quiz.updated_at = get_current_ist_datetime()
        
        db.session.commit()
        flash('Quiz updated successfully!', 'success')
        return redirect(url_for('lms_content_management.quiz_detail', quiz_id=quiz_id))
        
    except Exception as e:
        flash(f'Error updating quiz: {str(e)}', 'error')
        return redirect(url_for('lms_content_management.quiz_edit_form', quiz_id=quiz_id))

@lms_content_management.route('/quizzes/<int:quiz_id>/delete')
@require_admin()
def quiz_delete(quiz_id):
    """Delete quiz"""
    quiz = Quiz.query.get_or_404(quiz_id)
    
    try:
        # Delete all questions first (cascade should handle this, but be explicit)
        QuizQuestion.query.filter_by(quiz_id=quiz_id).delete()
        
        # Delete the quiz
        db.session.delete(quiz)
        db.session.commit()
        
        flash('Quiz deleted successfully!', 'success')
        return redirect(url_for('lms_content_management.quiz_list'))
        
    except Exception as e:
        flash(f'Error deleting quiz: {str(e)}', 'error')
        return redirect(url_for('lms_content_management.quiz_detail', quiz_id=quiz_id))

@lms_content_management.route('/quizzes/<int:quiz_id>/questions/<int:question_id>/edit')
@require_admin()
def question_edit_form(quiz_id, question_id):
    """Show question edit form"""
    quiz = Quiz.query.get_or_404(quiz_id)
    question = QuizQuestion.query.get_or_404(question_id)
    
    # Ensure question belongs to this quiz
    if question.quiz_id != quiz_id:
        flash('Question not found in this quiz', 'error')
        return redirect(url_for('lms_content_management.quiz_detail', quiz_id=quiz_id))
    
    return render_template('admin/content/question_edit.html', quiz=quiz, question=question)

@lms_content_management.route('/quizzes/<int:quiz_id>/questions/<int:question_id>/edit', methods=['POST'])
@require_admin()
def question_edit_process(quiz_id, question_id):
    """Process question editing"""
    quiz = Quiz.query.get_or_404(quiz_id)
    question = QuizQuestion.query.get_or_404(question_id)
    
    # Ensure question belongs to this quiz
    if question.quiz_id != quiz_id:
        flash('Question not found in this quiz', 'error')
        return redirect(url_for('lms_content_management.quiz_detail', quiz_id=quiz_id))
    
    try:
        # Get form data
        question.question_text = request.form.get('question_text')
        question.question_type = request.form.get('question_type', 'multiple_choice')
        question.points = request.form.get('points', 1, type=int)
        question.explanation = request.form.get('explanation', '')
        question.is_required = bool(request.form.get('is_required'))
        
        # Handle different question types
        if question.question_type in ['multiple_choice', 'multiple_select']:
            # Get options from the form
            options_list = request.form.getlist('options[]')
            options_list = [opt.strip() for opt in options_list if opt.strip()]
            
            if len(options_list) < 2:
                flash('At least 2 options are required for multiple choice questions', 'error')
                return redirect(url_for('lms_content_management.question_edit_form', quiz_id=quiz_id, question_id=question_id))
            
            question.options = json.dumps(options_list)
            
            if question.question_type == 'multiple_choice':
                question.correct_answer = request.form.get('correct_option')
            else:  # multiple_select
                correct_options = request.form.getlist('correct_options[]')
                question.correct_answer = json.dumps([int(opt) for opt in correct_options])
            
        elif question.question_type == 'true_false':
            question.options = json.dumps(['True', 'False'])
            question.correct_answer = request.form.get('true_false_answer')
            
        elif question.question_type in ['short_answer', 'essay']:
            question.correct_answer = request.form.get('correct_answer', '')
        
        question.updated_at = get_current_ist_datetime()
        
        # Recalculate quiz total score
        quiz.max_score = sum(q.points for q in quiz.questions)
        quiz.updated_at = get_current_ist_datetime()
        
        db.session.commit()
        flash('Question updated successfully!', 'success')
        return redirect(url_for('lms_content_management.quiz_detail', quiz_id=quiz_id))
        
    except Exception as e:
        flash(f'Error updating question: {str(e)}', 'error')
        return redirect(url_for('lms_content_management.question_edit_form', quiz_id=quiz_id, question_id=question_id))

@lms_content_management.route('/quizzes/<int:quiz_id>/questions/<int:question_id>/delete')
@require_admin()
def question_delete(quiz_id, question_id):
    """Delete question"""
    quiz = Quiz.query.get_or_404(quiz_id)
    question = QuizQuestion.query.get_or_404(question_id)
    
    # Ensure question belongs to this quiz
    if question.quiz_id != quiz_id:
        flash('Question not found in this quiz', 'error')
        return redirect(url_for('lms_content_management.quiz_detail', quiz_id=quiz_id))
    
    try:
        # Store points for score recalculation
        deleted_points = question.points
        
        # Delete the question
        db.session.delete(question)
        
        # Recalculate quiz totals
        quiz.total_questions = len(quiz.questions) - 1
        quiz.max_score = quiz.max_score - deleted_points
        quiz.updated_at = get_current_ist_datetime()
        
        db.session.commit()
        flash('Question deleted successfully!', 'success')
        
    except Exception as e:
        flash(f'Error deleting question: {str(e)}', 'error')
    
    return redirect(url_for('lms_content_management.quiz_detail', quiz_id=quiz_id))

@lms_content_management.route('/quizzes/<int:quiz_id>/publish', methods=['POST'])
@require_admin()
def quiz_publish(quiz_id):
    """Publish quiz"""
    quiz = Quiz.query.get_or_404(quiz_id)
    
    try:
        if len(quiz.questions) == 0:
            flash('Cannot publish quiz without questions', 'error')
        else:
            quiz.is_published = True
            quiz.workflow_stage = 'published'
            quiz.published_at = get_current_ist_datetime()
            db.session.commit()
            flash('Quiz published successfully!', 'success')
    except Exception as e:
        flash(f'Error publishing quiz: {str(e)}', 'error')
    
    return redirect(url_for('lms_content_management.quiz_detail', quiz_id=quiz_id))

# ==================== ASSIGNMENT MANAGEMENT ROUTES ====================

@lms_content_management.route('/assignments')
@require_admin()
def assignment_list():
    """List all assignments"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')
    course_id = request.args.get('course_id', type=int)
    
    query = AssignmentCreator.query
    
    if status != 'all':
        query = query.filter_by(workflow_stage=status)
    
    if course_id:
        query = query.filter_by(course_id=course_id)
    
    assignments = query.order_by(AssignmentCreator.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    courses = Course.query.filter_by(status='Active').all()
    
    return render_template('admin/content/assignment_list.html', 
                         assignments=assignments, 
                         courses=courses,
                         current_status=status,
                         current_course_id=course_id)

@lms_content_management.route('/assignments/create')
@require_admin()
def assignment_create_form():
    """Show assignment creation form"""
    courses = Course.query.filter_by(status='Active').all()
    
    return render_template('admin/content/assignment_create.html', courses=courses)

@lms_content_management.route('/assignments/create', methods=['POST'])
@require_admin()
def assignment_create_process():
    """Process assignment creation"""
    try:
        # Get form data
        course_id = request.form.get('course_id', type=int)
        module_id = request.form.get('module_id', type=int)
        section_id = request.form.get('section_id', type=int)
        assignment_placement = request.form.get('assignment_placement', 'section')  # New field
        placement_order = request.form.get('placement_order', 1, type=int)  # New field
        assignment_title = request.form.get('assignment_title')
        assignment_description = request.form.get('assignment_description', '')
        detailed_instructions = request.form.get('detailed_instructions', '')
        assignment_type = request.form.get('assignment_type', 'project')
        max_score = request.form.get('max_score', 100, type=int)
        
        # Due date
        due_date_str = request.form.get('due_date')
        due_date = None
        if due_date_str:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
        
        # Validation based on placement type
        if assignment_placement == 'module':
            # Module-level assignment - section_id is optional
            if not all([course_id, module_id, assignment_title]):
                flash('Missing required fields for module-level assignment', 'error')
                return redirect(url_for('lms_content_management.assignment_create_form'))
            section_id = None  # Set to None for module-level assignments
        else:
            # Section-level assignment - requires section_id
            if not all([course_id, module_id, section_id, assignment_title]):
                flash('Missing required fields for section-level assignment', 'error')
                return redirect(url_for('lms_content_management.assignment_create_form'))
        
        # Create assignment
        assignment = AssignmentCreator(
            course_id=course_id,
            module_id=module_id,
            section_id=section_id,
            assignment_placement=assignment_placement,
            placement_order=placement_order,
            assignment_title=assignment_title,
            assignment_description=assignment_description,
            detailed_instructions=detailed_instructions,
            assignment_type=assignment_type,
            max_score=max_score,
            due_date=due_date,
            created_by=session['user_id']
        )
        
        db.session.add(assignment)
        db.session.commit()
        
        flash('Assignment created successfully!', 'success')
        return redirect(url_for('lms_content_management.assignment_detail', assignment_id=assignment.id))
        
    except Exception as e:
        flash(f'Error creating assignment: {str(e)}', 'error')
        return redirect(url_for('lms_content_management.assignment_create_form'))

@lms_content_management.route('/assignments/<int:assignment_id>')
@require_admin()
def assignment_detail(assignment_id):
    """Show assignment details"""
    assignment = AssignmentCreator.query.get_or_404(assignment_id)
    
    return render_template('admin/content/assignment_detail.html', assignment=assignment)

@lms_content_management.route('/assignments/<int:assignment_id>/approve', methods=['POST'])
@require_admin()
def approve_assignment(assignment_id):
    """Approve assignment for publishing"""
    assignment = AssignmentCreator.query.get_or_404(assignment_id)
    comments = request.form.get('comments', '')
    
    try:
        assignment.workflow_stage = 'approved'
        assignment.approved_by = session['user_id']
        assignment.approved_at = get_current_ist_datetime()
        if comments:
            assignment.reviewer_comments = comments
        db.session.commit()
        flash('Assignment approved successfully!', 'success')
    except Exception as e:
        flash(f'Error approving assignment: {str(e)}', 'error')
    
    return redirect(url_for('lms_content_management.assignment_list'))

@lms_content_management.route('/assignments/<int:assignment_id>/reject', methods=['POST'])
@require_admin()
def reject_assignment(assignment_id):
    """Reject assignment with reason"""
    assignment = AssignmentCreator.query.get_or_404(assignment_id)
    rejection_reason = request.form.get('rejection_reason', '')
    
    if not rejection_reason:
        flash('Rejection reason is required.', 'error')
        return redirect(url_for('lms_content_management.assignment_list'))
    
    try:
        assignment.workflow_stage = 'rejected'
        assignment.rejection_reason = rejection_reason
        assignment.reviewed_by = session['user_id']
        assignment.reviewed_at = get_current_ist_datetime()
        db.session.commit()
        flash('Assignment rejected successfully.', 'info')
    except Exception as e:
        flash(f'Error rejecting assignment: {str(e)}', 'error')
    
    return redirect(url_for('lms_content_management.assignment_list'))

@lms_content_management.route('/assignments/<int:assignment_id>/submit-review', methods=['POST'])
@require_admin()
def submit_assignment_for_review(assignment_id):
    """Submit assignment for review"""
    assignment = AssignmentCreator.query.get_or_404(assignment_id)
    
    try:
        if assignment.workflow_stage == 'draft':
            assignment.workflow_stage = 'review'
            assignment.reviewed_at = get_current_ist_datetime()
            db.session.commit()
            return jsonify({'success': True, 'message': 'Assignment submitted for review'})
        else:
            return jsonify({'success': False, 'error': 'Assignment not in draft stage'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@lms_content_management.route('/assignments/<int:assignment_id>/publish', methods=['POST'])
@require_admin()
def assignment_publish(assignment_id):
    """Publish assignment"""
    assignment = AssignmentCreator.query.get_or_404(assignment_id)
    
    try:
        student_assignment = assignment.approve_assignment(session['user_id'])
        if student_assignment:
            flash('Assignment published successfully!', 'success')
        else:
            flash('Failed to publish assignment', 'error')
    except Exception as e:
        flash(f'Error publishing assignment: {str(e)}', 'error')
    
    return redirect(url_for('lms_content_management.assignment_detail', assignment_id=assignment_id))

@lms_content_management.route('/assignments/<int:assignment_id>/edit')
@require_admin()
def assignment_edit_form(assignment_id):
    """Show assignment edit form"""
    assignment = AssignmentCreator.query.get_or_404(assignment_id)
    
    # Check if assignment is published and warn user
    if assignment.workflow_stage == 'published':
        # For published assignments, we allow editing but warn about the implications
        flash('Warning: You are editing a published assignment. Changes will affect live content.', 'warning')
    elif assignment.workflow_stage not in ['draft', 'rejected', 'published', 'approved']:
        flash('Assignment cannot be edited in current stage.', 'error')
        return redirect(url_for('lms_content_management.assignment_detail', assignment_id=assignment_id))
    
    courses = Course.query.filter_by(status='Active').all()
    return render_template('admin/content/assignment_edit.html', assignment=assignment, courses=courses)

@lms_content_management.route('/assignments/<int:assignment_id>/edit', methods=['POST'])
@require_admin()
def assignment_edit_process(assignment_id):
    """Process assignment editing"""
    assignment = AssignmentCreator.query.get_or_404(assignment_id)
    
    # Allow editing for draft, rejected, approved, and published assignments
    if assignment.workflow_stage not in ['draft', 'rejected', 'approved', 'published']:
        flash('Assignment cannot be edited in current stage.', 'error')
        return redirect(url_for('lms_content_management.assignment_detail', assignment_id=assignment_id))
    
    try:
        # Store original workflow stage to handle post-edit logic
        original_stage = assignment.workflow_stage
        
        # Get form data
        assignment.course_id = request.form.get('course_id', type=int)
        assignment.module_id = request.form.get('module_id', type=int)
        assignment.section_id = request.form.get('section_id', type=int)
        assignment.assignment_placement = request.form.get('assignment_placement', 'section')
        assignment.placement_order = request.form.get('placement_order', 1, type=int)
        assignment.assignment_title = request.form.get('assignment_title')
        assignment.assignment_description = request.form.get('assignment_description', '')
        assignment.detailed_instructions = request.form.get('detailed_instructions', '')
        assignment.assignment_type = request.form.get('assignment_type', 'project')
        assignment.max_score = request.form.get('max_score', 100, type=int)
        
        # Handle placement changes
        if assignment.assignment_placement == 'module':
            assignment.section_id = None
        else:
            assignment.section_id = request.form.get('section_id', type=int)
        
        # Due date
        due_date_str = request.form.get('due_date')
        if due_date_str:
            assignment.due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
        else:
            assignment.due_date = None
        
        # Assignment settings
        assignment.is_mandatory = 'is_mandatory' in request.form
        assignment.requires_video_completion = 'requires_video_completion' in request.form
        assignment.group_assignment = 'group_assignment' in request.form
        assignment.late_submission_allowed = 'late_submission_allowed' in request.form
        
        # Submission requirements
        assignment.submission_format = request.form.get('submission_format', '')
        assignment.max_file_size_mb = request.form.get('max_file_size_mb', type=int)
        assignment.min_word_count = request.form.get('min_word_count', type=int)
        assignment.max_word_count = request.form.get('max_word_count', type=int)
        
        # Grading
        grading_rubric = request.form.get('grading_rubric', '')
        if grading_rubric:
            assignment.grading_rubric = grading_rubric
        
        # Handle workflow stage changes based on original stage
        if original_stage == 'rejected':
            # Reset to draft if it was rejected
            assignment.workflow_stage = 'draft'
            assignment.rejection_reason = None
            assignment.reviewed_by = None
            assignment.reviewed_at = None
        elif original_stage == 'published':
            # Keep as published but mark as updated
            assignment.workflow_stage = 'published'
            # Track post-publication edits
            assignment.last_published_edit = get_current_ist_datetime()
            if assignment.edit_count_post_publish is None:
                assignment.edit_count_post_publish = 0
            assignment.edit_count_post_publish += 1
            flash('Published assignment updated successfully! Changes are now live.', 'success')
        elif original_stage == 'approved':
            # Option to require re-approval for significant changes
            force_reapproval = request.form.get('force_reapproval', False)
            if force_reapproval:
                assignment.workflow_stage = 'draft'
                assignment.reviewed_by = None
                assignment.reviewed_at = None
                flash('Assignment changes require re-approval. Status changed to draft.', 'info')
        
        assignment.updated_at = get_current_ist_datetime()
        
        db.session.commit()
        
        if original_stage != 'published':
            flash('Assignment updated successfully!', 'success')
            
        return redirect(url_for('lms_content_management.assignment_detail', assignment_id=assignment_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating assignment: {str(e)}', 'error')
        return redirect(url_for('lms_content_management.assignment_edit_form', assignment_id=assignment_id))

@lms_content_management.route('/assignments/<int:assignment_id>/delete', methods=['POST'])
@require_admin()
def assignment_delete(assignment_id):
    """Delete assignment"""
    assignment = AssignmentCreator.query.get_or_404(assignment_id)
    
    # Only allow deletion for draft assignments or rejected assignments
    if assignment.workflow_stage not in ['draft', 'rejected']:
        flash('Assignment cannot be deleted in current stage. Only draft or rejected assignments can be deleted.', 'error')
        return redirect(url_for('lms_content_management.assignment_detail', assignment_id=assignment_id))
    
    try:
        assignment_title = assignment.assignment_title
        
        # Delete the assignment
        db.session.delete(assignment)
        db.session.commit()
        
        flash(f'Assignment "{assignment_title}" deleted successfully!', 'success')
        return redirect(url_for('lms_content_management.assignment_list'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting assignment: {str(e)}', 'error')
        return redirect(url_for('lms_content_management.assignment_detail', assignment_id=assignment_id))

@lms_content_management.route('/assignments/<int:assignment_id>/unpublish', methods=['POST'])
@require_admin()
def assignment_unpublish(assignment_id):
    """Unpublish assignment - revert from published to draft for major changes"""
    assignment = AssignmentCreator.query.get_or_404(assignment_id)
    
    # Only allow unpublishing published assignments
    if assignment.workflow_stage != 'published':
        flash('Only published assignments can be unpublished.', 'error')
        return redirect(url_for('lms_content_management.assignment_detail', assignment_id=assignment_id))
    
    try:
        reason = request.form.get('unpublish_reason', '').strip()
        if not reason:
            flash('Unpublish reason is required.', 'error')
            return redirect(url_for('lms_content_management.assignment_detail', assignment_id=assignment_id))
        
        # Revert to draft status
        assignment.workflow_stage = 'draft'
        assignment.unpublished_at = get_current_ist_datetime()
        assignment.unpublished_by = session['user_id']
        assignment.unpublish_reason = reason
        assignment.updated_at = get_current_ist_datetime()
        
        # Clear approval fields to require re-approval
        assignment.reviewed_by = None
        assignment.reviewed_at = None
        assignment.approved_by = None
        assignment.approved_at = None
        
        db.session.commit()
        
        flash(f'Assignment "{assignment.assignment_title}" has been unpublished and reverted to draft status.', 'warning')
        return redirect(url_for('lms_content_management.assignment_detail', assignment_id=assignment_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error unpublishing assignment: {str(e)}', 'error')
        return redirect(url_for('lms_content_management.assignment_detail', assignment_id=assignment_id))

@lms_content_management.route('/assignments/<int:assignment_id>/create-revision', methods=['POST'])
@require_admin()
def assignment_create_revision(assignment_id):
    """Create a new revision of a published assignment"""
    original_assignment = AssignmentCreator.query.get_or_404(assignment_id)
    
    # Only allow revision creation for published assignments
    if original_assignment.workflow_stage != 'published':
        flash('Only published assignments can have revisions created.', 'error')
        return redirect(url_for('lms_content_management.assignment_detail', assignment_id=assignment_id))
    
    try:
        revision_notes = request.form.get('revision_notes', '').strip()
        if not revision_notes:
            flash('Revision notes are required.', 'error')
            return redirect(url_for('lms_content_management.assignment_detail', assignment_id=assignment_id))
        
        # Create a new assignment as a revision
        new_assignment = AssignmentCreator(
            course_id=original_assignment.course_id,
            module_id=original_assignment.module_id,
            section_id=original_assignment.section_id,
            assignment_placement=original_assignment.assignment_placement,
            placement_order=original_assignment.placement_order,
            assignment_title=f"{original_assignment.assignment_title} (Revision)",
            assignment_description=original_assignment.assignment_description,
            detailed_instructions=original_assignment.detailed_instructions,
            assignment_type=original_assignment.assignment_type,
            max_score=original_assignment.max_score,
            due_date=original_assignment.due_date,
            is_mandatory=original_assignment.is_mandatory,
            requires_video_completion=original_assignment.requires_video_completion,
            group_assignment=original_assignment.group_assignment,
            late_submission_allowed=original_assignment.late_submission_allowed,
            submission_format=original_assignment.submission_format,
            max_file_size_mb=original_assignment.max_file_size_mb,
            min_word_count=original_assignment.min_word_count,
            max_word_count=original_assignment.max_word_count,
            grading_rubric=original_assignment.grading_rubric,
            workflow_stage='draft',
            created_by=session['user_id'],
            parent_assignment_id=original_assignment.id,
            revision_notes=revision_notes
        )
        
        db.session.add(new_assignment)
        db.session.commit()
        
        flash(f'New revision created successfully! You can now edit the revision.', 'success')
        return redirect(url_for('lms_content_management.assignment_edit_form', assignment_id=new_assignment.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating revision: {str(e)}', 'error')
        return redirect(url_for('lms_content_management.assignment_detail', assignment_id=assignment_id))

# ==================== WORKFLOW MANAGEMENT ROUTES ====================

@lms_content_management.route('/workflows')
@require_admin()
def workflow_list():
    """List all content workflows"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')
    content_type = request.args.get('content_type', 'all')
    priority = request.args.get('priority', 'all')
    assigned_to = request.args.get('assigned_to', 'all')
    
    query = ContentWorkflow.query
    
    if status != 'all':
        query = query.filter_by(workflow_stage=status)
    
    if content_type != 'all':
        query = query.filter_by(content_type=content_type)
    
    if priority != 'all':
        query = query.filter_by(priority=priority)
    
    if assigned_to == 'me':
        query = query.filter_by(assigned_to=session.get('user_id'))
    elif assigned_to == 'unassigned':
        query = query.filter(ContentWorkflow.assigned_to.is_(None))
    
    workflows = query.order_by(ContentWorkflow.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Calculate statistics
    stats = {
        'pending_review': ContentWorkflow.query.filter_by(workflow_stage='review').count(),
        'in_progress': ContentWorkflow.query.filter(ContentWorkflow.workflow_stage.in_(['draft', 'review'])).count(),
        'approved_today': ContentWorkflow.query.filter(
            ContentWorkflow.workflow_stage == 'approved',
            ContentWorkflow.completed_at >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        ).count(),
        'overdue': ContentWorkflow.query.filter(
            ContentWorkflow.due_date < datetime.now(),
            ContentWorkflow.workflow_stage.in_(['draft', 'review'])
        ).count()
    }
    
    return render_template('admin/content/workflow_list.html', 
                         workflows=workflows,
                         stats=stats,
                         current_status=status,
                         current_content_type=content_type,
                         current_priority=priority,
                         current_assigned_to=assigned_to)

# ==================== API ENDPOINTS ====================

@lms_content_management.route('/api/modules/<int:course_id>')
def api_get_modules(course_id):
    """API endpoint to get modules for a course"""
    modules = CourseModule.query.filter_by(course_id=course_id).all()
    return jsonify([{
        'id': module.id,
        'module_name': module.module_name,
        'module_order': module.module_order
    } for module in modules])

@lms_content_management.route('/api/sections/<int:module_id>')
def api_get_sections(module_id):
    """API endpoint to get sections for a module"""
    # Get section type filter from query params
    section_type_filter = request.args.get('type', 'all')
    
    if section_type_filter == 'document':
        # For document uploads, show all sections
        sections = CourseSection.query.filter_by(module_id=module_id).order_by(CourseSection.section_order).all()
    elif section_type_filter == 'video':
        # For video uploads, show all sections  
        sections = CourseSection.query.filter_by(module_id=module_id).order_by(CourseSection.section_order).all()
    elif section_type_filter == 'quiz':
        # For quiz creation, show all sections
        sections = CourseSection.query.filter_by(module_id=module_id).order_by(CourseSection.section_order).all()
    else:
        # For other content types, show all sections
        sections = CourseSection.query.filter_by(module_id=module_id).order_by(CourseSection.section_order).all()
    
    return jsonify([{
        'id': section.id,
        'section_name': section.section_name,
        'section_order': section.section_order,
        'section_type': section.section_type
    } for section in sections])

@lms_content_management.route('/api/upload-progress/<int:upload_id>/<string:upload_type>')
def api_upload_progress(upload_id, upload_type):
    """API endpoint to check upload progress"""
    if upload_type == 'video':
        upload = VideoUpload.query.get_or_404(upload_id)
    elif upload_type == 'document':
        upload = DocumentUpload.query.get_or_404(upload_id)
    else:
        abort(400)
    
    return jsonify({
        'upload_progress': upload.upload_progress,
        'upload_status': upload.upload_status,
        'processing_progress': getattr(upload, 'processing_progress', 0),
        'workflow_stage': upload.workflow_stage
    })

# ==================== FILE SERVING ROUTES ====================

@lms_content_management.route('/files/<int:file_id>/<filename>')
@require_admin()
def serve_file(file_id, filename):
    """Serve uploaded files with access control"""
    file_storage = FileStorage.query.get_or_404(file_id)
    
    if not os.path.exists(file_storage.file_path):
        abort(404)
    
    # Update access tracking
    file_storage.increment_access()
    
    return send_file(file_storage.file_path, as_attachment=False)

# ==================== UTILITY ROUTES ====================

@lms_content_management.route('/settings')
@require_admin()
def content_settings():
    """Content management settings"""
    settings_keys = [
        'max_video_file_size_mb', 'max_document_file_size_mb',
        'allowed_video_formats', 'allowed_document_formats',
        'auto_video_encoding', 'auto_document_watermarking',
        'content_approval_required', 'workflow_notification_enabled'
    ]
    
    settings = {}
    for key in settings_keys:
        setting = LMSSettings.query.filter_by(setting_key=key).first()
        if setting:
            settings[key] = setting.get_typed_value()
    
    return render_template('admin/content/settings.html', settings=settings)

@lms_content_management.route('/settings', methods=['POST'])
@require_admin()
def update_content_settings():
    """Update content management settings"""
    try:
        for key, value in request.form.items():
            if key.startswith('setting_'):
                setting_key = key.replace('setting_', '')
                
                # Handle array values (file formats)
                if 'formats' in setting_key and isinstance(value, str):
                    # Convert comma-separated string to list
                    format_list = [fmt.strip() for fmt in value.split(',') if fmt.strip()]
                    LMSSettings.set_setting(setting_key, format_list, 'json')
                # Handle boolean values
                elif setting_key in ['auto_video_encoding', 'auto_document_watermarking', 
                                   'content_approval_required', 'workflow_notification_enabled']:
                    # Checkbox values: if present = True, if not present = False
                    bool_value = value.lower() == 'true' if value else False
                    LMSSettings.set_setting(setting_key, bool_value, 'bool')
                # Handle integer values
                elif setting_key in ['max_video_file_size_mb', 'max_document_file_size_mb']:
                    LMSSettings.set_setting(setting_key, int(value) if value else 0, 'int')
                else:
                    # Handle as string
                    LMSSettings.set_setting(setting_key, value)
        
        # Handle unchecked checkboxes (they don't appear in form data)
        checkbox_settings = ['auto_video_encoding', 'auto_document_watermarking', 
                           'content_approval_required', 'workflow_notification_enabled']
        for checkbox_key in checkbox_settings:
            form_key = f'setting_{checkbox_key}'
            if form_key not in request.form:
                LMSSettings.set_setting(checkbox_key, False, 'bool')
        
        flash('Settings updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating settings: {str(e)}', 'error')
    
    return redirect(url_for('lms_content_management.content_settings'))

# Error handlers
@lms_content_management.errorhandler(404)
def not_found_error(error):
    return render_template('admin/content/404.html'), 404

@lms_content_management.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('admin/content/500.html'), 500
