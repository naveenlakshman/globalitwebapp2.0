from init_db import db
from datetime import datetime, timezone
from utils.timezone_helper import utc_to_ist  # IST conversion utility

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), default="user")
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_deleted = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "full_name": self.full_name,
            "role": self.role,
            "created_at": utc_to_ist(self.created_at)  # IST formatted datetime
        }
    
    def get_user_branch(self):
        """Get the primary branch for this user"""
        from models.branch_model import Branch
        from models.user_branch_assignment_model import UserBranchAssignment
        
        # First try the new user_branch_assignments table
        assignment = UserBranchAssignment.query.filter_by(
            user_id=self.id, 
            is_active=1
        ).first()
        
        if assignment:
            branch = Branch.query.get(assignment.branch_id)
            return branch
            
        # Fallback to legacy branch_id field
        if self.branch_id:
            branch = Branch.query.get(self.branch_id)
            return branch
            
        return None
    
    def has_corporate_access(self):
        """Check if user has corporate-level access (can see all branches)"""
        return self.role in ['corporate_admin', 'super_admin', 'admin']

    def get_active_batch_count(self):
        """Get count of active batches this trainer is assigned to"""
        try:
            from models.batch_trainer_assignment_model import BatchTrainerAssignment
            return BatchTrainerAssignment.query.filter_by(
                trainer_user_id=self.id,
                is_active=True
            ).count()
        except:
            return 0

    @property
    def mobile(self):
        """Get mobile number from user profile or return None"""
        # This would typically come from a user profile table
        # For now, return None as placeholder
        return None

    @property
    def user_id(self):
        """Alias for id to match template expectations"""
        return self.id