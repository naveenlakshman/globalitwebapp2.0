"""
Caching utilities for performance optimization
Provides decorators and utilities for caching expensive operations
"""

import functools
import time
from flask import g, current_app, session
from datetime import datetime, timedelta

# Simple in-memory cache for development
_cache = {}
_cache_timestamps = {}

def get_cache_key(prefix, *args, **kwargs):
    """Generate a cache key from function arguments"""
    # Include user context in cache key for security
    user_id = session.get('user_id', 'anonymous')
    user_role = session.get('user_role', 'guest')
    
    # Create a hash of arguments
    arg_str = str(args) + str(sorted(kwargs.items()))
    return f"{prefix}:{user_id}:{user_role}:{hash(arg_str)}"

def cache_result(timeout=300, key_prefix=None):
    """
    Decorator to cache function results
    
    Args:
        timeout: Cache timeout in seconds (default: 5 minutes)
        key_prefix: Custom prefix for cache key
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            prefix = key_prefix or func.__name__
            cache_key = get_cache_key(prefix, *args, **kwargs)
            
            # Check if cached result exists and is still valid
            if cache_key in _cache and cache_key in _cache_timestamps:
                cache_time = _cache_timestamps[cache_key]
                if time.time() - cache_time < timeout:
                    return _cache[cache_key]
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            
            # Store in cache
            _cache[cache_key] = result
            _cache_timestamps[cache_key] = time.time()
            
            # Clean old cache entries periodically
            _cleanup_cache()
            
            return result
        return wrapper
    return decorator

def _cleanup_cache():
    """Remove expired cache entries"""
    current_time = time.time()
    expired_keys = [
        key for key, timestamp in _cache_timestamps.items()
        if current_time - timestamp > 3600  # Remove entries older than 1 hour
    ]
    
    for key in expired_keys:
        _cache.pop(key, None)
        _cache_timestamps.pop(key, None)

def clear_cache(pattern=None):
    """
    Clear cache entries
    
    Args:
        pattern: If provided, only clear keys containing this pattern
    """
    if pattern:
        keys_to_remove = [key for key in _cache.keys() if pattern in key]
        for key in keys_to_remove:
            _cache.pop(key, None)
            _cache_timestamps.pop(key, None)
    else:
        _cache.clear()
        _cache_timestamps.clear()

def invalidate_user_cache(user_id):
    """Invalidate all cache entries for a specific user"""
    clear_cache(f":{user_id}:")

# Dashboard-specific caching utilities
class DashboardCache:
    """Utilities for caching dashboard data"""
    
    @staticmethod
    @cache_result(timeout=300, key_prefix='dashboard_stats')  # 5 minutes
    def get_student_stats(branch_id=None):
        """Get cached student statistics"""
        from models.student_model import Student
        
        query = Student.query.filter_by(is_deleted=0)
        if branch_id:
            query = query.filter_by(branch_id=branch_id)
        
        total = query.count()
        active = query.filter_by(status='Active').count()
        
        return {
            'total_students': total,
            'active_students': active,
            'cached_at': datetime.now().isoformat()
        }
    
    @staticmethod
    @cache_result(timeout=300, key_prefix='dashboard_leads')  # 5 minutes
    def get_lead_stats(branch_id=None):
        """Get cached lead statistics"""
        from models.lead_model import Lead
        
        query = Lead.query.filter_by(is_deleted=False)
        if branch_id:
            query = query.filter_by(branch_id=branch_id)
        
        total = query.count()
        open_leads = query.filter_by(lead_status='Open').count()
        converted = query.filter_by(lead_status='Converted').count()
        
        return {
            'total_leads': total,
            'open_leads': open_leads,
            'converted_leads': converted,
            'cached_at': datetime.now().isoformat()
        }
    
    @staticmethod
    @cache_result(timeout=600, key_prefix='dashboard_financial')  # 10 minutes
    def get_financial_stats(branch_id=None):
        """Get cached financial statistics"""
        from models.payment_model import Payment
        from models.installment_model import Installment
        from sqlalchemy import func
        from init_db import db
        
        # Total collections
        payment_query = db.session.query(func.sum(Payment.amount))
        if branch_id:
            # Assuming payments have branch relationship through student
            from models.student_model import Student
            payment_query = payment_query.join(Student).filter(Student.branch_id == branch_id)
        
        total_collections = payment_query.scalar() or 0
        
        # Pending dues
        installment_query = db.session.query(func.sum(Installment.amount)).filter(
            Installment.status.in_(['pending', 'partial'])
        )
        
        pending_dues = installment_query.scalar() or 0
        
        return {
            'total_collections': float(total_collections),
            'pending_dues': float(pending_dues),
            'cached_at': datetime.now().isoformat()
        }

# Query optimization utilities
def optimize_pagination_query(query, page, per_page, count_query=None):
    """
    Optimize pagination for large datasets
    
    Args:
        query: SQLAlchemy query object
        page: Page number
        per_page: Items per page
        count_query: Optional separate count query for performance
    """
    try:
        # Use separate count query if provided (more efficient for large datasets)
        if count_query:
            total = count_query.scalar()
        else:
            total = query.count()
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Get items with limit and offset
        items = query.offset(offset).limit(per_page).all()
        
        # Calculate pagination info
        pages = (total + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < pages
        
        return {
            'items': items,
            'total': total,
            'pages': pages,
            'page': page,
            'per_page': per_page,
            'has_prev': has_prev,
            'has_next': has_next,
            'prev_num': page - 1 if has_prev else None,
            'next_num': page + 1 if has_next else None
        }
        
    except Exception as e:
        current_app.logger.error(f"Pagination error: {e}")
        return {
            'items': [],
            'total': 0,
            'pages': 0,
            'page': 1,
            'per_page': per_page,
            'has_prev': False,
            'has_next': False,
            'prev_num': None,
            'next_num': None
        }

# Performance monitoring decorator
def monitor_performance(func):
    """Decorator to monitor function execution time"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Log slow operations (>1 second)
            if duration > 1.0:
                current_app.logger.warning(
                    f"Slow operation: {func.__name__} took {duration:.2f}s"
                )
            
            return result
        except Exception as e:
            duration = time.time() - start_time
            current_app.logger.error(
                f"Error in {func.__name__} after {duration:.2f}s: {e}"
            )
            raise
    
    return wrapper

# Database connection optimization
def optimize_db_connection():
    """Apply SQLite optimizations to current connection"""
    try:
        from init_db import db
        
        # Apply SQLite-specific optimizations using text() for raw SQL
        from sqlalchemy import text
        
        db.session.execute(text("PRAGMA journal_mode=WAL;"))
        db.session.execute(text("PRAGMA synchronous=NORMAL;"))
        db.session.execute(text("PRAGMA cache_size=-32000;"))  # 32MB cache
        db.session.execute(text("PRAGMA temp_store=MEMORY;"))
        db.session.commit()
        
        current_app.logger.info("Database connection optimized")
        
    except Exception as e:
        current_app.logger.error(f"Database optimization error: {e}")
