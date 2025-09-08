from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from models.student_attendance_model import StudentAttendance
from models.attendance_audit_model import AttendanceAudit
from models.batch_model import Batch
from models.student_model import Student
from models.user_model import User
from models.batch_trainer_assignment_model import BatchTrainerAssignment
from models.installment_model import Installment
from models.invoice_model import Invoice
from utils.auth import login_required
from init_db import db
from datetime import datetime, date, timezone, timedelta

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')

def get_user_branch_ids(user_id):
    """Helper function to get branch IDs for a user from user_branch_assignments table"""
    try:
        user_branch_assignments = db.session.execute(
            db.text("SELECT branch_id FROM user_branch_assignments WHERE user_id = :user_id AND is_active = 1"),
            {"user_id": user_id}
        ).fetchall()
        return [assignment[0] for assignment in user_branch_assignments]
    except Exception as e:
        print(f"Error getting user branch assignments: {e}")
        return []

def has_batch_access(user, batch):
    """Check if user has access to a specific batch"""
    if user.role == 'admin':
        return True
    elif user.role in ['franchise', 'regional_manager']:
        user_branches = get_user_branch_ids(user.id)
        return batch.branch_id in user_branches
    elif user.role in ['branch_manager', 'staff']:
        user_branch_id = session.get("user_branch_id")
        return batch.branch_id == user_branch_id
    elif user.role == 'trainer':
        # Trainers can only access batches they are assigned to
        return BatchTrainerAssignment.is_trainer_assigned_to_batch(batch.id, user.id)
    return False

# ================================
# ATTENDANCE MANAGEMENT ROUTES
# ================================

@attendance_bp.route('/batch/<int:batch_id>')
@login_required
def batch_attendance(batch_id):
    """Display attendance management interface for a batch"""
    try:
        from utils.timezone_helper import get_current_ist_datetime
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Validate access
        if not has_batch_access(current_user, batch):
            flash('You do not have access to this batch', 'error')
            return redirect(url_for('batches.list_batches'))
        
        # Validate batch status
        if batch.status != 'Active':
            flash(f'Cannot view attendance for {batch.status.lower()} batch. Only active batches allow attendance operations.', 'warning')
            # Still allow viewing but with warning
        
        # Get filter parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        status = request.args.get('status')
        page = request.args.get('page', 1, type=int)
        
        # Build attendance query
        attendance_query = StudentAttendance.query.filter_by(batch_id=batch_id)
        
        if start_date:
            attendance_query = attendance_query.filter(StudentAttendance.date >= start_date)
        if end_date:
            attendance_query = attendance_query.filter(StudentAttendance.date <= end_date)
        if status:
            attendance_query = attendance_query.filter_by(status=status)
        
        # Paginate results
        attendance_records = attendance_query.order_by(
            StudentAttendance.date.desc(),
            StudentAttendance.student_id
        ).paginate(
            page=page, per_page=50, error_out=False
        )
        
        # Get students in this batch
        students = Student.query.filter_by(batch_id=batch_id, is_deleted=0).all()
        
        # Get recent sessions (group by date to show session summaries)
        from collections import defaultdict
        
        # Get all attendance records for this batch, ordered by date
        all_attendance = StudentAttendance.query.filter_by(batch_id=batch_id)\
            .order_by(StudentAttendance.date.desc())\
            .limit(500).all()  # Get recent records for processing
        
        # Group by date to create session summaries
        sessions_by_date = defaultdict(lambda: {
            'date': None,
            'session_type': 'Regular',
            'check_in_time': None,
            'check_out_time': None,
            'present_count': 0,
            'late_count': 0,
            'absent_count': 0,
            'total_count': 0,
            'id': None
        })
        
        for record in all_attendance:
            date_key = record.date
            session_data = sessions_by_date[date_key]
            session_data['date'] = record.date
            session_data['id'] = record.id  # Use first record's ID
            if record.session_type:
                session_data['session_type'] = record.session_type
            if record.check_in_time and not session_data['check_in_time']:
                session_data['check_in_time'] = record.check_in_time
            if record.check_out_time and not session_data['check_out_time']:
                session_data['check_out_time'] = record.check_out_time
            
            # Count attendance status
            if record.status == 'Present':
                session_data['present_count'] += 1
            elif record.status == 'Late':
                session_data['late_count'] += 1
            elif record.status == 'Absent':
                session_data['absent_count'] += 1
            session_data['total_count'] += 1
        
        # Convert to list of session objects and sort by date (recent first)
        recent_sessions = []
        for date_key in sorted(sessions_by_date.keys(), reverse=True)[:10]:
            session_info = sessions_by_date[date_key]
            # Create a simple object-like structure
            class SessionSummary:
                def __init__(self, data):
                    for key, value in data.items():
                        setattr(self, key, value)
            
            recent_sessions.append(SessionSummary(session_info))
        
        # Calculate statistics
        total_sessions = get_total_sessions(batch_id)
        active_students_count = len(students)
        today_attendance = get_today_attendance(batch_id)
        
        return render_template('attendance/mark_attendance.html',
                             batch=batch,
                             attendance_records=attendance_records,
                             students=students,
                             recent_sessions=recent_sessions,
                             total_sessions=total_sessions,
                             active_students_count=active_students_count,
                             today_attendance=today_attendance,
                             selected_date=request.args.get('date'),
                             selected_session_type=request.args.get('session_type', 'Regular'),
                             today=get_current_ist_datetime().date().strftime('%Y-%m-%d'))
        
    except Exception as e:
        flash(f'Error loading attendance: {str(e)}', 'error')
        return redirect(url_for('batches.view_batch', batch_id=batch_id))

