from flask import Blueprint, render_template, jsonify
from init_db import db
from models.student_model import Student
from models.invoice_model import Invoice
from models.user_model import User
from models.batch_model import Batch
from models.course_model import Course
from models.lead_model import Lead
from models.batch_trainer_assignment_model import BatchTrainerAssignment
from models.student_attendance_model import StudentAttendance
from utils.timezone_helper import get_current_ist_datetime, get_current_ist_formatted, format_datetime_indian
from utils.lead_analytics import LeadAnalytics
from utils.auth import login_required, admin_required, role_required
import sqlalchemy
import os
dashboard_bp = Blueprint("dashboard_bp", __name__)

# 📊 JSON API for Dashboard metrics (AJAX use)
@dashboard_bp.route("/dashboard", methods=["GET"])
@login_required
def dashboard_metrics():
    total_students = Student.query.count()
    total_revenue = db.session.query(db.func.sum(Invoice.paid_amount)).scalar() or 0
    total_invoices = Invoice.query.count()
    total_batches = Batch.query.count()
    
    print(os.listdir('templates/dashboard'))
    return jsonify({
        "total_students": total_students,
        "total_revenue": total_revenue,
        "total_invoices": total_invoices,
        "total_batches": total_batches
    })

# 🖥️ Admin Dashboard Page
@dashboard_bp.route("/admin")
@login_required
@role_required(['admin', 'regional_manager'])
def admin_dashboard():
    from flask import session
    from utils.role_permissions import get_user_accessible_branches
    
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    # For regional managers, filter data by accessible branches
    if user_role == 'regional_manager':
        accessible_branch_ids = get_user_accessible_branches(user_id)
        
        if accessible_branch_ids:
            # Filter data to only show accessible branches
            total_students = Student.query.filter(
                Student.branch_id.in_(accessible_branch_ids),
                Student.is_deleted == 0
            ).count()
            
            total_courses = Course.query.filter_by(is_deleted=0).count()  # Courses are global
            
            # Revenue from accessible branches only
            total_revenue = db.session.query(db.func.sum(Invoice.paid_amount))\
                .join(Student, Invoice.student_id == Student.student_id)\
                .filter(Student.branch_id.in_(accessible_branch_ids)).scalar() or 0
                
            # Leads from accessible branches only  
            total_leads = Lead.query.filter(
                Lead.branch_id.in_(accessible_branch_ids),
                Lead.is_deleted == 0
            ).count()
        else:
            # No branch access
            total_students = total_courses = total_revenue = total_leads = 0
    else:
        # Admin or other roles see all data
        total_students = Student.query.filter_by(is_deleted=0).count()
        total_courses = Course.query.filter_by(is_deleted=0).count()
        total_revenue = db.session.query(db.func.sum(Invoice.paid_amount)).scalar() or 0
        total_leads = Lead.query.filter_by(is_deleted=0).count()

    print(os.listdir('templates/dashboard'))
    return render_template("dashboard/admin_dashboard.html",
                           total_students=total_students,
                           total_courses=total_courses,
                           total_revenue=int(total_revenue),
                           total_leads=total_leads)

