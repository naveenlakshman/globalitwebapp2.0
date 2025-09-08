from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from sqlalchemy.orm import joinedload
from init_db import db
from models.invoice_model import Invoice
from models.payment_model import Payment
from models.installment_model import Installment
from models.student_model import Student
from models.course_model import Course
from models.branch_model import Branch
from utils.auth import login_required, admin_required
from utils.timezone_helper import get_current_ist_datetime, get_current_ist_formatted, format_datetime_indian
from datetime import datetime, timedelta, timezone
import uuid

invoice_bp = Blueprint("invoices", __name__)

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

# ---------------------------------------
# Route: List All Invoices
# ---------------------------------------
@invoice_bp.route("/")
@login_required
def list_invoices():
    """List all invoices with role-based filtering"""
    try:
        from models.user_model import User
        current_user_id = session.get('user_id')
        current_user = User.query.get(current_user_id)
        
        # Get filter parameters
        status_filter = request.args.get('status', 'all')
        search_query = request.args.get('search', '').strip()
        
        # Base query
        query = db.session.query(Invoice, Student).join(Student, Invoice.student_id == Student.student_id).filter(Invoice.is_deleted == 0)
        
        # Apply role-based filtering
        if current_user.role in ['franchise', 'regional_manager']:
            user_branches = get_user_branch_ids(current_user.id)
            if user_branches:
                query = query.filter(Student.branch_id.in_(user_branches))
            else:
                query = query.filter(Student.branch_id == -1)  # No results
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                query = query.filter(Student.branch_id == user_branch_id)
            else:
                query = query.filter(Student.branch_id == -1)  # No results
        # Admin sees all invoices
        
        # Apply status filter
        if status_filter == 'pending':
            query = query.filter(Invoice.due_amount > 0)
        elif status_filter == 'paid':
            query = query.filter(Invoice.due_amount <= 0)
        
        # Apply search filter
        if search_query:
            query = query.filter(
                db.or_(
                    Student.full_name.ilike(f'%{search_query}%'),
                    Student.student_id.ilike(f'%{search_query}%')
                )
            )
        
        results = query.order_by(Invoice.created_at.desc()).all()
        
        invoices_data = []
        for invoice, student in results:
            invoices_data.append({
                'invoice': invoice,
                'student': student,
                'pending_amount': invoice.due_amount,
                'payment_status': 'Paid' if invoice.due_amount <= 0 else 'Pending'
            })
        
        return render_template('invoices/list_invoices.html', 
                             invoices=invoices_data,
                             current_user=current_user)
                             
    except Exception as e:
        flash(f'Error loading invoices: {str(e)}', 'error')
        return redirect(url_for('dashboard_bp.branch_manager_dashboard'))

# ---------------------------------------
# Route: Create New Invoice Form
# ---------------------------------------
@invoice_bp.route("/create")
@login_required
def create_invoice_form():
    """Show form to create new invoice"""
    try:
        from models.user_model import User
        current_user_id = session.get('user_id')
        current_user = User.query.get(current_user_id)
        
        # Get students based on user's branch access
        if current_user.role in ['franchise', 'regional_manager']:
            user_branches = get_user_branch_ids(current_user.id)
            if user_branches:
                students = Student.query.options(db.joinedload(Student.branch)).filter(
                    Student.branch_id.in_(user_branches),
                    Student.is_deleted == 0
                ).order_by(Student.full_name).all()
            else:
                students = []
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                students = Student.query.options(db.joinedload(Student.branch)).filter(
                    Student.branch_id == user_branch_id,
                    Student.is_deleted == 0
                ).order_by(Student.full_name).all()
            else:
                students = []
        else:
            # Admin sees all students
            students = Student.query.options(db.joinedload(Student.branch)).filter_by(is_deleted=0).order_by(Student.full_name).all()
        
        # Get active courses
        courses = Course.query.filter_by(status='Active', is_deleted=0).order_by(Course.course_name).all()
        
        # Calculate default date (7 days from now)
        default_date = (get_current_ist_datetime() + timedelta(days=7)).strftime('%Y-%m-%d')
        today_date = get_current_ist_datetime().strftime('%Y-%m-%d')
        
        return render_template('invoices/create_invoice.html', 
                             students=students,
                             courses=courses,
                             current_user=current_user,
                             default_date=default_date,
                             today_date=today_date)
                             
    except Exception as e:
        flash(f'Error loading invoice form: {str(e)}', 'error')
        return redirect(url_for('invoices.list_invoices'))