@attendance_bp.route('/batch/<int:batch_id>/mark', methods=['POST'])
@login_required
def mark_batch_attendance(batch_id):
    """Mark attendance for multiple students in a batch with full audit trail"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Validate access
        if not has_batch_access(current_user, batch):
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        # Validate batch status and date restrictions
        if batch.status != 'Active':
            flash(f'Cannot mark attendance for {batch.status.lower()} batch. Only active batches allow attendance marking.', 'error')
            return redirect(url_for('batches.view_batch', batch_id=batch_id))
        
        attendance_date = request.form.get('attendance_date')
        session_type = request.form.get('session_type', 'Regular')
        change_reason = request.form.get('change_reason', 'Regular attendance marking')
        
        if not attendance_date:
            flash('Attendance date is required', 'error')
            return redirect(url_for('attendance.mark_attendance_page', batch_id=batch_id))
        
        # Validate attendance date
        from utils.timezone_helper import get_current_ist_datetime
        ist_today = get_current_ist_datetime().date()
        
        try:
            attendance_date_obj = datetime.strptime(attendance_date, '%Y-%m-%d').date()
            
            # Cannot mark attendance before batch start date
            if batch.start_date:
                batch_start_date = datetime.strptime(batch.start_date, '%Y-%m-%d').date()
                if attendance_date_obj < batch_start_date:
                    flash(f'Cannot mark attendance for {attendance_date_obj.strftime("%d-%b-%Y")} as it is before batch start date ({batch_start_date.strftime("%d-%b-%Y")}).', 'error')
                    return redirect(url_for('attendance.mark_attendance_page', batch_id=batch_id))
            
            # Cannot mark attendance for future dates (more than today)
            if attendance_date_obj > ist_today:
                flash(f'Cannot mark attendance for future date ({attendance_date_obj.strftime("%d-%b-%Y")}). Please select today or a past date.', 'error')
                return redirect(url_for('attendance.mark_attendance_page', batch_id=batch_id))
                
        except ValueError:
            flash('Invalid attendance date format', 'error')
            return redirect(url_for('attendance.mark_attendance_page', batch_id=batch_id))
            return redirect(url_for('attendance.mark_attendance_page', batch_id=batch_id))
        
        # Get all students in batch
        students = Student.query.filter_by(batch_id=batch_id, is_deleted=0).all()
        marked_count = 0
        updated_count = 0
        audit_entries = []
        
        for student in students:
            attendance_key = f'attendance_{student.student_id}'
            
            if attendance_key in request.form:
                status = request.form[attendance_key]
                notes = request.form.get(f'notes_{student.student_id}', '')
                check_in_time_str = request.form.get(f'check_in_{student.student_id}', '')
                check_out_time_str = request.form.get(f'check_out_{student.student_id}', '')
                late_minutes = request.form.get(f'late_minutes_{student.student_id}', 0)
                practical_hours = request.form.get(f'practical_hours_{student.student_id}', 0.0)
                theory_hours = request.form.get(f'theory_hours_{student.student_id}', 0.0)
                fee_status = request.form.get(f'fee_status_{student.student_id}', '')
                due_amount = request.form.get(f'due_amount_{student.student_id}', '')
                due_date_str = request.form.get(f'due_date_{student.student_id}', '')
                
                # Parse check-in time
                check_in_time = None
                if check_in_time_str:
                    try:
                        from datetime import time as time_obj
                        hour, minute = map(int, check_in_time_str.split(':'))
                        check_in_time = time_obj(hour, minute)
                    except ValueError:
                        check_in_time = None

                # Parse check-out time
                check_out_time = None
                if check_out_time_str:
                    try:
                        from datetime import time as time_obj
                        hour, minute = map(int, check_out_time_str.split(':'))
                        check_out_time = time_obj(hour, minute)
                    except ValueError:
                        check_out_time = None

                # Parse due date
                due_date = None
                if due_date_str:
                    try:
                        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
                    except ValueError:
                        due_date = None
                
                # Convert to appropriate types
                try:
                    late_minutes = int(late_minutes) if late_minutes else 0
                    practical_hours = float(practical_hours) if practical_hours else 0.0
                    theory_hours = float(theory_hours) if theory_hours else 0.0
                    due_amount = float(due_amount) if due_amount else 0.0
                except ValueError:
                    late_minutes = 0
                    practical_hours = 0.0
                    theory_hours = 0.0
                    due_amount = 0.0
                
                # Check if attendance already exists
                existing_attendance = StudentAttendance.query.filter_by(
                    student_id=student.student_id,
                    batch_id=batch_id,
                    date=attendance_date
                ).first()
                
                # Prepare new data for comparison
                new_data = {
                    'status': status,
                    'notes': notes,
                    'check_in_time': check_in_time.strftime('%H:%M') if check_in_time else None,
                    'check_out_time': check_out_time.strftime('%H:%M') if check_out_time else None,
                    'late_minutes': late_minutes,
                    'practical_hours': practical_hours,
                    'theory_hours': theory_hours,
                    'session_type': session_type,
                    'fee_status': fee_status,
                    'due_amount': due_amount,
                    'due_date': due_date.strftime('%Y-%m-%d') if due_date else None
                }
                
                if existing_attendance:
                    # UPDATE existing attendance with audit trail
                    changes = existing_attendance.detect_changes(new_data)
                    
                    if changes:  # Only update if there are actual changes
                        # Update the record
                        existing_attendance.status = status
                        existing_attendance.notes = notes
                        existing_attendance.check_in_time = check_in_time
                        existing_attendance.check_out_time = check_out_time
                        existing_attendance.late_minutes = late_minutes
                        existing_attendance.practical_hours = practical_hours
                        existing_attendance.theory_hours = theory_hours
                        existing_attendance.session_type = session_type
                        existing_attendance.fee_status = fee_status
                        existing_attendance.due_amount = due_amount
                        existing_attendance.due_date = due_date
                        existing_attendance.marked_by = current_user.id
                        existing_attendance.marked_at = datetime.now(timezone.utc)
                        
                        # Log audit trail for changes
                        AttendanceAudit.log_attendance_change(
                            attendance_record=existing_attendance,
                            changed_by_user_id=current_user.id,
                            action_type='UPDATE',
                            change_reason=change_reason,
                            field_changes=changes,
                            request=request
                        )
                        
                        updated_count += 1
                else:
                    # CREATE new attendance record
                    attendance, success = StudentAttendance.mark_attendance(
                        student_id=student.student_id,
                        batch_id=batch_id,
                        date=attendance_date,
                        status=status,
                        marked_by=current_user.id,
                        notes=notes,
                        session_type=session_type,
                        check_in_time=check_in_time,
                        check_out_time=check_out_time,
                        late_minutes=late_minutes,
                        practical_hours=practical_hours,
                        theory_hours=theory_hours,
                        fee_status=fee_status,
                        due_amount=due_amount,
                        due_date=due_date
                    )
                    
                    if success:
                        # Log audit trail for new record
                        AttendanceAudit.log_attendance_change(
                            attendance_record=attendance,
                            changed_by_user_id=current_user.id,
                            action_type='CREATE',
                            change_reason=change_reason,
                            request=request
                        )
                        
                        marked_count += 1
        
        # Commit all changes and audit entries
        db.session.commit()
        
        # Provide detailed feedback
        if marked_count > 0 and updated_count > 0:
            flash(f'✅ Attendance processed: {marked_count} new records, {updated_count} updated records on {attendance_date}', 'success')
        elif marked_count > 0:
            flash(f'✅ Attendance marked for {marked_count} students on {attendance_date}', 'success')
        elif updated_count > 0:
            flash(f'✅ Attendance updated for {updated_count} students on {attendance_date} (changes logged)', 'success')
        else:
            flash('ℹ️ No attendance changes were made', 'info')
        
        return redirect(url_for('attendance.mark_attendance_page', 
                              batch_id=batch_id, 
                              date=attendance_date,
                              session_type=session_type))
        
    except Exception as e:
        flash(f'Error marking attendance: {str(e)}', 'error')
        return redirect(url_for('attendance.mark_attendance_page', batch_id=batch_id))


@attendance_bp.route('/audit/<int:batch_id>')
@login_required
def view_attendance_audit(batch_id):
    """View audit trail for attendance changes"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Validate access - only admin, branch managers, and assigned trainers can view audit
        if not (current_user.role in ['admin', 'branch_manager'] or has_batch_access(current_user, batch)):
            flash('You do not have permission to view audit trails.', 'error')
            return redirect(url_for('batches.view_batch', batch_id=batch_id))
        
        # Get audit trail for this batch
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        audit_records = AttendanceAudit.query.filter_by(
            batch_id=batch_id
        ).order_by(
            AttendanceAudit.changed_at.desc()
        ).paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        # Get unique students for filtering
        students = Student.query.filter_by(batch_id=batch_id, is_deleted=0).all()
        
        # Get users for display names
        user_ids = {record.changed_by for record in audit_records.items}
        users = {user.id: user for user in User.query.filter(User.id.in_(user_ids)).all()}
        
        return render_template('attendance/audit_trail.html',
                             batch=batch,
                             audit_records=audit_records,
                             students=students,
                             users=users)
    
    except Exception as e:
        print(f"Error viewing attendance audit: {e}")
        flash('An error occurred while loading audit trail', 'error')
        return redirect(url_for('batches.view_batch', batch_id=batch_id))