# 🏢 Franchise Dashboard Page
@dashboard_bp.route("/franchise")
@login_required
@role_required(['franchise'])
def franchise_dashboard():
    from flask import session, request
    from models.branch_model import Branch
    from models.student_attendance_model import StudentAttendance
    from datetime import datetime, timedelta
    import sqlalchemy as sa
    
    # Get franchise owner's branch information
    user_branch_id = session.get("user_branch_id")
    branch_name = session.get("branch_name", "All Branches")
    attendance_range = request.args.get('attendance_range', 'week')
    
    # Calculate date ranges
    today = get_current_ist_datetime().date()
    if attendance_range == 'today':
        start_date = today
    elif attendance_range == 'week':
        start_date = today - timedelta(days=7)
    else:  # month
        start_date = today - timedelta(days=30)
    
    if user_branch_id:
        # Show specific branch statistics
        branch = Branch.query.get(user_branch_id)
        total_students = Student.query.filter_by(branch_id=user_branch_id, is_deleted=0).count()
        total_batches = Batch.query.filter_by(branch_id=user_branch_id, is_deleted=0).count()
        
        # Get branch-specific revenue
        branch_revenue = db.session.query(db.func.sum(Invoice.paid_amount))\
            .join(Student, Invoice.student_id == Student.student_id)\
            .filter(Student.branch_id == user_branch_id).scalar() or 0
        
        # Get recent enrollments
        recent_students = Student.query.filter_by(branch_id=user_branch_id, is_deleted=0)\
            .order_by(Student.admission_date.desc()).limit(5).all()
        
        # Get active batches for this branch
        active_batches = Batch.query.filter_by(
            branch_id=user_branch_id, 
            status='Active', 
            is_deleted=0
        ).all()
        
        # Calculate attendance statistics
        attendance_stats = {
            'today_rate': 0,
            'today_present': 0,
            'today_total': 0,
            'weekly_rate': 0,
            'at_risk_count': 0,
            'today_late': 0
        }
        
        active_batches_attendance = []
        
        if active_batches:
            # Today's attendance across all batches
            today_attendance = db.session.query(
                sa.func.count(StudentAttendance.id).label('total'),
                sa.func.sum(sa.case((StudentAttendance.status.in_(['Present', 'Late']), 1), else_=0)).label('present'),
                sa.func.sum(sa.case((StudentAttendance.status == 'Late', 1), else_=0)).label('late')
            ).join(Student, StudentAttendance.student_id == Student.student_id)\
             .filter(Student.branch_id == user_branch_id, 
                    StudentAttendance.date == today).first()
            
            if today_attendance and today_attendance.total:
                attendance_stats['today_total'] = today_attendance.total or 0
                attendance_stats['today_present'] = today_attendance.present or 0
                attendance_stats['today_late'] = today_attendance.late or 0
                attendance_stats['today_rate'] = (attendance_stats['today_present'] / attendance_stats['today_total']) * 100
            
            # Weekly average
            weekly_attendance = db.session.query(
                sa.func.count(StudentAttendance.id).label('total'),
                sa.func.sum(sa.case((StudentAttendance.status.in_(['Present', 'Late']), 1), else_=0)).label('present')
            ).join(Student, StudentAttendance.student_id == Student.student_id)\
             .filter(Student.branch_id == user_branch_id, 
                    StudentAttendance.date >= start_date).first()
            
            if weekly_attendance and weekly_attendance.total:
                attendance_stats['weekly_rate'] = (weekly_attendance.present / weekly_attendance.total) * 100
            
            # At-risk students (below 65% attendance)
            at_risk_students = db.session.query(Student.student_id).join(StudentAttendance)\
                .filter(Student.branch_id == user_branch_id, Student.is_deleted == 0)\
                .group_by(Student.student_id)\
                .having(
                    (sa.func.sum(sa.case((StudentAttendance.status.in_(['Present', 'Late']), 1), else_=0)) * 100.0 / 
                     sa.func.count(StudentAttendance.id)) < 65
                ).count()
            attendance_stats['at_risk_count'] = at_risk_students
            
            # Get attendance data for each active batch
            for batch in active_batches:
                batch_students = Student.query.filter_by(
                    batch_id=batch.id, is_deleted=0
                ).count()
                
                # Today's batch attendance
                today_batch_attendance = db.session.query(
                    sa.func.count(StudentAttendance.id).label('total'),
                    sa.func.sum(sa.case((StudentAttendance.status.in_(['Present', 'Late']), 1), else_=0)).label('present')
                ).join(Student, StudentAttendance.student_id == Student.student_id)\
                 .filter(Student.batch_id == batch.id, 
                        StudentAttendance.date == today).first()
                
                today_rate = 0
                today_present = 0
                if today_batch_attendance and today_batch_attendance.total:
                    today_present = today_batch_attendance.present or 0
                    today_rate = (today_present / today_batch_attendance.total) * 100
                
                # Weekly batch average
                weekly_batch_attendance = db.session.query(
                    sa.func.count(StudentAttendance.id).label('total'),
                    sa.func.sum(sa.case((StudentAttendance.status.in_(['Present', 'Late']), 1), else_=0)).label('present')
                ).join(Student, StudentAttendance.student_id == Student.student_id)\
                 .filter(Student.batch_id == batch.id, 
                        StudentAttendance.date >= start_date).first()
                
                weekly_rate = 0
                if weekly_batch_attendance and weekly_batch_attendance.total:
                    weekly_rate = (weekly_batch_attendance.present / weekly_batch_attendance.total) * 100
                
                active_batches_attendance.append({
                    'batch': batch,
                    'total_students': batch_students,
                    'today_attendance_rate': today_rate,
                    'today_present': today_present,
                    'weekly_avg_rate': weekly_rate
                })
        
    else:
        # System view for owners with multiple branches
        total_students = Student.query.filter_by(is_deleted=0).count()
        total_batches = Batch.query.filter_by(is_deleted=0).count()
        branch_revenue = db.session.query(db.func.sum(Invoice.paid_amount)).scalar() or 0
        recent_students = Student.query.filter_by(is_deleted=0)\
            .order_by(Student.admission_date.desc()).limit(5).all()
        branch = None
        
        # Default attendance stats for multi-branch view
        attendance_stats = {
            'today_rate': 0,
            'today_present': 0,
            'today_total': 0,
            'weekly_rate': 0,
            'at_risk_count': 0,
            'today_late': 0
        }
        active_batches_attendance = []
    
    total_courses = Course.query.filter_by(is_deleted=0).count()
    current_date = get_current_ist_formatted(include_time=False)
    
    return render_template("dashboard/franchise_dashboard.html",
                           branch=branch,
                           branch_name=branch_name,
                           total_students=total_students,
                           total_courses=total_courses,
                           total_batches=total_batches,
                           branch_revenue=int(branch_revenue),
                           recent_students=recent_students,
                           attendance_stats=attendance_stats,
                           active_batches_attendance=active_batches_attendance,
                           current_date=current_date)

