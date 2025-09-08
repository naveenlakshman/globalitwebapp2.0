from init_db import db
from datetime import datetime, timezone
from utils.timezone_helper import format_datetime_indian

class AttendanceAudit(db.Model):
    """
    Comprehensive audit trail for attendance changes
    Tracks who changed what, when, and why
    """
    __tablename__ = 'attendance_audit'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Reference to original attendance record
    attendance_id = db.Column(db.Integer, db.ForeignKey('student_attendance.id'), nullable=False)
    student_id = db.Column(db.String(20), nullable=False)  # For quick lookup
    batch_id = db.Column(db.Integer, nullable=False)
    attendance_date = db.Column(db.Date, nullable=False)
    
    # Audit Information
    action_type = db.Column(db.String(20), nullable=False)  # CREATE, UPDATE, DELETE
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    changed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    change_reason = db.Column(db.String(500))  # Why was this changed?
    
    # Field-level change tracking
    field_changed = db.Column(db.String(50))  # Which field was changed
    old_value = db.Column(db.Text)  # Previous value
    new_value = db.Column(db.Text)  # New value
    
    # Original record state (JSON snapshot)
    original_data = db.Column(db.Text)  # JSON of original attendance record
    updated_data = db.Column(db.Text)   # JSON of updated attendance record
    
    # Additional context
    session_type = db.Column(db.String(20))
    ip_address = db.Column(db.String(45))  # IPv4/IPv6 address
    user_agent = db.Column(db.String(500))  # Browser/device info
    
    def to_dict(self):
        return {
            'id': self.id,
            'attendance_id': self.attendance_id,
            'student_id': self.student_id,
            'batch_id': self.batch_id,
            'attendance_date': self.attendance_date.strftime('%Y-%m-%d') if self.attendance_date else None,
            'action_type': self.action_type,
            'changed_by': self.changed_by,
            'changed_at': format_datetime_indian(self.changed_at, include_time=True, include_seconds=True) if self.changed_at else None,
            'change_reason': self.change_reason,
            'field_changed': self.field_changed,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'session_type': self.session_type,
            'ip_address': self.ip_address
        }
    
    @staticmethod
    def log_attendance_change(attendance_record, changed_by_user_id, action_type, 
                            change_reason=None, field_changes=None, request=None):
        """
        Log an attendance change with full audit trail
        
        Args:
            attendance_record: StudentAttendance instance
            changed_by_user_id: ID of user making the change
            action_type: CREATE, UPDATE, DELETE
            change_reason: Why the change was made
            field_changes: Dict of {field_name: {'old': old_val, 'new': new_val}}
            request: Flask request object for IP/user agent
        """
        import json
        
        # Get IP and user agent from request
        ip_address = None
        user_agent = None
        if request:
            ip_address = request.remote_addr
            user_agent = request.headers.get('User-Agent', '')[:500]
        
        # Convert attendance date string to date object if needed
        attendance_date_obj = attendance_record.date
        if isinstance(attendance_date_obj, str):
            from datetime import datetime
            attendance_date_obj = datetime.strptime(attendance_date_obj, '%Y-%m-%d').date()
        
        # Create audit record for each field change
        if field_changes:
            for field_name, change_data in field_changes.items():
                audit_record = AttendanceAudit(
                    attendance_id=attendance_record.id,
                    student_id=attendance_record.student_id,
                    batch_id=attendance_record.batch_id,
                    attendance_date=attendance_date_obj,
                    action_type=action_type,
                    changed_by=changed_by_user_id,
                    change_reason=change_reason,
                    field_changed=field_name,
                    old_value=str(change_data.get('old', '')),
                    new_value=str(change_data.get('new', '')),
                    session_type=attendance_record.session_type,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    original_data=json.dumps(change_data.get('original_record', {})),
                    updated_data=json.dumps(change_data.get('updated_record', {}))
                )
                db.session.add(audit_record)
        else:
            # Single audit record for complete action
            audit_record = AttendanceAudit(
                attendance_id=attendance_record.id,
                student_id=attendance_record.student_id,
                batch_id=attendance_record.batch_id,
                attendance_date=attendance_date_obj,
                action_type=action_type,
                changed_by=changed_by_user_id,
                change_reason=change_reason,
                session_type=attendance_record.session_type,
                ip_address=ip_address,
                user_agent=user_agent,
                original_data=json.dumps(attendance_record.to_dict() if hasattr(attendance_record, 'to_dict') else {}),
                updated_data=json.dumps(attendance_record.to_dict() if hasattr(attendance_record, 'to_dict') else {})
            )
            db.session.add(audit_record)
    
    @staticmethod
    def get_attendance_history(student_id, attendance_date, batch_id):
        """Get complete audit history for specific attendance record"""
        return AttendanceAudit.query.filter_by(
            student_id=student_id,
            attendance_date=attendance_date,
            batch_id=batch_id
        ).order_by(AttendanceAudit.changed_at.desc()).all()
    
    @staticmethod
    def get_user_audit_trail(user_id, limit=50):
        """Get audit trail for specific user"""
        return AttendanceAudit.query.filter_by(
            changed_by=user_id
        ).order_by(AttendanceAudit.changed_at.desc()).limit(limit).all()
    
    @staticmethod
    def get_batch_audit_trail(batch_id, limit=100):
        """Get audit trail for specific batch"""
        return AttendanceAudit.query.filter_by(
            batch_id=batch_id
        ).order_by(AttendanceAudit.changed_at.desc()).limit(limit).all()

    # Relationships
    attendance = db.relationship('StudentAttendance', backref='audit_trail')
    changed_by_user = db.relationship('User', foreign_keys=[changed_by])