@attendance_bp.route('/audit/student/<student_id>')
@login_required  
def view_student_audit(student_id):
    """View audit trail for a specific student's attendance"""
    try:
        current_user = User.query.get(session['user_id'])
        student = Student.query.filter_by(student_id=student_id).first_or_404()
        
        # Validate access
        if current_user.role not in ['admin', 'branch_manager']:
            if current_user.role == 'trainer':
                # Check if trainer is assigned to student's batch
                if not BatchTrainerAssignment.is_trainer_assigned_to_batch(student.batch_id, current_user.id):
                    flash('Access denied.', 'error')
                    return redirect(url_for('dashboard_bp.admin_dashboard'))
            else:
                flash('Access denied.', 'error')
                return redirect(url_for('dashboard_bp.admin_dashboard'))
        
        # Get audit trail for this student
        audit_records = AttendanceAudit.query.filter_by(
            student_id=student_id
        ).order_by(
            AttendanceAudit.changed_at.desc()
        ).limit(100).all()
        
        # Get users for display names
        user_ids = {record.changed_by for record in audit_records}
        users = {user.id: user for user in User.query.filter(User.id.in_(user_ids)).all()}
        
        return render_template('attendance/student_audit.html',
                             student=student,
                             audit_records=audit_records,
                             users=users)
    
    except Exception as e:
        print(f"Error viewing student audit: {e}")
        flash('An error occurred while loading student audit trail', 'error')
        return redirect(url_for('dashboard_bp.admin_dashboard'))


