from flask import render_template, session, request
from datetime import datetime
import uuid
import logging
from models.user_model import User
from models.branch_model import Branch
from init_db import db

def generate_error_report(error_message, module_name, action_attempted, error_type="SystemError"):
    """
    Generate a comprehensive error report page with all necessary details
    for easy debugging and user reporting.
    
    Args:
        error_message (str): The actual error message
        module_name (str): Name of the module where error occurred (e.g., "Finance", "Students")
        action_attempted (str): What the user was trying to do (e.g., "Loading Dashboard", "Recording Payment")
        error_type (str): Type of error (default: "SystemError")
    
    Returns:
        Rendered template with error details
    """
    
    # Generate unique error ID for tracking
    error_id = str(uuid.uuid4())[:8].upper()
    
    # Get current time in IST
    from utils.timezone_helper import get_current_ist_formatted
    error_time = get_current_ist_formatted()
    
    # Get user information
    user_info = {
        'username': 'Unknown',
        'role': 'Unknown',
        'branch_name': None
    }
    
    try:
        current_user_id = session.get('user_id')
        if current_user_id:
            user = User.query.get(current_user_id)
            if user:
                user_info['username'] = user.username
                user_info['role'] = user.role
                
                # Get branch name if user has branch_id
                if hasattr(user, 'branch_id') and user.branch_id:
                    branch = Branch.query.get(user.branch_id)
                    if branch:
                        user_info['branch_name'] = branch.branch_name
    except Exception:
        # If we can't get user info, use defaults
        pass
    
    # Get request information
    request_route = request.endpoint if request else 'Unknown'
    request_method = request.method if request else 'Unknown'
    
    # Log the error for admin tracking
    try:
        logging.error(f"Error ID {error_id}: {error_message} | Module: {module_name} | User: {user_info['username']} | Route: {request_route}")
    except Exception:
        # If logging fails, continue anyway
        pass
    
    # Render the error report template
    return render_template('error_report.html',
                         error_id=error_id,
                         error_message=error_message,
                         error_type=error_type,
                         module_name=module_name,
                         action_attempted=action_attempted,
                         error_time=error_time,
                         user_info=user_info,
                         request_route=request_route,
                         request_method=request_method)

def handle_finance_error(error_message, action_attempted):
    """
    Convenience function specifically for finance module errors
    """
    return generate_error_report(
        error_message=error_message,
        module_name="Finance",
        action_attempted=action_attempted,
        error_type="FinanceModuleError"
    )

def handle_database_error(error_message, action_attempted, module_name):
    """
    Convenience function for database-related errors
    """
    return generate_error_report(
        error_message=error_message,
        module_name=module_name,
        action_attempted=action_attempted,
        error_type="DatabaseError"
    )

def handle_permission_error(error_message, action_attempted, module_name):
    """
    Convenience function for permission-related errors
    """
    return generate_error_report(
        error_message=error_message,
        module_name=module_name,
        action_attempted=action_attempted,
        error_type="PermissionError"
    )
