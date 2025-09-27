import pandas as pd
import re
from datetime import datetime
from typing import Dict, List, Tuple, Any

class DataValidator:
    """Centralized data validation for imports"""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        if not email:
            return True  # Email is optional
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_mobile(mobile: str) -> bool:
        """Validate mobile number format"""
        if not mobile:
            return False
        # Remove any spaces or special characters
        mobile_clean = re.sub(r'[^\d]', '', str(mobile))
        # Check if it's 10 digits
        return len(mobile_clean) == 10 and mobile_clean.isdigit()
    
    @staticmethod
    def validate_date(date_str: str, date_format: str = '%Y-%m-%d') -> bool:
        """Validate date format - supports DD-MM-YYYY, DD/MM/YYYY, DD.MM.YYYY formats"""
        if not date_str:
            return True  # Date might be optional
        try:
            # First try Indian formats (DD-MM-YYYY, DD/MM/YYYY, DD.MM.YYYY)
            indian_formats = ['%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y']
            for fmt in indian_formats:
                try:
                    datetime.strptime(str(date_str), fmt)
                    return True
                except ValueError:
                    continue
            
            # Fallback to original format
            datetime.strptime(str(date_str), date_format)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_datetime(datetime_str: str) -> bool:
        """Validate datetime format - supports DD-MM-YYYY HH:MM AM/PM and DD-MM-YYYY HH:MM formats"""
        if not datetime_str:
            return True  # DateTime might be optional
        try:
            import re
            
            # Check for Indian datetime formats
            indian_patterns = [
                # 12-hour format with AM/PM
                r'\d{1,2}-\d{1,2}-\d{4}\s+\d{1,2}:\d{2}\s*(AM|PM)',
                r'\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s*(AM|PM)',
                r'\d{1,2}\.\d{1,2}\.\d{4}\s+\d{1,2}:\d{2}\s*(AM|PM)',
                # 24-hour format without AM/PM
                r'\d{1,2}-\d{1,2}-\d{4}\s+\d{1,2}:\d{2}$',
                r'\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}$',
                r'\d{1,2}\.\d{1,2}\.\d{4}\s+\d{1,2}:\d{2}$'
            ]
            
            for pattern in indian_patterns:
                if re.match(pattern, str(datetime_str), re.IGNORECASE):
                    return True
            
            # Fallback to standard formats
            standard_formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y']
            for fmt in standard_formats:
                try:
                    datetime.strptime(str(datetime_str), fmt)
                    return True
                except ValueError:
                    continue
                    
            return False
        except Exception:
            return False
    
    @staticmethod
    def validate_amount(amount: Any) -> bool:
        """Validate amount is a valid number"""
        if amount is None or amount == '':
            return False
        try:
            float_amount = float(amount)
            return float_amount >= 0
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_required_fields(data: Dict, required_fields: List[str]) -> List[str]:
        """Check if required fields are present and not empty"""
        missing_fields = []
        for field in required_fields:
            if field not in data or not data[field] or str(data[field]).strip() == '':
                missing_fields.append(field)
        return missing_fields
    
    @staticmethod
    def validate_branch_exists(branch_id: Any) -> Tuple[bool, str]:
        """Validate that branch_id exists in database"""
        if not branch_id:
            return True, ""  # Optional field
        
        try:
            from flask import current_app
            from models.branch_model import Branch
            
            branch_id = int(branch_id)
            branch = Branch.query.filter_by(id=branch_id).first()
            
            if branch is None:
                available_branches = Branch.query.all()
                branch_list = [f"ID {b.id}: {b.branch_name}" for b in available_branches]
                return False, f"Branch ID {branch_id} does not exist. Available branches: {', '.join(branch_list)}"
            
            return True, ""
        except (ValueError, TypeError):
            return False, f"Invalid branch ID format: {branch_id}"
        except Exception as e:
            return False, f"Database error checking branch: {str(e)}"
    
    @staticmethod
    def validate_course_exists(course_id: Any = None, course_name: str = None) -> Tuple[bool, str]:
        """Validate that course_id or course_name exists in database"""
        if not course_id and not course_name:
            return True, ""  # Both optional
        
        try:
            from flask import current_app
            from models.course_model import Course
            
            if course_id:
                course_id = int(course_id)
                course = Course.query.filter_by(id=course_id).first()
                if course is None:
                    available_courses = Course.query.all()
                    course_list = [f"ID {c.id}: {c.course_name}" for c in available_courses]
                    return False, f"Course ID {course_id} does not exist. Available courses: {', '.join(course_list)}"
            
            if course_name:
                course = Course.query.filter_by(course_name=course_name).first()
                if course is None:
                    available_courses = Course.query.all()
                    course_list = [f"{c.course_name}" for c in available_courses]
                    return False, f"Course '{course_name}' does not exist. Available courses: {', '.join(course_list)}"
            
            return True, ""
        except (ValueError, TypeError):
            return False, f"Invalid course ID format: {course_id}"
        except Exception as e:
            return False, f"Database error checking course: {str(e)}"
    
    @staticmethod
    def validate_batch_exists(batch_id: Any, branch_id: Any = None, course_id: Any = None) -> Tuple[bool, str]:
        """Validate that batch_id exists and optionally belongs to specified branch/course"""
        if not batch_id:
            return True, ""  # Optional field
        
        try:
            from flask import current_app
            from models.batch_model import Batch
            
            batch_id = int(batch_id)
            batch = Batch.query.filter_by(id=batch_id).first()
            
            if batch is None:
                available_batches = Batch.query.all()
                batch_list = [f"ID {b.id}: {b.name} (Branch: {b.branch_id}, Course: {b.course_id})" for b in available_batches]
                return False, f"Batch ID {batch_id} does not exist. Available batches: {', '.join(batch_list)}"
            
            # Validate batch belongs to specified branch
            if branch_id and int(branch_id) != batch.branch_id:
                return False, f"Batch {batch_id} belongs to branch {batch.branch_id}, not branch {branch_id}"
            
            # Validate batch belongs to specified course
            if course_id and int(course_id) != batch.course_id:
                return False, f"Batch {batch_id} belongs to course {batch.course_id}, not course {course_id}"
            
            return True, ""
        except (ValueError, TypeError):
            return False, f"Invalid batch ID format: {batch_id}"
        except Exception as e:
            return False, f"Database error checking batch: {str(e)}"

