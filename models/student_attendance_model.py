from init_db import db
from datetime import datetime, timezone, time
from utils.timezone_helper import format_datetime_indian
from sqlalchemy import func

class StudentAttendance(db.Model):
    __tablename__ = 'student_attendance'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False)  # Format: YYYY-MM-DD
    session_type = db.Column(db.String(20), default='Regular')  # Regular, Theory, Practical, Assessment
    status = db.Column(db.String(10), nullable=False, default='Present')  # Present, Absent, Late, ExcusedAbsent
    check_in_time = db.Column(db.Time, nullable=True)  # Actual check-in time
    check_out_time = db.Column(db.Time, nullable=True)  # Actual check-out time
    late_minutes = db.Column(db.Integer, default=0)  # Minutes late
    marked_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Who marked attendance
    marked_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    notes = db.Column(db.Text, nullable=True)  # Optional notes
    parent_notified = db.Column(db.Boolean, default=False)  # Parent notification status
    
    # Vocational Education specific fields
    practical_hours = db.Column(db.Float, default=0.0)  # Hours spent in practical work
    theory_hours = db.Column(db.Float, default=0.0)  # Hours spent in theory
    competency_evaluated = db.Column(db.Boolean, default=False)  # Was student evaluated today
    
    # Fee tracking fields (for daily attendance fee recovery)
    fee_status = db.Column(db.String(20), nullable=True)  # Paid, Pending, Overdue, Partial
    due_amount = db.Column(db.Float, default=0.0)  # Outstanding amount
    due_date = db.Column(db.Date, nullable=True)  # Next payment due date
    
    # Relationships
    student = db.relationship('Student', backref='attendance_records')
    batch = db.relationship('Batch', backref='attendance_records')
    marked_by_user = db.relationship('User', foreign_keys=[marked_by])

    # Constraints
    __table_args__ = (
        db.UniqueConstraint('student_id', 'batch_id', 'date', name='unique_student_batch_date'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'batch_id': self.batch_id,
            'date': self.date,
            'session_type': self.session_type,
            'status': self.status,
            'check_in_time': self.check_in_time.strftime('%H:%M') if self.check_in_time else None,
            'check_out_time': self.check_out_time.strftime('%H:%M') if self.check_out_time else None,
            'late_minutes': self.late_minutes,
            'marked_by': self.marked_by,
            'marked_at': format_datetime_indian(self.marked_at, include_time=True, include_seconds=True) if self.marked_at else None,
            'notes': self.notes,
            'parent_notified': self.parent_notified,
            'practical_hours': self.practical_hours,
            'theory_hours': self.theory_hours,
            'competency_evaluated': self.competency_evaluated,
            'fee_status': self.fee_status,
            'due_amount': self.due_amount,
            'due_date': self.due_date.strftime('%Y-%m-%d') if self.due_date else None
        }
    
    def create_audit_snapshot(self):
        """Create a snapshot of current state for audit purposes"""
        return self.to_dict()
    
    def detect_changes(self, new_data):
        """
        Detect what fields have changed by comparing current state with new data
        Returns dict of {field_name: {'old': old_value, 'new': new_value}}
        """
        changes = {}
        current_data = self.to_dict()
        
        # Define auditable fields
        auditable_fields = [
            'status', 'check_in_time', 'check_out_time', 'late_minutes',
            'notes', 'practical_hours', 'theory_hours', 'competency_evaluated'
        ]
        
        for field in auditable_fields:
            old_value = current_data.get(field)
            new_value = new_data.get(field)
            
            # Convert to comparable format
            if old_value != new_value:
                changes[field] = {
                    'old': old_value,
                    'new': new_value,
                    'original_record': current_data,
                    'updated_record': new_data
                }
        
        return changes

    @classmethod
    def mark_attendance(cls, student_id, batch_id, date, status='Present', marked_by=None, 
                       notes=None, session_type='Regular', check_in_time=None, check_out_time=None,
                       late_minutes=0, practical_hours=0.0, theory_hours=0.0, fee_status=None,
                       due_amount=0.0, due_date=None):
        """Enhanced attendance marking for vocational education"""
        try:
            # Check if attendance already exists
            attendance = cls.query.filter_by(
                student_id=student_id,
                batch_id=batch_id,
                date=date
            ).first()

            if attendance:
                # Update existing record
                attendance.status = status
                attendance.session_type = session_type
                attendance.marked_by = marked_by
                attendance.marked_at = datetime.now(timezone.utc)
                attendance.notes = notes
                attendance.late_minutes = late_minutes
                attendance.practical_hours = practical_hours
                attendance.theory_hours = theory_hours
                attendance.fee_status = fee_status
                attendance.due_amount = due_amount
                attendance.due_date = due_date
                if check_in_time:
                    attendance.check_in_time = check_in_time
                if check_out_time:
                    attendance.check_out_time = check_out_time
            else:
                # Create new record
                attendance = cls(
                    student_id=student_id,
                    batch_id=batch_id,
                    date=date,
                    session_type=session_type,
                    status=status,
                    check_in_time=check_in_time,
                    check_out_time=check_out_time,
                    late_minutes=late_minutes,
                    marked_by=marked_by,
                    notes=notes,
                    practical_hours=practical_hours,
                    theory_hours=theory_hours,
                    fee_status=fee_status,
                    due_amount=due_amount,
                    due_date=due_date
                )
                db.session.add(attendance)

            db.session.commit()
            return attendance, True

        except Exception as e:
            db.session.rollback()
            return None, False

    @classmethod
    def get_student_attendance_summary(cls, student_id, batch_id):
        """Get comprehensive attendance summary for a student in a batch"""
        records = cls.query.filter_by(student_id=student_id, batch_id=batch_id).all()
        
        if not records:
            return None
            
        total_sessions = len(records)
        present_sessions = len([r for r in records if r.status == 'Present'])
        late_sessions = len([r for r in records if r.status == 'Late'])
        absent_sessions = len([r for r in records if r.status == 'Absent'])
        excused_sessions = len([r for r in records if r.status == 'ExcusedAbsent'])
        
        total_practical_hours = sum(r.practical_hours for r in records)
        total_theory_hours = sum(r.theory_hours for r in records)
        total_late_minutes = sum(r.late_minutes for r in records)
        
        attendance_rate = (present_sessions + late_sessions) / total_sessions * 100 if total_sessions > 0 else 0
        
        return {
            'student_id': student_id,
            'batch_id': batch_id,
            'total_sessions': total_sessions,
            'present_sessions': present_sessions,
            'late_sessions': late_sessions,
            'absent_sessions': absent_sessions,
            'excused_sessions': excused_sessions,
            'attendance_rate': round(attendance_rate, 2),
            'total_practical_hours': total_practical_hours,
            'total_theory_hours': total_theory_hours,
            'total_late_minutes': total_late_minutes,
            'average_late_minutes': total_late_minutes / late_sessions if late_sessions > 0 else 0,
            'certification_eligible': attendance_rate >= 75,  # Industry standard
            'warning_status': 'Critical' if attendance_rate < 60 else 'Warning' if attendance_rate < 75 else 'Good'
        }

    @classmethod
    def get_batch_attendance(cls, batch_id, date):
        """Get attendance for all students in a batch on a specific date"""
        return cls.query.filter_by(batch_id=batch_id, date=date).all()

    @classmethod
    def get_student_attendance(cls, student_id, start_date=None, end_date=None):
        """Get attendance records for a student within date range"""
        query = cls.query.filter_by(student_id=student_id)
        
        if start_date:
            query = query.filter(cls.date >= start_date)
        if end_date:
            query = query.filter(cls.date <= end_date)
            
        return query.order_by(cls.date.desc()).all()

    @classmethod
    def get_batch_attendance_analytics(cls, batch_id, start_date=None, end_date=None):
        """Comprehensive batch attendance analytics for vocational education"""
        query = cls.query.filter_by(batch_id=batch_id)
        
        if start_date:
            query = query.filter(cls.date >= start_date)
        if end_date:
            query = query.filter(cls.date <= end_date)
            
        records = query.all()
        
        if not records:
            return {
                'batch_id': batch_id,
                'total_sessions': 0,
                'analytics': {}
            }
        
        # Group by session type
        session_analytics = {}
        for session_type in ['Regular', 'Theory', 'Practical', 'Assessment']:
            session_records = [r for r in records if r.session_type == session_type]
            if session_records:
                total = len(session_records)
                present = len([r for r in session_records if r.status in ['Present', 'Late']])
                session_analytics[session_type] = {
                    'total_sessions': total,
                    'present_count': present,
                    'attendance_rate': (present / total * 100) if total > 0 else 0
                }
        
        # Overall statistics
        unique_dates = len(set(r.date for r in records))
        total_records = len(records)
        present_records = len([r for r in records if r.status in ['Present', 'Late']])
        late_records = len([r for r in records if r.status == 'Late'])
        absent_records = len([r for r in records if r.status == 'Absent'])
        
        # Students with low attendance (below 75%)
        from collections import defaultdict
        student_attendance = defaultdict(list)
        for record in records:
            student_attendance[record.student_id].append(record)
        
        low_attendance_students = []
        for student_id, student_records in student_attendance.items():
            student_total = len(student_records)
            student_present = len([r for r in student_records if r.status in ['Present', 'Late']])
            student_rate = (student_present / student_total * 100) if student_total > 0 else 0
            
            if student_rate < 75:
                low_attendance_students.append({
                    'student_id': student_id,
                    'attendance_rate': round(student_rate, 2),
                    'total_sessions': student_total,
                    'present_sessions': student_present
                })
        
        return {
            'batch_id': batch_id,
            'date_range': {
                'start': start_date,
                'end': end_date
            },
            'overall_stats': {
                'unique_session_dates': unique_dates,
                'total_attendance_records': total_records,
                'present_records': present_records,
                'late_records': late_records,
                'absent_records': absent_records,
                'overall_attendance_rate': round((present_records / total_records * 100), 2) if total_records > 0 else 0,
                'punctuality_rate': round(((present_records - late_records) / total_records * 100), 2) if total_records > 0 else 0
            },
            'session_type_analytics': session_analytics,
            'low_attendance_students': low_attendance_students,
            'total_practical_hours': sum(r.practical_hours for r in records),
            'total_theory_hours': sum(r.theory_hours for r in records),
            'certification_readiness': {
                'eligible_students': len([s for s in student_attendance.keys() 
                                        if (len([r for r in student_attendance[s] if r.status in ['Present', 'Late']]) / 
                                            len(student_attendance[s]) * 100) >= 75]),
                'total_students': len(student_attendance.keys())
            }
        }

    @classmethod
    def get_attendance_stats(cls, batch_id, start_date=None, end_date=None):
        """Legacy method - maintained for backward compatibility"""
        analytics = cls.get_batch_attendance_analytics(batch_id, start_date, end_date)
        return {
            'total': analytics['overall_stats']['total_attendance_records'],
            'present': analytics['overall_stats']['present_records'],
            'absent': analytics['overall_stats']['absent_records'],
            'attendance_rate': analytics['overall_stats']['overall_attendance_rate']
        }