# 👔 Branch Manager Dashboard Page
@dashboard_bp.route("/branch_manager")
@login_required
@role_required(['branch_manager'])
def branch_manager_dashboard():
    from flask import session
    from models.branch_model import Branch
    from models.installment_model import Installment
    from datetime import date, datetime
    
    # Get branch manager's branch information
    user_branch_id = session.get("user_branch_id")
    branch_name = session.get("branch_name", "Not Assigned")
    
    if user_branch_id:
        # Show specific branch statistics
        branch = Branch.query.get(user_branch_id)
        total_students = Student.query.filter_by(branch_id=user_branch_id, is_deleted=0).count()
        total_batches = Batch.query.filter_by(branch_id=user_branch_id, is_deleted=0).count()
        
        # Get branch-specific revenue
        branch_revenue = db.session.query(db.func.sum(Invoice.paid_amount))\
            .join(Student, Invoice.student_id == Student.student_id)\
            .filter(Student.branch_id == user_branch_id).scalar() or 0
        
        # Get invoice statistics
        total_invoices = db.session.query(db.func.count(Invoice.id))\
            .join(Student, Invoice.student_id == Student.student_id)\
            .filter(Student.branch_id == user_branch_id, Invoice.is_deleted == 0).scalar() or 0
            
        pending_amount = db.session.query(db.func.sum(Invoice.due_amount))\
            .join(Student, Invoice.student_id == Student.student_id)\
            .filter(Student.branch_id == user_branch_id, Invoice.is_deleted == 0).scalar() or 0
        
        # Get installments due today
        today = get_current_ist_datetime().date()
        due_today_count = db.session.query(db.func.count(Installment.id))\
            .join(Invoice, Installment.invoice_id == Invoice.id)\
            .join(Student, Invoice.student_id == Student.student_id)\
            .filter(
                Student.branch_id == user_branch_id,
                Installment.due_date == today,
                Installment.status.in_(['pending', 'partial'])
            ).scalar() or 0
        
        # Get overdue installments count
        overdue_count = db.session.query(db.func.count(Installment.id))\
            .join(Invoice, Installment.invoice_id == Invoice.id)\
            .join(Student, Invoice.student_id == Student.student_id)\
            .filter(
                Student.branch_id == user_branch_id,
                Installment.due_date < today,
                Installment.status.in_(['pending', 'partial'])
            ).scalar() or 0
        
        # Get recent enrollments (last 10 students)
        recent_students = Student.query.filter_by(branch_id=user_branch_id, is_deleted=0)\
            .order_by(Student.admission_date.desc()).limit(10).all()
        
        # Get active batches for this branch (only Active status batches)
        active_batches = Batch.query.filter_by(
            branch_id=user_branch_id, 
            is_deleted=0, 
            status='Active'
        ).all()
        
        # Get leads/inquiries for this branch (if leads table has branch association)
        from models.lead_model import Lead
        recent_leads = Lead.query.filter_by(is_deleted=0)\
            .order_by(Lead.created_at.desc()).limit(5).all()
            
    else:
        # No branch assigned
        branch = None
        total_students = 0
        total_batches = 0
        branch_revenue = 0
        total_invoices = 0
        pending_amount = 0
        due_today_count = 0
        overdue_count = 0
        recent_students = []
        active_batches = []
        recent_leads = []
    
    total_courses = Course.query.filter_by(is_deleted=0).count()
    
    return render_template("dashboard/branch_manager_dashboard.html",
                           branch=branch,
                           branch_name=branch_name,
                           total_students=total_students,
                           total_courses=total_courses,
                           total_batches=total_batches,
                           total_invoices=total_invoices,
                           branch_revenue=int(branch_revenue),
                           pending_amount=int(pending_amount),
                           due_today_count=due_today_count,
                           overdue_count=overdue_count,
                           recent_students=recent_students,
                           active_batches=active_batches,
                           recent_leads=recent_leads)