class StudentValidator(DataValidator):
    """Specific validation for student data"""
    
    REQUIRED_FIELDS = ['full_name', 'mobile']
    OPTIONAL_FIELDS = ['student_reg_no', 'email', 'gender', 'dob', 'address', 'guardian_name', 'guardian_mobile', 
                      'qualification', 'course_name', 'branch_id', 'lead_source', 'status', 'admission_mode', 'referred_by']
    # Note: student_id is NOT in fields list - it's auto-generated and should not be in CSV
    
    VALID_GENDERS = ['Male', 'Female', 'Other']
    VALID_LEAD_SOURCES = ['Walk-in', 'Referral', 'Phone', 'Instagram', 'Facebook', 'Google', 
                         'College Visit', 'Tally', 'Other']
    VALID_STATUSES = ['Active', 'Hold', 'Inactive', 'Dropout', 'Completed']
    
    @classmethod
    def validate_row(cls, row_data: Dict, row_number: int) -> Tuple[bool, List[str]]:
        """Validate a single student row"""
        errors = []
        
        # Check required fields
        missing_fields = cls.validate_required_fields(row_data, cls.REQUIRED_FIELDS)
        if missing_fields:
            errors.append(f"Missing required fields: {', '.join(missing_fields)}")
        
        # Validate email
        if row_data.get('email') and not cls.validate_email(row_data['email']):
            errors.append("Invalid email format")
        
        # Validate mobile
        if row_data.get('mobile') and not cls.validate_mobile(row_data['mobile']):
            errors.append("Invalid mobile number (must be 10 digits)")
        
        # Validate guardian mobile
        if row_data.get('guardian_mobile') and not cls.validate_mobile(row_data['guardian_mobile']):
            errors.append("Invalid guardian mobile number")
        
        # Validate gender
        if row_data.get('gender') and row_data['gender'] not in cls.VALID_GENDERS:
            errors.append(f"Invalid gender. Must be one of: {', '.join(cls.VALID_GENDERS)}")
        
        # Validate lead source
        if row_data.get('lead_source') and row_data['lead_source'] not in cls.VALID_LEAD_SOURCES:
            errors.append(f"Invalid lead source. Must be one of: {', '.join(cls.VALID_LEAD_SOURCES)}")
        
        # Validate status
        if row_data.get('status') and row_data['status'] not in cls.VALID_STATUSES:
            errors.append(f"Invalid status. Must be one of: {', '.join(cls.VALID_STATUSES)}")
        
        # Validate date of birth
        if row_data.get('dob') and not cls.validate_date(str(row_data['dob'])):
            errors.append("Invalid date of birth format (expected DD-MM-YYYY, DD/MM/YYYY, or DD.MM.YYYY)")
        
        # Validate admission date
        if row_data.get('admission_date') and not cls.validate_datetime(str(row_data['admission_date'])):
            errors.append("Invalid admission date format (expected DD-MM-YYYY HH:MM AM/PM)")
        
        # Validate student registration number format (if provided)
        if row_data.get('student_reg_no'):
            reg_no = str(row_data['student_reg_no']).strip()
            if not cls.validate_registration_number(reg_no):
                errors.append("Invalid registration number format (expected format: GIT-1, GIT-2, etc.)")
        
        # DATABASE INTEGRITY VALIDATIONS
        # Validate branch exists
        if row_data.get('branch_id'):
            is_valid, error_msg = cls.validate_branch_exists(row_data['branch_id'])
            if not is_valid:
                errors.append(error_msg)
        
        # Validate course exists (either course_id or course_name)
        course_id = row_data.get('course_id')
        course_name = row_data.get('course_name')
        if course_id or course_name:
            is_valid, error_msg = cls.validate_course_exists(course_id, course_name)
            if not is_valid:
                errors.append(error_msg)
        
        # Validate batch exists and belongs to correct branch/course
        if row_data.get('batch_id'):
            is_valid, error_msg = cls.validate_batch_exists(
                row_data['batch_id'], 
                row_data.get('branch_id'), 
                row_data.get('course_id')
            )
            if not is_valid:
                errors.append(error_msg)
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_registration_number(reg_no: str) -> bool:
        """Validate student registration number format"""
        if not reg_no:
            return True  # Optional field
        
        # Expected format: PREFIX-NUMBER (e.g., GIT-1, GIT-2, BRANCH-123)
        import re
        pattern = r'^[A-Z]{2,10}-\d+$'
        return re.match(pattern, reg_no) is not None

