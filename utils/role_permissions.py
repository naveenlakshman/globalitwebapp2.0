"""
Enhanced Role-Based Access Control Utilities
Functions to check permissions based on the new role system
"""

from models.user_model import User
from models.branch_model import Branch
from init_db import db
from flask import session, flash, redirect, url_for
from functools import wraps
from sqlalchemy import text

def get_user_branch_access(user_id):
    """Get all branches a user has access to with their role at each branch"""
    try:
        # Query the user_branch_assignments table
        result = db.session.execute(text('''
            SELECT uba.branch_id, uba.role_at_branch, b.branch_name
            FROM user_branch_assignments uba
            JOIN branches b ON uba.branch_id = b.id
            WHERE uba.user_id = :user_id AND uba.is_active = 1
        '''), {'user_id': user_id}).fetchall()
        
        return [{'branch_id': row[0], 'role': row[1], 'branch_name': row[2]} for row in result]
    except Exception as e:
        print(f"Error in get_user_branch_access: {e}")
        # Fallback to old system
        user = User.query.get(user_id)
        if user and user.branch_id:
            branch = Branch.query.get(user.branch_id)
            return [{'branch_id': user.branch_id, 'role': user.role, 'branch_name': branch.branch_name if branch else 'Unknown'}]
        return []

def get_user_accessible_branches(user_id):
    """Get list of branch IDs the user can access"""
    branch_access = get_user_branch_access(user_id)
    return [access['branch_id'] for access in branch_access]

def check_module_permission(user_id, module, action='read'):
    """Check if user has permission for a specific module and action"""
    try:
        user = User.query.get(user_id)
        if not user:
            return False
        
        # Admin has access to everything
        if user.role == 'admin':
            return True
        
        # Try to check role permissions table if it exists
        try:
            result = db.session.execute(text('''
                SELECT permission_level, can_export, can_modify, can_delete, can_create
                FROM role_permissions
                WHERE role = :role AND module = :module
            '''), {'role': user.role, 'module': module}).fetchone()
            
            if result:
                permission_level, can_export, can_modify, can_delete, can_create = result
                
                # Check action permission
                if action == 'read' and permission_level in ['read', 'write', 'full']:
                    return True
                elif action == 'write' and permission_level in ['write', 'full']:
                    return True
                elif action == 'export' and can_export:
                    return True
                elif action == 'modify' and can_modify:
                    return True
                elif action == 'delete' and can_delete:
                    return True
                elif action == 'create' and can_create:
                    return True
                elif action == 'full' and permission_level == 'full':
                    return True
                    
                return False
        except Exception as e:
            # If role_permissions table doesn't exist, use fallback logic
            print(f"Role permissions table not found, using fallback: {e}")
            pass
        
        # Fallback permission logic for when role_permissions table doesn't exist
        if module == 'finance':
            # Finance module access based on role
            if user.role in ['admin', 'regional_manager', 'manager', 'franchise', 'branch_manager']:
                return True
            elif user.role == 'staff' and action in ['read', 'export']:
                return True
        elif module == 'leads':
            # Trainers should not have access to leads
            if user.role == 'trainer':
                return False
            else:
                return True
        elif module == 'students':
            # All roles except trainer should have student access
            if user.role == 'trainer':
                return action in ['read']  # Trainers can only read students
            else:
                return True
        elif module == 'attendance':
            # All roles have attendance access
            return True
        else:
            # Default access for other modules
            return user.role in ['admin', 'regional_manager', 'manager', 'franchise', 'branch_manager', 'staff']
        
        return False
        
    except Exception as e:
        print(f"Error in check_module_permission: {e}")
        # Final fallback - basic role check
        user = User.query.get(user_id)
        if user and user.role in ['admin', 'manager', 'franchise']:
            return True
        return False

def get_finance_branch_filter(user_id):
    """Get SQLAlchemy filter condition for finance queries based on user's branch access"""
    from models.student_model import Student
    
    user = User.query.get(user_id)
    if not user:
        return False
    
    # Admin sees everything
    if user.role == 'admin':
        return True
    
    # Get user's accessible branches
    accessible_branches = get_user_accessible_branches(user_id)
    
    if not accessible_branches:
        return False
    
    # If user has access to multiple branches, use IN clause
    if len(accessible_branches) == 1:
        return Student.branch_id == accessible_branches[0]
    else:
        return Student.branch_id.in_(accessible_branches)

def require_finance_permission(action='read'):
    """Decorator to check finance module permissions"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get('user_id')
            if not user_id:
                flash('Please log in', 'error')
                return redirect(url_for('auth.login'))
            
            if not check_module_permission(user_id, 'finance', action):
                flash('Access denied: Insufficient permissions', 'error')
                return redirect(url_for('dashboard_bp.admin_dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def can_export_financial_data(user_id):
    """Check if user can export financial data"""
    return check_module_permission(user_id, 'finance', 'export')

def can_modify_financial_data(user_id):
    """Check if user can modify financial data (collect payments, etc.)"""
    return check_module_permission(user_id, 'finance', 'modify')

def get_user_role_summary(user_id):
    """Get a summary of user's roles across branches"""
    user = User.query.get(user_id)
    if not user:
        return None
    
    branch_access = get_user_branch_access(user_id)
    
    return {
        'user_id': user_id,
        'username': user.username,
        'full_name': user.full_name,
        'primary_role': user.role,
        'branch_access': branch_access,
        'accessible_branch_count': len(branch_access),
        'is_admin': user.role == 'admin',
        'is_multi_branch': len(branch_access) > 1
    }