# �‍💼 Staff Dashboard Page
@dashboard_bp.route("/staff")
@login_required
@role_required(['staff'])
def staff_dashboard():
    from flask import session
    from models.branch_model import Branch
    from models.installment_model import Installment
    from datetime import date, datetime
    
    try:
        # Get staff member's branch information
        user_branch_id = session.get("user_branch_id")
        branch_name = session.get("branch_name", "Not Assigned")
        
        if user_branch_id:
            # Show specific branch statistics that staff can see
            branch = Branch.query.get(user_branch_id)
            total_students = Student.query.filter_by(branch_id=user_branch_id, is_deleted=0).count()
            total_batches = Batch.query.filter_by(branch_id=user_branch_id, is_deleted=0).count()
            
            # Get branch-specific revenue (staff can view but not modify)
            branch_revenue = db.session.query(db.func.sum(Invoice.paid_amount))\
                .join(Student, Invoice.student_id == Student.student_id)\
                .filter(Student.branch_id == user_branch_id).scalar() or 0
            
            # Get invoice statistics
            total_invoices = db.session.query(db.func.count(Invoice.id))\
                .join(Student, Invoice.student_id == Student.student_id)\
                .filter(Student.branch_id == user_branch_id, Invoice.is_deleted == 0).scalar() or 0
                
            pending_amount = db.session.query(db.func.sum(Invoice.due_amount))\
                .join(Student, Invoice.student_id == Student.student_id)\
                .filter(Student.branch_id == user_branch_id, Invoice.is_deleted == 0).scalar() or 0
            
            # Get installments due today
            today = get_current_ist_datetime().date()
            due_today_count = db.session.query(db.func.count(Installment.id))\
                .join(Invoice, Installment.invoice_id == Invoice.id)\
                .join(Student, Invoice.student_id == Student.student_id)\
                .filter(
                    Student.branch_id == user_branch_id,
                    Installment.due_date == today,
                    Installment.status.in_(['pending', 'partial'])
                ).scalar() or 0
            
            # Get overdue installments count
            overdue_count = db.session.query(db.func.count(Installment.id))\
                .join(Invoice, Installment.invoice_id == Invoice.id)\
                .join(Student, Invoice.student_id == Student.student_id)\
                .filter(
                    Student.branch_id == user_branch_id,
                    Installment.due_date < today,
                    Installment.status.in_(['pending', 'partial'])
                ).scalar() or 0
            
            # Get recent enrollments (last 10 students)
            recent_students = Student.query.filter_by(branch_id=user_branch_id, is_deleted=0)\
                .order_by(Student.admission_date.desc()).limit(10).all()
            
            # Get active batches for this branch
            active_batches = Batch.query.filter_by(
                branch_id=user_branch_id, 
                is_deleted=0, 
                status='Active'
            ).all()
            
            # Get recent leads (staff can view leads)
            recent_leads = Lead.query.filter_by(is_deleted=0)\
                .order_by(Lead.created_at.desc()).limit(5).all()
                
        else:
            # No branch assigned
            branch = None
            total_students = 0
            total_batches = 0
            branch_revenue = 0
            total_invoices = 0
            pending_amount = 0
            due_today_count = 0
            overdue_count = 0
            recent_students = []
            active_batches = []
            recent_leads = []
        
        total_courses = Course.query.filter_by(is_deleted=0).count()
        
        return render_template("dashboard/staff_dashboard.html",
                               branch=branch,
                               branch_name=branch_name,
                               total_students=total_students,
                               total_courses=total_courses,
                               total_batches=total_batches,
                               total_invoices=total_invoices,
                               branch_revenue=int(branch_revenue),
                               pending_amount=int(pending_amount),
                               due_today_count=due_today_count,
                               overdue_count=overdue_count,
                               recent_students=recent_students,
                               active_batches=active_batches,
                               recent_leads=recent_leads)
    except Exception as e:
        # For debugging - return a simple response with error info
        return f"<h1>Error in Staff Dashboard</h1><p>{str(e)}</p><p>Please check the logs for more details.</p>"

