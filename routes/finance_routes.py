from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from init_db import db
from models.payment_model import Payment
from models.installment_model import Installment
from models.invoice_model import Invoice
from models.student_model import Student
from models.batch_model import Batch
from models.branch_model import Branch
from models.user_model import User
from utils.auth import login_required, role_required
from utils.role_permissions import (
    get_finance_branch_filter, check_module_permission, 
    can_export_financial_data, can_modify_financial_data,
    get_user_accessible_branches
)
from utils.pdf_utils import generate_receipt_pdf, generate_financial_report, generate_financial_report_excel
from utils.timezone_helper import get_current_ist_datetime, get_current_ist_formatted, format_datetime_indian
from utils.error_handler import handle_finance_error
from datetime import datetime, timezone, timedelta, date
from sqlalchemy import func, desc, asc
from sqlalchemy.orm import joinedload
import json

finance_bp = Blueprint('finance', __name__, url_prefix='/finance')

@finance_bp.route('/dashboard')
@login_required
@role_required(['admin', 'regional_manager', 'manager', 'franchise', 'branch_manager', 'staff'])
def dashboard():
    """Finance dashboard with key metrics and charts"""
    try:
        current_user_id = session.get('user_id')
        user = User.query.get(current_user_id)
        
        # Check finance module access
        if not check_module_permission(current_user_id, 'finance', 'read'):
            flash('Access denied: No finance module access', 'error')
            # Redirect to appropriate dashboard based on role
            if user.role == 'franchise':
                return redirect(url_for('dashboard_bp.franchise_dashboard'))
            elif user.role in ['admin', 'regional_manager']:
                return redirect(url_for('dashboard_bp.admin_dashboard'))
            elif user.role == 'branch_manager':
                return redirect(url_for('dashboard_bp.branch_manager_dashboard'))
            elif user.role == 'staff':
                return redirect(url_for('dashboard_bp.staff_dashboard'))
            else:
                return redirect(url_for('dashboard_bp.admin_dashboard'))
        
        # Get branch filter using enhanced role system
        branch_filter = get_finance_branch_filter(current_user_id)
        
        if branch_filter is False:
            flash('No branch access configured', 'error')
            # Redirect to appropriate dashboard based on role
            if user.role == 'franchise':
                return redirect(url_for('dashboard_bp.franchise_dashboard'))
            elif user.role in ['admin', 'regional_manager']:
                return redirect(url_for('dashboard_bp.admin_dashboard'))
            elif user.role == 'branch_manager':
                return redirect(url_for('dashboard_bp.branch_manager_dashboard'))
            elif user.role == 'staff':
                return redirect(url_for('dashboard_bp.staff_dashboard'))
            else:
                return redirect(url_for('dashboard_bp.admin_dashboard'))
        
        # Current month start
        today = get_current_ist_datetime()
        current_month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Revenue Metrics
        total_revenue = db.session.query(func.sum(Payment.amount))\
            .join(Invoice).join(Student)\
            .filter(branch_filter).scalar() or 0
            
        monthly_revenue = db.session.query(func.sum(Payment.amount))\
            .join(Invoice).join(Student)\
            .filter(branch_filter)\
            .filter(Payment.paid_on >= current_month_start).scalar() or 0
            
        # Outstanding amounts - Calculate total invoiced amount minus total paid amount
        total_invoiced = db.session.query(func.sum(Invoice.total_amount))\
            .join(Student)\
            .filter(branch_filter).scalar() or 0
            
        total_paid = db.session.query(func.sum(Payment.amount))\
            .join(Invoice).join(Student)\
            .filter(branch_filter).scalar() or 0
            
        total_outstanding = total_invoiced - total_paid
        
        # Total sales (total invoiced amount including discounts)
        total_sales = total_invoiced
            
        # Installment metrics - count overdue installments that are not paid
        pending_installments = db.session.query(func.count(Installment.id))\
            .join(Invoice).join(Student)\
            .filter(branch_filter)\
            .filter(Installment.due_date <= today)\
            .filter(Installment.is_paid == False).scalar() or 0
            
        # Recent payments (last 10) - Load with relationships
        recent_payments = db.session.query(Payment)\
            .options(joinedload(Payment.invoice).joinedload(Invoice.student))\
            .join(Invoice).join(Student)\
            .filter(branch_filter)\
            .order_by(desc(Payment.paid_on))\
            .limit(10).all()
            
        # Monthly revenue trend (last 6 months)
        monthly_trend = []
        for i in range(6):
            month_start = (current_month_start - timedelta(days=32*i)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
            
            revenue = db.session.query(func.sum(Payment.amount))\
                .join(Invoice).join(Student)\
                .filter(branch_filter)\
                .filter(Payment.paid_on >= month_start)\
                .filter(Payment.paid_on <= month_end).scalar() or 0
                
            monthly_trend.append({
                'month': month_start.strftime('%b %Y'),
                'revenue': float(revenue)
            })
        
        monthly_trend.reverse()  # Oldest to newest
        
        # Payment method distribution
        payment_methods = db.session.query(Payment.mode, func.sum(Payment.amount))\
            .join(Invoice).join(Student)\
            .filter(branch_filter)\
            .group_by(Payment.mode).all()
            
        method_data = [{'method': method, 'amount': float(amount)} for method, amount in payment_methods]
        
        # Get user's accessible branches for display
        accessible_branches = get_user_accessible_branches(current_user_id)
        branch_names = []
        if accessible_branches:
            branches = Branch.query.filter(Branch.id.in_(accessible_branches)).all()
            branch_names = [branch.branch_name for branch in branches]
        
        return render_template('finance/dashboard.html',
                             total_revenue=total_revenue,
                             monthly_revenue=monthly_revenue,
                             total_sales=total_sales,
                             total_outstanding=total_outstanding,
                             pending_installments=pending_installments,
                             recent_payments=recent_payments,
                             monthly_trend=monthly_trend,
                             payment_methods=method_data,
                             overdue_amount=0,  # Simplified for now
                             user_role=user.role,
                             accessible_branches=branch_names,
                             can_export=can_export_financial_data(current_user_id))
                             
    except Exception as e:
        # Use the new error handler instead of role-based redirects
        return handle_finance_error(str(e), "Loading Finance Dashboard")

@finance_bp.route('/payments')
@login_required
@role_required(['admin', 'regional_manager', 'manager', 'franchise', 'branch_manager', 'staff'])
def payments_list():
    """List all payments with filtering and search"""
    try:
        current_user_id = session.get('user_id')
        user = User.query.get(current_user_id)
        
        # Check finance module access
        if not check_module_permission(current_user_id, 'finance', 'read'):
            flash('Access denied: No finance module access', 'error')
            return redirect(url_for('finance.dashboard'))
        
        # Base query - use direct invoice relationship
        query = db.session.query(Payment)\
            .join(Invoice, Payment.invoice_id == Invoice.id)\
            .join(Student, Invoice.student_id == Student.student_id)\
            .options(
                joinedload(Payment.invoice)
                .joinedload(Invoice.student)
            )
        
        # Apply enhanced role-based filtering
        branch_filter = get_finance_branch_filter(current_user_id)
        if branch_filter is not True:  # True means no filter (admin access)
            query = query.filter(branch_filter)
        
        # Search and filters
        search = request.args.get('search', '')
        payment_mode = request.args.get('mode', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        
        if search:
            query = query.filter(
                db.or_(
                    Student.full_name.contains(search),
                    Student.mobile.contains(search),
                    Student.email.contains(search),
                    Payment.utr_number.contains(search)
                )
            )
        
        if payment_mode:
            query = query.filter(Payment.mode == payment_mode)
        
        # Branch filter    
        branch_id = request.args.get('branch_id', '')
        if branch_id:
            query = query.filter(Student.branch_id == branch_id)
            
        if date_from:
            query = query.filter(Payment.paid_on >= datetime.strptime(date_from, '%Y-%m-%d'))
            
        if date_to:
            query = query.filter(Payment.paid_on <= datetime.strptime(date_to, '%Y-%m-%d'))
        
        # Pagination
        page = request.args.get('page', 1, type=int)
        payments = query.order_by(desc(Payment.paid_on)).paginate(
            page=page, per_page=20, error_out=False
        )
        
        # Payment modes for filter dropdown
        payment_modes = db.session.query(Payment.mode).distinct().all()
        modes = [mode[0] for mode in payment_modes]
        
        # Branches for filter dropdown - only show accessible branches
        accessible_branch_ids = get_user_accessible_branches(current_user_id)
        if accessible_branch_ids:
            branches = Branch.query.filter(Branch.id.in_(accessible_branch_ids)).all()
        else:
            branches = Branch.query.all() if user.role == 'admin' else []
        
        # Calculate statistics based on the filtered query (before pagination)
        total_amount = query.with_entities(func.sum(Payment.amount)).scalar() or 0
        
        # Today's collection (unfiltered)
        today = get_current_ist_datetime().date()
        today_collection = db.session.query(func.sum(Payment.amount)).filter(
            func.date(Payment.paid_on) == today
        ).scalar() or 0
        
        # This month's collection (unfiltered)
        month_start = date(today.year, today.month, 1)
        month_collection = db.session.query(func.sum(Payment.amount)).filter(
            Payment.paid_on >= month_start
        ).scalar() or 0
        
        return render_template('finance/payments_list.html',
                             payments=payments,
                             modes=modes,
                             branches=branches,
                             search=search,
                             payment_mode=payment_mode,
                             date_from=date_from,
                             date_to=date_to,
                             total_amount=total_amount,
                             today_collection=today_collection,
                             month_collection=month_collection,
                             user_role=user.role,
                             can_export=can_export_financial_data(current_user_id),
                             can_modify=can_modify_financial_data(current_user_id))
                             
    except Exception as e:
        return handle_finance_error(str(e), "Loading Payments List")

@finance_bp.route('/collect-payment/<int:student_id>')
@login_required
@role_required(['admin', 'manager', 'franchise'])
def collect_payment_form(student_id):
    """Show payment collection form for a student"""
    try:
        current_user_id = session.get('user_id')
        user = User.query.get(current_user_id)
        
        student = Student.query.get_or_404(student_id)
        
        # Check branch access for franchise users
        if user.role == 'franchise' and student.batch.branch_id != user.branch_id:
            flash('Access denied to student from different branch', 'error')
            return redirect(url_for('finance.dashboard'))
        
        # Get pending invoices and installments
        pending_invoices = Invoice.query.filter_by(student_id=student_id).all()
        pending_installments = db.session.query(Installment)\
            .join(Invoice)\
            .filter(Invoice.student_id == student_id)\
            .filter(Installment.is_paid == False).all()
        
        return render_template('finance/collect_payment.html',
                             student=student,
                             pending_invoices=pending_invoices,
                             pending_installments=pending_installments)
                             
    except Exception as e:
        return handle_finance_error(str(e), "Loading Payment Collection Form")

@finance_bp.route('/collect-payment', methods=['POST'])
@login_required
@role_required(['admin', 'regional_manager', 'manager', 'franchise'])
def process_payment():
    """Process a new payment"""
    try:
        current_user_id = session.get('user_id')
        
        # Get form data
        invoice_id = request.form.get('invoice_id', type=int)
        installment_id = request.form.get('installment_id', type=int)
        amount = request.form.get('amount', type=float)
        payment_mode = request.form.get('payment_mode', '')
        utr_number = request.form.get('utr_number', '')
        notes = request.form.get('notes', '')
        discount_amount = request.form.get('discount_amount', type=float) or 0.0
        
        # Validate required fields
        if not amount or amount <= 0:
            flash('Invalid payment amount', 'error')
            return redirect(request.referrer)
            
        if not payment_mode:
            flash('Payment mode is required', 'error')
            return redirect(request.referrer)
        
        # Create payment record
        payment = Payment(
            invoice_id=invoice_id if invoice_id else None,
            installment_id=installment_id if installment_id else None,
            amount=amount,
            mode=payment_mode,
            utr_number=utr_number,
            notes=notes,
            discount_amount=discount_amount,
            paid_on=get_current_ist_datetime()
        )
        
        db.session.add(payment)
        
        # Update installment if applicable
        if installment_id:
            installment = Installment.query.get(installment_id)
            if installment:
                installment.is_paid = True
                installment.payment_date = get_current_ist_datetime()
        
        db.session.commit()
        
        flash('Payment recorded successfully', 'success')
        
        # Generate receipt if requested
        if request.form.get('generate_receipt'):
            return redirect(url_for('finance.generate_receipt', payment_id=payment.id))
        
        return redirect(url_for('finance.payments_list'))
        
    except Exception as e:
        db.session.rollback()
        return handle_finance_error(str(e), "Processing Payment")

@finance_bp.route('/installments')
@login_required
@role_required(['admin', 'regional_manager', 'manager', 'franchise'])
def installments_list():
    """List installments with status tracking"""
    try:
        current_user_id = session.get('user_id')
        user = User.query.get(current_user_id)
        
        # Get branch filter for role-based access
        branch_filter = get_finance_branch_filter(current_user_id)
        
        if branch_filter is False:
            flash('No branch access configured', 'error')
            return redirect(url_for('finance.dashboard'))
        
        # Base query with branch filtering
        query = db.session.query(Installment)\
            .join(Invoice).join(Student)\
            .filter(branch_filter)
        
        # Status filter
        status_filter = request.args.get('status', '')
        today = get_current_ist_datetime().date()
        
        if status_filter == 'pending':
            query = query.filter(Installment.is_paid == False)
        elif status_filter == 'overdue':
            query = query.filter(
                Installment.due_date < today,
                Installment.is_paid == False
            )
        elif status_filter == 'paid':
            query = query.filter(Installment.is_paid == True)
        
        # Additional filters
        search = request.args.get('search', '')
        if search:
            query = query.filter(
                (Student.full_name.ilike(f'%{search}%')) |
                (Student.student_id.ilike(f'%{search}%'))
            )
        
        branch_id = request.args.get('branch_id', '')
        if branch_id:
            query = query.filter(Student.branch_id == branch_id)
        
        course = request.args.get('course', '')
        if course:
            query = query.filter(Student.course_name.ilike(f'%{course}%'))
        
        # Date filters
        due_from = request.args.get('due_from', '')
        if due_from:
            try:
                due_from_date = datetime.strptime(due_from, '%Y-%m-%d').date()
                query = query.filter(Installment.due_date >= due_from_date)
            except ValueError:
                pass
        
        due_to = request.args.get('due_to', '')
        if due_to:
            try:
                due_to_date = datetime.strptime(due_to, '%Y-%m-%d').date()
                query = query.filter(Installment.due_date <= due_to_date)
            except ValueError:
                pass
        
        # Calculate statistics with branch filtering
        all_installments = db.session.query(Installment).join(Invoice).join(Student)\
            .filter(branch_filter)
        
        pending_installments = all_installments.filter(Installment.is_paid == False)
        overdue_installments = all_installments.filter(
            Installment.due_date < today,
            Installment.is_paid == False
        )
        paid_installments = all_installments.filter(Installment.is_paid == True)
        
        # Count and sum calculations
        pending_count = pending_installments.count()
        pending_amount = sum([inst.balance_amount or inst.amount for inst in pending_installments])
        
        overdue_count = overdue_installments.count()
        overdue_amount = sum([inst.balance_amount or inst.amount for inst in overdue_installments])
        
        paid_count = paid_installments.count()
        paid_amount = sum([inst.paid_amount or 0 for inst in paid_installments])
        
        total_count = all_installments.count()
        total_amount = sum([inst.amount for inst in all_installments])
        
        # Get branches for filter dropdown with role-based filtering
        if user.role == 'admin':
            branches = Branch.query.all()
        elif user.role == 'regional_manager':
            # Get accessible branches for regional manager
            accessible_branch_ids = get_user_accessible_branches(current_user_id)
            if accessible_branch_ids:
                branches = Branch.query.filter(Branch.id.in_(accessible_branch_ids)).all()
            else:
                branches = []
        elif user.role == 'franchise':
            branches = Branch.query.filter_by(id=user.branch_id).all()
        else:
            branches = []
        
        # Pagination
        page = request.args.get('page', 1, type=int)
        installments = query.order_by(asc(Installment.due_date)).paginate(
            page=page, per_page=20, error_out=False
        )
        
        return render_template('finance/installments_list.html',
                             installments=installments,
                             status_filter=status_filter,
                             today=today,
                             branches=branches,
                             pending_count=pending_count,
                             pending_amount=pending_amount,
                             overdue_count=overdue_count,
                             overdue_amount=overdue_amount,
                             paid_count=paid_count,
                             paid_amount=paid_amount,
                             total_count=total_count,
                             total_amount=total_amount,
                             pagination=installments)
                             
    except Exception as e:
        flash(f'Error loading installments: {str(e)}', 'error')
        return redirect(url_for('finance.dashboard'))

@finance_bp.route('/receipt/<int:payment_id>')
@login_required
@role_required(['admin', 'regional_manager', 'manager', 'franchise'])
def generate_receipt(payment_id):
    """Generate PDF receipt for a payment"""
    try:
        payment = Payment.query.get_or_404(payment_id)
        
        # Check access permissions
        current_user_id = session.get('user_id')
        user = User.query.get(current_user_id)
        
        if user.role == 'franchise':
            if payment.invoice and payment.invoice.student:
                student = payment.invoice.student
                # Check if student has batch and branch info for access control
                if hasattr(student, 'batch') and student.batch and student.batch.branch_id != user.branch_id:
                    flash('Access denied', 'error')
                    return redirect(url_for('finance.dashboard'))
        
        # Generate PDF
        pdf_path = generate_receipt_pdf(payment)
        
        # Return the PDF file directly for download
        from flask import send_file
        return send_file(pdf_path, as_attachment=True, download_name=f"receipt_{payment.id}.pdf")
                             
    except Exception as e:
        flash(f'Error generating receipt: {str(e)}', 'error')
        return redirect(url_for('finance.payments_list'))

@finance_bp.route('/reports')
@login_required
@role_required(['admin', 'regional_manager', 'manager', 'franchise'])
def financial_reports():
    """Financial reports and analytics"""
    try:
        current_user_id = session.get('user_id')
        user = User.query.get(current_user_id)
        
        # Get branch filter for role-based access
        branch_filter = get_finance_branch_filter(current_user_id)
        
        if branch_filter is False:
            flash('No branch access configured', 'error')
            return redirect(url_for('finance.dashboard'))
        
        # Date range from request
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        report_type = request.args.get('type', 'summary')
        export_format = request.args.get('export', '')
        
        if not date_from:
            date_from = (get_current_ist_datetime() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not date_to:
            date_to = get_current_ist_datetime().strftime('%Y-%m-%d')
            
        # Payment summary with branch filtering
        payments_query = db.session.query(Payment)\
            .join(Invoice).join(Student)\
            .filter(branch_filter)\
            .filter(Payment.paid_on >= datetime.strptime(date_from, '%Y-%m-%d'))\
            .filter(Payment.paid_on <= datetime.strptime(date_to, '%Y-%m-%d'))
        
        total_collected = payments_query.with_entities(func.sum(Payment.amount)).scalar() or 0
        payment_count = payments_query.count()
        
        # Initialize variables that might not be calculated for all report types
        method_breakdown = []
        branch_breakdown = []
        daily_breakdown = []
        comparison_data = []
        
        # Report type specific logic
        if report_type == 'summary':
            # Basic payment method breakdown
            method_breakdown = db.session.query(Payment.mode, func.sum(Payment.amount), func.count(Payment.id))\
                .join(Invoice).join(Student)\
                .filter(branch_filter)\
                .filter(Payment.paid_on >= datetime.strptime(date_from, '%Y-%m-%d'))\
                .filter(Payment.paid_on <= datetime.strptime(date_to, '%Y-%m-%d'))\
                .group_by(Payment.mode).all()
            
            # Branch-wise breakdown for admin/manager
            if user.role in ['admin', 'manager']:
                branch_breakdown = db.session.query(
                    Branch.branch_name, 
                    func.sum(Payment.amount), 
                    func.count(Payment.id)
                )\
                    .select_from(Payment)\
                    .join(Invoice).join(Student).join(Branch, Student.branch_id == Branch.id)\
                    .filter(Payment.paid_on >= datetime.strptime(date_from, '%Y-%m-%d'))\
                    .filter(Payment.paid_on <= datetime.strptime(date_to, '%Y-%m-%d'))\
                    .group_by(Branch.id, Branch.branch_name).all()
                    
        elif report_type == 'detailed':
            # More detailed breakdowns including daily data
            method_breakdown = db.session.query(Payment.mode, func.sum(Payment.amount), func.count(Payment.id))\
                .join(Invoice).join(Student)\
                .filter(branch_filter)\
                .filter(Payment.paid_on >= datetime.strptime(date_from, '%Y-%m-%d'))\
                .filter(Payment.paid_on <= datetime.strptime(date_to, '%Y-%m-%d'))\
                .group_by(Payment.mode).all()
            
            if user.role in ['admin', 'manager']:
                branch_breakdown = db.session.query(
                    Branch.branch_name, 
                    func.sum(Payment.amount), 
                    func.count(Payment.id)
                )\
                    .select_from(Payment)\
                    .join(Invoice).join(Student).join(Branch, Student.branch_id == Branch.id)\
                    .filter(Payment.paid_on >= datetime.strptime(date_from, '%Y-%m-%d'))\
                    .filter(Payment.paid_on <= datetime.strptime(date_to, '%Y-%m-%d'))\
                    .group_by(Branch.id, Branch.branch_name).all()
            
            # Daily breakdown for detailed view
            daily_breakdown = db.session.query(
                func.strftime('%Y-%m-%d', Payment.paid_on).label('date'),
                func.sum(Payment.amount).label('amount'),
                func.count(Payment.id).label('count')
            )\
                .join(Invoice).join(Student)\
                .filter(branch_filter)\
                .filter(Payment.paid_on >= datetime.strptime(date_from, '%Y-%m-%d'))\
                .filter(Payment.paid_on <= datetime.strptime(date_to, '%Y-%m-%d'))\
                .group_by(func.strftime('%Y-%m-%d', Payment.paid_on))\
                .order_by(func.strftime('%Y-%m-%d', Payment.paid_on)).all()
                
        elif report_type == 'comparison':
            # Same period comparison with previous period
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            period_days = (date_to_obj - date_from_obj).days + 1
            
            # Previous period
            prev_date_to = date_from_obj - timedelta(days=1)
            prev_date_from = prev_date_to - timedelta(days=period_days-1)
            
            # Current period data
            current_payments = db.session.query(Payment)\
                .join(Invoice).join(Student)\
                .filter(branch_filter)\
                .filter(Payment.paid_on >= date_from_obj)\
                .filter(Payment.paid_on <= date_to_obj)
            
            current_total = current_payments.with_entities(func.sum(Payment.amount)).scalar() or 0
            current_count = current_payments.count()
            
            # Previous period data
            previous_payments = db.session.query(Payment)\
                .join(Invoice).join(Student)\
                .filter(branch_filter)\
                .filter(Payment.paid_on >= prev_date_from)\
                .filter(Payment.paid_on <= prev_date_to)
            
            previous_total = previous_payments.with_entities(func.sum(Payment.amount)).scalar() or 0
            previous_count = previous_payments.count()
            
            # Calculate growth
            amount_growth = ((current_total - previous_total) / previous_total * 100) if previous_total > 0 else 0
            count_growth = ((current_count - previous_count) / previous_count * 100) if previous_count > 0 else 0
            
            comparison_data = {
                'current_period': {'total': current_total, 'count': current_count},
                'previous_period': {'total': previous_total, 'count': previous_count},
                'growth': {'amount': amount_growth, 'count': count_growth},
                'period_label': f"{prev_date_from.strftime('%Y-%m-%d')} to {prev_date_to.strftime('%Y-%m-%d')}"
            }
            
            # Still show basic breakdowns for comparison
            method_breakdown = db.session.query(Payment.mode, func.sum(Payment.amount), func.count(Payment.id))\
                .join(Invoice).join(Student)\
                .filter(branch_filter)\
                .filter(Payment.paid_on >= datetime.strptime(date_from, '%Y-%m-%d'))\
                .filter(Payment.paid_on <= datetime.strptime(date_to, '%Y-%m-%d'))\
                .group_by(Payment.mode).all()
        
        # Calculate period days
        date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
        period_days = (date_to_obj - date_from_obj).days + 1
        
        # Calculate daily averages
        daily_average = total_collected / period_days if period_days > 0 else 0
        daily_payments = payment_count / period_days if period_days > 0 else 0
        
        # Calculate other metrics for template
        average_payment = total_collected / payment_count if payment_count > 0 else 0
        method_count = len(method_breakdown) if method_breakdown else 0
        branch_count = len(branch_breakdown) if branch_breakdown else 1
        
        # Calculate percentages for method breakdown
        method_breakdown_with_percent = []
        for method, amount, count in method_breakdown:
            percentage = (amount / total_collected * 100) if total_collected > 0 else 0
            method_breakdown_with_percent.append((method, amount, count, percentage))
        
        # Calculate percentages for branch breakdown
        branch_breakdown_with_percent = []
        for branch_name, amount, count in branch_breakdown:
            percentage = (amount / total_collected * 100) if total_collected > 0 else 0
            branch_breakdown_with_percent.append((branch_name, amount, count, percentage))
        
        # Handle export formats
        if export_format in ['pdf', 'excel']:
            
            try:
                if export_format == 'pdf':
                    # Prepare data for PDF export (without percentages)
                    pdf_export_data = {
                        'total_collected': total_collected,
                        'payment_count': payment_count,
                        'average_payment': average_payment,
                        'method_breakdown': method_breakdown,  # Original format without percentages
                        'branch_breakdown': branch_breakdown,  # Original format without percentages
                        'daily_breakdown': daily_breakdown,
                        'comparison_data': comparison_data
                    }
                    # Generate PDF
                    pdf_path = generate_financial_report(pdf_export_data, report_type, date_from, date_to)
                    return send_file(pdf_path, as_attachment=True, download_name=f'financial_report_{report_type}_{date_from}_to_{date_to}.pdf')
                
                elif export_format == 'excel':
                    # Prepare data for Excel export (with percentages)
                    excel_export_data = {
                        'total_collected': total_collected,
                        'payment_count': payment_count,
                        'average_payment': average_payment,
                        'method_breakdown': method_breakdown_with_percent,
                        'branch_breakdown': branch_breakdown_with_percent,
                        'daily_breakdown': daily_breakdown,
                        'comparison_data': comparison_data
                    }
                    # Generate Excel
                    excel_path = generate_financial_report_excel(excel_export_data, report_type, date_from, date_to)
                    return send_file(excel_path, as_attachment=True, download_name=f'financial_report_{report_type}_{date_from}_to_{date_to}.xlsx')
                    
            except Exception as e:
                flash(f'Error generating {export_format.upper()} export: {str(e)}', 'error')
                # Continue to render the template instead of erroring out
        
        return render_template('finance/reports.html',
                             date_from=date_from,
                             date_to=date_to,
                             report_type=report_type,
                             total_collected=total_collected,
                             payment_count=payment_count,
                             method_breakdown=method_breakdown_with_percent,
                             branch_breakdown=branch_breakdown_with_percent,
                             daily_breakdown=daily_breakdown,
                             comparison_data=comparison_data,
                             period_days=period_days,
                             daily_average=daily_average,
                             daily_payments=daily_payments,
                             average_payment=average_payment,
                             method_count=method_count,
                             branch_count=branch_count)
                             
    except Exception as e:
        flash(f'Error generating report: {str(e)}', 'error')
        return redirect(url_for('finance.dashboard'))

@finance_bp.route('/api/revenue-chart')
@login_required
@role_required(['admin', 'regional_manager', 'manager', 'franchise'])
def revenue_chart_data():
    """API endpoint for revenue chart data"""
    try:
        current_user_id = session.get('user_id')
        user = User.query.get(current_user_id)
        
        # Base filter
        if user.role == 'franchise':
            branch_filter = Student.branch_id == user.branch_id
        else:
            branch_filter = True
        
        # Get period from request (days)
        period = request.args.get('period', 30, type=int)
        end_date = get_current_ist_datetime()
        start_date = end_date - timedelta(days=period)
        
        # Daily revenue for the period
        daily_revenue = []
        for i in range(period + 1):
            day = start_date + timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            revenue = db.session.query(func.sum(Payment.amount))\
                .join(Invoice).join(Student)\
                .filter(branch_filter)\
                .filter(Payment.paid_on >= day_start)\
                .filter(Payment.paid_on <= day_end).scalar() or 0
            
            daily_revenue.append({
                'date': day.strftime('%Y-%m-%d'),
                'revenue': float(revenue)
            })
        
        return jsonify(daily_revenue)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@finance_bp.route('/outstanding')
@login_required
@role_required(['admin', 'regional_manager', 'manager', 'franchise'])
def outstanding_payments():
    """List students with outstanding payments"""
    try:
        current_user_id = session.get('user_id')
        user = User.query.get(current_user_id)
        
        # Complex query to find outstanding amounts
        # This needs to be properly structured based on your invoice/payment relationship
        
        # For now, let's get students with pending installments
        query = db.session.query(Student)\
            .join(Invoice)\
            .join(Installment)\
            .filter(Installment.is_paid == False)
        
        # Role-based filtering
        if user.role == 'franchise':
            query = query.filter(Student.branch_id == user.branch_id)
        
        # Get unique students
        students_with_outstanding = query.distinct().all()
        
        # Calculate outstanding for each student
        outstanding_data = []
        for student in students_with_outstanding:
            total_due = 0
            overdue_amount = 0
            today = get_current_ist_datetime().date()
            
            for installment in student.installments:
                if not installment.is_paid:
                    total_due += installment.amount
                    if installment.due_date < today:
                        overdue_amount += installment.amount
            
            if total_due > 0:
                outstanding_data.append({
                    'student': student,
                    'total_due': total_due,
                    'overdue_amount': overdue_amount
                })
        
        # Sort by overdue amount (highest first)
        outstanding_data.sort(key=lambda x: x['overdue_amount'], reverse=True)
        
        return render_template('finance/outstanding.html',
                             outstanding_data=outstanding_data)
                             
    except Exception as e:
        flash(f'Error loading outstanding payments: {str(e)}', 'error')
        return redirect(url_for('finance.dashboard'))

@finance_bp.route('/collect-payment/<int:installment_id>')
@login_required
@role_required(['admin', 'regional_manager', 'manager', 'franchise'])
def collect_payment(installment_id):
    """Collect payment for a specific installment"""
    try:
        # Get the installment
        installment = Installment.query.get_or_404(installment_id)
        
        # Check access permissions
        current_user_id = session.get('user_id')
        user = User.query.get(current_user_id)
        
        if user.role == 'franchise':
            if installment.invoice and installment.invoice.student:
                student = installment.invoice.student
                if hasattr(student, 'branch_id') and student.branch_id != user.branch_id:
                    flash('Access denied', 'error')
                    return redirect(url_for('finance.installments_list'))
        
        # Get student and invoice details
        student = installment.invoice.student if installment.invoice else None
        invoice = installment.invoice
        
        # Calculate remaining balance
        remaining_balance = installment.balance_amount or installment.amount
        
        return render_template('finance/collect_payment.html',
                             installment=installment,
                             student=student,
                             invoice=invoice,
                             remaining_balance=remaining_balance)
                             
    except Exception as e:
        flash(f'Error loading payment collection: {str(e)}', 'error')
        return redirect(url_for('finance.installments_list'))
