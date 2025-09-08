"""
Model Helper Functions for UTC to IST Conversion
Provides consistent datetime formatting across all models
"""

from utils.timezone_helper import format_datetime_indian, format_date_indian

def safe_format_datetime(dt, include_time=True, include_seconds=False):
    """
    Safely format datetime with timezone conversion
    
    Args:
        dt: datetime object or None
        include_time: Include time portion
        include_seconds: Include seconds
    
    Returns:
        str: Formatted datetime string in IST or None
    """
    if dt is None:
        return None
    return format_datetime_indian(dt, include_time, include_seconds)

def safe_format_date(dt):
    """
    Safely format date
    
    Args:
        dt: date object or None
    
    Returns:
        str: Formatted date string or None
    """
    if dt is None:
        return None
    return format_date_indian(dt)

def standardize_model_datetime_fields(model_instance, datetime_fields=None):
    """
    Standardize datetime fields in model to_dict() output
    
    Args:
        model_instance: SQLAlchemy model instance
        datetime_fields: List of datetime fields to format, if None auto-detects
    
    Returns:
        dict: Model data with standardized datetime formatting
    """
    data = {}
    
    # Auto-detect datetime fields if not provided
    if datetime_fields is None:
        datetime_fields = []
        for column in model_instance.__table__.columns:
            if str(column.type).startswith('DATETIME'):
                datetime_fields.append(column.name)
    
    # Process all columns
    for column in model_instance.__table__.columns:
        field_name = column.name
        value = getattr(model_instance, field_name, None)
        
        if value is None:
            data[field_name] = None
        elif field_name in datetime_fields:
            data[field_name] = safe_format_datetime(value, include_time=True, include_seconds=True)
        elif hasattr(value, 'strftime'):
            # Auto-detect datetime/date
            if hasattr(value, 'hour'):  # datetime
                data[field_name] = safe_format_datetime(value, include_time=True, include_seconds=False)
            else:  # date
                data[field_name] = safe_format_date(value)
        else:
            data[field_name] = value
    
    return data

# Template for adding to existing models
MODEL_TO_DICT_TEMPLATE = '''
def to_dict(self):
    """Convert model to dictionary with proper timezone formatting"""
    from utils.model_helpers import standardize_model_datetime_fields
    
    # Get base data with automatic timezone formatting
    data = standardize_model_datetime_fields(self)
    
    # Add any custom fields or overrides here
    # data['custom_field'] = self.custom_property
    
    return data
'''

print("Model helper functions created for consistent UTC to IST conversion!")
