"""
Utility functions to help with branch access control and multi-branch support
"""
from flask import session

def get_user_accessible_branch_ids():
    """
    Get all branch IDs the current user can access.
    Returns a list of branch IDs based on user role and assignments.
    """
    user_role = session.get("role")
    
    # Corporate users can see all branches
    if user_role in ['admin', 'super_admin', 'corporate_admin']:
        from models.branch_model import Branch
        all_branches = Branch.query.filter_by(is_deleted=0).all()
        return [branch.id for branch in all_branches]
    
    # For franchise and other roles, use their assigned branches
    user_branch_ids = session.get("user_branch_ids", [])
    
    # Fallback to single branch for backward compatibility
    if not user_branch_ids:
        user_branch_id = session.get("user_branch_id")
        if user_branch_id:
            user_branch_ids = [user_branch_id]
    
    return user_branch_ids

def get_user_branch_filter_condition(branch_column):
    """
    Get a filter condition for SQLAlchemy queries based on user's accessible branches.
    
    Args:
        branch_column: The column to filter on (e.g., Student.branch_id)
    
    Returns:
        SQLAlchemy filter condition or None if user has access to all branches
    """
    user_role = session.get("role")
    
    # Corporate users can see all branches - no filter needed
    if user_role in ['admin', 'super_admin', 'corporate_admin']:
        return None
    
    # Get accessible branch IDs
    accessible_branch_ids = get_user_accessible_branch_ids()
    
    if accessible_branch_ids:
        return branch_column.in_(accessible_branch_ids)
    else:
        # If no branches assigned, return condition that matches nothing
        return branch_column.in_([])

def get_user_branch_names():
    """
    Get a human-readable string of branch names the user can access
    """
    all_branch_names = session.get("all_branch_names", [])
    
    if all_branch_names:
        if len(all_branch_names) == 1:
            return all_branch_names[0]
        else:
            return ", ".join(all_branch_names)
    
    # Fallback to single branch name
    branch_name = session.get("branch_name")
    return branch_name if branch_name else "No Branch Assigned"

def user_can_access_branch(branch_id):
    """
    Check if the current user can access a specific branch
    
    Args:
        branch_id: The branch ID to check access for
        
    Returns:
        bool: True if user can access the branch, False otherwise
    """
    accessible_branch_ids = get_user_accessible_branch_ids()
    return branch_id in accessible_branch_ids