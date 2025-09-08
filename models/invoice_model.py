from init_db import db
from datetime import datetime, timezone
from utils.timezone_helper import utc_to_ist  # ✅ Centralized IST conversion

class Invoice(db.Model):
    __tablename__ = 'invoices'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'))
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))  # ✅ Added course reference
    course_fee = db.Column(db.Float, nullable=False)  # ✅ Store original course fee
    total_amount = db.Column(db.Float, nullable=False)
    paid_amount = db.Column(db.Float, default=0.0)
    due_amount = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, default=0.0)
    enrollment_date = db.Column(db.Date, nullable=False)  # ✅ When student enrolled for course
    invoice_date = db.Column(db.Date)  # ✅ Invoice issue date
    due_date = db.Column(db.Date)  # ✅ Payment due date
    payment_terms = db.Column(db.String(100))  # ✅ Payment terms (e.g., "Net 30 days")
    invoice_notes = db.Column(db.Text)  # ✅ Added notes field
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    # Remove the direct payments relationship since payments now go through installments
    is_deleted = db.Column(db.Integer, default=0)

    # Relationships
    student = db.relationship('Student', backref='invoices')
    course = db.relationship('Course', backref='invoices')  # ✅ Added course relationship

    def to_dict(self):
        return {
            "invoice_id": self.id,
            "student_id": self.student_id,
            "course_id": self.course_id,
            "course_name": self.course.course_name if self.course else None,
            "course_fee": self.course_fee,
            "total": self.total_amount,
            "paid": self.paid_amount,
            "due": self.due_amount,
            "discount": self.discount,
            "enrollment_date": self.enrollment_date.strftime('%Y-%m-%d') if self.enrollment_date else None,
            "invoice_date": self.invoice_date.strftime('%Y-%m-%d') if self.invoice_date else None,
            "due_date": self.due_date.strftime('%Y-%m-%d') if self.due_date else None,
            "payment_terms": self.payment_terms,
            "invoice_notes": self.invoice_notes,
            "created_at": utc_to_ist(self.created_at)  # ✅ Consistent IST timestamp
        }
