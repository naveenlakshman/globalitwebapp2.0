from init_db import db
from datetime import datetime, timezone
from utils.timezone_helper import utc_to_ist

class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    amount = db.Column(db.Float, nullable=False)
    mode = db.Column(db.String(20), nullable=False)  # This is the payment method column
    utr_number = db.Column(db.String(50))
    notes = db.Column(db.String(255))
    paid_on = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    payment_date = db.Column(db.DateTime)
    installment_id = db.Column(db.Integer, db.ForeignKey('installments.id'))
    discount_amount = db.Column(db.Float, default=0.0)

    # Relationships
    invoice = db.relationship('Invoice', backref='payments')
    installment = db.relationship('Installment', backref='payments')

    @property
    def payment_method(self):
        """Map mode to payment_method for compatibility"""
        return self.mode

    @payment_method.setter
    def payment_method(self, value):
        """Map payment_method to mode for compatibility"""
        self.mode = value

    def to_dict(self):
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "installment_id": self.installment_id,
            "amount": self.amount,
            "payment_method": self.mode,
            "utr_number": self.utr_number,
            "notes": self.notes,
            "paid_on": utc_to_ist(self.paid_on).strftime("%Y-%m-%d %H:%M:%S") if self.paid_on else "",
            "payment_date": utc_to_ist(self.payment_date).strftime("%Y-%m-%d %H:%M:%S") if self.payment_date else "",
            "discount_amount": self.discount_amount or 0.0
        }