class InvoiceValidator(DataValidator):
    """Specific validation for invoice data"""
    
    REQUIRED_FIELDS = ['student_id', 'total_amount', 'enrollment_date']
    
    @classmethod
    def validate_row(cls, row_data: Dict, row_number: int) -> Tuple[bool, List[str]]:
        """Validate a single invoice row"""
        errors = []
        
        # Check required fields
        missing_fields = cls.validate_required_fields(row_data, cls.REQUIRED_FIELDS)
        if missing_fields:
            errors.append(f"Missing required fields: {', '.join(missing_fields)}")
        
        # Validate amounts
        for amount_field in ['total_amount', 'paid_amount', 'due_amount', 'discount']:
            if row_data.get(amount_field) and not cls.validate_amount(row_data[amount_field]):
                errors.append(f"Invalid {amount_field} format")
        
        # Validate dates
        for date_field in ['enrollment_date', 'invoice_date', 'due_date']:
            if row_data.get(date_field) and not cls.validate_date(str(row_data[date_field])):
                errors.append(f"Invalid {date_field} format (expected YYYY-MM-DD)")
        
        return len(errors) == 0, errors

class InstallmentValidator(DataValidator):
    """Specific validation for installment data"""
    
    REQUIRED_FIELDS = ['invoice_id', 'due_date', 'amount']
    VALID_STATUSES = ['pending', 'paid', 'overdue', 'partial']
    
    @classmethod
    def validate_row(cls, row_data: Dict, row_number: int) -> Tuple[bool, List[str]]:
        """Validate a single installment row"""
        errors = []
        
        # Check required fields
        missing_fields = cls.validate_required_fields(row_data, cls.REQUIRED_FIELDS)
        if missing_fields:
            errors.append(f"Missing required fields: {', '.join(missing_fields)}")
        
        # Validate amounts
        for amount_field in ['amount', 'paid_amount', 'balance_amount', 'late_fee', 'discount_amount']:
            if row_data.get(amount_field) and not cls.validate_amount(row_data[amount_field]):
                errors.append(f"Invalid {amount_field} format")
        
        # Validate due date
        if row_data.get('due_date') and not cls.validate_date(str(row_data['due_date'])):
            errors.append("Invalid due_date format (expected YYYY-MM-DD)")
        
        # Validate status
        if row_data.get('status') and row_data['status'] not in cls.VALID_STATUSES:
            errors.append(f"Invalid status. Must be one of: {', '.join(cls.VALID_STATUSES)}")
        
        return len(errors) == 0, errors

