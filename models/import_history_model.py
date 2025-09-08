from init_db import db
from datetime import datetime, timezone
from utils.timezone_helper import utc_to_ist

class ImportHistory(db.Model):
    __tablename__ = 'import_history'

    id = db.Column(db.Integer, primary_key=True)
    import_type = db.Column(db.String(50), nullable=False)  # students, invoices, installments, payments
    filename = db.Column(db.String(255), nullable=False)
    total_records = db.Column(db.Integer, default=0)
    successful_records = db.Column(db.Integer, default=0)
    failed_records = db.Column(db.Integer, default=0)
    skipped_records = db.Column(db.Integer, default=0)
    import_status = db.Column(db.String(20), default='pending')  # pending, completed, failed, partial
    error_log = db.Column(db.Text)  # Store error details
    import_notes = db.Column(db.Text)
    duplicate_handling = db.Column(db.String(20))  # skip, update, error
    imported_by = db.Column(db.String(100))  # User who performed import
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'))  # Import scope
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime)
    
    # Relationships
    branch = db.relationship('Branch', backref='import_history')
    
    def to_dict(self):
        return {
            "id": self.id,
            "import_type": self.import_type,
            "filename": self.filename,
            "total_records": self.total_records,
            "successful_records": self.successful_records,
            "failed_records": self.failed_records,
            "skipped_records": self.skipped_records,
            "import_status": self.import_status,
            "error_log": self.error_log,
            "import_notes": self.import_notes,
            "duplicate_handling": self.duplicate_handling,
            "imported_by": self.imported_by,
            "branch_id": self.branch_id,
            "branch_name": self.branch.name if self.branch else None,
            "created_at": utc_to_ist(self.created_at).strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "",
            "completed_at": utc_to_ist(self.completed_at).strftime("%Y-%m-%d %H:%M:%S") if self.completed_at else ""
        }

    def update_progress(self, successful=0, failed=0, skipped=0, status=None):
        """Update import progress"""
        self.successful_records += successful
        self.failed_records += failed
        self.skipped_records += skipped
        
        if status:
            self.import_status = status
            
        if status == 'completed' or status == 'failed':
            self.completed_at = datetime.now(timezone.utc)
            
        db.session.commit()

    def add_error(self, error_message):
        """Add error to error log"""
        if self.error_log:
            self.error_log += f"\n{error_message}"
        else:
            self.error_log = error_message
        db.session.commit()
