from init_db import db
from datetime import datetime, timezone
from utils.timezone_helper import format_date_indian

class UserBranchAssignment(db.Model):
    __tablename__ = 'user_branch_assignments'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=False)
    role_at_branch = db.Column(db.Text, nullable=True)  # Fixed to match schema
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assigned_on = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Integer, default=1)
    notes = db.Column(db.Text, nullable=True)

    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='branch_assignments')
    branch = db.relationship('Branch', backref='user_assignments')
    assigned_by_user = db.relationship('User', foreign_keys=[assigned_by])

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'branch_id': self.branch_id,
            'role_at_branch': self.role_at_branch,
            'assigned_by': self.assigned_by,
            'assigned_on': format_date_indian(self.assigned_on) if self.assigned_on else None,
            'is_active': self.is_active,
            'notes': self.notes
        }