class PaymentValidator(DataValidator):
    """Specific validation for payment data"""
    
    REQUIRED_FIELDS = ['amount', 'mode']
    VALID_PAYMENT_MODES = ['Cash', 'Card', 'UPI', 'NEFT', 'RTGS', 'Cheque', 'Online']
    
    @classmethod
    def validate_row(cls, row_data: Dict, row_number: int) -> Tuple[bool, List[str]]:
        """Validate a single payment row"""
        errors = []
        
        # Check required fields
        missing_fields = cls.validate_required_fields(row_data, cls.REQUIRED_FIELDS)
        if missing_fields:
            errors.append(f"Missing required fields: {', '.join(missing_fields)}")
        
        # Validate amount
        if row_data.get('amount') and not cls.validate_amount(row_data['amount']):
            errors.append("Invalid amount format")
        
        # Validate payment mode
        if row_data.get('mode') and row_data['mode'] not in cls.VALID_PAYMENT_MODES:
            errors.append(f"Invalid payment mode. Must be one of: {', '.join(cls.VALID_PAYMENT_MODES)}")
        
        # Validate payment date
        if row_data.get('payment_date') and not cls.validate_date(str(row_data['payment_date']), '%Y-%m-%d %H:%M:%S'):
            errors.append("Invalid payment_date format (expected YYYY-MM-DD HH:MM:SS)")
        
        # Must have either invoice_id or installment_id
        if not row_data.get('invoice_id') and not row_data.get('installment_id'):
            errors.append("Either invoice_id or installment_id is required")
        
        return len(errors) == 0, errors

