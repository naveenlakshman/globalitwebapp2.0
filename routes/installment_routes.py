from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from init_db import db
from models.installment_model import Installment
from models.invoice_model import Invoice
from models.payment_model import Payment
from models.student_model import Student
from utils.auth import login_required
from utils.timezone_helper import utc_to_ist
from datetime import datetime, timedelta, timezone, date

installment_bp = Blueprint("installments", __name__)

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
# Route: List All Installments
# ---------------------------------------
@installment_bp.route("/")
@login_required
def list_installments():
    """List all installments with filtering options"""
    try:
        from models.user_model import User
        current_user_id = session.get('user_id')
        current_user = User.query.get(current_user_id)
        
        # Get filter parameters
        status_filter = request.args.get('status', 'all')
        date_filter = request.args.get('date', 'all')
        
        # Base query - simplified to avoid multiple FROMS issue
        query = db.session.query(Installment).join(
            Invoice, Installment.invoice_id == Invoice.id
        ).join(
            Student, Invoice.student_id == Student.student_id
        ).filter(
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
        
        # Apply status filter
        if status_filter != 'all':
            query = query.filter(Installment.status == status_filter)
        
        # Apply date filter
        today = datetime.now().date()
        if date_filter == 'due_today':
            query = query.filter(Installment.due_date == today)
        elif date_filter == 'overdue':
            query = query.filter(Installment.due_date < today, Installment.status.in_(['pending', 'partial']))
        elif date_filter == 'upcoming':
            query = query.filter(Installment.due_date > today)
        
        results = query.order_by(Installment.due_date.asc()).all()
        
        installments_data = []
        for installment in results:
            invoice = Invoice.query.get(installment.invoice_id)
            student = Student.query.filter_by(student_id=invoice.student_id).first()
            
            installments_data.append({
                'installment': installment,
                'invoice': invoice,
                'student': student,
                'days_overdue': (today - installment.due_date).days if installment.due_date < today else 0
            })
        
        return render_template('installments/list_installments.html',
                             installments=installments_data,
                             current_user=current_user,
                             status_filter=status_filter,
                             date_filter=date_filter,
                             today=today)
                             
    except Exception as e:
        flash(f'Error loading installments: {str(e)}', 'error')
        return redirect(url_for('dashboard_bp.branch_manager_dashboard'))

# ---------------------------------------
# Route: View Installment Details
# ---------------------------------------
@installment_bp.route("/<int:installment_id>")
@login_required
def view_installment(installment_id):
    """View detailed installment information"""
    try:
        installment = Installment.query.get_or_404(installment_id)
        invoice = Invoice.query.get(installment.invoice_id)
        student = Student.query.filter_by(student_id=invoice.student_id).first()
        
        # Get payments for this installment
        payments = Payment.query.filter_by(installment_id=installment_id).order_by(Payment.paid_on.desc()).all()
        
        from datetime import date
        today = date.today()
        
        return render_template('installments/view_installment.html',
                             installment=installment,
                             invoice=invoice,
                             student=student,
                             payments=payments,
                             today=today)
                             
    except Exception as e:
        flash(f'Error loading installment: {str(e)}', 'error')
        return redirect(url_for('installments.list_installments'))

# ---------------------------------------
# Route: Payment Form for Installment
# ---------------------------------------
@installment_bp.route("/<int:installment_id>/pay")
@login_required
def payment_form(installment_id):
    """Show payment form for specific installment"""
    try:
        installment = Installment.query.get_or_404(installment_id)
        invoice = Invoice.query.get(installment.invoice_id)
        student = Student.query.filter_by(student_id=invoice.student_id).first()
        
        if installment.status == 'paid':
            flash('This installment is already paid.', 'info')
            return redirect(url_for('installments.view_installment', installment_id=installment_id))
        
        payment_methods = ['Cash', 'Card', 'UPI', 'Net Banking', 'Cheque', 'Bank Transfer']
        
        return render_template('installments/payment_form.html',
                             installment=installment,
                             invoice=invoice,
                             student=student,
                             payment_methods=payment_methods)
                             
    except Exception as e:
        flash(f'Error loading payment form: {str(e)}', 'error')
        return redirect(url_for('installments.view_installment', installment_id=installment_id))

# ---------------------------------------
# Route: Record Payment for Installment
# ---------------------------------------
@installment_bp.route("/<int:installment_id>/pay", methods=["POST"])
@login_required
def record_payment(installment_id):
    """Record payment for specific installment"""
    try:
        installment = Installment.query.get_or_404(installment_id)
        invoice = Invoice.query.get(installment.invoice_id)
        
        payment_amount = float(request.form.get("payment_amount", 0))
        payment_method = request.form.get("payment_method")
        utr_ref = request.form.get("utr_ref", "")
        notes = request.form.get("notes", "")
        
        if payment_amount <= 0:
            flash("Payment amount must be greater than 0.", 'error')
            return redirect(url_for('installments.payment_form', installment_id=installment_id))
        
        # Use tolerance for floating-point comparison to handle precision issues
        tolerance = 0.01
        if payment_amount > (installment.balance_amount + tolerance):
            flash(f"Payment amount cannot exceed balance amount of ₹{installment.balance_amount:.2f}.", 'error')
            return redirect(url_for('installments.payment_form', installment_id=installment_id))
        
        # Create payment record
        payment = Payment(
            invoice_id=invoice.id,
            installment_id=installment_id,
            amount=payment_amount,
            mode=payment_method,
            utr_number=utr_ref,
            notes=notes,
            paid_on=datetime.now(timezone.utc)
        )
        
        db.session.add(payment)
        
        # Update installment
        installment.paid_amount += payment_amount
        installment.balance_amount -= payment_amount
        
        # Use tolerance for floating-point comparison in status determination
        tolerance = 0.01
        
        # Update status based on actual amounts with tolerance for precision
        if installment.balance_amount <= tolerance:  # Consider effectively zero
            installment.status = 'paid'
            installment.is_paid = True
            installment.balance_amount = 0.0  # Set exactly to zero to avoid tiny remainders
            installment.payment_date = datetime.now(timezone.utc)
        elif installment.paid_amount > tolerance:  # Has some payment
            installment.status = 'partial'
            installment.is_paid = False
        else:
            installment.status = 'pending'
            installment.is_paid = False
        
        # Update invoice amounts using direct calculation to avoid double-counting
        # Calculate total payments from database (this already includes the new payment we just added)
        total_invoice_payments = db.session.query(db.func.sum(Payment.amount)).filter_by(invoice_id=invoice.id).scalar() or 0
        calculated_due = invoice.total_amount - invoice.discount - total_invoice_payments
        
        # Set invoice amounts correctly (don't add, just set to calculated totals)
        invoice.paid_amount = total_invoice_payments
        invoice.due_amount = calculated_due
        
        db.session.commit()
        
        flash(f'Payment of ₹{payment_amount} recorded successfully!', 'success')
        return redirect(url_for('installments.view_installment', installment_id=installment_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error recording payment: {str(e)}', 'error')
        return redirect(url_for('installments.payment_form', installment_id=installment_id))

# ---------------------------------------
# Route: Due Today
# ---------------------------------------
@installment_bp.route("/due-today")
@login_required
def due_today():
    """Show installments due today"""
    try:
        from models.user_model import User
        current_user_id = session.get('user_id')
        current_user = User.query.get(current_user_id)
        
        today = datetime.now().date()
        
        # Base query for today's due installments with explicit joins
        query = db.session.query(Installment, Invoice, Student)\
            .select_from(Installment)\
            .join(Invoice, Installment.invoice_id == Invoice.id)\
            .join(Student, Invoice.student_id == Student.student_id)\
            .filter(
                Installment.due_date == today,
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
        
        due_today_data = query.order_by(Student.full_name).all()
        
        return render_template('installments/due_today.html',
                             due_today_data=due_today_data,
                             current_user=current_user,
                             today=today)
                             
    except Exception as e:
        flash(f'Error loading due today report: {str(e)}', 'error')
        return redirect(url_for('installments.list_installments'))

# ---------------------------------------
# Route: Overdue Installments
# ---------------------------------------
@installment_bp.route("/overdue")
@login_required
def overdue():
    """Show overdue installments"""
    try:
        from models.user_model import User
        current_user_id = session.get('user_id')
        current_user = User.query.get(current_user_id)
        
        today = datetime.now().date()
        
        # Base query for overdue installments with explicit joins
        query = db.session.query(Installment, Invoice, Student)\
            .select_from(Installment)\
            .join(Invoice, Installment.invoice_id == Invoice.id)\
            .join(Student, Invoice.student_id == Student.student_id)\
            .filter(
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
        
        overdue_data = query.order_by(Installment.due_date.asc()).all()
        
        return render_template('installments/overdue.html',
                             overdue_data=overdue_data,
                             current_user=current_user,
                             today=today)
                             
    except Exception as e:
        flash(f'Error loading overdue report: {str(e)}', 'error')
        return redirect(url_for('installments.list_installments'))

# ---------------------------------------
# API Routes
# ---------------------------------------
@installment_bp.route("/api/installment/<int:installment_id>")
@login_required
def api_get_installment(installment_id):
    """Get installment data as JSON"""
    try:
        installment = Installment.query.get_or_404(installment_id)
        
        return jsonify({
            'success': True,
            'installment': installment.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400

# Keep the original API routes for backward compatibility
def serialize_installment(inst):
    return {
        "id": inst.id,
        "invoice_id": inst.invoice_id,
        "amount": inst.amount,
        "due_date": inst.due_date.strftime("%Y-%m-%d"),
        "status": inst.status
    }

@installment_bp.route("/installments/pending", methods=["GET"])
def get_pending_installments():
    results = Installment.query.filter(Installment.status.in_(["Pending", "Partially Paid"])).all()
    return jsonify([serialize_installment(inst) for inst in results])

@installment_bp.route("/installments/<int:installment_id>", methods=["PUT"])
def update_installment_status(installment_id):
    installment = Installment.query.get_or_404(installment_id)
    data = request.json
    
    if "status" in data:
        installment.status = data["status"]
    if "paid_amount" in data:
        installment.paid_amount = data["paid_amount"]
        installment.balance_amount = installment.amount - installment.paid_amount
    
    db.session.commit()
    return jsonify(serialize_installment(installment))

@installment_bp.route("/installments/overdue", methods=["GET"])
def get_overdue_installments():
    today = date.today()
    results = Installment.query.filter(
        Installment.due_date < today,
        Installment.status.in_(["Pending", "Partially Paid"])
    ).all()
    return jsonify([serialize_installment(inst) for inst in results])

# ---------------------------------------
# Route: Print Installment (HTML Print View)
# ---------------------------------------
@installment_bp.route("/<int:installment_id>/print")
@login_required
def print_installment(installment_id):
    """Generate print-friendly installment view"""
    try:
        installment = Installment.query.get_or_404(installment_id)
        invoice = Invoice.query.get(installment.invoice_id)
        student = Student.query.filter_by(student_id=invoice.student_id).first()
        
        if not student:
            flash("Student not found for this installment.", 'error')
            return redirect(url_for('installments.list_installments'))
        
        # Get course and branch details
        from models.course_model import Course
        from models.branch_model import Branch
        course = Course.query.filter_by(id=student.course_id).first() if student.course_id else None
        branch = Branch.query.filter_by(id=student.branch_id).first() if student.branch_id else None
        
        # Get payments for this installment
        payments = Payment.query.filter_by(installment_id=installment_id).order_by(Payment.paid_on.desc()).all()
        
        from utils.timezone_helper import get_current_ist_datetime
        current_time = get_current_ist_datetime()
        
        return render_template('installments/print_installment.html',
                             installment=installment,
                             invoice=invoice,
                             student=student,
                             course=course,
                             branch=branch,
                             payments=payments,
                             current_time=current_time)
                             
    except Exception as e:
        flash(f'Error generating print view: {str(e)}', 'error')
        return redirect(url_for('installments.view_installment', installment_id=installment_id))

# ---------------------------------------
# Route: Download Installment PDF
# ---------------------------------------
@installment_bp.route("/<int:installment_id>/pdf")
@login_required
def download_installment_pdf(installment_id):
    """Generate and download installment as PDF"""
    try:
        from flask import make_response
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
        from io import BytesIO
        
        installment = Installment.query.get_or_404(installment_id)
        invoice = Invoice.query.get(installment.invoice_id)
        student = Student.query.filter_by(student_id=invoice.student_id).first()
        
        if not student:
            flash("Student not found for this installment.", 'error')
            return redirect(url_for('installments.list_installments'))
        
        # Get related data
        from models.course_model import Course
        from models.branch_model import Branch
        course = Course.query.filter_by(id=student.course_id).first() if student.course_id else None
        branch = Branch.query.filter_by(id=student.branch_id).first() if student.branch_id else None
        payments = Payment.query.filter_by(installment_id=installment_id).order_by(Payment.paid_on.desc()).all()
        
        # Create PDF in memory
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        
        # Container for the 'Flowable' objects
        elements = []
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
        )
        
        # Title with Logo
        from reportlab.platypus import Image
        import os
        
        # Create logo and title in a table for proper alignment
        logo_path = os.path.join('static', 'Global IT Edication Logo.png')
        if os.path.exists(logo_path):
            # Create a table with logo and title side by side
            logo = Image(logo_path, width=1*inch, height=0.8*inch)
            title_paragraph = Paragraph(f"Installment #{installment.installment_number} - Payment Receipt", title_style)
            
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
            elements.append(Paragraph(f"Installment #{installment.installment_number} - Payment Receipt", title_style))
        
        elements.append(Spacer(1, 20))
        
        # Company information (if branch exists)
        if branch:
            company_data = [
                [f"{branch.branch_name}"],
                [f"{branch.address or 'Address not provided'}"],
                [f"Phone: {branch.phone or 'N/A'}"],
                [f"Email: {branch.email or 'N/A'}"]
            ]
            
            company_table = Table(company_data, colWidths=[6*inch])
            company_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),  # Make company name bold via style
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),     # Regular font for other info
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(company_table)
            elements.append(Spacer(1, 20))
        
        # Installment details header
        installment_header_data = [
            ['Installment Number:', f'{installment.installment_number}', 'Due Date:', installment.due_date.strftime('%d/%m/%Y') if installment.due_date else 'N/A'],
            ['Invoice Number:', f'INV-{invoice.id}', 'Status:', installment.status or 'Pending']
        ]
        
        installment_header_table = Table(installment_header_data, colWidths=[1.5*inch, 2*inch, 1*inch, 1.5*inch])
        installment_header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        elements.append(installment_header_table)
        elements.append(Spacer(1, 20))
        
        # Student Information
        elements.append(Paragraph("Student Information:", heading_style))
        student_info = [
            ['Student Name:', student.full_name or 'N/A'],
            ['Student ID:', student.student_id or 'N/A'],
            ['Phone:', student.mobile or 'N/A'],
            ['Email:', student.email or 'N/A'],
            ['Course:', course.course_name if course else 'N/A'],
        ]
        
        student_table = Table(student_info, colWidths=[1.5*inch, 4*inch])
        student_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(student_table)
        elements.append(Spacer(1, 20))
        
        # Installment details
        elements.append(Paragraph("Installment Details:", heading_style))
        installment_data = [
            ['Description', 'Amount (₹)'],
            [f'Installment #{installment.installment_number} - {course.course_name if course else "Course Fee"}', f'₹{installment.amount:,.2f}'],
        ]
        
        # Add total row
        installment_data.append(['', ''])
        installment_data.append(['Total Amount:', f'₹{installment.amount:,.2f}'])
        installment_data.append(['Paid Amount:', f'₹{installment.paid_amount:,.2f}'])
        installment_data.append(['Balance Amount:', f'₹{installment.balance_amount:,.2f}'])
        
        installment_table = Table(installment_data, colWidths=[4*inch, 2*inch])
        installment_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, 1), 1, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ]))
        elements.append(installment_table)
        elements.append(Spacer(1, 20))
        
        # Payment History
        if payments:
            elements.append(Paragraph("Payment History:", heading_style))
            payment_data = [['Date', 'Amount (₹)', 'Method', 'Reference']]
            
            for payment in payments:
                payment_data.append([
                    payment.paid_on.strftime('%d/%m/%Y %H:%M'),
                    f'₹{payment.amount:,.2f}',
                    payment.payment_method or 'Cash',
                    payment.utr_number or '-'
                ])
            
            payment_table = Table(payment_data, colWidths=[2*inch, 1.5*inch, 1.5*inch, 1*inch])
            payment_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ]))
            elements.append(payment_table)
        
        # Build PDF
        doc.build(elements)
        
        # Get PDF data
        pdf_data = buffer.getvalue()
        buffer.close()
        
        # Create response
        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=installment_{installment.installment_number}_INV{invoice.id}.pdf'
        
        return response
        
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('installments.view_installment', installment_id=installment_id))
