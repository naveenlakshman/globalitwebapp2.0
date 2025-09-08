from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for
from models.user_model import User
from models.batch_model import Batch
from models.student_model import Student
from models.student_attendance_model import StudentAttendance
from models.branch_model import Branch
from models.course_model import Course
from models.user_branch_assignment_model import UserBranchAssignment
from init_db import db
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta, date
import calendar

def login_required(f):
    """Simple login required decorator"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def get_user_branch_ids(user_id):
    """Get list of branch IDs a user has access to"""
    assignments = UserBranchAssignment.query.filter_by(user_id=user_id, is_active=1).all()
    return [assignment.branch_id for assignment in assignments]

# Create blueprint
attendance_reports_bp = Blueprint('attendance_reports', __name__)

def has_branch_access(user, branch_id):
    """Check if user has access to a specific branch"""
    if user.role in ['admin', 'regional_manager']:
        return True
    elif user.role == 'franchise':
        user_branches = get_user_branch_ids(user.id)
        return branch_id in user_branches if user_branches else False
    elif user.role in ['branch_manager', 'staff']:
        return session.get('user_branch_id') == branch_id
    elif user.role == 'trainer':
        # Trainers can only access their assigned branch
        return session.get('user_branch_id') == branch_id
    return False

@attendance_reports_bp.route('/')
@login_required
def attendance_reports():
    """Main attendance reports dashboard"""
    try:
        current_user_id = session.get('user_id')
        current_user = User.query.get(current_user_id)
        
        # Get date range (default to current month)
        today = date.today()
        start_date = request.args.get('start_date', today.replace(day=1).strftime('%Y-%m-%d'))
        end_date = request.args.get('end_date', today.strftime('%Y-%m-%d'))
        branch_id = request.args.get('branch_id', type=int)
        batch_id = request.args.get('batch_id', type=int)
        batch_status = request.args.get('batch_status', '')
        
        # Auto-select user's branch if no branch filter applied
        if not branch_id and current_user.role in ['branch_manager', 'staff']:
            branch_id = session.get('user_branch_id')
        
        # Auto-select user's branch if no branch filter is specified
        if not branch_id and current_user.role in ['branch_manager', 'staff', 'trainer']:
            branch_id = session.get('user_branch_id')
        
        # Convert to datetime objects
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Base queries with role-based filtering
        # Filter by batch status if specified, otherwise show all statuses
        if batch_status:
            batch_query = Batch.query.filter(Batch.status == batch_status)
        else:
            batch_query = Batch.query.filter(Batch.status.in_(['Active', 'Completed', 'Suspended', 'Inactive']))
        
        student_query = Student.query.filter_by(is_deleted=0)
        
        # Apply role-based branch filtering
        if current_user.role == 'franchise':
            user_branches = get_user_branch_ids(current_user.id)
            if user_branches:
                batch_query = batch_query.filter(Batch.branch_id.in_(user_branches))
                student_query = student_query.join(Batch).filter(Batch.branch_id.in_(user_branches))
            else:
                batch_query = batch_query.filter(False)  # No access
                student_query = student_query.filter(False)
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get('user_branch_id')
            if user_branch_id:
                batch_query = batch_query.filter_by(branch_id=user_branch_id)
                student_query = student_query.join(Batch).filter(Batch.branch_id == user_branch_id)
            else:
                batch_query = batch_query.filter(False)
                student_query = student_query.filter(False)
        elif current_user.role == 'trainer':
            # Trainers see only their assigned batches
            from models.batch_trainer_assignment_model import BatchTrainerAssignment
            trainer_batch_ids = db.session.query(BatchTrainerAssignment.batch_id).filter_by(
                trainer_id=current_user.id, is_active=1
            ).all()
            trainer_batch_ids = [row[0] for row in trainer_batch_ids]
            print(f"Debug: Trainer {current_user.full_name} has batch assignments: {trainer_batch_ids}")
            if trainer_batch_ids:
                batch_query = batch_query.filter(Batch.id.in_(trainer_batch_ids))
                student_query = student_query.join(Batch).filter(Batch.id.in_(trainer_batch_ids))
            else:
                batch_query = batch_query.filter(False)
                student_query = student_query.filter(False)
        
        # Apply additional filters
        if branch_id:
            batch_query = batch_query.filter_by(branch_id=branch_id)
            # Only apply if not already filtered by role
            if current_user.role not in ['franchise', 'branch_manager', 'staff', 'trainer']:
                student_query = student_query.join(Batch).filter(Batch.branch_id == branch_id)
        
        if batch_id:
            batch_query = batch_query.filter_by(id=batch_id)
            student_query = student_query.filter_by(batch_id=batch_id)
        
        # Get filtered data
        batches = batch_query.all()
        batch_ids = [batch.id for batch in batches]
        
        # Debug: Show what batches were found
        print(f"Debug: Found {len(batches)} batches for user:")
        for batch in batches:
            print(f"  - {batch.name} (ID: {batch.id}) - Status: {batch.status}")
        
        # Calculate attendance statistics
        total_students = student_query.count()
        
        # Get all branches for filter dropdowns - role-based filtering
        if current_user.role == 'franchise':
            user_branches = get_user_branch_ids(current_user.id)
            if user_branches:
                branches = Branch.query.filter(Branch.id.in_(user_branches)).all()
            else:
                branches = []
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get('user_branch_id')
            if user_branch_id:
                branches = Branch.query.filter_by(id=user_branch_id).all()
            else:
                branches = []
        elif current_user.role == 'trainer':
            # Trainers should only see their assigned branch
            user_branch_id = session.get('user_branch_id')
            if user_branch_id:
                branches = Branch.query.filter_by(id=user_branch_id).all()
            else:
                branches = []
        elif current_user.role == 'admin':
            # Only admins can see all branches
            branches = Branch.query.filter_by(is_deleted=0).all()
        else:
            branches = []
        
        # Debug print
        print(f"Debug: Current user role: {current_user.role}")
        print(f"Debug: User branch ID from session: {session.get('user_branch_id')}")
        print(f"Debug: Available branches for user: {[b.branch_name for b in branches]}")
        print(f"Debug: Total students: {total_students}")
        print(f"Debug: Batch IDs: {batch_ids}")
        print(f"Debug: Date range: {start_date} to {end_date}")
        
        # Get attendance records for the date range
        if batch_ids:
            attendance_query = StudentAttendance.query.filter(
                and_(
                    StudentAttendance.date >= start_date,
                    StudentAttendance.date <= end_date,
                    StudentAttendance.batch_id.in_(batch_ids)
                )
            )
        else:
            # No batches available, return empty query
            attendance_query = StudentAttendance.query.filter(False)
        
        # Debug: Check how many records we're getting
        all_attendance_records = attendance_query.all()
        print(f"Debug: Found {len(all_attendance_records)} attendance records")
        for record in all_attendance_records[:5]:  # Show first 5
            print(f"  - Student: {record.student_id}, Date: {record.date}, Status: {record.status}, Batch: {record.batch_id}")
        
        # Calculate attendance metrics
        total_attendance_records = attendance_query.count()
        present_count = attendance_query.filter_by(status='Present').count()
        absent_count = attendance_query.filter_by(status='Absent').count()
        late_count = attendance_query.filter_by(status='Late').count()
        
        # Calculate attendance rate
        attendance_rate = (present_count + late_count) / total_attendance_records * 100 if total_attendance_records > 0 else 0
        
        # Get batch-wise attendance summary
        batch_attendance = []
        for batch in batches:
            batch_students = Student.query.filter_by(batch_id=batch.id, is_deleted=0).count()
            batch_attendance_records = StudentAttendance.query.filter(
                and_(
                    StudentAttendance.batch_id == batch.id,
                    StudentAttendance.date >= start_date,
                    StudentAttendance.date <= end_date
                )
            ).count()
            
            batch_present = StudentAttendance.query.filter(
                and_(
                    StudentAttendance.batch_id == batch.id,
                    StudentAttendance.date >= start_date,
                    StudentAttendance.date <= end_date,
                    StudentAttendance.status.in_(['Present', 'Late'])
                )
            ).count()
            
            batch_rate = (batch_present / batch_attendance_records * 100) if batch_attendance_records > 0 else 0
            
            batch_attendance.append({
                'batch': batch,
                'student_count': batch_students,
                'attendance_rate': round(batch_rate, 1),
                'total_records': batch_attendance_records,
                'present_count': batch_present
            })
        
        # Sort batches by attendance rate (lowest first for attention)
        batch_attendance.sort(key=lambda x: x['attendance_rate'])
        
        # Get daily attendance trend for chart
        daily_attendance = []
        current_date = start_dt
        while current_date <= end_dt:
            current_date_str = current_date.strftime('%Y-%m-%d')
            if batch_ids:
                daily_records = StudentAttendance.query.filter(
                    and_(
                        StudentAttendance.date == current_date_str,
                        StudentAttendance.batch_id.in_(batch_ids)
                    )
                ).count()
                
                daily_present = StudentAttendance.query.filter(
                    and_(
                        StudentAttendance.date == current_date_str,
                        StudentAttendance.batch_id.in_(batch_ids),
                        StudentAttendance.status.in_(['Present', 'Late'])
                    )
                ).count()
            else:
                daily_records = 0
                daily_present = 0
            
            daily_rate = (daily_present / daily_records * 100) if daily_records > 0 else 0
            
            daily_attendance.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'rate': round(daily_rate, 1),
                'present': daily_present,
                'total': daily_records
            })
            
            current_date += timedelta(days=1)
        
        # Get courses for filtering
        courses = Course.query.filter_by(is_deleted=0, status='Active').all()
        
        return render_template('attendance/reports.html',
                             total_students=total_students,
                             total_attendance_records=total_attendance_records,
                             present_count=present_count,
                             absent_count=absent_count,
                             late_count=late_count,
                             attendance_rate=round(attendance_rate, 1),
                             batch_attendance=batch_attendance,
                             daily_attendance=daily_attendance,
                             branches=branches,
                             courses=courses,
                             batches=batches,
                             start_date=start_date,
                             end_date=end_date,
                             batch_status=batch_status,
                             current_user=current_user)
        
    except Exception as e:
        print(f"Attendance reports error: {str(e)}")  # Debug logging
        flash(f'Error loading attendance reports: {str(e)}', 'error')
        from flask import url_for
        return redirect(f"/error?message=Attendance Reports Error: {str(e)}")

@attendance_reports_bp.route('/batch/<int:batch_id>')
@login_required
def batch_attendance_report(batch_id):
    """Detailed attendance report for a specific batch"""
    try:
        current_user_id = session.get('user_id')
        current_user = User.query.get(current_user_id)
        batch = Batch.query.get_or_404(batch_id)
        
        # Check access
        if not has_branch_access(current_user, batch.branch_id):
            flash('You do not have permission to view this batch report.', 'error')
            return redirect(url_for('attendance_reports.attendance_reports'))
        
        # Get date range
        start_date = request.args.get('start_date', (date.today() - timedelta(days=30)).strftime('%Y-%m-%d'))
        end_date = request.args.get('end_date', date.today().strftime('%Y-%m-%d'))
        
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Get students in batch
        students = Student.query.filter_by(batch_id=batch_id, is_deleted=0).order_by(Student.full_name).all()
        
        # Get attendance data for each student
        student_attendance_data = []
        for student in students:
            attendance_records = StudentAttendance.query.filter(
                and_(
                    StudentAttendance.student_id == student.student_id,
                    StudentAttendance.date >= start_date,
                    StudentAttendance.date <= end_date
                )
            ).order_by(StudentAttendance.date.desc()).all()
            
            total_days = len(attendance_records)
            present_days = len([r for r in attendance_records if r.status in ['Present', 'Late']])
            absent_days = len([r for r in attendance_records if r.status == 'Absent'])
            
            attendance_rate = (present_days / total_days * 100) if total_days > 0 else 0
            
            student_attendance_data.append({
                'student': student,
                'total_days': total_days,
                'present_days': present_days,
                'absent_days': absent_days,
                'attendance_rate': round(attendance_rate, 1),
                'recent_records': attendance_records[:10]  # Last 10 records
            })
        
        # Sort by attendance rate (lowest first)
        student_attendance_data.sort(key=lambda x: x['attendance_rate'])
        
        return render_template('attendance/batch_report.html',
                             batch=batch,
                             student_attendance_data=student_attendance_data,
                             start_date=start_date,
                             end_date=end_date)
        
    except Exception as e:
        flash(f'Error loading batch attendance report: {str(e)}', 'error')
        return redirect(f"/error?message=Batch Attendance Report Error: {str(e)}")

@attendance_reports_bp.route('/api/attendance-data')
@login_required
def get_attendance_data():
    """API endpoint for attendance chart data"""
    try:
        current_user_id = session.get('user_id')
        current_user = User.query.get(current_user_id)
        
        # Get parameters
        start_date = request.args.get('start_date', (date.today() - timedelta(days=30)).strftime('%Y-%m-%d'))
        end_date = request.args.get('end_date', date.today().strftime('%Y-%m-%d'))
        branch_id = request.args.get('branch_id', type=int)
        batch_id = request.args.get('batch_id', type=int)
        
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Build query with filters
        query = StudentAttendance.query.filter(
            and_(
                StudentAttendance.date >= start_date,
                StudentAttendance.date <= end_date
            )
        )
        
        # Apply role-based filtering
        if current_user.role == 'franchise':
            user_branches = get_user_branch_ids(current_user.id)
            if user_branches:
                query = query.join(Batch).filter(Batch.branch_id.in_(user_branches))
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get('user_branch_id')
            if user_branch_id:
                query = query.join(Batch).filter(Batch.branch_id == user_branch_id)
        
        # Apply additional filters
        if branch_id:
            query = query.join(Batch).filter(Batch.branch_id == branch_id)
        if batch_id:
            query = query.filter(StudentAttendance.batch_id == batch_id)
        
        # Get daily data
        daily_data = []
        current_date = start_dt
        while current_date <= end_dt:
            current_date_str = current_date.strftime('%Y-%m-%d')
            day_records = query.filter(StudentAttendance.date == current_date_str).all()
            
            total = len(day_records)
            present = len([r for r in day_records if r.status in ['Present', 'Late']])
            absent = len([r for r in day_records if r.status == 'Absent'])
            
            daily_data.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'total': total,
                'present': present,
                'absent': absent,
                'rate': round((present / total * 100) if total > 0 else 0, 1)
            })
            
            current_date += timedelta(days=1)
        
        return jsonify({
            'success': True,
            'data': daily_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500