class BatchValidator(DataValidator):
    """Specific validation for batch data"""
    
    REQUIRED_FIELDS = ['name', 'course_id', 'branch_id', 'start_date']
    OPTIONAL_FIELDS = ['id', 'course_name', 'end_date', 'timing', 'checkin_time', 'checkout_time', 
                      'max_capacity', 'status', 'completion_date', 'archived_at', 'archived_by',
                      'suspended_at', 'suspended_by', 'suspension_reason', 'suspension_notes',
                      'expected_resume_date', 'cancelled_at', 'cancelled_by', 'cancellation_reason',
                      'cancellation_notes', 'created_at', 'is_deleted']
    
    VALID_STATUSES = ['Active', 'Completed', 'Suspended', 'Cancelled', 'Archived']
    
    @classmethod
    def validate_row(cls, row_data: Dict, row_number: int) -> Tuple[bool, List[str]]:
        """Validate a single batch row"""
        errors = []
        
        # Check required fields
        missing_fields = cls.validate_required_fields(row_data, cls.REQUIRED_FIELDS)
        if missing_fields:
            errors.append(f"Missing required fields: {', '.join(missing_fields)}")
        
        # Validate batch name (must not be empty)
        if row_data.get('name') and not str(row_data['name']).strip():
            errors.append("Batch name cannot be empty")
        
        # Validate status
        if row_data.get('status') and row_data['status'] not in cls.VALID_STATUSES:
            errors.append(f"Invalid status. Must be one of: {', '.join(cls.VALID_STATUSES)}")
        
        # Validate dates
        date_fields = ['start_date', 'end_date', 'completion_date', 'archived_at', 'suspended_at', 
                      'expected_resume_date', 'cancelled_at', 'created_at']
        for date_field in date_fields:
            if row_data.get(date_field):
                # Check if it's a datetime field (has time component)
                if date_field in ['archived_at', 'suspended_at', 'cancelled_at', 'created_at']:
                    if not cls.validate_datetime(str(row_data[date_field])):
                        errors.append(f"Invalid {date_field} format (expected DD-MM-YYYY HH:MM AM/PM or DD-MM-YYYY HH:MM)")
                else:
                    if not cls.validate_date(str(row_data[date_field])):
                        errors.append(f"Invalid {date_field} format (expected DD-MM-YYYY)")
        
        # Validate time fields
        time_fields = ['timing', 'checkin_time', 'checkout_time']
        for time_field in time_fields:
            if row_data.get(time_field):
                if not cls.validate_time_format(str(row_data[time_field])):
                    errors.append(f"Invalid {time_field} format (expected HH:MM AM/PM or HH:MM)")
        
        # Validate numeric fields
        if row_data.get('max_capacity'):
            try:
                capacity = int(row_data['max_capacity'])
                if capacity <= 0:
                    errors.append("Max capacity must be a positive number")
            except (ValueError, TypeError):
                errors.append("Invalid max_capacity format (must be a number)")
        
        # Validate boolean fields
        if row_data.get('is_deleted'):
            if str(row_data['is_deleted']).lower() not in ['true', 'false', '1', '0', 'yes', 'no']:
                errors.append("Invalid is_deleted format (must be true/false, 1/0, or yes/no)")
        
        # DATABASE INTEGRITY VALIDATIONS
        # Validate course exists
        course_id = row_data.get('course_id')
        course_name = row_data.get('course_name')
        if course_id or course_name:
            is_valid, error_msg = cls.validate_course_exists(course_id, course_name)
            if not is_valid:
                errors.append(error_msg)
        
        # Validate branch exists
        if row_data.get('branch_id'):
            is_valid, error_msg = cls.validate_branch_exists(row_data['branch_id'])
            if not is_valid:
                errors.append(error_msg)
        
        # Validate start_date is before end_date
        if row_data.get('start_date') and row_data.get('end_date'):
            try:
                from utils.csv_processor import DataMapper
                start_converted = DataMapper.convert_indian_date_format(str(row_data['start_date']), include_time=False)
                end_converted = DataMapper.convert_indian_date_format(str(row_data['end_date']), include_time=False)
                
                if start_converted and end_converted:
                    from datetime import datetime
                    start_dt = datetime.strptime(start_converted, '%Y-%m-%d')
                    end_dt = datetime.strptime(end_converted, '%Y-%m-%d')
                    
                    if start_dt >= end_dt:
                        errors.append("Start date must be before end date")
            except Exception:
                pass  # Date format errors already caught above
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_time_format(time_str: str) -> bool:
        """Validate time format - supports various time formats including 12-hour and 24-hour"""
        if not time_str:
            return True  # Time might be optional
        
        try:
            import re
            time_str = str(time_str).strip()
            
            # Check for 12-hour format with AM/PM (various patterns)
            ampm_patterns = [
                r'^\d{1,2}:\d{2}\s*(AM|PM)$',           # 2:00 PM
                r'^\d{1,2}:\d{2}(AM|PM)$',              # 2:00PM (no space)
                r'^\d{1,2}\.\d{2}\s*(AM|PM)$',          # 2.00 PM
                r'^\d{1,2}\.\d{2}(AM|PM)$',             # 2.00PM (no space)
                r'^\d{1,2}:\d{2}\s*([AP]M)$',           # 2:00 P
                r'^\d{1,2}:\d{2}([AP]M)$',              # 2:00P (no space)
                r'^\d{1,2}\.\d{2}\s*([AP]M)$',          # 2.00 P
                r'^\d{1,2}\.\d{2}([AP]M)$',             # 2.00P (no space)
                r'^\d{1,2}\s*(AM|PM)$',                 # 11 AM, 2 PM
                r'^\d{1,2}(AM|PM)$',                    # 11AM, 2PM (no space)
                r'^\d{1,2}\s*([AP]M)$',                 # 11 A, 2 P
                r'^\d{1,2}([AP]M)$'                     # 11A, 2P (no space)
            ]
            
            for i, pattern in enumerate(ampm_patterns):
                match = re.match(pattern, time_str, re.IGNORECASE)
                if match:
                    if i >= 8:  # Patterns without minutes (11 AM, 2 PM, 11AM, 2PM)
                        hour = int(re.findall(r'\d{1,2}', time_str)[0])
                        minute = 0
                    else:  # Patterns with minutes (2:00 PM, 2:00PM)
                        # Extract time part before AM/PM
                        time_part = re.findall(r'\d{1,2}[:\.]\d{2}', time_str)
                        if time_part:
                            parts = re.split(r'[:.]', time_part[0])
                            hour = int(parts[0])
                            minute = int(parts[1])
                        else:
                            continue
                    
                    # Validate ranges for 12-hour format
                    if 1 <= hour <= 12 and 0 <= minute <= 59:
                        return True
            
            # Check for 24-hour format (various patterns)
            hour24_patterns = [
                r'^\d{1,2}:\d{2}:\d{2}$',              # HH:MM:SS
                r'^\d{1,2}:\d{2}$',                    # HH:MM
                r'^\d{1,2}\.\d{2}$'                    # HH.MM
            ]
            
            for pattern in hour24_patterns:
                if re.match(pattern, time_str):
                    # Extract components for validation
                    if ':' in time_str:
                        parts = time_str.split(':')
                    else:
                        parts = time_str.split('.')
                    
                    hour = int(parts[0])
                    minute = int(parts[1])
                    second = int(parts[2]) if len(parts) > 2 else 0
                    
                    # Validate ranges for 24-hour format
                    if 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59:
                        return True
            
            return False
        except Exception:
            return False