# ---------------------------------------
# Route: Create New Invoice
# ---------------------------------------
@invoice_bp.route("/create", methods=["POST"])
@login_required
def create_invoice():
    """Create new invoice for multiple courses"""
    try:
        student_id = request.form.get("student_id")
        course_ids = request.form.getlist("course_ids[]")
        course_fees = request.form.getlist("course_fees[]")
        total_amount = float(request.form.get("total_amount", 0))
        discount = float(request.form.get("discount", 0))
        installment_count = int(request.form.get("installment_count", 1))
        start_date = request.form.get("start_date")
        installment_dates = request.form.getlist("installment_dates[]")
        notes = request.form.get("notes", "")

        if not student_id or not course_ids:
            flash("Student and at least one course selection are required.", 'error')
            return redirect(url_for('invoices.create_invoice_form'))

        # Validate student exists and user has access
        student = Student.query.filter_by(student_id=student_id, is_deleted=0).first()
        if not student:
            flash("Student not found.", 'error')
            return redirect(url_for('invoices.create_invoice_form'))

        # Validate courses exist
        courses = []
        total_course_fees = 0
        for i, course_id in enumerate(course_ids):
            course = Course.query.filter_by(id=course_id, status='Active', is_deleted=0).first()
            if not course:
                flash(f"Course with ID {course_id} not found or inactive.", 'error')
                return redirect(url_for('invoices.create_invoice_form'))
            
            # Check if student already has an active invoice for this course
            existing_invoice = Invoice.query.filter_by(
                student_id=student_id, 
                course_id=course_id, 
                is_deleted=0
            ).filter(Invoice.due_amount > 0).first()
            
            if existing_invoice:
                flash(f"Student already has a pending invoice for {course.course_name}. Please complete payment first.", 'warning')
                return redirect(url_for('invoices.view_invoice', invoice_id=existing_invoice.id))
            
            courses.append(course)
            total_course_fees += course.fee

        if total_amount <= 0:
            flash("Invalid amount. Amount must be greater than 0.", 'error')
            return redirect(url_for('invoices.create_invoice_form'))

        due_amount = total_amount - discount

        # Create separate invoice for each course (this is the standard approach)
        # Alternatively, you could create one invoice with multiple line items
        created_invoices = []
        
        # Calculate fee proportion for each course for discount distribution
        for i, course in enumerate(courses):
            course_proportion = course.fee / total_course_fees
            course_discount = discount * course_proportion
            course_due_amount = course.fee - course_discount
            
            invoice = Invoice(
                student_id=student_id,
                course_id=course.id,
                course_fee=course.fee,
                total_amount=course.fee,
                discount=course_discount,
                due_amount=course_due_amount,
                enrollment_date=get_current_ist_datetime().date(),
                invoice_date=get_current_ist_datetime().date(),  # Set invoice date to today
                due_date=None,  # Can be set later based on payment terms
                payment_terms="As per agreement",  # Default payment terms
                invoice_notes=f"{notes}\n[Part of multi-course enrollment: {', '.join([c.course_name for c in courses])}]"
            )

            db.session.add(invoice)
            db.session.flush()  # Get invoice ID
            created_invoices.append(invoice)

            # Create installments for this course
            if installment_count > 1:
                # Multiple installments
                per_installment = round(course_due_amount / installment_count, 2)
                
                # Handle any rounding differences in the last installment
                total_distributed = per_installment * (installment_count - 1)
                last_installment_amount = course_due_amount - total_distributed
                
                if installment_dates and len(installment_dates) >= installment_count:
                    # Use provided installment dates
                    for j in range(installment_count):
                        if j < len(installment_dates) and installment_dates[j]:
                            due_date = datetime.strptime(installment_dates[j], "%Y-%m-%d")
                        else:
                            # Fallback to calculated date if specific date not provided
                            base_date = datetime.strptime(start_date, "%Y-%m-%d") if start_date else get_current_ist_datetime()
                            due_date = base_date + timedelta(days=30 * j)
                        
                        # Use exact amount for last installment to handle rounding
                        amount = last_installment_amount if j == installment_count - 1 else per_installment
                        
                        installment = Installment(
                            invoice_id=invoice.id,
                            installment_number=j + 1,
                            due_date=due_date.date(),
                            amount=amount,
                            balance_amount=amount,
                            notes=notes,
                            status='pending'
                        )
                        db.session.add(installment)
                else:
                    # Generate installment dates automatically (monthly)
                    base_date = datetime.strptime(start_date, "%Y-%m-%d") if start_date else get_current_ist_datetime()
                    
                    for j in range(installment_count):
                        due_date = base_date + timedelta(days=30 * j)
                        
                        # Use exact amount for last installment to handle rounding
                        amount = last_installment_amount if j == installment_count - 1 else per_installment
                        
                        installment = Installment(
                            invoice_id=invoice.id,
                            installment_number=j + 1,
                            due_date=due_date.date(),
                            amount=amount,
                            balance_amount=amount,
                            notes=notes,
                            status='pending'
                        )
                        db.session.add(installment)
            else:
                # Single payment - create one installment
                due_date = datetime.strptime(start_date, "%Y-%m-%d") if start_date else get_current_ist_datetime()
                installment = Installment(
                    invoice_id=invoice.id,
                    installment_number=1,
                    due_date=due_date.date(),
                    amount=course_due_amount,
                    balance_amount=course_due_amount,
                    notes=notes,
                    status='pending'
                )
                db.session.add(installment)

        db.session.commit()

        course_names = ', '.join([course.course_name for course in courses])
        if len(created_invoices) == 1:
            flash(f'Invoice created successfully for {student.full_name} - {course_names}!', 'success')
            return redirect(url_for('invoices.view_invoice', invoice_id=created_invoices[0].id))
        else:
            flash(f'{len(created_invoices)} invoices created successfully for {student.full_name} - {course_names}!', 'success')
            return redirect(url_for('invoices.list_invoices'))

    except Exception as e:
        db.session.rollback()
        flash(f'Error creating invoice: {str(e)}', 'error')
        return redirect(url_for('invoices.create_invoice_form'))