# 👨‍🏫 Trainer Dashboard Page
@dashboard_bp.route("/trainer")
@login_required
@role_required(['trainer'])
def trainer_dashboard():
    from flask import session
    from models.branch_model import Branch
    from datetime import date
    
    # Get current trainer's ID
    current_user_id = session.get("user_id")
    
    # Get trainer's branch information
    user_branch_id = session.get("user_branch_id")
    branch_name = session.get("branch_name", "Not Assigned")
    
    # For trainers, we should check assignments regardless of branch
    if current_user_id:
        # Show specific branch statistics if available
        branch = Branch.query.get(user_branch_id) if user_branch_id else None
        
        # Get batches assigned to this specific trainer
        trainer_assignments = BatchTrainerAssignment.get_trainer_batches(current_user_id, active_only=True)
        trainer_batches = [assignment.batch for assignment in trainer_assignments if assignment.batch and not assignment.batch.is_deleted]
        
        # Get students from trainer's assigned batches
        trainer_students = []
        total_students = 0
        attendance_summary = []
        
        for batch in trainer_batches:
            batch_students = Student.query.filter_by(batch_id=batch.id, is_deleted=0).all()
            trainer_students.extend(batch_students)
            total_students += len(batch_students)
            
            # Get today's attendance for this batch
            today = get_current_ist_datetime().strftime('%Y-%m-%d')
            today_attendance = StudentAttendance.query.filter_by(
                batch_id=batch.id,
                date=today
            ).all()
            
            present_today = sum(1 for att in today_attendance if att.status == 'Present')
            total_today = len(today_attendance)
            
            attendance_summary.append({
                'batch_id': batch.id,
                'batch_name': batch.name,
                'course_name': batch.course_name,
                'total_students': len(batch_students),
                'present_today': present_today,
                'total_today': total_today,
                'attendance_marked': total_today > 0
            })
        
        # Get recent enrollments in trainer's batches
        batch_ids = [batch.id for batch in trainer_batches]
        if batch_ids:
            recent_students = Student.query.filter(
                Student.batch_id.in_(batch_ids),
                Student.is_deleted == 0
            ).order_by(Student.admission_date.desc()).limit(8).all()
        else:
            recent_students = []
            
        # Calculate overall attendance rate for trainer
        total_attendance_records = 0
        present_records = 0
        
        for batch in trainer_batches:
            batch_attendance = StudentAttendance.query.filter_by(batch_id=batch.id).all()
            total_attendance_records += len(batch_attendance)
            present_records += sum(1 for att in batch_attendance if att.status == 'Present')
        
        # Calculate attendance rate
        attendance_rate = 0
        if total_attendance_records > 0:
            attendance_rate = round((present_records / total_attendance_records) * 100, 1)
        
        # Today's classes (trainer's assigned batches)
        today_classes = []
        for batch in trainer_batches:
            students_count = Student.query.filter_by(batch_id=batch.id, is_deleted=0).count()
            today_classes.append({
                'batch_id': batch.id,
                'batch_name': batch.name,
                'course_name': batch.course_name,
                'timing': batch.timing or '10:00 AM - 12:00 PM',
                'students_count': students_count,
                'can_mark_attendance': True
            })
            
    else:
        # No branch assigned or no user
        branch = None
        trainer_batches = []
        trainer_students = []
        total_students = 0
        recent_students = []
        today_classes = []
        attendance_summary = []
        attendance_rate = 0
    
    total_batches = len(trainer_batches)
    
    return render_template("dashboard/trainer_dashboard.html",
                           branch=branch,
                           branch_name=branch_name,
                           total_students=total_students,
                           total_batches=total_batches,
                           trainer_batches=trainer_batches,
                           trainer_students=trainer_students,
                           recent_students=recent_students,
                           today_classes=today_classes,
                           attendance_summary=attendance_summary,
                           attendance_rate=attendance_rate)

