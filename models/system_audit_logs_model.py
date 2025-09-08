from init_db import db
from datetime import datetime, timezone
from utils.timezone_helper import utc_to_ist

class SystemAuditLog(db.Model):
    __tablename__ = 'system_audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    username = db.Column(db.String(50))
    action = db.Column(db.String(100))
    target = db.Column(db.String(100))
    ip_address = db.Column(db.String(45))  # IPv6 support
    user_agent = db.Column(db.Text)
    details = db.Column(db.Text)  # Additional context/data
    success = db.Column(db.Boolean, default=True)  # Track failed operations
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Security monitoring fields
    risk_level = db.Column(db.String(20), default='LOW')  # LOW, MEDIUM, HIGH, CRITICAL
    session_id = db.Column(db.String(100))

    def to_dict(self):
        # Handle timestamp conversion properly
        formatted_time = ""
        if self.timestamp:
            if isinstance(self.timestamp, str):
                # If timestamp is already a string, use it directly
                formatted_time = self.timestamp
            else:
                # If timestamp is a datetime object, format it
                formatted_time = utc_to_ist(self.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "action": self.action,
            "target": self.target,
            "ip_address": self.ip_address,
            "details": self.details,
            "success": self.success,
            "risk_level": self.risk_level,
            "timestamp": self.timestamp,
            "formatted_time": formatted_time
        }

    @staticmethod
    def log_action(user_id=None, username=None, action=None, target=None, 
                   ip_address=None, user_agent=None, details=None, success=True, 
                   risk_level='LOW', session_id=None):
        """Helper method to create audit log entries"""
        log_entry = SystemAuditLog(
            user_id=user_id,
            username=username,
            action=action,
            target=target,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
            success=success,
            risk_level=risk_level,
            session_id=session_id
        )
        db.session.add(log_entry)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Failed to log audit entry: {e}")

class SecurityAlert(db.Model):
    __tablename__ = 'security_alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    alert_type = db.Column(db.String(50))  # FAILED_LOGIN, PERMISSION_VIOLATION, SUSPICIOUS_ACTIVITY
    severity = db.Column(db.String(20))  # LOW, MEDIUM, HIGH, CRITICAL
    user_id = db.Column(db.Integer)
    username = db.Column(db.String(50))
    ip_address = db.Column(db.String(45))
    description = db.Column(db.Text)
    resolved = db.Column(db.Boolean, default=False)
    resolved_by = db.Column(db.Integer)
    resolved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        # Handle timestamp conversion properly for created_at
        created_at_formatted = ""
        if self.created_at:
            if isinstance(self.created_at, str):
                created_at_formatted = self.created_at
            else:
                created_at_formatted = utc_to_ist(self.created_at).strftime("%Y-%m-%d %H:%M:%S")
        
        # Handle timestamp conversion properly for resolved_at
        resolved_at_formatted = ""
        if self.resolved_at:
            if isinstance(self.resolved_at, str):
                resolved_at_formatted = self.resolved_at
            else:
                resolved_at_formatted = utc_to_ist(self.resolved_at).strftime("%Y-%m-%d %H:%M:%S")
        
        return {
            "id": self.id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "user_id": self.user_id,
            "username": self.username,
            "ip_address": self.ip_address,
            "description": self.description,
            "resolved": self.resolved,
            "created_at": created_at_formatted,
            "resolved_at": resolved_at_formatted
        }
