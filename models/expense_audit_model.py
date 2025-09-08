"""
Expense Audit Model for Global IT Web Application
Comprehensive audit trail for all expense management operations
Tracks who changed what, when, and why for full accountability
"""

from init_db import db
from datetime import datetime, timezone
import json
from utils.timezone_helper import utc_to_ist, format_datetime_indian, format_date_indian

class ExpenseAudit(db.Model):
    """
    Comprehensive audit trail for expense changes
    Tracks all modifications to expense records for accountability
    """
    __tablename__ = 'expense_audit'
    
    # Primary Key
    id = db.Column(db.Integer, primary_key=True)
    
    # Reference to original expense record
    expense_id = db.Column(db.Integer, db.ForeignKey('expenses.id'), nullable=False, index=True)
    expense_reference = db.Column(db.String(20), nullable=False, index=True)  # EXP-YYYY-NNNN for quick lookup
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True, index=True)
    
    # Audit Information
    action_type = db.Column(db.String(20), nullable=False, index=True)  # CREATE, UPDATE, DELETE, APPROVE, REJECT
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    changed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    change_reason = db.Column(db.String(500))  # Why was this changed?
    
    # Field-level change tracking
    field_changed = db.Column(db.String(50))  # Which field was changed
    old_value = db.Column(db.Text)  # Previous value (JSON for complex fields)
    new_value = db.Column(db.Text)  # New value (JSON for complex fields)
    
    # Complete record snapshots
    original_data = db.Column(db.Text)  # JSON snapshot of original expense record
    updated_data = db.Column(db.Text)   # JSON snapshot of updated expense record
    
    # Session and security context
    ip_address = db.Column(db.String(45))  # IPv4/IPv6 address
    user_agent = db.Column(db.String(500))  # Browser/device info
    session_id = db.Column(db.String(100))  # Session identifier
    
    # Expense-specific audit fields
    amount_change = db.Column(db.Numeric(precision=10, scale=2))  # Amount difference (new - old)
    status_change = db.Column(db.String(100))  # Payment status change description
    approval_level = db.Column(db.String(50))  # Approval level if action involves approval
    
    # File operation tracking
    file_operation = db.Column(db.String(20))  # UPLOAD, DELETE, REPLACE for file changes
    file_name = db.Column(db.String(255))  # Name of file affected
    file_path = db.Column(db.String(500))  # Path of file affected
    
    # Relationships
    user = db.relationship('User', backref='expense_audit_logs', lazy=True)
    expense = db.relationship('Expense', backref='audit_logs', lazy=True)
    branch = db.relationship('Branch', backref='expense_audit_logs', lazy=True)
    
    def __repr__(self):
        return f'<ExpenseAudit {self.expense_reference} - {self.action_type} by User {self.changed_by}>'
    
    def to_dict(self):
        """Convert audit record to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'expense_id': self.expense_id,
            'expense_reference': self.expense_reference,
            'branch_id': self.branch_id,
            'action_type': self.action_type,
            'changed_by': self.changed_by,
            'changed_at': utc_to_ist(self.changed_at),
            'change_reason': self.change_reason,
            'field_changed': self.field_changed,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent[:100] if self.user_agent else None,  # Truncate for display
            'amount_change': float(self.amount_change) if self.amount_change else None,
            'status_change': self.status_change,
            'approval_level': self.approval_level,
            'file_operation': self.file_operation,
            'file_name': self.file_name
        }
    
    def get_formatted_changed_at(self):
        """Get formatted timestamp in Indian timezone"""
        return utc_to_ist(self.changed_at)
    
    @staticmethod
    def log_expense_change(expense_record, changed_by_user_id, action_type, 
                          change_reason=None, field_changes=None, request=None,
                          old_record_data=None, file_operation=None, file_info=None):
        """
        Log an expense change with full audit trail
        
        Args:
            expense_record: Expense model instance
            changed_by_user_id: ID of user making the change
            action_type: CREATE, UPDATE, DELETE, APPROVE, REJECT
            change_reason: Why the change was made
            field_changes: Dict of {field_name: {'old': old_val, 'new': new_val}}
            request: Flask request object for IP/user agent/session
            old_record_data: Previous state of the record for UPDATE operations
            file_operation: UPLOAD, DELETE, REPLACE for file operations
            file_info: Dict with file details {'name': str, 'path': str}
        """
        try:
            # Get session context from request
            ip_address = None
            user_agent = None
            session_id = None
            
            if request:
                ip_address = request.remote_addr
                user_agent = request.headers.get('User-Agent', '')[:500]
                session_id = request.cookies.get('session', '')[:100]
            
            # Prepare record data
            current_data = {
                'id': expense_record.id,
                'expense_id': expense_record.expense_id,
                'branch_id': expense_record.branch_id,
                'expense_date': format_date_indian(expense_record.expense_date) if expense_record.expense_date else None,
                'expense_category': expense_record.expense_category,
                'description': expense_record.description,
                'vendor_supplier': expense_record.vendor_supplier,
                'invoice_bill_number': expense_record.invoice_bill_number,
                'payment_method': expense_record.payment_method,
                'amount': float(expense_record.amount) if expense_record.amount else 0,
                'gst_percentage': float(expense_record.gst_percentage) if expense_record.gst_percentage else 0,
                'gst_amount': float(expense_record.gst_amount) if expense_record.gst_amount else 0,
                'total_amount': float(expense_record.total_amount) if expense_record.total_amount else 0,
                'payment_status': expense_record.payment_status,
                'linked_ledger_account': expense_record.linked_ledger_account,
                'branch_location': expense_record.branch_location,
                'created_at': format_datetime_indian(expense_record.created_at, include_time=True) if expense_record.created_at else None,
                'updated_at': format_datetime_indian(expense_record.updated_at, include_time=True) if expense_record.updated_at else None
            }
            
            # Calculate amount change for UPDATE operations
            amount_change = None
            if action_type == 'UPDATE' and old_record_data and 'total_amount' in old_record_data:
                old_amount = float(old_record_data.get('total_amount', 0))
                new_amount = float(expense_record.total_amount) if expense_record.total_amount else 0
                amount_change = new_amount - old_amount
            
            # Generate status change description
            status_change = None
            if action_type == 'UPDATE' and old_record_data and 'payment_status' in old_record_data:
                old_status = old_record_data.get('payment_status')
                new_status = expense_record.payment_status
                if old_status != new_status:
                    status_change = f"{old_status} → {new_status}"
            
            # Create main audit record
            main_audit = ExpenseAudit(
                expense_id=expense_record.id,
                expense_reference=expense_record.expense_id,
                branch_id=expense_record.branch_id,
                action_type=action_type,
                changed_by=changed_by_user_id,
                change_reason=change_reason,
                original_data=json.dumps(old_record_data) if old_record_data else None,
                updated_data=json.dumps(current_data),
                ip_address=ip_address,
                user_agent=user_agent,
                session_id=session_id,
                amount_change=amount_change,
                status_change=status_change,
                file_operation=file_operation,
                file_name=file_info.get('name') if file_info else None,
                file_path=file_info.get('path') if file_info else None
            )
            
            db.session.add(main_audit)
            
            # Create individual field change records
            if field_changes:
                for field_name, change_data in field_changes.items():
                    field_audit = ExpenseAudit(
                        expense_id=expense_record.id,
                        expense_reference=expense_record.expense_id,
                        branch_id=expense_record.branch_id,
                        action_type=action_type,
                        changed_by=changed_by_user_id,
                        change_reason=change_reason,
                        field_changed=field_name,
                        old_value=str(change_data.get('old', '')),
                        new_value=str(change_data.get('new', '')),
                        ip_address=ip_address,
                        user_agent=user_agent,
                        session_id=session_id
                    )
                    db.session.add(field_audit)
            
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"Error logging expense audit: {str(e)}")
            return False
    
    @staticmethod
    def get_expense_audit_trail(expense_id, limit=50):
        """Get audit trail for a specific expense"""
        return ExpenseAudit.query.filter_by(expense_id=expense_id)\
                                .order_by(ExpenseAudit.changed_at.desc())\
                                .limit(limit).all()
    
    @staticmethod
    def get_user_audit_activity(user_id, limit=100):
        """Get audit activity for a specific user"""
        return ExpenseAudit.query.filter_by(changed_by=user_id)\
                                .order_by(ExpenseAudit.changed_at.desc())\
                                .limit(limit).all()
    
    @staticmethod
    def get_branch_audit_activity(branch_id, limit=100):
        """Get audit activity for a specific branch"""
        return ExpenseAudit.query.filter_by(branch_id=branch_id)\
                                .order_by(ExpenseAudit.changed_at.desc())\
                                .limit(limit).all()
    
    @staticmethod
    def get_recent_changes(days=7, limit=100):
        """Get recent expense changes across the system"""
        from datetime import timedelta
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        return ExpenseAudit.query.filter(ExpenseAudit.changed_at >= cutoff_date)\
                                .order_by(ExpenseAudit.changed_at.desc())\
                                .limit(limit).all()
    
    @staticmethod
    def get_amount_changes_summary(start_date=None, end_date=None):
        """Get summary of amount changes for analysis"""
        query = ExpenseAudit.query.filter(
            ExpenseAudit.amount_change.isnot(None),
            ExpenseAudit.amount_change != 0
        )
        
        if start_date:
            query = query.filter(ExpenseAudit.changed_at >= start_date)
        if end_date:
            query = query.filter(ExpenseAudit.changed_at <= end_date)
        
        return query.order_by(ExpenseAudit.changed_at.desc()).all()