class CourseValidator(DataValidator):
    """Specific validation for course data"""
    
    REQUIRED_FIELDS = ['course_name', 'duration', 'fee']
    OPTIONAL_FIELDS = ['id', 'course_code', 'category', 'duration_in_hours', 'duration_in_days', 
                      'registration_fee', 'material_fee', 'certification_fee', 'early_bird_discount',
                      'group_discount', 'description', 'course_outline', 'prerequisites', 
                      'learning_outcomes', 'software_requirements', 'target_audience',
                      'career_opportunities', 'difficulty_level', 'delivery_mode', 'batch_size_min',
                      'batch_size_max', 'has_certification', 'certification_body', 'assessment_type',
                      'passing_criteria', 'typical_schedule', 'flexible_timing', 'is_featured',
                      'is_popular', 'display_order', 'course_image', 'brochure_path', 'status',
                      'created_by']
    
    VALID_CATEGORIES = ['Programming', 'Office Suite', 'Web Development', 'Data Science', 
                       'Digital Marketing', 'Graphic Design', 'Hardware', 'Networking', 
                       'Cloud Computing', 'Mobile Development', 'Digital Foundations',
                       'Programming & AI', 'Finance & Accounting', 'Communication & Soft Skills', 
                       'Other']
    
    VALID_DIFFICULTY_LEVELS = ['Beginner', 'Intermediate', 'Advanced', 'Expert']
    
    VALID_DELIVERY_MODES = ['Classroom', 'Online', 'Hybrid', 'Offline', 'Offline/Hybrid']
    
    VALID_ASSESSMENT_TYPES = ['Project', 'Exam', 'Both', 'Continuous']
    
    VALID_COURSE_STATUSES = ['Active', 'Inactive', 'Draft', 'Archived']
    
    @classmethod
    def validate_row(cls, row_data: Dict, row_number: int) -> Tuple[bool, List[str]]:
        """Validate a single course row"""
        errors = []
        
        # Check required fields
        missing_fields = cls.validate_required_fields(row_data, cls.REQUIRED_FIELDS)
        if missing_fields:
            errors.extend([f"Missing required field: {field}" for field in missing_fields])
        
        # Validate course_name uniqueness (basic format check)
        if 'course_name' in row_data and row_data['course_name']:
            course_name = str(row_data['course_name']).strip()
            if len(course_name) < 5:
                errors.append("Course name must be at least 5 characters long")
            elif len(course_name) > 120:
                errors.append("Course name cannot exceed 120 characters")
        
        # Validate course_code format
        if 'course_code' in row_data and row_data['course_code']:
            course_code = str(row_data['course_code']).strip()
            if len(course_code) > 20:
                errors.append("Course code cannot exceed 20 characters")
        
        # Validate category
        if 'category' in row_data and row_data['category']:
            if str(row_data['category']) not in cls.VALID_CATEGORIES:
                errors.append(f"Invalid category. Must be one of: {', '.join(cls.VALID_CATEGORIES)}")
        
        # Validate duration format
        if 'duration' in row_data and row_data['duration']:
            duration = str(row_data['duration']).strip()
            if len(duration) > 50:
                errors.append("Duration cannot exceed 50 characters")
        
        # Validate numeric fields
        numeric_fields = ['duration_in_hours', 'duration_in_days', 'fee', 'registration_fee', 
                         'material_fee', 'certification_fee', 'batch_size_min', 'batch_size_max', 
                         'display_order']
        
        for field in numeric_fields:
            if field in row_data and row_data[field]:
                try:
                    value = float(row_data[field])
                    if field in ['duration_in_hours', 'duration_in_days', 'batch_size_min', 'batch_size_max', 'display_order']:
                        if value < 0:
                            errors.append(f"{field} cannot be negative")
                    elif field == 'fee' and value <= 0:
                        errors.append("Course fee must be greater than 0")
                    elif field in ['registration_fee', 'material_fee', 'certification_fee'] and value < 0:
                        errors.append(f"{field} cannot be negative")
                except (ValueError, TypeError):
                    errors.append(f"Invalid {field}: must be a number")
        
        # Validate percentage fields
        percentage_fields = ['early_bird_discount', 'group_discount']
        for field in percentage_fields:
            if field in row_data and row_data[field]:
                try:
                    value = float(row_data[field])
                    if value < 0 or value > 100:
                        errors.append(f"{field} must be between 0 and 100")
                except (ValueError, TypeError):
                    errors.append(f"Invalid {field}: must be a number between 0-100")
        
        # Validate enum fields
        enum_validations = [
            ('difficulty_level', cls.VALID_DIFFICULTY_LEVELS),
            ('delivery_mode', cls.VALID_DELIVERY_MODES),
            ('assessment_type', cls.VALID_ASSESSMENT_TYPES),
            ('status', cls.VALID_COURSE_STATUSES)
        ]
        
        for field, valid_values in enum_validations:
            if field in row_data and row_data[field]:
                if str(row_data[field]) not in valid_values:
                    errors.append(f"Invalid {field}. Must be one of: {', '.join(valid_values)}")
        
        # Validate boolean fields
        boolean_fields = ['has_certification', 'flexible_timing', 'is_featured', 'is_popular']
        for field in boolean_fields:
            if field in row_data and row_data[field]:
                value = str(row_data[field]).lower()
                if value not in ['true', 'false', '1', '0', 'yes', 'no']:
                    errors.append(f"Invalid {field}: must be true/false, 1/0, or yes/no")
        
        # Validate batch size logic
        if ('batch_size_min' in row_data and 'batch_size_max' in row_data and 
            row_data['batch_size_min'] and row_data['batch_size_max']):
            try:
                min_size = int(row_data['batch_size_min'])
                max_size = int(row_data['batch_size_max'])
                if min_size > max_size:
                    errors.append("Batch size minimum cannot be greater than maximum")
            except (ValueError, TypeError):
                pass  # Error already caught in numeric validation
        
        # Validate text field lengths
        text_length_limits = [
            ('description', 2000),
            ('course_outline', 5000),
            ('prerequisites', 1000),
            ('learning_outcomes', 2000),
            ('software_requirements', 1000),
            ('target_audience', 1000),
            ('career_opportunities', 2000),
            ('certification_body', 100),
            ('passing_criteria', 100),
            ('typical_schedule', 200),
            ('course_image', 200),
            ('brochure_path', 200)
        ]
        
        for field, max_length in text_length_limits:
            if field in row_data and row_data[field]:
                if len(str(row_data[field])) > max_length:
                    errors.append(f"{field} cannot exceed {max_length} characters")
        
        return len(errors) == 0, errors
