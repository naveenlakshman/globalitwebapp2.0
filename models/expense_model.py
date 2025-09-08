"""
Expense Recording Model for Global IT Web Application
Tracks business expenses with detailed categorization and payment status
"""

from init_db import db
from datetime import datetime
from decimal import Decimal
from utils.timezone_helper import format_datetime_indian, format_date_indian

class Expense(db.Model):
    __tablename__ = 'expenses'
    
    # Primary Key
    id = db.Column(db.Integer, primary_key=True)
    
    # Expense ID (Auto-generated unique identifier)
    expense_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    
    # Branch/Franchise Relationship
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True, index=True)
    branch = db.relationship('Branch', backref='expenses', lazy=True)
    
    # Date Information
    expense_date = db.Column(db.Date, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Expense Details
    expense_category = db.Column(db.String(50), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    vendor_supplier = db.Column(db.String(200), nullable=True)
    invoice_bill_number = db.Column(db.String(100), nullable=True)
    
    # Payment Information
    payment_method = db.Column(db.String(30), nullable=False)
    
    # Amount Details (stored as Decimal for precision)
    amount = db.Column(db.Numeric(precision=10, scale=2), nullable=False)
    gst_percentage = db.Column(db.Numeric(precision=5, scale=2), default=0.00)
    gst_amount = db.Column(db.Numeric(precision=10, scale=2), default=0.00)
    total_amount = db.Column(db.Numeric(precision=10, scale=2), nullable=False)
    
    # Payment Status
    payment_status = db.Column(db.String(20), nullable=False, default='Unpaid')
    
    # Accounting Information
    linked_ledger_account = db.Column(db.String(100), nullable=True)
    
    # Location and Department Tracking
    branch_location = db.Column(db.String(100), nullable=True)
    department_project = db.Column(db.String(100), nullable=True)
    
    # File Management
    attachment_filename = db.Column(db.String(255), nullable=True)
    attachment_path = db.Column(db.String(500), nullable=True)
    
    # Additional Information
    notes = db.Column(db.Text, nullable=True)
    
    # User Tracking
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Soft Delete
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Relationships
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_expenses')
    updater = db.relationship('User', foreign_keys=[updated_by], backref='updated_expenses')
    deleter = db.relationship('User', foreign_keys=[deleted_by], backref='deleted_expenses')
    
    def __init__(self, **kwargs):
        super(Expense, self).__init__(**kwargs)
        if not self.expense_id:
            self.expense_id = self.generate_expense_id()
        
        # Auto-calculate GST amount and total
        if self.amount and self.gst_percentage:
            self.calculate_gst_and_total()
    
    @staticmethod
    def generate_expense_id():
        """Generate unique expense ID in format EXP-YYYY-NNNN"""
        from datetime import datetime
        year = datetime.now().year
        
        # Get the highest expense number for current year
        latest_expense = Expense.query.filter(
            Expense.expense_id.like(f'EXP-{year}-%')
        ).order_by(Expense.expense_id.desc()).first()
        
        if latest_expense:
            # Extract number from existing ID and increment
            try:
                last_number = int(latest_expense.expense_id.split('-')[-1])
                new_number = last_number + 1
            except (ValueError, IndexError):
                new_number = 1
        else:
            new_number = 1
        
        return f"EXP-{year}-{new_number:04d}"
    
    def calculate_gst_and_total(self):
        """Calculate GST amount and total amount"""
        if self.amount and self.gst_percentage:
            self.gst_amount = (self.amount * self.gst_percentage) / 100
            self.total_amount = self.amount + self.gst_amount
        else:
            self.gst_amount = 0.00
            self.total_amount = self.amount if self.amount else 0.00
    
    def update_totals(self):
        """Update calculated fields when amount or GST changes"""
        self.calculate_gst_and_total()
        self.updated_at = datetime.utcnow()
    
    @property
    def formatted_amount(self):
        """Return formatted amount with commas"""
        return f"₹{self.amount:,.2f}" if self.amount else "₹0.00"
    
    @property
    def formatted_gst_amount(self):
        """Return formatted GST amount with commas"""
        return f"₹{self.gst_amount:,.2f}" if self.gst_amount else "₹0.00"
    
    @property
    def formatted_total_amount(self):
        """Return formatted total amount with commas"""
        return f"₹{self.total_amount:,.2f}" if self.total_amount else "₹0.00"
    
    @property
    def is_paid(self):
        """Check if expense is fully paid"""
        return self.payment_status == 'Paid'
    
    @property
    def is_overdue(self):
        """Check if unpaid expense is overdue (more than 30 days old)"""
        if self.payment_status == 'Paid':
            return False
        
        from datetime import date, timedelta
        overdue_date = self.expense_date + timedelta(days=30)
        return date.today() > overdue_date
    
    def to_dict(self):
        """Convert expense object to dictionary"""
        return {
            'id': self.id,
            'expense_id': self.expense_id,
            'expense_date': format_date_indian(self.expense_date) if self.expense_date else None,
            'expense_category': self.expense_category,
            'description': self.description,
            'vendor_supplier': self.vendor_supplier,
            'invoice_bill_number': self.invoice_bill_number,
            'payment_method': self.payment_method,
            'amount': float(self.amount) if self.amount else 0.0,
            'gst_percentage': float(self.gst_percentage) if self.gst_percentage else 0.0,
            'gst_amount': float(self.gst_amount) if self.gst_amount else 0.0,
            'total_amount': float(self.total_amount) if self.total_amount else 0.0,
            'payment_status': self.payment_status,
            'linked_ledger_account': self.linked_ledger_account,
            'branch_location': self.branch_location,
            'department_project': self.department_project,
            'attachment_filename': self.attachment_filename,
            'notes': self.notes,
            'created_at': format_datetime_indian(self.created_at, include_time=True) if self.created_at else None,
            'updated_at': format_datetime_indian(self.updated_at, include_time=True) if self.updated_at else None,
            'is_deleted': self.is_deleted,
            'formatted_amount': self.formatted_amount,
            'formatted_gst_amount': self.formatted_gst_amount,
            'formatted_total_amount': self.formatted_total_amount,
            'is_paid': self.is_paid,
            'is_overdue': self.is_overdue
        }
    
    def soft_delete(self, deleted_by_user_id):
        """Soft delete the expense"""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by = deleted_by_user_id
        self.updated_at = datetime.utcnow()
    
    def restore(self):
        """Restore soft deleted expense"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.updated_at = datetime.utcnow()
    
    @staticmethod
    def get_expense_categories():
        """Return list of predefined expense categories"""
        return [
            'Rent',
            'Utilities',
            'Salaries',
            'Marketing',
            'Travel',
            'Maintenance',
            'Software',
            'Office Supplies',
            'Training',
            'Professional Services',
            'Insurance',
            'Legal & Compliance',
            'Bank Charges',
            'Depreciation',
            'Miscellaneous'
        ]
    
    @staticmethod
    def get_payment_methods():
        """Return list of payment methods"""
        return [
            'Cash',
            'Bank Transfer',
            'UPI',
            'Credit Card',
            'Debit Card',
            'Cheque',
            'Digital Wallet'
        ]
    
    @staticmethod
    def get_payment_statuses():
        """Return list of payment statuses"""
        return [
            'Paid',
            'Partially Paid',
            'Unpaid'
        ]
    
    @staticmethod
    def get_ledger_accounts():
        """Return list of ledger accounts"""
        return [
            'Bank - SBI',
            'Bank - HDFC',
            'Bank - ICICI',
            'Cash',
            'Accounts Payable',
            'Credit Card - HDFC',
            'Credit Card - SBI',
            'Petty Cash'
        ]
    
    @staticmethod
    def get_branch_locations():
        """Return list of active branch locations from database"""
        try:
            from models.branch_model import Branch
            branches = Branch.query.filter(
                Branch.is_deleted == 0,
                Branch.status == 'Active'
            ).all()
            
            branch_list = []
            for branch in branches:
                # Include both branch name and code for better identification
                display_name = f"{branch.branch_name} ({branch.branch_code})" if branch.branch_code else branch.branch_name
                branch_list.append({
                    'id': branch.id,
                    'name': display_name,
                    'code': branch.branch_code,
                    'city': branch.city
                })
            
            # Add Head Office option
            branch_list.insert(0, {
                'id': None,
                'name': 'Head Office',
                'code': 'HO',
                'city': 'Main'
            })
            
            return branch_list
        except Exception as e:
            # Fallback to static list if there's an error
            return [
                {'id': None, 'name': 'Head Office', 'code': 'HO', 'city': 'Main'},
                {'id': None, 'name': 'Hoskote Branch', 'code': 'HSK', 'city': 'Hoskote'},
                {'id': None, 'name': 'Bangalore Branch', 'code': 'BLR', 'city': 'Bangalore'},
                {'id': None, 'name': 'Remote/Online', 'code': 'RMT', 'city': 'Online'}
            ]
    
    @staticmethod
    def get_departments():
        """Return list of departments/projects"""
        return [
            'Marketing',
            'Training',
            'Admin',
            'IT Support',
            'Operations',
            'Finance',
            'Human Resources',
            'Business Development'
        ]
    
    def __repr__(self):
        return f'<Expense {self.expense_id}: {self.description[:50]}...>'


# Expense Category Model for detailed tracking
class ExpenseCategory(db.Model):
    __tablename__ = 'expense_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    parent_category_id = db.Column(db.Integer, db.ForeignKey('expense_categories.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Self-referential relationship for sub-categories
    parent = db.relationship('ExpenseCategory', remote_side=[id], backref='subcategories')
    creator = db.relationship('User', backref='expense_categories_created')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'parent_category_id': self.parent_category_id,
            'is_active': self.is_active,
            'created_at': format_datetime_indian(self.created_at, include_time=True) if self.created_at else None
        }
    
    def __repr__(self):
        return f'<ExpenseCategory {self.name}>'