# ---------------------------------------
# Route: View Invoice Details
# ---------------------------------------
@invoice_bp.route("/<int:invoice_id>")
@login_required
def view_invoice(invoice_id):
    """View detailed invoice information"""
    try:
        from datetime import date
        
        invoice = Invoice.query.get_or_404(invoice_id)
        student = Student.query.filter_by(student_id=invoice.student_id).first()
        
        if not student:
            flash("Student not found for this invoice.", 'error')
            return redirect(url_for('invoices.list_invoices'))
        
        # Get installments
        installments = Installment.query.filter_by(invoice_id=invoice_id).order_by(Installment.installment_number).all()
        
        # Get payments
        payments = Payment.query.filter_by(invoice_id=invoice_id).order_by(Payment.paid_on.desc()).all()
        
        today = get_current_ist_datetime().date()
        
        return render_template('invoices/view_invoice.html',
                             invoice=invoice,
                             student=student,
                             installments=installments,
                             payments=payments,
                             today=today)
                             
    except Exception as e:
        flash(f'Error loading invoice: {str(e)}', 'error')
        return redirect(url_for('invoices.list_invoices'))

# ---------------------------------------
# Route: Record Payment Form
# ---------------------------------------
@invoice_bp.route("/<int:invoice_id>/pay")
@login_required
def payment_form(invoice_id):
    """Show payment form for invoice"""
    try:
        from datetime import date
        
        invoice = Invoice.query.get_or_404(invoice_id)
        student = Student.query.filter_by(student_id=invoice.student_id).first()
        
        # Get pending installments
        pending_installments = Installment.query.filter_by(
            invoice_id=invoice_id
        ).filter(Installment.status.in_(['pending', 'partial'])).order_by(Installment.due_date).all()
        
        payment_methods = ['Cash', 'Card', 'UPI', 'Net Banking', 'Cheque', 'Bank Transfer']
        today = get_current_ist_datetime().date()
        
        return render_template('invoices/payment_form.html',
                             invoice=invoice,
                             student=student,
                             pending_installments=pending_installments,
                             payment_methods=payment_methods,
                             today=today)
                             
    except Exception as e:
        flash(f'Error loading payment form: {str(e)}', 'error')
