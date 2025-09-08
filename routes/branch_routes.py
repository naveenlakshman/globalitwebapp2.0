from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from models.branch_model import Branch
from models.course_model import Course
from models.user_model import User
from utils.role_permissions import get_user_accessible_branches, check_module_permission
from init_db import db
from datetime import datetime
import os

branch_bp = Blueprint('branch', __name__, url_prefix='/branches')

@branch_bp.route('/')
def list_branches():
    """List all branches with management controls"""
    # Check if user is logged in and has admin access
    if not session.get('user_id'):
        flash('Access denied. Please login.', 'error')
        return redirect(url_for('auth.login'))
    
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    # Franchise owners should only see their own branch
    if user_role == 'franchise':
        user_branch_id = session.get('user_branch_id')
        if user_branch_id:
            return redirect(url_for('branch.view_branch', branch_id=user_branch_id))
        else:
            flash('No branch assigned to your account. Contact administrator.', 'warning')
            return redirect(url_for('dashboard_bp.franchise_dashboard'))
    
    # Check user permissions for branch access
    # Admin and regional managers can access branch overview
    if user_role not in ['admin', 'regional_manager']:
        flash('Access denied. You do not have permission to view branches.', 'error')
        return redirect(url_for('auth.login'))
    
    # Get branches based on user role and access
    if user_role == 'admin':
        # Admin can see all branches
        branches = Branch.query.filter_by(is_deleted=0).all()
    elif user_role == 'regional_manager':
        # Regional managers can see their assigned branches
        accessible_branch_ids = get_user_accessible_branches(user_id)
        if accessible_branch_ids:
            branches = Branch.query.filter(Branch.id.in_(accessible_branch_ids), Branch.is_deleted == 0).all()
        else:
            branches = []
            flash('No branches assigned to your account. Contact administrator.', 'warning')
    else:
        # Other roles get redirected to their specific dashboard
        flash('Access denied. Insufficient privileges to view all branches.', 'error')
        return redirect(url_for('auth.login'))
    
    # Get branch statistics
    branch_stats = []
    for branch in branches:
        # Count students in this branch
        from models.student_model import Student
        student_count = Student.query.filter_by(branch_id=branch.id, is_deleted=0).count()
        
        # Count batches in this branch
        from models.batch_model import Batch
        batch_count = Batch.query.filter_by(branch_id=branch.id, is_deleted=0).count()
        
        # Count active users in this branch
        # Simple count for now - can be enhanced later with proper user_branch_access join
        user_count = 0  # Placeholder - will implement proper user-branch relationship later
        
        branch_stats.append({
            'branch': branch,
            'student_count': student_count,
            'batch_count': batch_count,
            'user_count': user_count
        })
    
    return render_template('branches/list.html', branch_stats=branch_stats)

