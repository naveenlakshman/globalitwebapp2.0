from init_db import db
from datetime import datetime, timezone, date
from utils.timezone_helper import utc_to_ist

class Installment(db.Model):
    __tablename__ = 'installments'

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    installment_number = db.Column(db.Integer, nullable=False)  # 1, 2, 3, etc.
    due_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    paid_amount = db.Column(db.Float, default=0.0)
    balance_amount = db.Column(db.Float)
    is_paid = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default="pending")  # pending, paid, overdue, partial
    payment_date = db.Column(db.DateTime)
    late_fee = db.Column(db.Float, default=0.0)
    discount_amount = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text)
    reminder_sent = db.Column(db.Integer, default=0)  # Count of reminders sent
    last_reminder_date = db.Column(db.DateTime)
    is_deleted = db.Column(db.Integer, default=0)  # Soft delete flag
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    invoice = db.relationship('Invoice', backref='installments')

    def __init__(self, **kwargs):
        super(Installment, self).__init__(**kwargs)
        if self.balance_amount is None:
            self.balance_amount = self.amount

    def to_dict(self):
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "installment_number": self.installment_number,
            "due_date": self.due_date.strftime("%Y-%m-%d") if self.due_date else "",
            "amount": self.amount,
            "paid_amount": self.paid_amount,
            "balance_amount": self.balance_amount,
            "is_paid": self.is_paid,
            "status": self.status,
            "payment_date": utc_to_ist(self.payment_date).strftime("%Y-%m-%d %H:%M:%S") if self.payment_date else "",
            "late_fee": self.late_fee,
            "discount_amount": self.discount_amount,
            "notes": self.notes,
            "reminder_sent": self.reminder_sent,
            "last_reminder_date": utc_to_ist(self.last_reminder_date).strftime("%Y-%m-%d %H:%M:%S") if self.last_reminder_date else "",
            "created_at": utc_to_ist(self.created_at).strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "",
            "days_overdue": self.get_days_overdue(),
            "is_overdue": self.is_overdue()
        }

    def get_days_overdue(self):
        """Calculate days overdue"""
        if self.is_paid or not self.due_date:
            return 0
        today = date.today()
        if self.due_date < today:
            return (today - self.due_date).days
        return 0

    def is_overdue(self):
        """Check if installment is overdue"""
        return self.get_days_overdue() > 0 and not self.is_paid

    def update_status(self):
        """Update installment status based on payment"""
        if self.is_paid:
            self.status = "paid"
        elif self.paid_amount > 0:
            self.status = "partial"
        elif self.is_overdue():
            self.status = "overdue"
        else:
            self.status = "pending"

    def calculate_late_fee(self, rate_per_day=10):
        """Calculate late fee based on days overdue"""
        if self.is_overdue():
            self.late_fee = self.get_days_overdue() * rate_per_day
        return self.late_fee

    def make_payment(self, amount, discount=0):
        """Process payment for this installment"""
        self.paid_amount += amount
        self.discount_amount += discount
        self.balance_amount = self.amount - self.paid_amount - self.discount_amount
        
        if self.balance_amount <= 0:
            self.is_paid = True
            self.payment_date = datetime.now(timezone.utc)
            self.balance_amount = 0
        
        self.update_status()
        return self.balance_amount