# 👨‍🎓 Student Dashboard Page
@dashboard_bp.route("/student")
@login_required
@role_required(['student'])
def student_dashboard():
    from flask import session
    from models.branch_model import Branch
    from models.payment_model import Payment
    
    # Get student's information from session or username
    user_id = session.get("user_id")
    username = session.get("username")
    
    if not user_id or not username:
        from flask import flash, redirect, url_for
        flash("❌ Please login to access your dashboard", "warning")
        return redirect(url_for("auth.login"))
    
    # Try to find student by username (assuming username matches student_id)
    student = Student.query.filter_by(student_id=username, is_deleted=0).first()
    
    if not student:
        from flask import flash
        flash("❌ Student record not found. Please contact administration.", "danger")
        return render_template("dashboard/student_dashboard.html",
                             student=None,
                             error_message="Student record not found")
    
    # Get student's branch information
    branch = None
    if student.branch_id:
        branch = Branch.query.get(student.branch_id)
    
    # Get student's batch information
    batch = None
    batch_mates = []
    if student.batch_id:
        batch = Batch.query.get(student.batch_id)
        if batch:
            # Get other students in the same batch (excluding current student)
            batch_mates = Student.query.filter_by(
                batch_id=student.batch_id, 
                is_deleted=0
            ).filter(Student.student_id != student.student_id).all()
    
    # Get student's course information
    course = None
    if batch and batch.course_name:
        course = Course.query.filter_by(course_name=batch.course_name).first()
    
    # Get financial information
    student_invoices = Invoice.query.filter_by(
        student_id=student.student_id, 
        is_deleted=0
    ).order_by(Invoice.created_at.desc()).all()
    
    # Calculate totals
    total_amount = sum(inv.total_amount for inv in student_invoices)
    total_paid = sum(inv.paid_amount for inv in student_invoices)
    total_due = sum(inv.due_amount for inv in student_invoices)
    
    # Get recent payments
    recent_payments = []
    for invoice in student_invoices:
        payments = Payment.query.filter_by(
            invoice_id=invoice.id
        ).order_by(Payment.paid_on.desc()).limit(5).all()
        recent_payments.extend(payments)
    
    # Sort recent payments by date
    recent_payments.sort(key=lambda x: x.paid_on, reverse=True)
    recent_payments = recent_payments[:5]  # Keep only last 5 payments
    
    # Get upcoming classes (mock data for now)
    # TODO: Implement proper class schedule system
    upcoming_classes = []
    if batch:
        upcoming_classes = [
            {
                'subject': course.course_name if course else 'Course',
                'date': 'Today',
                'time': batch.timing or '10:00 AM - 12:00 PM',
                'trainer': 'Instructor',  # TODO: Add trainer info to batch
                'location': branch.branch_name if branch else 'Campus'
            },
            {
                'subject': course.course_name if course else 'Course',
                'date': 'Tomorrow',
                'time': batch.timing or '10:00 AM - 12:00 PM',
                'trainer': 'Instructor',
                'location': branch.branch_name if branch else 'Campus'
            }
        ]
    
    return render_template("dashboard/student_dashboard.html",
                           student=student,
                           branch=branch,
                           batch=batch,
                           course=course,
                           batch_mates=batch_mates,
                           student_invoices=student_invoices,
                           total_amount=total_amount,
                           total_paid=total_paid,
                           total_due=total_due,
                           recent_payments=recent_payments,
                           upcoming_classes=upcoming_classes)

