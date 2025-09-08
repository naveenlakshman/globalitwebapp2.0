# Student Authentication Utilities
# Global IT Education Management System - Student Portal
# This file provides authentication decorators and utilities specifically for student access

from functools import wraps
from flask import session, redirect, url_for, flash, request
from models.student_model import Student

def student_required(f):
    """
    Decorator to ensure only authenticated students can access certain routes.
    This works alongside existing authentication without interfering.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is logged in
        if 'user_id' not in session:
            flash('Please login to access the student portal.', 'warning')
            return redirect(url_for('student_portal.student_login'))
        
        # Check if user has student role
        if session.get('role') != 'student':
            flash('Student access required. Please login with your student credentials.', 'error')
            return redirect(url_for('student_portal.student_login'))
        
        # Verify student exists and is active
        student_id = session.get('student_id')
        if not student_id:
            flash('Invalid student session. Please login again.', 'error')
            return redirect(url_for('student_portal.student_login'))
            
        student = Student.query.filter_by(student_id=student_id).first()
        if not student:
            flash('Student account not found. Please contact support.', 'error')
            return redirect(url_for('student_portal.student_login'))
        
        # Check if portal is enabled for this student (optional feature)
        if hasattr(student, 'portal_enabled') and not student.portal_enabled:
            flash('Your portal access has been disabled. Please contact support.', 'error')
            return redirect(url_for('student_portal.student_login'))
        
        return f(*args, **kwargs)
    return decorated_function

def get_current_student():
    """
    Helper function to get the currently logged-in student.
    Returns Student object or None if not logged in as student.
    """
    if session.get('role') == 'student' and 'student_id' in session:
        try:
            return Student.query.filter_by(student_id=session['student_id']).first()
        except Exception as e:
            print(f"Error getting current student: {e}")
            return None
    return None

def student_login_required(f):
    """
    Alternative decorator that just checks for student login without role validation.
    Useful for routes that might be accessible to multiple roles but need student context.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'student_id' not in session:
            flash('Please login to access this feature.', 'warning')
            return redirect(url_for('student_portal.student_login'))
        return f(*args, **kwargs)
    return decorated_function

def get_student_context():
    """
    Get comprehensive student context for templates.
    Returns dictionary with student information and portal settings.
    """
    student = get_current_student()
    if not student:
        return {}
    
    return {
        'student': student,
        'student_id': student.student_id,
        'student_name': student.full_name,
        'course_id': student.course_id,
        'branch_id': student.branch_id,
        'is_student_portal': True
    }

def log_student_activity(student_id, activity_type, description=None):
    """
    Log student portal activities for audit purposes.
    This works alongside existing audit logging.
    """
    try:
        from datetime import datetime
        # You can extend this to log to database or files
        print(f"[{datetime.now()}] Student {student_id}: {activity_type} - {description}")
    except Exception as e:
        print(f"Error logging student activity: {e}")
