from functools import wraps
from flask import session, redirect, url_for, flash, request, current_app
import logging

def login_required(f):
    """Decorator to require user login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(allowed_roles):
    """Decorator to require specific user roles"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.', 'error')
                return redirect(url_for('auth.login', next=request.url))
            
            user_role = session.get('role')
            if user_role not in allowed_roles:
                flash('You do not have permission to access this page.', 'error')
                current_app.logger.warning(f"User {session.get('user_id')} with role '{user_role}' attempted to access restricted resource")
                return redirect(url_for('dashboard_bp.admin_dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    """Decorator to require admin role only"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth.login', next=request.url))
        
        user_role = session.get('role')
        if user_role != 'admin':
            flash('Access denied. This feature is restricted to administrators only.', 'error')
            current_app.logger.warning(f"User {session.get('user_id')} with role '{user_role}' attempted to access admin-only resource")
            # Redirect to invoice list instead of dashboard
            return redirect(url_for('invoices.list_invoices'))
        
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Get current logged-in user information"""
    if 'user_id' in session:
        return {
            'user_id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role'),
            'branch_id': session.get('branch_id'),
            'full_name': session.get('full_name')
        }
    return None

def is_admin():
    """Check if current user is admin"""
    return session.get('role') == 'admin'

def is_franchise():
    """Check if current user is franchise owner"""
    return session.get('role') == 'franchise'

def is_manager():
    """Check if current user is manager (includes regional and branch managers)"""
    return session.get('role') in ['manager', 'regional_manager', 'branch_manager']

def is_regional_manager():
    """Check if current user is regional manager"""
    return session.get('role') == 'regional_manager'

def is_branch_manager():
    """Check if current user is branch manager"""
    return session.get('role') == 'branch_manager'

def is_staff():
    """Check if current user is staff"""
    return session.get('role') == 'staff'

def can_access_branch(branch_id):
    """Check if current user can access specific branch"""
    user_role = session.get('role')
    user_branch_id = session.get('branch_id')
    
    # Admin can access all branches
    if user_role == 'admin':
        return True
    
    # Regional managers can access assigned branches (need to check user_branch_assignments)
    if user_role == 'regional_manager':
        # For now, allow access - this should be enhanced with proper branch assignment checking
        return True
    
    # Managers can access all branches (backward compatibility)
    if user_role == 'manager':
        return True
    
    # Franchise, branch managers, staff, and trainers can only access their assigned branch
    if user_role in ['franchise', 'branch_manager', 'staff', 'trainer']:
        return str(user_branch_id) == str(branch_id)
    
    return False

def log_access_attempt(resource, success=True):
    """Log access attempts for security auditing"""
    user_id = session.get('user_id', 'anonymous')
    user_role = session.get('role', 'unknown')
    
    if success:
        current_app.logger.info(f"User {user_id} ({user_role}) accessed {resource}")
    else:
        current_app.logger.warning(f"User {user_id} ({user_role}) denied access to {resource}")