@branch_bp.route('/create', methods=['GET', 'POST'])
def create_branch():
    """Create a new branch/franchise"""
    if not session.get('user_id') or session.get('role') not in ['admin', 'corporate_admin']:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        try:
            # Generate branch code
            branch_count = Branch.query.filter_by(is_deleted=0).count()
            branch_code = f"FR{str(branch_count + 1).zfill(3)}"
            
            # Parse opening date
            opening_date = None
            if request.form.get('opening_date'):
                opening_date = datetime.strptime(request.form.get('opening_date'), '%Y-%m-%d').date()
            
            # Parse franchise fees (handle empty strings)
            franchise_fee = request.form.get('franchise_fee', '').strip()
            franchise_fee = float(franchise_fee) if franchise_fee else 0.0
            
            monthly_fee = request.form.get('monthly_fee', '').strip()
            monthly_fee = float(monthly_fee) if monthly_fee else 0.0
            
            # Create new branch
            branch = Branch(
                branch_name=request.form.get('branch_name'),
                branch_code=branch_code,
                address=request.form.get('address'),
                city=request.form.get('city'),
                state=request.form.get('state'),
                pincode=request.form.get('pincode'),
                phone=request.form.get('phone'),
                email=request.form.get('email'),
                manager_name=request.form.get('manager_name'),
                manager_phone=request.form.get('manager_phone'),
                branch_type=request.form.get('branch_type', 'Franchise'),
                status=request.form.get('status', 'Active'),
                opening_date=opening_date,
                franchise_fee=franchise_fee,
                monthly_fee=monthly_fee,
                gst_number=request.form.get('gst_number'),
                pan_number=request.form.get('pan_number')
            )
            
            db.session.add(branch)
            db.session.commit()
            
            flash(f'Branch "{branch.branch_name}" created successfully with code {branch_code}!', 'success')
            return redirect(url_for('branch.list_branches'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating branch: {str(e)}', 'error')
    
    # Pass current date to template
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('branches/create.html', today=today)

@branch_bp.route('/edit/<int:branch_id>', methods=['GET', 'POST'])
def edit_branch(branch_id):
    """Edit existing branch details"""
    if not session.get('user_id') or session.get('role') not in ['admin', 'corporate_admin']:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('auth.login'))
    
    branch = Branch.query.get_or_404(branch_id)
    
    if request.method == 'POST':
        try:
            # Parse opening date
            opening_date = None
            if request.form.get('opening_date'):
                opening_date = datetime.strptime(request.form.get('opening_date'), '%Y-%m-%d').date()
            
            # Parse franchise fees (handle empty strings)
            franchise_fee = request.form.get('franchise_fee', '').strip()
            franchise_fee = float(franchise_fee) if franchise_fee else 0.0
            
            monthly_fee = request.form.get('monthly_fee', '').strip()
            monthly_fee = float(monthly_fee) if monthly_fee else 0.0
            
            # Update branch details
            branch.branch_name = request.form.get('branch_name')
            branch.address = request.form.get('address')
            branch.city = request.form.get('city')
            branch.state = request.form.get('state')
            branch.pincode = request.form.get('pincode')
            branch.phone = request.form.get('phone')
            branch.email = request.form.get('email')
            branch.manager_name = request.form.get('manager_name')
            branch.manager_phone = request.form.get('manager_phone')
            branch.branch_type = request.form.get('branch_type')
            branch.status = request.form.get('status')
            branch.opening_date = opening_date
            branch.franchise_fee = franchise_fee
            branch.monthly_fee = monthly_fee
            branch.gst_number = request.form.get('gst_number')
            branch.pan_number = request.form.get('pan_number')
            
            db.session.commit()
            
            flash(f'Branch "{branch.branch_name}" updated successfully!', 'success')
            return redirect(url_for('branch.list_branches'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating branch: {str(e)}', 'error')
    
    # Pass current date to template
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('branches/edit.html', branch=branch, today=today)

@branch_bp.route('/view/<int:branch_id>')
def view_branch(branch_id):
    """View detailed branch information"""
    if not session.get('user_id'):
        flash('Please log in to access this page.', 'error')
        return redirect(url_for('auth.login'))
    
    user_id = session.get('user_id')
    user_role = session.get('role')
    
    # Check if user can access this branch
    accessible_branch_ids = get_user_accessible_branches(user_id)
    
    # Admin can access all branches
    if user_role != 'admin' and branch_id not in accessible_branch_ids:
        flash('Access denied. You do not have permission to view this branch.', 'error')
        return redirect(url_for('branch.list_branches'))
    
    branch = Branch.query.get_or_404(branch_id)
    
    # Get branch statistics
    from models.student_model import Student
    from models.batch_model import Batch
    
    students = Student.query.filter_by(branch_id=branch.id, is_deleted=0).all()
    batches = Batch.query.filter_by(branch_id=branch.id, is_deleted=0).all()
    
    # Get recent activities (last 10 students registered)
    recent_students = Student.query.filter_by(branch_id=branch.id, is_deleted=0)\
                                  .order_by(Student.admission_date.desc()).limit(10).all()
    
    return render_template('branches/view.html', 
                         branch=branch, 
                         students=students, 
                         batches=batches,
                         recent_students=recent_students)

@branch_bp.route('/delete/<int:branch_id>', methods=['POST'])
def delete_branch(branch_id):
    """Soft delete a branch (mark as deleted)"""
    if not session.get('user_id') or session.get('role') not in ['admin', 'corporate_admin']:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        branch = Branch.query.get_or_404(branch_id)
        
        # Check if branch has active students
        from models.student_model import Student
        active_students = Student.query.filter_by(branch_id=branch.id, is_deleted=0).count()
        
        if active_students > 0:
            return jsonify({'error': f'Cannot delete branch with {active_students} active students'}), 400
        
        # Soft delete the branch
        branch.is_deleted = 1
        branch.status = 'Inactive'
        db.session.commit()
        
        return jsonify({'success': f'Branch "{branch.branch_name}" deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@branch_bp.route('/toggle-status/<int:branch_id>', methods=['POST'])
def toggle_branch_status(branch_id):
    """Toggle branch status between Active/Inactive"""
    if not session.get('user_id') or session.get('role') not in ['admin', 'corporate_admin']:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        branch = Branch.query.get_or_404(branch_id)
        
        # Toggle status
        new_status = 'Inactive' if branch.status == 'Active' else 'Active'
        branch.status = new_status
        db.session.commit()
        
        return jsonify({
            'success': f'Branch status updated to {new_status}',
            'new_status': new_status
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@branch_bp.route('/courses')
def manage_courses():
    """Course management interface"""
    if not session.get('user_id') or session.get('role') not in ['admin', 'corporate_admin']:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('auth.login'))
    
    courses = Course.query.filter_by(is_deleted=0).all()
    
    # Get course statistics
    course_stats = []
    for course in courses:
        from models.batch_model import Batch
        from models.student_model import Student
        
        # Count batches offering this course
        batch_count = Batch.query.filter_by(course_name=course.course_name, is_deleted=0).count()
        
        # Count students enrolled in this course
        student_count = Student.query.filter_by(course_name=course.course_name, is_deleted=0).count()
        
        course_stats.append({
            'course': course,
            'batch_count': batch_count,
            'student_count': student_count
        })
    
    return render_template('branches/courses.html', course_stats=course_stats)

@branch_bp.route('/courses/create', methods=['POST'])
def create_course():
    """Create a new course"""
    if not session.get('user_id') or session.get('role') not in ['admin', 'corporate_admin']:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        course = Course(
            course_name=request.form.get('course_name'),
            duration=request.form.get('duration'),
            fee=float(request.form.get('fee')),
            description=request.form.get('description'),
            status=request.form.get('status', 'Active')
        )
        
        db.session.add(course)
        db.session.commit()
        
        return jsonify({'success': f'Course "{course.course_name}" created successfully!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@branch_bp.route('/courses/edit/<int:course_id>', methods=['POST'])
def edit_course(course_id):
    """Edit existing course"""
    if not session.get('user_id') or session.get('role') not in ['admin', 'corporate_admin']:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        course = Course.query.get_or_404(course_id)
        
        course.course_name = request.form.get('course_name')
        course.duration = request.form.get('duration')
        course.fee = float(request.form.get('fee'))
        course.description = request.form.get('description')
        course.status = request.form.get('status')
        
        db.session.commit()
        
        return jsonify({'success': f'Course "{course.course_name}" updated successfully!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@branch_bp.route('/courses/delete/<int:course_id>', methods=['POST'])
def delete_course(course_id):
    """Soft delete a course"""
    if not session.get('user_id') or session.get('role') not in ['admin', 'corporate_admin']:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        course = Course.query.get_or_404(course_id)
        
        # Check if course has active batches
        from models.batch_model import Batch
        active_batches = Batch.query.filter_by(course_name=course.course_name, is_deleted=0).count()
        
        if active_batches > 0:
            return jsonify({'error': f'Cannot delete course with {active_batches} active batches'}), 400
        
        course.is_deleted = 1
        course.status = 'Inactive'
        db.session.commit()
        
        return jsonify({'success': f'Course "{course.course_name}" deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# API endpoints for AJAX calls
@branch_bp.route('/api/branches')
def api_branches():
    """API endpoint to get all active branches"""
    branches = Branch.query.filter_by(is_deleted=0, status='Active').all()
    return jsonify([branch.to_dict() for branch in branches])

@branch_bp.route('/api/courses')
def api_courses():
    """API endpoint to get all active courses"""
    courses = Course.query.filter_by(is_deleted=0, status='Active').all()
    return jsonify([{
        'id': course.id,
        'course_name': course.course_name,
        'duration': course.duration,
        'fee': course.fee,
        'description': course.description
    } for course in courses])
