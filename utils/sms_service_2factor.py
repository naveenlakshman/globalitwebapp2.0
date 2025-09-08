import requests
import json
from datetime import datetime, timezone
from init_db import db
from models.sms_automation_model import SMSLog
from utils.logger import log_error, log_info

class TwoFactorSMSService:
    """
    SMS Service using 2Factor.in API
    Supports both OTP and Transactional SMS
    """
    
    def __init__(self, api_key=None):
        self.api_key = api_key or "34e9feb1-66a4-11f0-a562-0200cd936042"  # Replace with actual API key
        self.base_url = "https://2factor.in/API/V1"
        
    def send_otp(self, phone_number, template_name="GLOBAL_IT_OTP"):
        """
        Send OTP using 2Factor.in
        
        Args:
            phone_number (str): 10-digit phone number without country code
            template_name (str): Template name registered with 2Factor.in
            
        Returns:
            dict: Response with session_id and status
        """
        try:
            url = f"{self.base_url}/{self.api_key}/SMS/{phone_number}/AUTOGEN/{template_name}"
            
            response = requests.get(url, timeout=30)
            result = response.json()
            
            if result.get('Status') == 'Success':
                log_info(f"OTP sent successfully to {phone_number}")
                return {
                    'success': True,
                    'session_id': result.get('Details'),
                    'message': 'OTP sent successfully'
                }
            else:
                log_error(f"Failed to send OTP to {phone_number}: {result}")
                return {
                    'success': False,
                    'error': result.get('Details', 'Unknown error')
                }
                
        except Exception as e:
            log_error(f"Error sending OTP to {phone_number}: {str(e)}")
            return {
                'success': False,
                'error': f'Network error: {str(e)}'
            }
    
    def verify_otp(self, session_id, otp_code):
        """
        Verify OTP using 2Factor.in
        
        Args:
            session_id (str): Session ID from send_otp response
            otp_code (str): OTP code entered by user
            
        Returns:
            dict: Verification result
        """
        try:
            url = f"{self.base_url}/{self.api_key}/SMS/VERIFY/{session_id}/{otp_code}"
            
            response = requests.get(url, timeout=30)
            result = response.json()
            
            if result.get('Status') == 'Success':
                log_info(f"OTP verified successfully for session {session_id}")
                return {
                    'success': True,
                    'message': 'OTP verified successfully'
                }
            else:
                log_error(f"OTP verification failed for session {session_id}: {result}")
                return {
                    'success': False,
                    'error': result.get('Details', 'Invalid OTP')
                }
                
        except Exception as e:
            log_error(f"Error verifying OTP for session {session_id}: {str(e)}")
            return {
                'success': False,
                'error': f'Network error: {str(e)}'
            }
    
    def send_transactional_sms(self, phone_number, message, template_id=None, 
                             student_id=None, user_id=None, branch_id=None, 
                             message_type='general', sent_by=None):
        """
        Send transactional SMS using 2Factor.in
        
        Args:
            phone_number (str): 10-digit phone number
            message (str): SMS message content
            template_id (str): Template ID if using pre-approved template
            student_id (str): Student ID for logging
            user_id (int): User ID for logging
            branch_id (int): Branch ID for logging
            message_type (str): Type of message for categorization
            sent_by (int): User ID who sent the SMS
            
        Returns:
            dict: Send result with status and details
        """
        try:
            # Clean phone number (remove spaces, country code if present)
            clean_phone = phone_number.replace(" ", "").replace("-", "")
            if clean_phone.startswith("+91"):
                clean_phone = clean_phone[3:]
            elif clean_phone.startswith("91") and len(clean_phone) == 12:
                clean_phone = clean_phone[2:]
            
            # Validate phone number
            if len(clean_phone) != 10 or not clean_phone.isdigit():
                return {
                    'success': False,
                    'error': 'Invalid phone number format'
                }
            
            # Use transactional SMS endpoint
            if template_id:
                # Using pre-approved template
                url = f"{self.base_url}/{self.api_key}/SMS/{clean_phone}/{message}/{template_id}"
            else:
                # Direct text message (requires sender ID approval)
                url = f"{self.base_url}/{self.api_key}/SMS/{clean_phone}/{message}"
            
            response = requests.get(url, timeout=30)
            result = response.json()
            
            # Log the SMS attempt
            sms_log = SMSLog(
                phone_number=clean_phone,
                message=message,
                template_id=template_id,
                message_type=message_type,
                student_id=student_id,
                user_id=user_id,
                branch_id=branch_id,
                sent_by=sent_by,
                provider_response=json.dumps(result),
                status='pending'
            )
            
            if result.get('Status') == 'Success':
                sms_log.status = 'sent'
                sms_log.session_id = result.get('Details')
                log_info(f"SMS sent successfully to {clean_phone}")
                
                db.session.add(sms_log)
                db.session.commit()
                
                return {
                    'success': True,
                    'session_id': result.get('Details'),
                    'message': 'SMS sent successfully',
                    'sms_log_id': sms_log.id
                }
            else:
                sms_log.status = 'failed'
                db.session.add(sms_log)
                db.session.commit()
                
                log_error(f"Failed to send SMS to {clean_phone}: {result}")
                return {
                    'success': False,
                    'error': result.get('Details', 'Unknown error'),
                    'sms_log_id': sms_log.id
                }
                
        except Exception as e:
            log_error(f"Error sending SMS to {phone_number}: {str(e)}")
            return {
                'success': False,
                'error': f'Network error: {str(e)}'
            }
    
    def get_sms_status(self, session_id):
        """
        Get delivery status of sent SMS
        
        Args:
            session_id (str): Session ID from send SMS response
            
        Returns:
            dict: Status information
        """
        try:
            url = f"{self.base_url}/{self.api_key}/SMS/STATUS/{session_id}"
            
            response = requests.get(url, timeout=30)
            result = response.json()
            
            return {
                'success': True,
                'status': result.get('Status'),
                'details': result.get('Details')
            }
                
        except Exception as e:
            log_error(f"Error getting SMS status for session {session_id}: {str(e)}")
            return {
                'success': False,
                'error': f'Network error: {str(e)}'
            }
    
    def get_account_balance(self):
        """
        Get account balance from 2Factor.in
        
        Returns:
            dict: Balance information
        """
        try:
            url = f"{self.base_url}/{self.api_key}/ADDON_SERVICES/BAL/SMS"
            
            response = requests.get(url, timeout=30)
            result = response.json()
            
            if result.get('Status') == 'Success':
                return {
                    'success': True,
                    'balance': result.get('Details')
                }
            else:
                return {
                    'success': False,
                    'error': result.get('Details', 'Could not fetch balance')
                }
                
        except Exception as e:
            log_error(f"Error getting account balance: {str(e)}")
            return {
                'success': False,
                'error': f'Network error: {str(e)}'
            }

