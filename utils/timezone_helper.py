"""
Enhanced Timezone Helper for Global IT Web Application
Provides standardized date/time formatting for Indian users

Target Format: DD-MMM-YYYY HH:MM (e.g., 15-Aug-2025 14:30)
Timezone: UTC to IST conversion
"""

from datetime import datetime, timezone, date
import pytz

# Indian Standard Time timezone
IST = pytz.timezone('Asia/Kolkata')

def utc_to_ist(dt):
    """
    Convert UTC datetime to IST with basic formatting (Legacy function)
    
    Args:
        dt: datetime object (assumed to be in UTC)
    
    Returns:
        str: Formatted datetime string in IST
    """
    if dt is None:
        return None
    
    # Ensure datetime is timezone-aware (UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.utc)
    elif dt.tzinfo != pytz.utc:
        dt = dt.astimezone(pytz.utc)
    
    # Convert to IST
    ist_dt = dt.astimezone(IST)
    return ist_dt.strftime("%Y-%m-%d %H:%M:%S")

def format_datetime_indian(dt, include_time=True, include_seconds=False):
    """
    Format datetime in Indian-friendly format: DD-MMM-YYYY HH:MM
    
    Args:
        dt: datetime object (assumed to be in UTC)
        include_time: bool, whether to include time portion
        include_seconds: bool, whether to include seconds
    
    Returns:
        str: Formatted datetime string
    """
    if dt is None:
        return ""
    
    # Handle string inputs (for backward compatibility)
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except:
            return dt  # Return as-is if parsing fails
    
    # Ensure datetime is timezone-aware (UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.utc)
    elif dt.tzinfo != pytz.utc:
        dt = dt.astimezone(pytz.utc)
    
    # Convert to IST
    ist_dt = dt.astimezone(IST)
    
    if include_time:
        if include_seconds:
            return ist_dt.strftime("%d-%b-%Y %H:%M:%S")
        else:
            return ist_dt.strftime("%d-%b-%Y %H:%M")
    else:
        return ist_dt.strftime("%d-%b-%Y")

def format_date_indian(dt):
    """
    Format date only in Indian format: DD-MMM-YYYY
    
    Args:
        dt: datetime or date object
    
    Returns:
        str: Formatted date string
    """
    if dt is None:
        return ""
    
    # Handle string inputs
    if isinstance(dt, str):
        try:
            dt = datetime.strptime(dt, '%Y-%m-%d').date()
        except:
            return dt  # Return as-is if parsing fails
    
    # Handle both datetime and date objects
    if hasattr(dt, 'date'):
        dt = dt.date()
    
    return dt.strftime("%d-%b-%Y")

def format_time_indian(dt):
    """
    Format time only in Indian format: HH:MM
    
    Args:
        dt: datetime object (assumed to be in UTC)
    
    Returns:
        str: Formatted time string in IST
    """
    if dt is None:
        return ""
    
    # Ensure datetime is timezone-aware (UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.utc)
    elif dt.tzinfo != pytz.utc:
        dt = dt.astimezone(pytz.utc)
    
    # Convert to IST
    ist_dt = dt.astimezone(IST)
    return ist_dt.strftime("%H:%M")

def get_current_ist_datetime():
    """
    Get current datetime in IST
    
    Returns:
        datetime: Current datetime in IST timezone
    """
    return datetime.now(IST)

def get_current_ist_formatted(include_time=True, include_seconds=False):
    """
    Get current datetime formatted in Indian format
    
    Args:
        include_time: bool, whether to include time portion
        include_seconds: bool, whether to include seconds
    
    Returns:
        str: Current datetime in Indian format
    """
    current_dt = get_current_ist_datetime()
    
    if include_time:
        if include_seconds:
            return current_dt.strftime("%d-%b-%Y %H:%M:%S")
        else:
            return current_dt.strftime("%d-%b-%Y %H:%M")
    else:
        return current_dt.strftime("%d-%b-%Y")

def parse_date_string(date_str, input_format="%Y-%m-%d"):
    """
    Parse date string and return date object
    
    Args:
        date_str: str, date string to parse
        input_format: str, format of input date string
    
    Returns:
        date: Parsed date object
    """
    if not date_str:
        return None
    
    try:
        return datetime.strptime(date_str, input_format).date()
    except ValueError:
        return None

# Jinja2 template filters
def register_template_filters(app):
    """
    Register custom Jinja2 filters for the Flask app
    
    Args:
        app: Flask application instance
    """
    
    @app.template_filter('format_datetime_indian')
    def _format_datetime_indian(dt, include_time=True, include_seconds=False):
        return format_datetime_indian(dt, include_time, include_seconds)
    
    @app.template_filter('format_date_indian')
    def _format_date_indian(dt):
        return format_date_indian(dt)
    
    @app.template_filter('format_time_indian')
    def _format_time_indian(dt):
        return format_time_indian(dt)
    
    @app.template_filter('format_datetime')
    def _format_datetime_legacy(dt):
        """Legacy filter for backward compatibility"""
        return format_datetime_indian(dt, include_time=True, include_seconds=False)

class TimezoneAwareMixin:
    """
    Mixin class to provide consistent timezone-aware datetime formatting
    for all models. Add this to any model that has datetime fields.
    """
    
    def format_datetime_field(self, field_name, include_time=True, include_seconds=False):
        """
        Format any datetime field using Indian timezone
        
        Args:
            field_name: Name of the datetime field
            include_time: Include time portion
            include_seconds: Include seconds
        
        Returns:
            str: Formatted datetime string in IST
        """
        value = getattr(self, field_name, None)
        return format_datetime_indian(value, include_time, include_seconds)
    
    def format_date_field(self, field_name):
        """Format any date field using Indian format"""
        value = getattr(self, field_name, None)
        return format_date_indian(value)
    
    def to_dict_with_timezone(self, datetime_fields=None, date_fields=None):
        """
        Helper method to convert model to dict with proper timezone formatting
        
        Args:
            datetime_fields: List of datetime field names to format
            date_fields: List of date field names to format
        
        Returns:
            dict: Model data with properly formatted datetime/date fields
        """
        data = {}
        
        # Get all columns
        for column in self.__table__.columns:
            field_name = column.name
            value = getattr(self, field_name, None)
            
            if value is None:
                data[field_name] = None
            elif datetime_fields and field_name in datetime_fields:
                # Format as Indian datetime
                data[field_name] = format_datetime_indian(value, include_time=True, include_seconds=False)
            elif date_fields and field_name in date_fields:
                # Format as Indian date
                data[field_name] = format_date_indian(value)
            elif hasattr(value, 'strftime'):
                # Auto-detect datetime/date fields
                if hasattr(value, 'hour'):  # It's a datetime
                    data[field_name] = format_datetime_indian(value, include_time=True, include_seconds=False)
                else:  # It's a date
                    data[field_name] = format_date_indian(value)
            else:
                data[field_name] = value
                
        return data
