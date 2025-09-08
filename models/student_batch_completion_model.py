from init_db import db
from utils.timezone_helper import format_datetime_indian, format_date_indian
from utils.model_helpers import standardize_model_datetime_fields
from datetime import datetime, timezone

class StudentBatchCompletion(db.Model):
    __tablename__ = 'student_batch_completions'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), db.ForeignKey('students.student_id'), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'), nullable=False)
    completion_date = db.Column(db.Date)
    completion_status = db.Column(db.String(20), default='Completed')  # Completed, Incomplete, Dropped
    certificate_issued = db.Column(db.Integer, default=0)  # 0 = No, 1 = Yes
    final_grade = db.Column(db.String(10))  # A+, A, B+, B, C, etc.
    completion_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    student = db.relationship('Student', backref='batch_completions')
    batch = db.relationship('Batch', backref='student_completions')

    def to_dict(self):
        return {
            "id": self.id,
            "student_id": self.student_id,
            "batch_id": self.batch_id,
            "completion_date": self.completion_date.strftime('%Y-%m-%d') if self.completion_date else None,
            "completion_status": self.completion_status,
            "certificate_issued": bool(self.certificate_issued),
            "final_grade": self.final_grade,
            "completion_notes": self.completion_notes,
            "created_at": self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            "student_name": self.student.full_name if self.student else None,
            "batch_name": self.batch.name if self.batch else None,
            "course_name": self.batch.course.course_name if self.batch and self.batch.course else None
        }

    @staticmethod
    def create_completion_records(batch_id, user_id=None):
        """Create completion records for all students in a batch when it's marked complete"""
        from models.student_model import Student
        
        # Get all active students in the batch
        students = Student.query.filter_by(batch_id=batch_id, is_deleted=0).all()
        
        completion_records = []
        for student in students:
            # Check if completion record already exists
            existing = StudentBatchCompletion.query.filter_by(
                student_id=student.student_id,
                batch_id=batch_id
            ).first()
            
            if not existing:
                completion = StudentBatchCompletion(
                    student_id=student.student_id,
                    batch_id=batch_id,
                    completion_date=datetime.now().date(),
                    completion_status='Completed'
                )
                db.session.add(completion)
                completion_records.append(completion)
        
        if completion_records:
            db.session.commit()
            return len(completion_records)
        return 0

    @staticmethod
    def get_student_completions(student_id):
        """Get all batch completions for a student"""
        return StudentBatchCompletion.query.filter_by(student_id=student_id).all()

    @staticmethod
    def get_batch_completions(batch_id):
        """Get all student completions for a batch"""
        return StudentBatchCompletion.query.filter_by(batch_id=batch_id).all()

    @staticmethod
    def get_completion_stats(batch_id=None, student_id=None):
        """Get completion statistics"""
        query = StudentBatchCompletion.query
        
        if batch_id:
            query = query.filter_by(batch_id=batch_id)
        if student_id:
            query = query.filter_by(student_id=student_id)
        
        completions = query.all()
        
        stats = {
            'total_completions': len(completions),
            'completed': len([c for c in completions if c.completion_status == 'Completed']),
            'incomplete': len([c for c in completions if c.completion_status == 'Incomplete']),
            'dropped': len([c for c in completions if c.completion_status == 'Dropped']),
            'certificates_issued': len([c for c in completions if c.certificate_issued]),
            'grade_distribution': {}
        }
        
        # Grade distribution
        for completion in completions:
            if completion.final_grade:
                grade = completion.final_grade
                stats['grade_distribution'][grade] = stats['grade_distribution'].get(grade, 0) + 1
        
        return stats

    def __repr__(self):
        return f'<StudentBatchCompletion {self.student_id} - Batch {self.batch_id}>'
