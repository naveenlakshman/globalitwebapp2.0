from init_db import db
from datetime import datetime, timezone
from utils.timezone_helper import format_datetime_indian

class BatchTrainerAssignment(db.Model):
    __tablename__ = 'batch_trainer_assignments'

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'), nullable=False)
    trainer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assigned_on = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Integer, default=1)
    role_in_batch = db.Column(db.String(50), default='Primary Trainer')  # Primary Trainer, Assistant Trainer, Guest Trainer
    notes = db.Column(db.Text, nullable=True)

    # Relationships
    batch = db.relationship('Batch', backref='trainer_assignments')
    trainer = db.relationship('User', foreign_keys=[trainer_id], backref='batch_assignments')
    assigned_by_user = db.relationship('User', foreign_keys=[assigned_by])

    # Constraints
    __table_args__ = (
        db.UniqueConstraint('batch_id', 'trainer_id', name='unique_batch_trainer'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'batch_id': self.batch_id,
            'trainer_id': self.trainer_id,
            'assigned_by': self.assigned_by,
            'assigned_on': format_datetime_indian(self.assigned_on, include_time=True, include_seconds=True) if self.assigned_on else None,
            'is_active': self.is_active,
            'role_in_batch': self.role_in_batch,
            'notes': self.notes,
            'trainer_name': self.trainer.full_name if self.trainer else None,
            'batch_name': self.batch.name if self.batch else None
        }

    @classmethod
    def assign_trainer_to_batch(cls, batch_id, trainer_id, assigned_by=None, role_in_batch='Primary Trainer', notes=None):
        """Assign a trainer to a batch"""
        try:
            # Check if assignment already exists
            existing = cls.query.filter_by(
                batch_id=batch_id,
                trainer_id=trainer_id
            ).first()

            if existing:
                # Update existing assignment
                existing.is_active = 1
                existing.assigned_by = assigned_by
                existing.assigned_on = datetime.now(timezone.utc)
                existing.role_in_batch = role_in_batch
                existing.notes = notes
                assignment = existing
            else:
                # Create new assignment
                assignment = cls(
                    batch_id=batch_id,
                    trainer_id=trainer_id,
                    assigned_by=assigned_by,
                    role_in_batch=role_in_batch,
                    notes=notes
                )
                db.session.add(assignment)

            db.session.commit()
            return assignment, True

        except Exception as e:
            db.session.rollback()
            return None, False

    @classmethod
    def remove_trainer_from_batch(cls, batch_id, trainer_id):
        """Remove/deactivate a trainer from a batch"""
        try:
            assignment = cls.query.filter_by(
                batch_id=batch_id,
                trainer_id=trainer_id
            ).first()

            if assignment:
                assignment.is_active = 0
                db.session.commit()
                return True
            return False

        except Exception as e:
            db.session.rollback()
            return False

    @classmethod
    def get_batch_trainers(cls, batch_id, active_only=True):
        """Get all trainers assigned to a specific batch"""
        query = cls.query.filter_by(batch_id=batch_id)
        if active_only:
            query = query.filter_by(is_active=1)
        return query.all()

    @classmethod
    def get_trainer_batches(cls, trainer_id, active_only=True):
        """Get all batches assigned to a specific trainer"""
        query = cls.query.filter_by(trainer_id=trainer_id)
        if active_only:
            query = query.filter_by(is_active=1)
        return query.all()

    @classmethod
    def is_trainer_assigned_to_batch(cls, batch_id, trainer_id):
        """Check if a trainer is assigned to a batch"""
        assignment = cls.query.filter_by(
            batch_id=batch_id,
            trainer_id=trainer_id,
            is_active=1
        ).first()
        return assignment is not None

    @classmethod
    def get_available_trainers_for_batch(cls, batch_id, branch_id):
        """Get trainers who can be assigned to a batch (trainers from the same branch)"""
        from models.user_model import User
        from models.user_branch_assignment_model import UserBranchAssignment
        
        # Get trainers from the same branch who are not already assigned to this batch
        trainers_query = db.session.query(User).join(
            UserBranchAssignment,
            User.id == UserBranchAssignment.user_id
        ).filter(
            User.role == 'trainer',
            UserBranchAssignment.branch_id == branch_id,
            UserBranchAssignment.is_active == 1,
            User.is_deleted == 0
        )

        # Exclude trainers already assigned to this batch
        assigned_trainer_ids = db.session.query(cls.trainer_id).filter_by(
            batch_id=batch_id,
            is_active=1
        ).subquery()

        available_trainers = trainers_query.filter(
            ~User.id.in_(assigned_trainer_ids)
        ).all()

        return available_trainers

    def deactivate(self):
        """Deactivate this trainer assignment"""
        self.is_active = 0
        db.session.commit()

    def activate(self):
        """Activate this trainer assignment"""
        self.is_active = 1
        db.session.commit()