# ---------------------------------------
# Route: Record Payment
# ---------------------------------------
@invoice_bp.route("/<int:invoice_id>/pay", methods=["POST"])
@login_required
def record_payment(invoice_id):
    """Record payment for invoice"""
    try:
        invoice = Invoice.query.get_or_404(invoice_id)
        
        payment_amount = float(request.form.get("payment_amount", 0))
        payment_method = request.form.get("payment_method")
        installment_id = request.form.get("installment_id")
        utr_ref = request.form.get("utr_ref", "")
        notes = request.form.get("notes", "")
        
        if payment_amount <= 0:
            flash("Payment amount must be greater than 0.", 'error')
            return redirect(url_for('invoices.payment_form', invoice_id=invoice_id))
        
        # Use tolerance for floating-point comparison to handle precision issues
        tolerance = 0.01
        if payment_amount > (invoice.due_amount + tolerance):
            flash(f"Payment amount cannot exceed due amount of ₹{invoice.due_amount:.2f}.", 'error')
            return redirect(url_for('invoices.payment_form', invoice_id=invoice_id))
        
        # Create payment record
        payment = Payment(
            invoice_id=invoice_id,
            installment_id=int(installment_id) if installment_id else None,
            amount=payment_amount,
            mode=payment_method,
            utr_number=utr_ref,
            notes=notes,
            paid_on=get_current_ist_datetime()
        )
        
        db.session.add(payment)
        
        # Handle installment allocation with proper business logic
        if installment_id:
            # Payment applied to specific installment
            installment = Installment.query.get(installment_id)
            if installment:
                installment.paid_amount += payment_amount
                installment.balance_amount -= payment_amount
                
                # Update status with tolerance for floating-point precision
                tolerance = 0.01
                if installment.balance_amount <= tolerance:
                    installment.status = 'paid'
                    installment.is_paid = True
                    installment.balance_amount = 0.0
                    installment.payment_date = get_current_ist_datetime()
                elif installment.paid_amount > tolerance:
                    installment.status = 'partial'
                    installment.is_paid = False
                else:
                    installment.status = 'pending'
                    installment.is_paid = False
        else:
            # No specific installment selected - apply payment to oldest pending installments
            # This is proper business logic: First In, First Out (FIFO) for installment payments
            remaining_payment = payment_amount
            tolerance = 0.01
            
            # Get pending installments for this invoice ordered by due date (oldest first)
            pending_installments = Installment.query.filter_by(
                invoice_id=invoice_id
            ).filter(
                Installment.status.in_(['pending', 'partial'])
            ).order_by(Installment.due_date.asc()).all()
            
            for installment in pending_installments:
                if remaining_payment <= tolerance:
                    break
                    
                # Calculate how much we can apply to this installment
                installment_balance = installment.balance_amount
                amount_to_apply = min(remaining_payment, installment_balance)
                
                # Update installment amounts
                installment.paid_amount += amount_to_apply
                installment.balance_amount -= amount_to_apply
                remaining_payment -= amount_to_apply
                
                # Update installment status
                if installment.balance_amount <= tolerance:
                    installment.status = 'paid'
                    installment.is_paid = True
                    installment.balance_amount = 0.0
                    installment.payment_date = get_current_ist_datetime()
                elif installment.paid_amount > tolerance:
                    installment.status = 'partial'
                    installment.is_paid = False
                else:
                    installment.status = 'pending'
                    installment.is_paid = False
            
            # If there's still remaining payment after all installments are paid,
            # it becomes an advance payment (this is normal business practice)
            if remaining_payment > tolerance:
                # You could log this or handle advance payments separately
                # For now, the invoice due_amount will show the correct balance
                pass
        
        # Calculate invoice amounts from actual payments (don't double-count)
        total_invoice_payments = db.session.query(db.func.sum(Payment.amount)).filter_by(invoice_id=invoice_id).scalar() or 0
        calculated_due = invoice.total_amount - invoice.discount - total_invoice_payments
        
        # Set invoice amounts correctly
        invoice.paid_amount = total_invoice_payments
        invoice.due_amount = calculated_due
        
        db.session.commit()
        
        flash(f'Payment of ₹{payment_amount} recorded successfully!', 'success')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error recording payment: {str(e)}', 'error')
        return redirect(url_for('invoices.payment_form', invoice_id=invoice_id))