# Pre-defined message templates for common use cases
SMS_TEMPLATES = {
    'payment_reminder': {
        'template': "Dear {student_name}, your fee payment of Rs.{amount} is due on {due_date}. Please pay to avoid late charges. - Global IT Education",
        'variables': ['student_name', 'amount', 'due_date']
    },
    'payment_confirmation': {
        'template': "Dear {student_name}, we have received your payment of Rs.{amount} on {payment_date}. Receipt: {receipt_no}. Thank you! - Global IT Education",
        'variables': ['student_name', 'amount', 'payment_date', 'receipt_no']
    },
    'class_reminder': {
        'template': "Dear {student_name}, reminder: Your {course_name} class is scheduled for {date} at {time}. Venue: {venue}. - Global IT Education",
        'variables': ['student_name', 'course_name', 'date', 'time', 'venue']
    },
    'attendance_alert': {
        'template': "Dear Parent, {student_name} was absent from {course_name} class on {date}. Please ensure regular attendance. - Global IT Education",
        'variables': ['student_name', 'course_name', 'date']
    },
    'course_completion': {
        'template': "Congratulations {student_name}! You have successfully completed {course_name}. Certificate will be issued soon. - Global IT Education",
        'variables': ['student_name', 'course_name']
    },
    'admission_confirmation': {
        'template': "Welcome {student_name}! Your admission to {course_name} is confirmed. Classes start on {start_date} at {branch_name}. - Global IT Education",
        'variables': ['student_name', 'course_name', 'start_date', 'branch_name']
    }
}

def get_sms_service():
    """Get SMS service instance"""
    return TwoFactorSMSService()

def send_bulk_sms(phone_numbers, message, template_id=None, message_type='bulk', sent_by=None):
    """
    Send SMS to multiple recipients
    
    Args:
        phone_numbers (list): List of phone numbers
        message (str): Message content
        template_id (str): Template ID if using template
        message_type (str): Type of message
        sent_by (int): User ID who sent the SMS
        
    Returns:
        dict: Bulk send results
    """
    sms_service = get_sms_service()
    results = {
        'total': len(phone_numbers),
        'sent': 0,
        'failed': 0,
        'results': []
    }
    
    for phone in phone_numbers:
        result = sms_service.send_transactional_sms(
            phone_number=phone,
            message=message,
            template_id=template_id,
            message_type=message_type,
            sent_by=sent_by
        )
        
        if result['success']:
            results['sent'] += 1
        else:
            results['failed'] += 1
            
        results['results'].append({
            'phone': phone,
            'success': result['success'],
            'error': result.get('error')
        })
    
    return results
