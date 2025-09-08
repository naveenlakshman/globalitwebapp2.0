"""
Search utility functions for the Global IT Web Application
"""
from sqlalchemy import or_, and_, func
from models.student_model import Student
from models.batch_model import Batch
from models.user_model import User


def search_students(query, branch_id=None, exclude_batch_id=None, limit=50):
    """
    Search students by name, student ID, mobile number, or email
    
    Args:
        query (str): Search query string
        branch_id (int, optional): Filter by branch ID
        exclude_batch_id (int, optional): Exclude students from this batch
        limit (int): Maximum number of results to return
        
    Returns:
        list: List of Student objects matching the search criteria
    """
    if not query or len(query.strip()) < 2:
        # If query is too short, return all students with filters
        student_query = Student.query
    else:
        # Clean the query
        search_term = f"%{query.strip()}%"
        
        # Build search query - search in multiple fields
        student_query = Student.query.filter(
            or_(
                func.lower(Student.full_name).like(func.lower(search_term)),
                func.lower(Student.student_id).like(func.lower(search_term)),
                func.lower(Student.mobile).like(func.lower(search_term)),
                func.lower(Student.email).like(func.lower(search_term))
            )
        )
    
    # Apply branch filter if provided
    if branch_id:
        student_query = student_query.filter(Student.branch_id == branch_id)
    
    # Exclude students from specific batch if provided
    if exclude_batch_id:
        student_query = student_query.filter(Student.batch_id != exclude_batch_id)
    
    # Order by relevance (exact matches first, then partial matches)
    if query and len(query.strip()) >= 2:
        exact_term = query.strip()
        student_query = student_query.order_by(
            # Exact matches first
            func.lower(Student.full_name) == func.lower(exact_term).desc(),
            func.lower(Student.student_id) == func.lower(exact_term).desc(),
            # Then partial matches by name
            Student.full_name.asc()
        )
    else:
        student_query = student_query.order_by(Student.full_name.asc())
    
    return student_query.limit(limit).all()


def search_students_for_batch(query, batch_id, limit=50):
    """
    Search for students that can be added to a specific batch
    (excludes students already in the batch and filters by branch)
    
    Args:
        query (str): Search query string
        batch_id (int): Target batch ID
        limit (int): Maximum number of results to return
        
    Returns:
        list: List of Student objects that can be added to the batch
    """
    # Get the batch to determine branch
    batch = Batch.query.get(batch_id)
    if not batch:
        return []
    
    return search_students(
        query=query,
        branch_id=batch.branch_id,
        exclude_batch_id=batch_id,
        limit=limit
    )


def search_batches(query, branch_id=None, limit=50):
    """
    Search batches by name, course name, or batch code
    
    Args:
        query (str): Search query string
        branch_id (int, optional): Filter by branch ID
        limit (int): Maximum number of results to return
        
    Returns:
        list: List of Batch objects matching the search criteria
    """
    if not query or len(query.strip()) < 2:
        batch_query = Batch.query
    else:
        search_term = f"%{query.strip()}%"
        batch_query = Batch.query.filter(
            or_(
                func.lower(Batch.name).like(func.lower(search_term)),
                func.lower(Batch.course_name).like(func.lower(search_term))
            )
        )
    
    # Apply branch filter if provided
    if branch_id:
        batch_query = batch_query.filter(Batch.branch_id == branch_id)
    
    return batch_query.order_by(Batch.name.asc()).limit(limit).all()


def search_users(query, role=None, branch_id=None, limit=50):
    """
    Search users by name, username, or email
    
    Args:
        query (str): Search query string
        role (str, optional): Filter by user role
        branch_id (int, optional): Filter by branch ID
        limit (int): Maximum number of results to return
        
    Returns:
        list: List of User objects matching the search criteria
    """
    if not query or len(query.strip()) < 2:
        user_query = User.query
    else:
        search_term = f"%{query.strip()}%"
        user_query = User.query.filter(
            or_(
                func.lower(User.full_name).like(func.lower(search_term)),
                func.lower(User.username).like(func.lower(search_term)),
                func.lower(User.email).like(func.lower(search_term))
            )
        )
    
    # Apply role filter if provided
    if role:
        user_query = user_query.filter(User.role == role)
    
    # Apply branch filter if provided (assuming users have branch_id)
    if branch_id and hasattr(User, 'branch_id'):
        user_query = user_query.filter(User.branch_id == branch_id)
    
    return user_query.order_by(User.full_name.asc()).limit(limit).all()


def get_search_suggestions(query, search_type='students', **kwargs):
    """
    Get search suggestions based on partial query
    
    Args:
        query (str): Partial search query
        search_type (str): Type of search ('students', 'batches', 'users')
        **kwargs: Additional arguments for specific search functions
        
    Returns:
        list: List of suggestions (dictionaries with id, text, and type)
    """
    suggestions = []
    
    if len(query.strip()) < 2:
        return suggestions
    
    try:
        if search_type == 'students':
            results = search_students(query, **kwargs)
            for student in results[:10]:  # Limit suggestions
                suggestions.append({
                    'id': student.student_id,
                    'text': f"{student.full_name} ({student.student_id})",
                    'type': 'student',
                    'mobile': student.mobile,
                    'email': student.email
                })
        
        elif search_type == 'batches':
            results = search_batches(query, **kwargs)
            for batch in results[:10]:
                suggestions.append({
                    'id': batch.id,
                    'text': f"{batch.name} - {batch.course_name}",
                    'type': 'batch',
                    'course': batch.course_name
                })
        
        elif search_type == 'users':
            results = search_users(query, **kwargs)
            for user in results[:10]:
                suggestions.append({
                    'id': user.id,
                    'text': f"{user.full_name} ({user.username})",
                    'type': 'user',
                    'role': user.role,
                    'email': user.email
                })
    
    except Exception as e:
        # Log error and return empty suggestions
        print(f"Error in get_search_suggestions: {e}")
    
    return suggestions