# ---------------------------------------
# Route: Edit Invoice Form
# ---------------------------------------
@invoice_bp.route("/<int:invoice_id>/edit")
@login_required
@admin_required
def edit_invoice_form(invoice_id):
    """Show form to edit invoice"""
    try:
        invoice = Invoice.query.get_or_404(invoice_id)
        student = Student.query.filter_by(student_id=invoice.student_id).first()
        
        return render_template('invoices/edit_invoice.html',
                             invoice=invoice,
                             student=student)
                             
    except Exception as e:
        flash(f'Error loading invoice for editing: {str(e)}', 'error')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))

# ---------------------------------------
# Route: Update Invoice
# ---------------------------------------
@invoice_bp.route("/<int:invoice_id>/edit", methods=["POST"])
@login_required
@admin_required
def update_invoice(invoice_id):
    """Update invoice details"""
    try:
        invoice = Invoice.query.get_or_404(invoice_id)
        
        # Update basic details
        total_amount = float(request.form.get("total_amount", invoice.total_amount))
        discount = float(request.form.get("discount", invoice.discount))
        
        # Recalculate due amount
        new_due_amount = total_amount - discount - invoice.paid_amount
        
        if new_due_amount < 0:
            flash("Total amount minus discount cannot be less than paid amount.", 'error')
            return redirect(url_for('invoices.edit_invoice_form', invoice_id=invoice_id))
        
        invoice.total_amount = total_amount
        invoice.discount = discount
        invoice.due_amount = new_due_amount
        
        db.session.commit()
        
        flash('Invoice updated successfully!', 'success')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating invoice: {str(e)}', 'error')
        return redirect(url_for('invoices.edit_invoice_form', invoice_id=invoice_id))