# 👨‍👩‍👧‍👦 Parent Dashboard Page
@dashboard_bp.route("/parent")
@login_required
@role_required(['parent'])
def parent_dashboard():
    from flask import session
    from models.branch_model import Branch
    
    # Get parent's information from session
    user_id = session.get("user_id")
    username = session.get("username")
    
    if not user_id or not username:
        from flask import flash, redirect, url_for
        flash("❌ Please login to access your dashboard", "warning")
        return redirect(url_for("auth.login"))
    
    # For now, we'll show a general parent dashboard
    # TODO: Implement parent-child relationship to show specific child's data
    
    # Get all students (we can later filter by parent-child relationship)
    recent_students = Student.query.filter_by(is_deleted=0)\
        .order_by(Student.admission_date.desc()).limit(10).all()
    
    # Mock data for parent dashboard
    children_enrolled = 1  # TODO: Get actual count from parent-child relationship
    total_fees_paid = 15000  # TODO: Calculate from child's payments
    pending_fees = 10000   # TODO: Calculate from child's invoices
    
    # Get recent activities (mock data for now)
    recent_activities = [
        {
            'type': 'payment',
            'description': 'Fee payment received for Python Programming',
            'date': 'Today',
            'amount': '₹5,000'
        },
        {
            'type': 'attendance', 
            'description': 'Attendance marked for today\'s class',
            'date': 'Today',
            'status': 'Present'
        },
        {
            'type': 'assignment',
            'description': 'Assignment submitted - Python Basics',
            'date': 'Yesterday',
            'grade': 'A'
        }
    ]
    
    # Upcoming events for child
    upcoming_events = [
        {
            'title': 'Python Programming Class',
            'date': 'Today',
            'time': '10:00 AM - 12:00 PM',
            'type': 'class'
        },
        {
            'title': 'Monthly Assessment',
            'date': 'Friday',
            'time': '2:00 PM - 4:00 PM', 
            'type': 'exam'
        },
        {
            'title': 'Parent-Teacher Meeting',
            'date': 'Next Monday',
            'time': '11:00 AM - 12:00 PM',
            'type': 'meeting'
        }
    ]
    
    return render_template("dashboard/parent_dashboard.html",
                           children_enrolled=children_enrolled,
                           total_fees_paid=total_fees_paid,
                           pending_fees=pending_fees,
                           recent_students=recent_students,
                           recent_activities=recent_activities,
                           upcoming_events=upcoming_events)

# 📈 Lead Analytics Dashboard
@dashboard_bp.route("/lead-analytics")
@login_required
@role_required(['admin', 'branch_manager', 'franchise_owner'])
def lead_analytics():
    """
    Lead analytics dashboard showing impact of auto-lead creation
    """
    from flask import session, request
    from datetime import datetime, timedelta
    
    user_id = session.get('user_id')
    user_role = session.get('role')
    
    # Get date range from query params (default to last 30 days)
    days_back = int(request.args.get('days', 30))
    branch_id = request.args.get('branch_id', type=int)
    
    # For non-admin users, limit to their branch
    if user_role in ['franchise', 'branch_manager'] and not branch_id:
        branch_id = session.get('user_branch_id')
    
    # Get analytics data
    source_stats = LeadAnalytics.get_lead_source_stats(branch_id=branch_id)
    conversion_funnel = LeadAnalytics.get_conversion_funnel(branch_id=branch_id)
    recovery_stats = LeadAnalytics.get_missed_lead_recovery_stats(branch_id=branch_id, days_back=days_back)
    
    # Get recent auto-created leads
    recent_auto_leads = db.session.query(
        Student.student_id,
        Student.full_name,
        Student.admission_date,
        Student.lead_source,
        Student.course_name,
        Lead.lead_sl_number
    ).join(
        Lead, Student.auto_created_lead_id == Lead.id
    ).filter(
        Student.auto_created_lead == True,
        Student.admission_date >= datetime.now() - timedelta(days=days_back)
    )
    
    if branch_id:
        recent_auto_leads = recent_auto_leads.filter(Student.branch_id == branch_id)
    
    recent_auto_leads = recent_auto_leads.order_by(Student.admission_date.desc()).limit(10).all()
    
    # Get branches for filter (if admin)
    branches = None
    if user_role in ['corporate_admin', 'regional_manager']:
        from models.branch_model import Branch
        branches = Branch.query.all()
    
    return render_template("dashboard/lead_analytics.html",
                           source_stats=source_stats,
                           conversion_funnel=conversion_funnel,
                           recovery_stats=recovery_stats,
                           recent_auto_leads=recent_auto_leads,
                           branches=branches,
                           selected_branch_id=branch_id,
                           days_back=days_back)
