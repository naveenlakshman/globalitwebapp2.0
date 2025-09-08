from init_db import db
from datetime import datetime, timezone
from utils.timezone_helper import utc_to_ist  # ✅ IST helper

class LoginLog(db.Model):
    __tablename__ = 'login_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    user_role = db.Column(db.String(50), nullable=False)
    login_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ip_address = db.Column(db.String(100))
    device_info = db.Column(db.String(200))

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_role": self.user_role,
            "login_time": utc_to_ist(self.login_time),  # ✅ IST timestamp
            "ip_address": self.ip_address,
            "device_info": self.device_info
        }
