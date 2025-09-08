from init_db import db
from datetime import datetime, timezone
from utils.timezone_helper import format_date_indian

class Branch(db.Model):
    __tablename__ = 'branches'

    id = db.Column(db.Integer, primary_key=True)
    branch_name = db.Column(db.String(100), nullable=False, unique=True)
    branch_code = db.Column(db.String(10), unique=True)  # FR001, FR002, etc.
    address = db.Column(db.Text)
    city = db.Column(db.String(50))
    state = db.Column(db.String(50))
    pincode = db.Column(db.String(10))
    phone = db.Column(db.String(15))
    email = db.Column(db.String(100))
    manager_name = db.Column(db.String(100))
    manager_phone = db.Column(db.String(15))
    branch_type = db.Column(db.String(20), default='Franchise')  # Corporate/Franchise
    status = db.Column(db.String(20), default='Active')  # Active/Inactive/Suspended
    opening_date = db.Column(db.Date)
    franchise_fee = db.Column(db.Float, default=0.0)
    monthly_fee = db.Column(db.Float, default=0.0)
    gst_number = db.Column(db.String(20))
    pan_number = db.Column(db.String(15))
    is_deleted = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "branch_name": self.branch_name,
            "branch_code": self.branch_code,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "pincode": self.pincode,
            "phone": self.phone,
            "email": self.email,
            "manager_name": self.manager_name,
            "manager_phone": self.manager_phone,
            "branch_type": self.branch_type,
            "status": self.status,
            "opening_date": format_date_indian(self.opening_date) if self.opening_date else None,
            "franchise_fee": self.franchise_fee,
            "monthly_fee": self.monthly_fee,
            "gst_number": self.gst_number,
            "pan_number": self.pan_number
        }
