from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from sqlalchemy import and_, or_, func, desc, asc
from datetime import datetime
from utils.timezone_helper import get_current_ist_datetime, format_datetime_indian
import uuid

# Import models
from models.course_model import Course
from models.user_model import User
from models.batch_model import Batch
from models.student_model import Student
from models.invoice_model import Invoice
from utils.auth import login_required, admin_required
from utils.role_permissions import get_user_accessible_branches
from init_db import db

course_bp = Blueprint('courses', __name__, url_prefix='/courses')

# ============================================================================
# COURSE LISTING AND SEARCH
# ============================================================================

@course_bp.route('/')
@login_required
def list_courses():
    """List all courses with search and filtering"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        search = request.args.get('search', '').strip()
        category = request.args.get('category', '').strip()
        status = request.args.get('status', 'Active').strip()
        sort_by = request.args.get('sort_by', 'display_order').strip()
        
        # Build query
        query = Course.query.filter_by(is_deleted=0)
        
        # Apply filters
        if search:
            query = query.filter(
                or_(
                    Course.course_name.ilike(f'%{search}%'),
                    Course.course_code.ilike(f'%{search}%'),
                    Course.description.ilike(f'%{search}%')
                )
            )
        
        if category and category != 'All':
            query = query.filter_by(category=category)
            
        if status and status != 'All':
            query = query.filter_by(status=status)
        
        # Apply sorting
        if sort_by == 'name':
            query = query.order_by(asc(Course.course_name))
        elif sort_by == 'fee':
            query = query.order_by(desc(Course.fee))
        elif sort_by == 'category':
            query = query.order_by(asc(Course.category))
        elif sort_by == 'created':
            query = query.order_by(desc(Course.created_at))
        else:  # display_order
            query = query.order_by(asc(Course.display_order), asc(Course.course_name))
        
        # Paginate
        courses = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Get course categories for filter dropdown
        categories = db.session.query(Course.category).filter_by(is_deleted=0).distinct().all()
        categories = [cat[0] for cat in categories if cat[0]]
        
        return render_template('courses/list_courses.html', 
                             courses=courses, 
                             search=search,
                             category=category,
                             status=status,
                             sort_by=sort_by,
                             categories=categories)
                             
    except Exception as e:
        flash(f'Error loading courses: {str(e)}', 'error')
        return redirect(url_for('index'))

# ============================================================================
# COURSE DETAILS AND VIEW
# ============================================================================

@course_bp.route('/<int:course_id>')
@login_required
def view_course(course_id):
    """View detailed course information with statistics"""
    try:
        course = Course.query.filter_by(id=course_id, is_deleted=0).first()
        if not course:
            flash('Course not found.', 'error')
            return redirect(url_for('courses.list_courses'))
        
        # Get course statistics
        stats = {
            'total_enrollments': course.total_enrollments,
            'active_batches': course.active_batches_count,
            'total_revenue': course.total_revenue,
            'recent_enrollments': Student.query.filter_by(
                course_name=course.course_name, is_deleted=0
            ).order_by(desc(Student.admission_date)).limit(5).all(),
            'active_batches_list': Batch.query.filter_by(
                course_id=course.id, is_deleted=0
            ).filter(Batch.status.in_(['Active', 'In Progress'])).all()
        }
        
        return render_template('courses/view_course.html', course=course, stats=stats)
        
    except Exception as e:
        flash(f'Error loading course: {str(e)}', 'error')
        return redirect(url_for('courses.list_courses'))

# ============================================================================
# COURSE CREATION
# ============================================================================

@course_bp.route('/create')
@admin_required
def create_course_form():
    """Show course creation form"""
    return render_template('courses/create_course.html')

@course_bp.route('/create', methods=['POST'])
@admin_required
def create_course():
    """Create new course"""
    try:
        # Extract form data
        data = request.form.to_dict()
        
        # Validate required fields
        required_fields = ['course_name', 'duration', 'fee']
        for field in required_fields:
            if not data.get(field, '').strip():
                flash(f'{field.replace("_", " ").title()} is required.', 'error')
                return redirect(url_for('courses.create_course_form'))
        
        # Validate numeric fields
        try:
            fee = float(data['fee'].strip())
            if fee < 0:
                flash('Course fee cannot be negative.', 'error')
                return redirect(url_for('courses.create_course_form'))
        except (ValueError, TypeError):
            flash('Course fee must be a valid number.', 'error')
            return redirect(url_for('courses.create_course_form'))
        
        # Validate optional numeric fields
        def safe_float(value, field_name):
            if not value or value.strip() == '':
                return 0.0
            try:
                num = float(value.strip())
                if num < 0:
                    flash(f'{field_name} cannot be negative.', 'error')
                    return None
                return num
            except (ValueError, TypeError):
                flash(f'{field_name} must be a valid number.', 'error')
                return None
        
        def safe_int(value, field_name, default=0):
            if not value or value.strip() == '':
                return default
            try:
                num = int(value.strip())
                if num < 0:
                    flash(f'{field_name} cannot be negative.', 'error')
                    return None
                return num
            except (ValueError, TypeError):
                flash(f'{field_name} must be a valid number.', 'error')
                return None
        
        registration_fee = safe_float(data.get('registration_fee', ''), 'Registration fee')
        material_fee = safe_float(data.get('material_fee', ''), 'Material fee')
        certification_fee = safe_float(data.get('certification_fee', ''), 'Certification fee')
        early_bird_discount = safe_float(data.get('early_bird_discount', ''), 'Early bird discount')
        group_discount = safe_float(data.get('group_discount', ''), 'Group discount')
        duration_in_hours = safe_int(data.get('duration_in_hours', ''), 'Duration in hours')
        duration_in_days = safe_int(data.get('duration_in_days', ''), 'Duration in days')
        batch_size_min = safe_int(data.get('batch_size_min', '5'), 'Minimum batch size', 5)
        batch_size_max = safe_int(data.get('batch_size_max', '30'), 'Maximum batch size', 30)
        display_order = safe_int(data.get('display_order', '100'), 'Display order', 100)
        
        # Check if any validation failed
        if any(x is None for x in [registration_fee, material_fee, certification_fee, 
                                   early_bird_discount, group_discount, duration_in_hours, 
                                   duration_in_days, batch_size_min, batch_size_max, display_order]):
            return redirect(url_for('courses.create_course_form'))
        
        # Check for duplicate course name
        existing = Course.query.filter_by(course_name=data['course_name'].strip(), is_deleted=0).first()
        if existing:
            flash('Course with this name already exists.', 'error')
            return redirect(url_for('courses.create_course_form'))
        
        # Generate course code if not provided
        course_code = data.get('course_code', '').strip()
        if not course_code:
            # Auto-generate from course name
            words = data['course_name'].strip().upper().split()
            if len(words) >= 2:
                course_code = ''.join([word[:3] for word in words[:2]])
            else:
                course_code = words[0][:6] if words else 'COURSE'
            
            # Ensure uniqueness
            counter = 1
            original_code = course_code
            while Course.query.filter_by(course_code=course_code, is_deleted=0).first():
                course_code = f"{original_code}{counter:02d}"
                counter += 1
        
        # Create course object
        course = Course(
            course_name=data['course_name'].strip(),
            course_code=course_code,
            category=data.get('category', 'Programming'),
            duration=data['duration'].strip(),
            duration_in_hours=duration_in_hours if duration_in_hours > 0 else None,
            duration_in_days=duration_in_days if duration_in_days > 0 else None,
            fee=fee,
            registration_fee=registration_fee,
            material_fee=material_fee,
            certification_fee=certification_fee,
            early_bird_discount=early_bird_discount,
            group_discount=group_discount,
            description=data.get('description', '').strip() or None,
            course_outline=data.get('course_outline', '').strip() or None,
            prerequisites=data.get('prerequisites', '').strip() or None,
            learning_outcomes=data.get('learning_outcomes', '').strip() or None,
            software_requirements=data.get('software_requirements', '').strip() or None,
            target_audience=data.get('target_audience', '').strip() or None,
            career_opportunities=data.get('career_opportunities', '').strip() or None,
            difficulty_level=data.get('difficulty_level', 'Beginner'),
            delivery_mode=data.get('delivery_mode', 'Classroom'),
            batch_size_min=batch_size_min,
            batch_size_max=batch_size_max,
            has_certification=data.get('has_certification') == 'on',
            certification_body=data.get('certification_body', '').strip() or None,
            assessment_type=data.get('assessment_type', 'Both'),
            passing_criteria=data.get('passing_criteria', '').strip() or None,
            typical_schedule=data.get('typical_schedule', '').strip() or None,
            flexible_timing=data.get('flexible_timing') == 'on',
            is_featured=data.get('is_featured') == 'on',
            is_popular=data.get('is_popular') == 'on',
            display_order=display_order,
            status=data.get('status', 'Active'),
            created_by=session.get('user_id')
        )
        
        db.session.add(course)
        db.session.commit()
        
        # Enhanced success message
        success_msg = f'Course "{course.course_name}" created successfully!'
            
        flash(success_msg, 'success')
        return redirect(url_for('courses.view_course', course_id=course.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating course: {str(e)}', 'error')
        return redirect(url_for('courses.create_course_form'))

# ============================================================================
# COURSE EDITING
# ============================================================================

@course_bp.route('/<int:course_id>/edit')
@admin_required
def edit_course_form(course_id):
    """Show course edit form"""
    course = Course.query.filter_by(id=course_id, is_deleted=0).first()
    if not course:
        flash('Course not found.', 'error')
        return redirect(url_for('courses.list_courses'))
    
    return render_template('courses/edit_course.html', course=course)

@course_bp.route('/<int:course_id>/edit', methods=['POST'])
@admin_required
def edit_course(course_id):
    """Update existing course"""
    try:
        course = Course.query.filter_by(id=course_id, is_deleted=0).first()
        if not course:
            flash('Course not found.', 'error')
            return redirect(url_for('courses.list_courses'))
        
        data = request.form.to_dict()
        
        # Validate required fields
        required_fields = ['course_name', 'duration', 'fee']
        for field in required_fields:
            if not data.get(field, '').strip():
                flash(f'{field.replace("_", " ").title()} is required.', 'error')
                return redirect(url_for('courses.edit_course_form', course_id=course_id))
        
        # Validate numeric fields
        try:
            fee = float(data['fee'].strip())
            if fee < 0:
                flash('Course fee cannot be negative.', 'error')
                return redirect(url_for('courses.edit_course_form', course_id=course_id))
        except (ValueError, TypeError):
            flash('Course fee must be a valid number.', 'error')
            return redirect(url_for('courses.edit_course_form', course_id=course_id))
        
        # Validate optional numeric fields
        def safe_float(value, field_name):
            if not value or value.strip() == '':
                return 0.0
            try:
                num = float(value.strip())
                if num < 0:
                    flash(f'{field_name} cannot be negative.', 'error')
                    return None
                return num
            except (ValueError, TypeError):
                flash(f'{field_name} must be a valid number.', 'error')
                return None
        
        def safe_int(value, field_name, default=0):
            if not value or value.strip() == '':
                return default
            try:
                num = int(value.strip())
                if num < 0:
                    flash(f'{field_name} cannot be negative.', 'error')
                    return None
                return num
            except (ValueError, TypeError):
                flash(f'{field_name} must be a valid number.', 'error')
                return None
        
        registration_fee = safe_float(data.get('registration_fee', ''), 'Registration fee')
        material_fee = safe_float(data.get('material_fee', ''), 'Material fee')
        certification_fee = safe_float(data.get('certification_fee', ''), 'Certification fee')
        early_bird_discount = safe_float(data.get('early_bird_discount', ''), 'Early bird discount')
        group_discount = safe_float(data.get('group_discount', ''), 'Group discount')
        duration_in_hours = safe_int(data.get('duration_in_hours', ''), 'Duration in hours')
        duration_in_days = safe_int(data.get('duration_in_days', ''), 'Duration in days')
        batch_size_min = safe_int(data.get('batch_size_min', '5'), 'Minimum batch size', 5)
        batch_size_max = safe_int(data.get('batch_size_max', '30'), 'Maximum batch size', 30)
        display_order = safe_int(data.get('display_order', '100'), 'Display order', 100)
        
        # Check if any validation failed
        if any(x is None for x in [registration_fee, material_fee, certification_fee, 
                                   early_bird_discount, group_discount, duration_in_hours, 
                                   duration_in_days, batch_size_min, batch_size_max, display_order]):
            return redirect(url_for('courses.edit_course_form', course_id=course_id))
        
        # Check for duplicate course name (excluding current course)
        existing = Course.query.filter(
            Course.course_name == data['course_name'].strip(),
            Course.id != course_id,
            Course.is_deleted == 0
        ).first()
        if existing:
            flash('Another course with this name already exists.', 'error')
            return redirect(url_for('courses.edit_course_form', course_id=course_id))
        
        # Update course fields
        course.course_name = data['course_name'].strip()
        course.course_code = data.get('course_code', '').strip() or course.course_code
        course.category = data.get('category', course.category)
        course.duration = data['duration'].strip()
        course.duration_in_hours = duration_in_hours if duration_in_hours > 0 else None
        course.duration_in_days = duration_in_days if duration_in_days > 0 else None
        course.fee = fee
        course.registration_fee = registration_fee
        course.material_fee = material_fee
        course.certification_fee = certification_fee
        course.early_bird_discount = early_bird_discount
        course.group_discount = group_discount
        course.description = data.get('description', '').strip() or None
        course.course_outline = data.get('course_outline', '').strip() or None
        course.prerequisites = data.get('prerequisites', '').strip() or None
        course.learning_outcomes = data.get('learning_outcomes', '').strip() or None
        course.software_requirements = data.get('software_requirements', '').strip() or None
        course.target_audience = data.get('target_audience', '').strip() or None
        course.career_opportunities = data.get('career_opportunities', '').strip() or None
        course.difficulty_level = data.get('difficulty_level', course.difficulty_level)
        course.delivery_mode = data.get('delivery_mode', course.delivery_mode)
        course.batch_size_min = batch_size_min
        course.batch_size_max = batch_size_max
        course.has_certification = data.get('has_certification') == 'on'
        course.certification_body = data.get('certification_body', '').strip() or None
        course.assessment_type = data.get('assessment_type', course.assessment_type)
        course.passing_criteria = data.get('passing_criteria', '').strip() or None
        course.typical_schedule = data.get('typical_schedule', '').strip() or None
        course.flexible_timing = data.get('flexible_timing') == 'on'
        course.is_featured = data.get('is_featured') == 'on'
        course.is_popular = data.get('is_popular') == 'on'
        course.display_order = display_order
        course.status = data.get('status', course.status)
        course.updated_at = get_current_ist_datetime()
        
        db.session.commit()
        
        flash(f'Course "{course.course_name}" updated successfully!', 'success')
        return redirect(url_for('courses.view_course', course_id=course.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating course: {str(e)}', 'error')
        return redirect(url_for('courses.edit_course_form', course_id=course_id))

# ============================================================================
# COURSE STATUS MANAGEMENT
# ============================================================================

@course_bp.route('/<int:course_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_course_status(course_id):
    """Toggle course active/inactive status"""
    try:
        course = Course.query.filter_by(id=course_id, is_deleted=0).first()
        if not course:
            return jsonify({'success': False, 'message': 'Course not found'})
        
        # Toggle status
        if course.status == 'Active':
            course.status = 'Inactive'
            message = f'Course "{course.course_name}" has been deactivated.'
        else:
            course.status = 'Active'
            message = f'Course "{course.course_name}" has been activated.'
        
        course.updated_at = get_current_ist_datetime()
        db.session.commit()
        
        return jsonify({'success': True, 'message': message, 'new_status': course.status})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@course_bp.route('/<int:course_id>/archive', methods=['POST'])
@admin_required
def archive_course(course_id):
    """Archive a course (soft delete)"""
    try:
        course = Course.query.filter_by(id=course_id, is_deleted=0).first()
        if not course:
            flash('Course not found.', 'error')
            return redirect(url_for('courses.list_courses'))
        
        # Check if course has active batches or recent enrollments
        active_batches = Batch.query.filter_by(course_id=course.id, is_deleted=0).filter(
            Batch.status.in_(['Active', 'In Progress'])
        ).count()
        
        if active_batches > 0:
            flash(f'Cannot archive course. It has {active_batches} active batch(es).', 'error')
            return redirect(url_for('courses.view_course', course_id=course_id))
        
        # Archive the course
        course.status = 'Archived'
        course.updated_at = get_current_ist_datetime()
        db.session.commit()
        
        flash(f'Course "{course.course_name}" has been archived.', 'success')
        return redirect(url_for('courses.list_courses'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error archiving course: {str(e)}', 'error')
        return redirect(url_for('courses.view_course', course_id=course_id))

# ============================================================================
# API ENDPOINTS FOR AJAX CALLS
# ============================================================================

@course_bp.route('/api/search')
@login_required
def api_search_courses():
    """API endpoint to search courses for AJAX calls"""
    try:
        query = request.args.get('q', '').strip()
        status = request.args.get('status', 'Active')
        limit = request.args.get('limit', 10, type=int)
        
        courses_query = Course.query.filter_by(is_deleted=0, status=status)
        
        if query:
            courses_query = courses_query.filter(
                or_(
                    Course.course_name.ilike(f'%{query}%'),
                    Course.course_code.ilike(f'%{query}%')
                )
            )
        
        courses = courses_query.order_by(Course.display_order, Course.course_name).limit(limit).all()
        
        return jsonify({
            'success': True,
            'courses': [course.to_dict() for course in courses]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@course_bp.route('/api/<int:course_id>')
@login_required
def api_get_course(course_id):
    """API endpoint to get course details"""
    try:
        course = Course.query.filter_by(id=course_id, is_deleted=0).first()
        if not course:
            return jsonify({'success': False, 'message': 'Course not found'})
        
        return jsonify({
            'success': True,
            'course': course.to_dict(include_stats=True)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@course_bp.route('/api/categories')
@login_required
def api_get_categories():
    """API endpoint to get all course categories"""
    try:
        categories = db.session.query(Course.category).filter_by(is_deleted=0).distinct().all()
        categories = [cat[0] for cat in categories if cat[0]]
        
        return jsonify({
            'success': True,
            'categories': sorted(categories)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ============================================================================
# BULK OPERATIONS
# ============================================================================

@course_bp.route('/bulk/update-display-order', methods=['POST'])
@admin_required
def bulk_update_display_order():
    """Update display order for multiple courses"""
    try:
        course_orders = request.get_json()
        
        for item in course_orders:
            course_id = item.get('course_id')
            display_order = item.get('display_order')
            
            course = Course.query.filter_by(id=course_id, is_deleted=0).first()
            if course:
                course.display_order = display_order
                course.updated_at = get_current_ist_datetime()
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Display order updated successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

# ============================================================================
# COURSE ANALYTICS AND REPORTS
# ============================================================================

@course_bp.route('/analytics')
@admin_required
def course_analytics():
    """Show course analytics and performance metrics"""
    try:
        # Get comprehensive course statistics
        courses_stats_raw = db.session.query(
            Course.id,
            Course.course_name,
            Course.category,
            Course.fee,
            func.count(Student.student_id).label('total_students'),
            func.sum(Invoice.paid_amount).label('total_revenue'),
            func.count(Batch.id).label('total_batches')
        ).outerjoin(Student, Student.course_name == Course.course_name)\
         .outerjoin(Invoice, Invoice.course_id == Course.id)\
         .outerjoin(Batch, Batch.course_id == Course.id)\
         .filter(Course.is_deleted == 0)\
         .group_by(Course.id, Course.course_name, Course.category, Course.fee)\
         .all()
        
        # Convert to list of dictionaries and handle None values
        courses_stats = []
        for stat in courses_stats_raw:
            courses_stats.append({
                'id': stat.id,
                'course_name': stat.course_name,
                'category': stat.category,
                'fee': stat.fee or 0,
                'total_students': stat.total_students or 0,
                'total_revenue': stat.total_revenue or 0,
                'total_batches': stat.total_batches or 0
            })
        
        # Category-wise analytics
        category_stats_raw = db.session.query(
            Course.category,
            func.count(Course.id).label('course_count'),
            func.sum(Invoice.paid_amount).label('category_revenue')
        ).outerjoin(Invoice, Invoice.course_id == Course.id)\
         .filter(Course.is_deleted == 0)\
         .group_by(Course.category)\
         .all()
        
        # Convert to list of dictionaries and handle None values
        category_stats = []
        for stat in category_stats_raw:
            category_stats.append({
                'category': stat.category,
                'course_count': stat.course_count or 0,
                'category_revenue': stat.category_revenue or 0
            })
        
        return render_template('courses/analytics.html', 
                             courses_stats=courses_stats,
                             category_stats=category_stats)
        
    except Exception as e:
        flash(f'Error loading analytics: {str(e)}', 'error')
        return redirect(url_for('courses.list_courses'))

# ============================================================================
# COURSE MODULE MANAGEMENT
# ============================================================================

@course_bp.route('/<int:course_id>/modules')
@login_required
@admin_required
def course_modules(course_id):
    """List modules for a specific course"""
    try:
        course = Course.query.get_or_404(course_id)
        
        # Import CourseModule here to avoid circular imports
        from models.lms_model import CourseModule
        
        modules = CourseModule.query.filter_by(course_id=course_id).order_by(CourseModule.module_order).all()
        
        return render_template('courses/modules.html', course=course, modules=modules)
        
    except Exception as e:
        flash(f'Error loading course modules: {str(e)}', 'error')
        return redirect(url_for('courses.list_courses'))

@course_bp.route('/<int:course_id>/modules/create')
@login_required
@admin_required
def create_module_form(course_id):
    """Show create module form"""
    try:
        course = Course.query.get_or_404(course_id)
        return render_template('courses/create_module.html', course=course)
        
    except Exception as e:
        flash(f'Error loading create module form: {str(e)}', 'error')
        return redirect(url_for('courses.course_modules', course_id=course_id))

@course_bp.route('/<int:course_id>/modules/create', methods=['POST'])
@login_required
@admin_required
def create_module(course_id):
    """Create a new module for a course"""
    try:
        course = Course.query.get_or_404(course_id)
        
        # Import CourseModule here to avoid circular imports
        from models.lms_model import CourseModule
        
        # Get form data
        module_name = request.form.get('module_name', '').strip()
        module_description = request.form.get('module_description', '').strip()
        estimated_duration_hours = request.form.get('estimated_duration_hours', 0, type=int)
        learning_objectives = request.form.get('learning_objectives', '').strip()
        prerequisites = request.form.get('prerequisites', '').strip()
        is_mandatory = request.form.get('is_mandatory') == 'on'
        
        # Validation
        if not module_name:
            flash('Module name is required', 'error')
            return redirect(url_for('courses.create_module_form', course_id=course_id))
        
        # Get next module order
        max_order = db.session.query(func.max(CourseModule.module_order)).filter_by(course_id=course_id).scalar() or 0
        
        # Create module
        module = CourseModule(
            course_id=course_id,
            module_name=module_name,
            module_description=module_description,
            module_order=max_order + 1,
            estimated_duration_hours=estimated_duration_hours,
            learning_objectives=learning_objectives,
            prerequisites=prerequisites,
            is_mandatory=is_mandatory,
            is_published=True,  # Always active since no publishing workflow
            created_by=session.get('user_id'),
            created_at=get_current_ist_datetime(),
            updated_at=get_current_ist_datetime()
        )
        
        db.session.add(module)
        db.session.commit()
        
        flash(f'Module "{module_name}" created successfully!', 'success')
        return redirect(url_for('courses.course_modules', course_id=course_id))
        
    except Exception as e:
        flash(f'Error creating module: {str(e)}', 'error')
        return redirect(url_for('courses.create_module_form', course_id=course_id))

@course_bp.route('/modules/<int:module_id>/edit')
@login_required
@admin_required
def edit_module_form(module_id):
    """Show edit module form"""
    try:
        from models.lms_model import CourseModule
        
        module = CourseModule.query.get_or_404(module_id)
        return render_template('courses/edit_module.html', module=module)
        
    except Exception as e:
        flash(f'Error loading edit module form: {str(e)}', 'error')
        return redirect(url_for('courses.course_modules', course_id=module.course_id if 'module' in locals() else 1))

@course_bp.route('/modules/<int:module_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_module(module_id):
    """Edit an existing module"""
    try:
        from models.lms_model import CourseModule
        
        module = CourseModule.query.get_or_404(module_id)
        
        # Get form data
        module_name = request.form.get('module_name', '').strip()
        module_description = request.form.get('module_description', '').strip()
        estimated_duration_hours = request.form.get('estimated_duration_hours', 0, type=int)
        learning_objectives = request.form.get('learning_objectives', '').strip()
        prerequisites = request.form.get('prerequisites', '').strip()
        is_mandatory = request.form.get('is_mandatory') == 'on'
        
        # Validation
        if not module_name:
            flash('Module name is required', 'error')
            return redirect(url_for('courses.edit_module_form', module_id=module_id))
        
        # Update module
        module.module_name = module_name
        module.module_description = module_description
        module.estimated_duration_hours = estimated_duration_hours
        module.learning_objectives = learning_objectives
        module.prerequisites = prerequisites
        module.is_mandatory = is_mandatory
        module.updated_at = get_current_ist_datetime()
        
        db.session.commit()
        
        flash(f'Module "{module_name}" updated successfully!', 'success')
        return redirect(url_for('courses.course_modules', course_id=module.course_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating module: {str(e)}', 'error')
        return redirect(url_for('courses.edit_module_form', module_id=module_id))

@course_bp.route('/modules/<int:module_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_module(module_id):
    """Delete a module and all its sections"""
    try:
        from models.lms_model import CourseModule
        
        module = CourseModule.query.get_or_404(module_id)
        course_id = module.course_id
        module_name = module.module_name
        
        # Delete the module (this will cascade delete sections due to relationship)
        db.session.delete(module)
        db.session.commit()
        
        flash(f'Module "{module_name}" deleted successfully!', 'success')
        return jsonify({'success': True, 'message': f'Module "{module_name}" deleted successfully!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error deleting module: {str(e)}'})

@course_bp.route('/modules/<int:module_id>/sections')
@login_required
@admin_required
def module_sections(module_id):
    """List sections for a specific module"""
    try:
        # Import models here to avoid circular imports
        from models.lms_model import CourseModule, CourseSection
        
        module = CourseModule.query.get_or_404(module_id)
        sections = CourseSection.query.filter_by(module_id=module_id).order_by(CourseSection.section_order).all()
        
        return render_template('courses/sections.html', module=module, sections=sections)
        
    except Exception as e:
        flash(f'Error loading module sections: {str(e)}', 'error')
        return redirect(url_for('courses.list_courses'))

@course_bp.route('/modules/<int:module_id>/sections/create')
@login_required
@admin_required
def create_section_form(module_id):
    """Show create section form"""
    try:
        from models.lms_model import CourseModule
        
        module = CourseModule.query.get_or_404(module_id)
        return render_template('courses/create_section.html', module=module)
        
    except Exception as e:
        flash(f'Error loading create section form: {str(e)}', 'error')
        return redirect(url_for('courses.module_sections', module_id=module_id))

@course_bp.route('/modules/<int:module_id>/sections/create', methods=['POST'])
@login_required
@admin_required
def create_section(module_id):
    """Create a new section for a module"""
    try:
        from models.lms_model import CourseModule, CourseSection
        
        module = CourseModule.query.get_or_404(module_id)
        
        # Get form data
        section_name = request.form.get('section_name', '').strip()
        section_description = request.form.get('section_description', '').strip()
        estimated_duration_minutes = request.form.get('estimated_duration_minutes', 30, type=int)
        learning_outcomes = request.form.get('learning_outcomes', '').strip()
        section_type = request.form.get('section_type', 'content').strip()
        is_mandatory = request.form.get('is_mandatory') == 'on'
        
        # Validation
        if not section_name:
            flash('Section name is required', 'error')
            return redirect(url_for('courses.create_section_form', module_id=module_id))
        
        # Get next section order
        max_order = db.session.query(func.max(CourseSection.section_order)).filter_by(module_id=module_id).scalar() or 0
        
        # Create section
        section = CourseSection(
            module_id=module_id,
            section_name=section_name,
            section_description=section_description,
            section_order=max_order + 1,
            estimated_duration_minutes=estimated_duration_minutes,
            learning_outcomes=learning_outcomes,
            section_type=section_type,
            is_mandatory=is_mandatory,
            is_published=True,  # Always active since no publishing workflow
            created_by=session.get('user_id'),
            created_at=get_current_ist_datetime(),
            updated_at=get_current_ist_datetime()
        )
        
        db.session.add(section)
        db.session.commit()
        
        flash(f'Section "{section_name}" created successfully!', 'success')
        return redirect(url_for('courses.module_sections', module_id=module_id))
        
    except Exception as e:
        flash(f'Error creating section: {str(e)}', 'error')
        return redirect(url_for('courses.create_section_form', module_id=module_id))

# ============================================================================
# API ENDPOINTS FOR DYNAMIC DROPDOWNS
# ============================================================================

@course_bp.route('/api/modules/<int:course_id>')
@login_required
def api_get_course_modules(course_id):
    """API endpoint to get modules for a course"""
    try:
        from models.lms_model import CourseModule
        
        # For content management, show all modules (published and draft)
        modules = CourseModule.query.filter_by(course_id=course_id).order_by(CourseModule.module_order).all()
        
        modules_data = []
        for module in modules:
            modules_data.append({
                'id': module.id,
                'name': module.module_name,
                'description': module.module_description
            })
        
        return jsonify({'success': True, 'modules': modules_data})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@course_bp.route('/api/sections/<int:module_id>')
@login_required
def api_get_module_sections(module_id):
    """API endpoint to get sections for a module"""
    try:
        from models.lms_model import CourseSection
        
        # Get section type filter from query params (for different content types)
        section_type_filter = request.args.get('type', 'video')
        
        # For video uploads, show only video and content sections
        if section_type_filter == 'video':
            allowed_types = ['video', 'content']
            sections = CourseSection.query.filter(
                CourseSection.module_id == module_id,
                CourseSection.section_type.in_(allowed_types)
            ).order_by(CourseSection.section_order).all()
        elif section_type_filter == 'document':
            # For document uploads, show only document and content sections
            allowed_types = ['document', 'content']
            sections = CourseSection.query.filter(
                CourseSection.module_id == module_id,
                CourseSection.section_type.in_(allowed_types)
            ).order_by(CourseSection.section_order).all()
        else:
            # For other content types, show all sections
            sections = CourseSection.query.filter_by(module_id=module_id).order_by(CourseSection.section_order).all()
        
        sections_data = []
        for section in sections:
            sections_data.append({
                'id': section.id,
                'name': section.section_name,
                'description': section.section_description,
                'type': section.section_type
            })
        
        return jsonify({'success': True, 'sections': sections_data})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