# ---------------------------------------
# Route: Delete Invoice
# ---------------------------------------
@invoice_bp.route("/<int:invoice_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_invoice(invoice_id):
    """Soft delete invoice"""
    try:
        invoice = Invoice.query.get_or_404(invoice_id)
        
        # Check if invoice has payments
        if invoice.paid_amount > 0:
            flash("Cannot delete invoice with payments. Please contact admin.", 'error')
            return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))
        
        # Soft delete
        invoice.is_deleted = 1
        
        # Delete associated installments
        installments = Installment.query.filter_by(invoice_id=invoice_id).all()
        for installment in installments:
            db.session.delete(installment)  # Hard delete for now
        
        db.session.commit()
        
        flash('Invoice deleted successfully!', 'success')
        return redirect(url_for('invoices.list_invoices'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting invoice: {str(e)}', 'error')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))

# ---------------------------------------
# Route: Overdue Invoices Report
# ---------------------------------------
@invoice_bp.route("/overdue")
@login_required
def overdue_invoices():
    """List overdue invoices and installments"""
    try:
        from models.user_model import User
        current_user_id = session.get('user_id')
        current_user = User.query.get(current_user_id)
        
        # Get overdue installments - simplified query to avoid multiple FROMs issue
        today = get_current_ist_datetime().date()
        query = db.session.query(Installment).join(
            Invoice, Installment.invoice_id == Invoice.id
        ).join(
            Student, Invoice.student_id == Student.student_id
        ).filter(
            Installment.due_date < today,
            Installment.status.in_(['pending', 'partial']),
            Invoice.is_deleted == 0
        )
        
        # Apply role-based filtering
        if current_user.role in ['franchise', 'regional_manager']:
            user_branches = get_user_branch_ids(current_user.id)
            if user_branches:
                query = query.filter(Student.branch_id.in_(user_branches))
            else:
                query = query.filter(Student.branch_id == -1)
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                query = query.filter(Student.branch_id == user_branch_id)
            else:
                query = query.filter(Student.branch_id == -1)
        
        overdue_installments = query.order_by(Installment.due_date).all()
        
        # Build overdue data with related objects
        overdue_data = []
        for installment in overdue_installments:
            invoice = Invoice.query.get(installment.invoice_id)
            student = Student.query.filter_by(student_id=invoice.student_id).first()
            days_overdue = (today - installment.due_date).days
            
            overdue_data.append({
                'installment': installment,
                'invoice': invoice,
                'student': student,
                'days_overdue': days_overdue
            })
        
        return render_template('invoices/overdue_report.html',
                             overdue_data=overdue_data,
                             current_user=current_user,
                             today=today)
                             
    except Exception as e:
        flash(f'Error loading overdue report: {str(e)}', 'error')
        return redirect(url_for('invoices.list_invoices'))

# ---------------------------------------
# API Routes for AJAX/JSON
# ---------------------------------------
@invoice_bp.route("/api/invoice/<int:invoice_id>")
@login_required
def api_get_invoice(invoice_id):
    """Get invoice data as JSON"""
    try:
        invoice = Invoice.query.get_or_404(invoice_id)
        student = Student.query.filter_by(student_id=invoice.student_id).first()
        
        return jsonify({
            'success': True,
            'invoice': invoice.to_dict(),
            'student': student.to_dict() if student else None
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400

@invoice_bp.route("/api/student/<int:student_id>/invoices")
@login_required
def api_student_invoices(student_id):
    """Get all invoices for a student"""
    try:
        invoices = Invoice.query.filter_by(student_id=student_id, is_deleted=0).all()
        
        return jsonify({
            'success': True,
            'invoices': [invoice.to_dict() for invoice in invoices]
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400

# ---------------------------------------
# Route: Print Invoice (HTML Print View)
# ---------------------------------------
@invoice_bp.route("/<int:invoice_id>/print")
@login_required
def print_invoice(invoice_id):
    """Generate print-friendly invoice view"""
    try:
        invoice = Invoice.query.get_or_404(invoice_id)
        student = Student.query.filter_by(student_id=invoice.student_id).first()
        
        if not student:
            flash("Student not found for this invoice.", 'error')
            return redirect(url_for('invoices.list_invoices'))
        
        # Get course details
        course = Course.query.filter_by(id=student.course_id).first() if student.course_id else None
        
        # Get branch details
        branch = Branch.query.filter_by(id=student.branch_id).first() if student.branch_id else None
        
        # Get installments
        installments = Installment.query.filter_by(invoice_id=invoice_id).order_by(Installment.installment_number).all()
        
        # Get payments
        payments = Payment.query.filter_by(invoice_id=invoice_id).order_by(Payment.paid_on.desc()).all()
        
        return render_template('invoices/print_invoice.html',
                             invoice=invoice,
                             student=student,
                             course=course,
                             branch=branch,
                             installments=installments,
                             payments=payments)
                             
    except Exception as e:
        flash(f'Error generating print view: {str(e)}', 'error')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))

# ---------------------------------------
# Route: Download Invoice PDF
# ---------------------------------------
@invoice_bp.route("/<int:invoice_id>/pdf")
@login_required
def download_invoice_pdf(invoice_id):
    """Generate and download invoice as PDF"""
    try:
        from flask import make_response
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
        from io import BytesIO
        
        invoice = Invoice.query.get_or_404(invoice_id)
        student = Student.query.filter_by(student_id=invoice.student_id).first()
        
        if not student:
            flash("Student not found for this invoice.", 'error')
            return redirect(url_for('invoices.list_invoices'))
        
        # Get related data
        course = Course.query.filter_by(id=student.course_id).first() if student.course_id else None
        branch = Branch.query.filter_by(id=student.branch_id).first() if student.branch_id else None
        installments = Installment.query.filter_by(invoice_id=invoice_id).order_by(Installment.installment_number).all()
        payments = Payment.query.filter_by(invoice_id=invoice_id).order_by(Payment.paid_on.desc()).all()
        
        # Create PDF in memory with compact A4 layout
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0.5*inch, leftMargin=0.5*inch, 
                              topMargin=0.5*inch, bottomMargin=0.5*inch)
        
        # Container for the 'Flowable' objects
        elements = []
        
        # Define styles - more compact
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=15,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#2c3e50')
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=12,
            spaceAfter=8,
            textColor=colors.HexColor('#34495e')
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=9,
            spaceAfter=4
        )
        
        # Add logo and title together
        from reportlab.platypus import Image
        import os
        
        # Create logo and title in a table for proper alignment
        logo_path = os.path.join('static', 'Global IT Edication Logo.png')
        if os.path.exists(logo_path):
            # Create a table with logo and title side by side
            logo = Image(logo_path, width=1*inch, height=0.8*inch)
            title_paragraph = Paragraph("INVOICE", title_style)
            
            # Create a table for logo and title alignment
            header_data = [[logo, title_paragraph]]
            header_table = Table(header_data, colWidths=[1.5*inch, 4.5*inch])
            header_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),   # Align logo to left
                ('ALIGN', (1, 0), (1, 0), 'CENTER'), # Align title to center
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(header_table)
        else:
            # Fallback if logo not found
            title = Paragraph("INVOICE", title_style)
            elements.append(title)
        
        elements.append(Spacer(1, 15))
        
        # Company/Branch Information
        if branch:
            company_info = [
                [f"{branch.branch_name}"],
                [f"{branch.address or 'Address not provided'}"],
                [f"Phone: {branch.phone or 'N/A'}"],
                [f"Email: {branch.email or 'N/A'}"]
            ]
            
            company_table = Table(company_info, colWidths=[4*inch])
            company_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),  # Make company name bold via style
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),     # Regular font for other info
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(company_table)
            elements.append(Spacer(1, 12))
        
        # Invoice details header
        invoice_header_data = [
            ['Invoice Number:', f'INV-{invoice.id}', 'Date:', invoice.invoice_date.strftime('%d/%m/%Y') if invoice.invoice_date else 'N/A'],
            ['Due Date:', invoice.due_date.strftime('%d/%m/%Y') if invoice.due_date else 'N/A', 'Status:', 'Paid' if invoice.due_amount <= 0 else 'Pending']
        ]
        
        invoice_header_table = Table(invoice_header_data, colWidths=[1.2*inch, 2.2*inch, 0.8*inch, 1.8*inch])
        invoice_header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        elements.append(invoice_header_table)
        elements.append(Spacer(1, 12))
        
        # Student Information
        elements.append(Paragraph("Bill To:", heading_style))
        student_info = [
            ['Student Name:', student.full_name or 'N/A'],
            ['Student ID:', student.student_id or 'N/A'],
            ['Phone:', student.mobile or 'N/A'],
            ['Email:', student.email or 'N/A'],
            ['Course:', course.course_name if course else 'N/A'],
        ]
        
        student_table = Table(student_info, colWidths=[1.2*inch, 4.8*inch])
        student_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(student_table)
        elements.append(Spacer(1, 12))
        
        # Invoice Items
        elements.append(Paragraph("Invoice Details:", heading_style))
        invoice_data = [
            ['Description', 'Amount (₹)']
        ]
        
        # Add course fee
        if course:
            invoice_data.append([f'{course.course_name} - Course Fee', f'₹{invoice.total_amount:,.2f}'])
        else:
            invoice_data.append(['Course Fee', f'₹{invoice.total_amount:,.2f}'])
        
        # Add total row
        invoice_data.append(['', ''])
        if invoice.discount > 0:
            invoice_data.append(['Discount:', f'-₹{invoice.discount:,.2f}'])
        invoice_data.append(['Total Amount:', f'₹{invoice.total_amount:,.2f}'])
        invoice_data.append(['Paid Amount:', f'₹{invoice.paid_amount:,.2f}'])
        invoice_data.append(['Due Amount:', f'₹{invoice.due_amount:,.2f}'])
        
        invoice_table = Table(invoice_data, colWidths=[4.2*inch, 1.8*inch])
        invoice_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (-1, 0), 1, colors.grey),
            ('GRID', (0, -3), (-1, -1), 1, colors.grey),
            ('FONTNAME', (0, -3), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ]))
        elements.append(invoice_table)
        
        # Payment History if any
        if payments:
            elements.append(Spacer(1, 12))
            elements.append(Paragraph("Payment History:", heading_style))
            
            payment_data = [['Date', 'Amount (₹)', 'Method', 'Reference']]
            for payment in payments:
                payment_data.append([
                    payment.paid_on.strftime('%d/%m/%Y') if payment.paid_on else 'N/A',
                    f'₹{payment.amount:,.2f}',
                    payment.payment_method or 'N/A',
                    payment.utr_number or 'N/A'
                ])
            
            payment_table = Table(payment_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
            payment_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),  # Center align Date column
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),   # Right align Amount column
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ]))
            elements.append(payment_table)
        
        # Installment Schedule if any
        if installments:
            elements.append(Spacer(1, 12))
            elements.append(Paragraph("Installment Schedule:", heading_style))
            
            installment_data = [['Installment #', 'Due Date', 'Amount (₹)', 'Status']]
            for installment in installments:
                status = 'Paid' if installment.is_paid else 'Pending'
                installment_data.append([
                    str(installment.installment_number),
                    installment.due_date.strftime('%d/%m/%Y') if installment.due_date else 'N/A',
                    f'₹{installment.amount:,.2f}',
                    status
                ])
            
            installment_table = Table(installment_data, colWidths=[1.2*inch, 1.5*inch, 1.5*inch, 1.8*inch])
            installment_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),  # Center align Installment # column
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),  # Center align Due Date column
                ('ALIGN', (2, 0), (2, -1), 'RIGHT'),   # Right align Amount column
                ('ALIGN', (3, 0), (3, -1), 'CENTER'),  # Center align Status column
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ]))
            elements.append(installment_table)
        
        # Footer
        elements.append(Spacer(1, 20))
        footer_text = "Thank you for your business!"
        footer = Paragraph(footer_text, ParagraphStyle('Footer', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10))
        elements.append(footer)
        
        # Build PDF
        doc.build(elements)
        
        # Get PDF data
        pdf_data = buffer.getvalue()
        buffer.close()
        
        # Create response
        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=invoice_{invoice.id}.pdf'
        
        return response
        
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))