@attendance_bp.route('/<int:attendance_id>/edit', methods=['POST'])
@login_required
def edit_attendance(attendance_id):
    """Edit individual attendance record via AJAX"""
    try:
        current_user = User.query.get(session['user_id'])
        attendance = StudentAttendance.query.get_or_404(attendance_id)
        batch = Batch.query.get(attendance.batch_id)
        
        # Validate access
        if not has_batch_access(current_user, batch):
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        # Get data from request
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Update attendance record
        attendance.status = data.get('status', attendance.status)
        attendance.notes = data.get('notes', attendance.notes)
        attendance.marked_by = current_user.id
        attendance.marked_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Attendance updated successfully',
            'attendance': {
                'id': attendance.id,
                'status': attendance.status,
                'notes': attendance.notes,
                'marked_by': current_user.full_name
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@attendance_bp.route('/student/<student_id>')
@login_required
def student_attendance_history(student_id):
    """Display attendance history for a specific student"""
    try:
        current_user = User.query.get(session['user_id'])
        student = Student.query.get_or_404(student_id)
        
        # Validate access - check if user has access to student's batch/branch
        if student.batch_id:
            batch = Batch.query.get(student.batch_id)
            if batch and not has_batch_access(current_user, batch):
                flash('You do not have access to this student', 'error')
                return redirect(url_for('batches.list_batches'))
        
        # Get filter parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        page = request.args.get('page', 1, type=int)
        
        # Get attendance records
        attendance_records = StudentAttendance.get_student_attendance(
            student_id=student_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Paginate results
        per_page = 20
        total = len(attendance_records)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_records = attendance_records[start_idx:end_idx]
        
        # Calculate statistics
        if attendance_records:
            total_sessions = len(attendance_records)
            present_sessions = sum(1 for record in attendance_records if record.status == 'Present')
            late_sessions = sum(1 for record in attendance_records if record.status == 'Late')
            absent_sessions = sum(1 for record in attendance_records if record.status == 'Absent')
            excused_sessions = sum(1 for record in attendance_records if record.status == 'Excused')
            attendance_rate = (present_sessions / total_sessions * 100) if total_sessions > 0 else 0
            
            # Calculate hours
            practical_hours = sum(record.practical_hours or 0 for record in attendance_records)
            theory_hours = sum(record.theory_hours or 0 for record in attendance_records)
            total_hours = practical_hours + theory_hours
            
            # Calculate average late minutes
            late_records = [record for record in attendance_records if record.late_minutes]
            average_late_minutes = sum(record.late_minutes for record in late_records) / len(late_records) if late_records else 0
        else:
            total_sessions = present_sessions = late_sessions = absent_sessions = excused_sessions = attendance_rate = 0
            practical_hours = theory_hours = total_hours = average_late_minutes = 0

        # Get the batch for template
        batch = None
        if student.batch_id:
            batch = Batch.query.get(student.batch_id)

        return render_template('attendance/student_history.html',
                             student=student,
                             batch=batch,
                             current_user=current_user,
                             attendance_records=paginated_records,
                             total_sessions=total_sessions,
                             present_count=present_sessions,
                             late_count=late_sessions,
                             absent_count=absent_sessions,
                             excused_count=excused_sessions,
                             attendance_percentage=round(attendance_rate, 1),
                             practical_hours=practical_hours,
                             theory_hours=theory_hours,
                             total_hours=total_hours,
                             average_late_minutes=round(average_late_minutes, 1),
                             competency_evaluations=[],  # TODO: Implement competency evaluations
                             parent_notifications_sent=0,  # TODO: Implement parent notifications tracking
                             last_notification_date=None,  # TODO: Implement last notification date
                             page=page,
                             total_pages=(total + per_page - 1) // per_page)
        
    except Exception as e:
        flash(f'Error loading student attendance: {str(e)}', 'error')
        return redirect(url_for('batches.list_batches'))

@attendance_bp.route('/report/batch/<int:batch_id>')
@login_required
def batch_attendance_report(batch_id):
    """Generate attendance report for a batch"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Validate access
        if not has_batch_access(current_user, batch):
            return jsonify({'error': 'Access denied'}), 403
        
        # Get date range parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        format_type = request.args.get('format', 'json')  # json, csv, excel
        
        # Get attendance statistics
        stats = StudentAttendance.get_attendance_stats(
            batch_id=batch_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Get detailed records
        query = StudentAttendance.query.filter_by(batch_id=batch_id)
        if start_date:
            query = query.filter(StudentAttendance.date >= start_date)
        if end_date:
            query = query.filter(StudentAttendance.date <= end_date)
        
        attendance_records = query.order_by(StudentAttendance.date.desc()).all()
        
        # Get students in batch
        students = Student.query.filter_by(batch_id=batch_id, is_deleted=0).all()
        
        report_data = {
            'batch': {
                'id': batch.id,
                'name': batch.name,
                'course_name': batch.course_name,
                'branch_name': batch.branch.branch_name if batch.branch else 'Unknown'
            },
            'date_range': {
                'start_date': start_date,
                'end_date': end_date
            },
            'statistics': stats,
            'students': len(students),
            'total_records': len(attendance_records),
            'records': [record.to_dict() for record in attendance_records]
        }
        
        if format_type == 'json':
            return jsonify(report_data)
        elif format_type == 'csv':
            # TODO: Implement CSV export
            return jsonify({'error': 'CSV export not implemented yet'}), 501
        elif format_type == 'excel':
            # TODO: Implement Excel export
            return jsonify({'error': 'Excel export not implemented yet'}), 501
        else:
            return jsonify(report_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@attendance_bp.route('/mark_attendance/<int:batch_id>')
@login_required
def mark_attendance(batch_id):
    """Alternative route name for batch attendance - redirects to main attendance page"""
    return redirect(url_for('attendance.batch_attendance', batch_id=batch_id))

@attendance_bp.route('/mark/<int:batch_id>')
@login_required
def mark_attendance_page(batch_id):
    """Show the attendance marking page for a specific batch"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Validate access
        if not has_batch_access(current_user, batch):
            flash('You do not have access to this batch', 'error')
            return redirect(url_for('batches.list_batches'))
        
        # Validate batch status and date restrictions
        from utils.timezone_helper import get_current_ist_datetime
        ist_today = get_current_ist_datetime().date()
        
        # Check if batch is active
        if batch.status != 'Active':
            flash(f'Cannot mark attendance for {batch.status.lower()} batch. Only active batches allow attendance marking.', 'error')
            return redirect(url_for('batches.view_batch', batch_id=batch_id))
        
        # Check if batch has started
        if batch.start_date:
            try:
                batch_start_date = datetime.strptime(batch.start_date, '%Y-%m-%d').date()
                if ist_today < batch_start_date:
                    flash(f'Cannot mark attendance before batch start date ({batch.start_date}). Batch starts on {batch_start_date.strftime("%d-%b-%Y")}.', 'error')
                    return redirect(url_for('batches.view_batch', batch_id=batch_id))
            except ValueError:
                flash('Invalid batch start date format. Please contact administrator.', 'error')
                return redirect(url_for('batches.view_batch', batch_id=batch_id))
        
        # Validate selected attendance date
        selected_date = request.args.get('date', ist_today.strftime('%Y-%m-%d'))
        try:
            selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            
            # Cannot mark attendance before batch start date
            if batch.start_date:
                batch_start_date = datetime.strptime(batch.start_date, '%Y-%m-%d').date()
                if selected_date_obj < batch_start_date:
                    flash(f'Cannot mark attendance for {selected_date_obj.strftime("%d-%b-%Y")} as it is before batch start date ({batch_start_date.strftime("%d-%b-%Y")}).', 'error')
                    return redirect(url_for('attendance.mark_attendance_page', batch_id=batch_id, date=batch_start_date.strftime('%Y-%m-%d')))
            
            # Cannot mark attendance for future dates (more than today)
            if selected_date_obj > ist_today:
                flash(f'Cannot mark attendance for future date ({selected_date_obj.strftime("%d-%b-%Y")}). Please select today or a past date.', 'error')
                return redirect(url_for('attendance.mark_attendance_page', batch_id=batch_id, date=ist_today.strftime('%Y-%m-%d')))
                
        except ValueError:
            flash('Invalid date format selected. Using today\'s date.', 'warning')
            selected_date = ist_today.strftime('%Y-%m-%d')
        selected_session_type = request.args.get('session_type', 'Regular')
        
        # Get students in this batch
        students = Student.query.filter_by(batch_id=batch_id, is_deleted=0).all()
        
        # Get fee information for each student from installments and invoices
        students_with_fee_info = []
        for student in students:
            # Get the latest invoice for this student
            latest_invoice = Invoice.query.filter_by(
                student_id=student.student_id,
                is_deleted=0
            ).order_by(Invoice.created_at.desc()).first()
            
            fee_status = "Unknown"
            due_amount = 0.0
            next_due_date = None
            
            if latest_invoice:
                # Get pending/overdue installments for this student
                pending_installments = Installment.query.filter_by(
                    invoice_id=latest_invoice.id,
                    is_deleted=0
                ).filter(
                    Installment.status.in_(['pending', 'overdue', 'partial'])
                ).order_by(Installment.due_date).all()
                
                # Get all installments for this invoice to check if any exist
                all_installments = Installment.query.filter_by(
                    invoice_id=latest_invoice.id,
                    is_deleted=0
                ).all()
                
                if not all_installments:
                    # No installments exist - determine status from invoice data
                    if latest_invoice.due_amount <= 0:
                        fee_status = "Paid"
                        due_amount = 0.0
                        next_due_date = None
                    else:
                        fee_status = "Pending"
                        due_amount = latest_invoice.due_amount
                        # Use invoice creation date + 30 days as due date if no installments
                        next_due_date = (latest_invoice.created_at.date() + timedelta(days=30))
                        
                elif pending_installments:
                    # Calculate total due amount
                    due_amount = sum(inst.balance_amount or (inst.amount - inst.paid_amount) for inst in pending_installments)
                    
                    # Get the next due date
                    next_due_date = pending_installments[0].due_date
                    
                    # Determine fee status based on due dates
                    today = date.today()
                    overdue_installments = [inst for inst in pending_installments if inst.due_date < today]
                    
                    if overdue_installments:
                        fee_status = "Overdue"
                    elif due_amount > 0:
                        # Check if any installment has partial payment
                        partial_payments = [inst for inst in pending_installments if inst.paid_amount > 0 and inst.paid_amount < inst.amount]
                        if partial_payments:
                            fee_status = "Partial"
                        else:
                            fee_status = "Pending"
                    else:
                        fee_status = "Paid"
                else:
                    # No pending installments - check if all are paid
                    if all_installments and all(inst.is_paid for inst in all_installments):
                        fee_status = "Paid"
                    else:
                        fee_status = "Unknown"
            
            # Add fee info to student object
            student.fee_status = fee_status
            student.due_amount = due_amount
            student.next_due_date = next_due_date.strftime('%Y-%m-%d') if next_due_date else None
            students_with_fee_info.append(student)
            
            # Debug: Print fee information for debugging
            print(f"DEBUG - Student {student.student_id} ({student.full_name}): Fee Status={fee_status}, Due Amount={due_amount}, Due Date={next_due_date}")
            
            # Special debug for specific students
            if student.full_name in ['Arjun Patel', 'Aarav Sharma']:
                print(f"   DETAILED DEBUG for {student.full_name}:")
                print(f"   - Latest Invoice: {latest_invoice.id if latest_invoice else 'None'}")
                if latest_invoice:
                    all_installments = Installment.query.filter_by(
                        invoice_id=latest_invoice.id,
                        is_deleted=0
                    ).all()
                    print(f"   - Total Installments: {len(all_installments)}")
                    for inst in all_installments:
                        print(f"     * Installment {inst.installment_number}: Amount={inst.amount}, Paid={inst.paid_amount}, Status={inst.status}, Due={inst.due_date}")
                else:
                    print(f"   - No invoice found for {student.full_name}")
        
        students = students_with_fee_info
        
        # Get existing attendance for the selected date
        existing_attendance_records = StudentAttendance.query.filter_by(
            batch_id=batch_id,
            date=selected_date
        ).all()
        
        # Create a dictionary for easy lookup - only if there are actual records
        existing_attendance = None
        if existing_attendance_records:
            existing_attendance = {}
            for record in existing_attendance_records:
                existing_attendance[record.student_id] = {
                    'status': record.status,
                    'check_in_time': record.check_in_time.strftime('%H:%M') if record.check_in_time else '',
                    'check_out_time': record.check_out_time.strftime('%H:%M') if record.check_out_time else '',
                    'late_minutes': record.late_minutes,
                    'practical_hours': record.practical_hours,
                    'theory_hours': record.theory_hours,
                    'notes': record.notes or '',
                    'fee_status': record.fee_status or 'Unknown',
                    'due_amount': record.due_amount or 0.0,
                    'due_date': record.due_date.strftime('%Y-%m-%d') if record.due_date else ''
                }
        
        # Initialize current fee info for all students (for display purposes)
        student_fee_info = {}
        for student in students:
            student_fee_info[student.student_id] = {
                'fee_status': student.fee_status,
                'due_amount': student.due_amount,
                'due_date': student.next_due_date or ''
            }
        
        # Calculate today's attendance stats
        today_attendance = None
        if existing_attendance_records:
            present_count = sum(1 for r in existing_attendance_records if r.status == 'Present')
            absent_count = sum(1 for r in existing_attendance_records if r.status == 'Absent')
            late_count = sum(1 for r in existing_attendance_records if r.status == 'Late')
            today_attendance = {
                'present_count': present_count,
                'absent_count': absent_count,
                'late_count': late_count
            }
        
        # Prepare batch timing data for auto-fill functionality
        batch_timings = {
            'checkin_time': batch.checkin_time.strftime('%H:%M') if batch.checkin_time else '',
            'checkout_time': batch.checkout_time.strftime('%H:%M') if batch.checkout_time else ''
        }
        
        return render_template('attendance/mark_attendance.html',
                             batch=batch,
                             batch_timings=batch_timings,
                             students=students,
                             selected_date=selected_date,
                             selected_session_type=selected_session_type,
                             existing_attendance=existing_attendance,
                             student_fee_info=student_fee_info,
                             today_attendance=today_attendance,
                             today=ist_today.strftime('%Y-%m-%d'))
        
    except Exception as e:
        flash(f'Error loading attendance page: {str(e)}', 'error')
        return redirect(url_for('batches.list_batches'))

@attendance_bp.route('/api/stats/batch/<int:batch_id>')
@login_required
def get_batch_attendance_stats(batch_id):
    """Get attendance statistics for a batch via API"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Validate access
        if not has_batch_access(current_user, batch):
            return jsonify({'error': 'Access denied'}), 403
        
        # Get date range parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Get statistics
        stats = StudentAttendance.get_attendance_stats(
            batch_id=batch_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify({
            'success': True,
            'batch_id': batch_id,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@attendance_bp.route('/trainer/my-batches')
@login_required
def trainer_batches():
    """Display all batches assigned to the current trainer"""
    try:
        current_user = User.query.get(session['user_id'])
        
        # Only trainers can access this route
        if current_user.role != 'trainer':
            flash('Access denied. This page is for trainers only.', 'error')
            return redirect(url_for('dashboard_bp.admin_dashboard'))
        
        # Get trainer's batch assignments
        trainer_assignments = BatchTrainerAssignment.get_trainer_batches(current_user.id, active_only=True)
        trainer_batches = []
        
        for assignment in trainer_assignments:
            if assignment.batch and not assignment.batch.is_deleted:
                batch = assignment.batch
                
                # Get batch statistics
                total_students = Student.query.filter_by(batch_id=batch.id, is_deleted=0).count()
                
                # Get recent attendance
                recent_attendance = StudentAttendance.query.filter_by(batch_id=batch.id)\
                                                          .order_by(StudentAttendance.date.desc())\
                                                          .limit(5).all()
                
                trainer_batches.append({
                    'batch': batch,
                    'assignment': assignment,
                    'total_students': total_students,
                    'recent_attendance': recent_attendance
                })
        
        return render_template('attendance/trainer_batches.html',
                             trainer_batches=trainer_batches,
                             current_user=current_user)
        
    except Exception as e:
        flash(f'Error loading trainer batches: {str(e)}', 'error')
        return redirect(url_for('dashboard_bp.trainer_dashboard'))

# Helper Functions
def get_total_sessions(batch_id):
    """Calculate total sessions for a batch"""
    return StudentAttendance.query.filter_by(batch_id=batch_id)\
                                 .distinct(StudentAttendance.date)\
                                 .count()

def get_today_attendance(batch_id):
    """Get today's attendance summary using IST"""
    from utils.timezone_helper import get_current_ist_datetime
    ist_today = get_current_ist_datetime().date().strftime('%Y-%m-%d')
    attendance_records = StudentAttendance.query.filter_by(
        batch_id=batch_id,
        date=ist_today
    ).all()
    
    if not attendance_records:
        return None
    
    present_count = sum(1 for record in attendance_records if record.status == 'Present')
    total_count = len(attendance_records)
    
    return {
        'present_count': present_count,
        'total_count': total_count,
        'date': ist_today
    }

@attendance_bp.route('/analytics/batch/<int:batch_id>')
@login_required
def analytics(batch_id):
    """Display analytics dashboard for a batch"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Validate access
        if not has_batch_access(current_user, batch):
            flash('You do not have access to this batch', 'error')
            return redirect(url_for('batches.list_batches'))
        
        # Get analytics data
        analytics_data = StudentAttendance.get_batch_attendance_analytics(batch_id)
        
        return render_template('attendance/analytics.html',
                             batch=batch,
                             analytics=analytics_data)
        
    except Exception as e:
        flash(f'Error loading analytics: {str(e)}', 'error')
        return redirect(url_for('attendance.batch_attendance', batch_id=batch_id))

@attendance_bp.route('/export/analytics/batch/<int:batch_id>')
@login_required
def export_analytics(batch_id):
    """Export analytics data for a batch"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Validate access
        if not has_batch_access(current_user, batch):
            return jsonify({'error': 'Access denied'}), 403
        
        # Get analytics data
        analytics_data = StudentAttendance.get_batch_attendance_analytics(batch_id)
        
        # For now, return JSON - can be extended to Excel/PDF later
        return jsonify({
            'batch_name': batch.name,
            'analytics': analytics_data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
