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
        """Validate date format"""
        if not date_str:
            return True  # Date might be optional
        try:
            datetime.strptime(str(date_str), date_format)
            return True
        except ValueError:
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

class StudentValidator(DataValidator):
    """Specific validation for student data"""
    
    REQUIRED_FIELDS = ['full_name', 'mobile']
    OPTIONAL_FIELDS = ['email', 'gender', 'dob', 'address', 'guardian_name', 'guardian_mobile', 
                      'qualification', 'course_name', 'branch_id', 'lead_source']
    
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
            errors.append("Invalid date of birth format (expected YYYY-MM-DD)")
        
        # Validate admission date
        if row_data.get('admission_date') and not cls.validate_date(str(row_data['admission_date']), '%Y-%m-%d %H:%M:%S'):
            errors.append("Invalid admission date format (expected YYYY-MM-DD HH:MM:SS)")
        
        return len(errors) == 0, errors

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
