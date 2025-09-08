"""
Expense Management Routes for Global IT Web Application
Handles expense recording, tracking, and reporting
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from models.expense_model import Expense, ExpenseCategory
from models.expense_audit_model import ExpenseAudit
from models.user_model import User
from models.branch_model import Branch
from utils.auth import login_required
from utils.timezone_helper import (
    utc_to_ist, format_datetime_indian, format_date_indian, 
    format_time_indian, get_current_ist_datetime, get_current_ist_formatted,
    parse_date_string
)
from init_db import db
import os
import uuid
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from sqlalchemy import and_, or_, func, desc

expense_bp = Blueprint("expenses", __name__)

# File upload configuration
UPLOAD_FOLDER = "static/uploads/expenses"
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx'}

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@expense_bp.route("/", methods=["GET"])
@login_required
def expense_dashboard():
    """Expense management dashboard"""
    try:
        user_id = session.get("user_id")
        user_role = session.get("role")
        
        # Date filtering
        date_filter = request.args.get('date_filter', 'this_month')
        start_date = None
        end_date = None
        
        today = date.today()
        
        if date_filter == 'today':
            start_date = end_date = today
        elif date_filter == 'this_week':
            start_date = today - timedelta(days=today.weekday())
            end_date = today
        elif date_filter == 'this_month':
            start_date = today.replace(day=1)
            end_date = today
        elif date_filter == 'last_month':
            if today.month == 1:
                start_date = date(today.year - 1, 12, 1)
                end_date = date(today.year - 1, 12, 31)
            else:
                start_date = date(today.year, today.month - 1, 1)
                # Last day of previous month
                end_date = today.replace(day=1) - timedelta(days=1)
        elif date_filter == 'this_year':
            start_date = date(today.year, 1, 1)
            end_date = today
        
        # Build query
        query = Expense.query.filter(Expense.is_deleted == False)
        
        if start_date and end_date:
            query = query.filter(
                Expense.expense_date >= start_date,
                Expense.expense_date <= end_date
            )
        
        # Branch-based filtering
        user_branch_ids = []
        if user_role in ['admin', 'franchise']:
            # Admin and franchise owners can see all expenses
            pass
        else:
            # Other roles see only their branch expenses
            from models.user_model import User
            user = User.query.get(user_id)
            if user and hasattr(user, 'branch_assignments'):
                user_branch_ids = [assignment.branch_id for assignment in user.branch_assignments]
                if user_branch_ids:
                    query = query.filter(
                        or_(
                            Expense.branch_id.in_(user_branch_ids),
                            Expense.created_by == user_id  # Always show user's own expenses
                        )
                    )
                else:
                    # If no branch assignments, show only user's own expenses
                    query = query.filter(Expense.created_by == user_id)
            else:
                # Fallback to user-created expenses only
                query = query.filter(Expense.created_by == user_id)
        
        expenses = query.order_by(desc(Expense.created_at)).all()
        
        # Calculate summary statistics
        total_expenses = sum(float(exp.total_amount) for exp in expenses)
        paid_expenses = sum(float(exp.total_amount) for exp in expenses if exp.payment_status == 'Paid')
        pending_expenses = sum(float(exp.total_amount) for exp in expenses if exp.payment_status in ['Unpaid', 'Partially Paid'])
        
        # Category-wise breakdown
        category_stats = {}
        for expense in expenses:
            category = expense.expense_category
            if category not in category_stats:
                category_stats[category] = {'count': 0, 'amount': 0}
            category_stats[category]['count'] += 1
            category_stats[category]['amount'] += float(expense.total_amount)
        
        # Recent expenses (last 10)
        recent_expenses = expenses[:10]
        
        # Overdue expenses
        overdue_expenses = [exp for exp in expenses if exp.is_overdue]
        
        return render_template("expenses/dashboard.html",
                             expenses=expenses,
                             recent_expenses=recent_expenses,
                             overdue_expenses=overdue_expenses,
                             total_expenses=total_expenses,
                             paid_expenses=paid_expenses,
                             pending_expenses=pending_expenses,
                             category_stats=category_stats,
                             date_filter=date_filter,
                             expense_categories=Expense.get_expense_categories())
        
    except Exception as e:
        flash(f"Error loading expense dashboard: {str(e)}", "error")
        return render_template("expenses/dashboard.html",
                             expenses=[],
                             recent_expenses=[],
                             overdue_expenses=[],
                             total_expenses=0,
                             paid_expenses=0,
                             pending_expenses=0,
                             category_stats={},
                             date_filter='this_month',
                             expense_categories=Expense.get_expense_categories())

@expense_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_expense():
    """Add new expense"""
    if request.method == "GET":
        from utils.timezone_helper import get_current_ist_datetime
        current_date = get_current_ist_datetime().date()
        
        # Get user's branch information
        user_id = session.get("user_id")
        user_role = session.get("role")
        
        user_branches = []
        can_select_branch = user_role in ['admin', 'franchise']
        
        if can_select_branch:
            # Admin/franchise can select any active branch
            from models.branch_model import Branch
            branches = Branch.query.filter(
                Branch.is_deleted == 0,
                Branch.status == 'Active'
            ).all()
            user_branches = [{'id': b.id, 'name': f"{b.branch_name} ({b.branch_code})"} for b in branches]
        else:
            # Other users get their assigned branches
            from models.user_model import User
            user = User.query.get(user_id)
            if user and hasattr(user, 'branch_assignments'):
                for assignment in user.branch_assignments:
                    if assignment.branch.status == 'Active':
                        user_branches.append({
                            'id': assignment.branch_id,
                            'name': f"{assignment.branch.branch_name} ({assignment.branch.branch_code})"
                        })
        
        return render_template("expenses/add_expense.html",
                             current_date=current_date,
                             user_branches=user_branches,
                             can_select_branch=can_select_branch,
                             expense_categories=Expense.get_expense_categories(),
                             payment_methods=Expense.get_payment_methods(),
                             payment_statuses=Expense.get_payment_statuses(),
                             ledger_accounts=Expense.get_ledger_accounts(),
                             branch_locations=Expense.get_branch_locations(),
                             departments=Expense.get_departments())
    
    try:
        form = request.form
        user_id = session.get("user_id")
        
        # Handle file upload
        attachment_filename = None
        attachment_path = None
        
        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Add timestamp to avoid conflicts
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{timestamp}_{filename}"
                
                # Ensure upload directory exists
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                
                attachment_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(attachment_path)
                attachment_filename = filename
        
        # Parse and validate form data
        expense_date = parse_date_string(form.get("expense_date")) if form.get("expense_date") else date.today()
        amount = Decimal(form.get("amount", "0.00"))
        gst_percentage = Decimal(form.get("gst_percentage", "0.00"))
        
        # Get user's branch assignment
        user_branch_id = None
        selected_branch_id = form.get("branch_id")  # From form selection
        
        # If branch is selected in form, use that (admin/franchise can select any branch)
        if selected_branch_id and selected_branch_id.isdigit():
            user_branch_id = int(selected_branch_id)
        else:
            # Auto-assign based on user's role and branch access
            from models.user_model import User
            user = User.query.get(user_id)
            if user:
                # Check if user has branch assignments
                if hasattr(user, 'branch_assignments') and user.branch_assignments:
                    # Use the first assigned branch
                    user_branch_id = user.branch_assignments[0].branch_id
                elif session.get('role') in ['admin', 'franchise']:
                    # Admin/franchise can create expenses without specific branch
                    user_branch_id = None
        
        # Create new expense
        expense = Expense(
            expense_date=expense_date,
            expense_category=form.get("expense_category"),
            description=form.get("description"),
            vendor_supplier=form.get("vendor_supplier"),
            invoice_bill_number=form.get("invoice_bill_number"),
            payment_method=form.get("payment_method"),
            amount=amount,
            gst_percentage=gst_percentage,
            payment_status=form.get("payment_status", "Unpaid"),
            linked_ledger_account=form.get("linked_ledger_account"),
            branch_id=user_branch_id,
            branch_location=form.get("branch_location"),
            department_project=form.get("department_project"),
            attachment_filename=attachment_filename,
            attachment_path=attachment_path,
            notes=form.get("notes"),
            created_by=user_id
        )
        
        # Auto-calculate GST and total
        expense.calculate_gst_and_total()
        
        db.session.add(expense)
        db.session.commit()
        
        # Log audit trail for expense creation
        try:
            ExpenseAudit.log_expense_change(
                expense_record=expense,
                changed_by_user_id=user_id,
                action_type='CREATE',
                change_reason='New expense created',
                request=request,
                file_operation='UPLOAD' if attachment_filename else None,
                file_info={'name': attachment_filename, 'path': attachment_path} if attachment_filename else None
            )
        except Exception as audit_error:
            print(f"Audit logging failed for expense creation {expense.expense_id}: {str(audit_error)}")
        
        flash(f"Expense {expense.expense_id} added successfully!", "success")
        return redirect(url_for("expenses.expense_dashboard"))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding expense: {str(e)}", "error")
        return render_template("expenses/add_expense.html",
                             expense_categories=Expense.get_expense_categories(),
                             payment_methods=Expense.get_payment_methods(),
                             payment_statuses=Expense.get_payment_statuses(),
                             ledger_accounts=Expense.get_ledger_accounts(),
                             branch_locations=Expense.get_branch_locations(),
                             departments=Expense.get_departments())

@expense_bp.route("/view/<expense_id>", methods=["GET"])
@login_required
def view_expense(expense_id):
    """View expense details"""
    try:
        user_id = session.get("user_id")
        user_role = session.get("role")
        
        expense = Expense.query.filter(
            Expense.expense_id == expense_id,
            Expense.is_deleted == False
        ).first()
        
        if not expense:
            flash("Expense not found!", "error")
            return redirect(url_for("expenses.expense_dashboard"))
        
        # Check permission
        if user_role not in ['admin', 'franchise'] and expense.created_by != user_id:
            flash("You don't have permission to view this expense!", "error")
            return redirect(url_for("expenses.expense_dashboard"))
        
        # Get creator details
        creator = User.query.get(expense.created_by)
        
        return render_template("expenses/view_expense.html",
                             expense=expense,
                             creator=creator)
        
    except Exception as e:
        flash(f"Error viewing expense: {str(e)}", "error")
        return redirect(url_for("expenses.expense_dashboard"))

@expense_bp.route("/edit/<expense_id>", methods=["GET", "POST"])
@login_required
def edit_expense(expense_id):
    """Edit expense details"""
    try:
        user_id = session.get("user_id")
        user_role = session.get("role")
        
        expense = Expense.query.filter(
            Expense.expense_id == expense_id,
            Expense.is_deleted == False
        ).first()
        
        if not expense:
            flash("Expense not found!", "error")
            return redirect(url_for("expenses.expense_dashboard"))
        
        # Check permission
        if user_role not in ['admin', 'franchise'] and expense.created_by != user_id:
            flash("You don't have permission to edit this expense!", "error")
            return redirect(url_for("expenses.expense_dashboard"))
        
        if request.method == "GET":
            return render_template("expenses/edit_expense.html",
                                 expense=expense,
                                 expense_categories=Expense.get_expense_categories(),
                                 payment_methods=Expense.get_payment_methods(),
                                 payment_statuses=Expense.get_payment_statuses(),
                                 ledger_accounts=Expense.get_ledger_accounts(),
                                 branch_locations=Expense.get_branch_locations(),
                                 departments=Expense.get_departments())
        
        # POST request - update expense
        form = request.form
        
        # Capture original values for audit trail
        original_data = {
            'expense_date': expense.expense_date.isoformat() if expense.expense_date else None,
            'expense_category': expense.expense_category,
            'description': expense.description,
            'vendor_supplier': expense.vendor_supplier,
            'invoice_bill_number': expense.invoice_bill_number,
            'payment_method': expense.payment_method,
            'amount': float(expense.amount) if expense.amount else 0,
            'gst_percentage': float(expense.gst_percentage) if expense.gst_percentage else 0,
            'gst_amount': float(expense.gst_amount) if expense.gst_amount else 0,
            'total_amount': float(expense.total_amount) if expense.total_amount else 0,
            'payment_status': expense.payment_status,
            'linked_ledger_account': expense.linked_ledger_account,
            'branch_location': expense.branch_location,
            'department_project': expense.department_project,
            'notes': expense.notes,
            'attachment_filename': expense.attachment_filename,
            'attachment_path': expense.attachment_path
        }
        
        # Track field changes for audit
        field_changes = {}
        change_reason = form.get('change_reason', 'Expense details updated')
        
        # Handle new file upload
        file_operation = None
        file_info = None
        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{timestamp}_{filename}"
                
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                
                attachment_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(attachment_path)
                
                # Track file changes
                if expense.attachment_filename:
                    file_operation = 'REPLACE'
                    field_changes['attachment_filename'] = {
                        'old': expense.attachment_filename,
                        'new': filename
                    }
                else:
                    file_operation = 'UPLOAD'
                
                file_info = {'name': filename, 'path': attachment_path}
                
                # Delete old file if exists
                if expense.attachment_path and os.path.exists(expense.attachment_path):
                    try:
                        os.remove(expense.attachment_path)
                    except:
                        pass  # Continue if file deletion fails
                
                expense.attachment_filename = filename
                expense.attachment_path = attachment_path
        
        # Track field changes
        new_expense_date = parse_date_string(form.get("expense_date")) if form.get("expense_date") else expense.expense_date
        if new_expense_date != expense.expense_date:
            field_changes['expense_date'] = {
                'old': expense.expense_date.isoformat() if expense.expense_date else None,
                'new': new_expense_date.isoformat() if new_expense_date else None
            }
        
        new_amount = Decimal(form.get("amount", str(expense.amount)))
        if new_amount != expense.amount:
            field_changes['amount'] = {
                'old': float(expense.amount),
                'new': float(new_amount)
            }
        
        new_payment_status = form.get("payment_status", expense.payment_status)
        if new_payment_status != expense.payment_status:
            field_changes['payment_status'] = {
                'old': expense.payment_status,
                'new': new_payment_status
            }
        
        # Track other significant field changes
        fields_to_track = [
            'expense_category', 'description', 'vendor_supplier', 
            'invoice_bill_number', 'payment_method', 'gst_percentage',
            'linked_ledger_account', 'branch_location', 'department_project', 'notes'
        ]
        
        for field in fields_to_track:
            new_value = form.get(field, getattr(expense, field, ''))
            old_value = getattr(expense, field, '')
            if str(new_value) != str(old_value):
                field_changes[field] = {
                    'old': str(old_value),
                    'new': str(new_value)
                }
        
        # Update expense fields
        expense.expense_date = new_expense_date
        expense.expense_category = form.get("expense_category", expense.expense_category)
        expense.description = form.get("description", expense.description)
        expense.vendor_supplier = form.get("vendor_supplier", expense.vendor_supplier)
        expense.invoice_bill_number = form.get("invoice_bill_number", expense.invoice_bill_number)
        expense.payment_method = form.get("payment_method", expense.payment_method)
        expense.amount = new_amount
        expense.gst_percentage = Decimal(form.get("gst_percentage", str(expense.gst_percentage)))
        expense.payment_status = new_payment_status
        expense.linked_ledger_account = form.get("linked_ledger_account", expense.linked_ledger_account)
        expense.branch_location = form.get("branch_location", expense.branch_location)
        expense.department_project = form.get("department_project", expense.department_project)
        expense.notes = form.get("notes", expense.notes)
        expense.updated_by = user_id
        
        # Recalculate totals
        expense.update_totals()
        
        db.session.commit()
        
        # Log audit trail for expense update
        if field_changes:  # Only log if there were actual changes
            try:
                ExpenseAudit.log_expense_change(
                    expense_record=expense,
                    changed_by_user_id=user_id,
                    action_type='UPDATE',
                    change_reason=change_reason,
                    field_changes=field_changes,
                    request=request,
                    old_record_data=original_data,
                    file_operation=file_operation,
                    file_info=file_info
                )
            except Exception as audit_error:
                print(f"Audit logging failed for expense update {expense.expense_id}: {str(audit_error)}")
        
        flash(f"Expense {expense.expense_id} updated successfully!", "success")
        return redirect(url_for("expenses.view_expense", expense_id=expense_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating expense: {str(e)}", "error")
        return redirect(url_for("expenses.edit_expense", expense_id=expense_id))

@expense_bp.route("/delete/<expense_id>", methods=["POST"])
@login_required
def delete_expense(expense_id):
    """Soft delete expense"""
    try:
        user_id = session.get("user_id")
        user_role = session.get("role")
        
        expense = Expense.query.filter(
            Expense.expense_id == expense_id,
            Expense.is_deleted == False
        ).first()
        
        if not expense:
            flash("Expense not found!", "error")
            return redirect(url_for("expenses.expense_dashboard"))
        
        # Check permission
        if user_role not in ['admin', 'franchise'] and expense.created_by != user_id:
            flash("You don't have permission to delete this expense!", "error")
            return redirect(url_for("expenses.expense_dashboard"))
        
        # Capture expense data before deletion for audit trail
        deletion_reason = request.form.get('deletion_reason', 'Expense deleted')
        original_data = {
            'expense_id': expense.expense_id,
            'expense_date': expense.expense_date.isoformat() if expense.expense_date else None,
            'expense_category': expense.expense_category,
            'description': expense.description,
            'vendor_supplier': expense.vendor_supplier,
            'invoice_bill_number': expense.invoice_bill_number,
            'payment_method': expense.payment_method,
            'amount': float(expense.amount) if expense.amount else 0,
            'total_amount': float(expense.total_amount) if expense.total_amount else 0,
            'payment_status': expense.payment_status,
            'branch_id': expense.branch_id,
            'created_by': expense.created_by
        }
        
        expense.soft_delete(user_id)
        db.session.commit()
        
        # Log audit trail for expense deletion
        try:
            ExpenseAudit.log_expense_change(
                expense_record=expense,
                changed_by_user_id=user_id,
                action_type='DELETE',
                change_reason=deletion_reason,
                request=request,
                old_record_data=original_data
            )
        except Exception as audit_error:
            print(f"Audit logging failed for expense deletion {expense.expense_id}: {str(audit_error)}")
        
        flash(f"Expense {expense.expense_id} deleted successfully!", "success")
        return redirect(url_for("expenses.expense_dashboard"))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting expense: {str(e)}", "error")
        return redirect(url_for("expenses.expense_dashboard"))

@expense_bp.route("/reports", methods=["GET"])
@login_required
def expense_reports():
    """Expense reports and analytics"""
    try:
        user_id = session.get("user_id")
        user_role = session.get("role")
        
        # Date range filtering
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        category_filter = request.args.get('category')
        status_filter = request.args.get('status')
        branch_filter = request.args.get('branch_location')  # Support branch filtering
        
        # Default to current month
        today = date.today()
        start_date = parse_date_string(start_date_str) if start_date_str else today.replace(day=1)
        end_date = parse_date_string(end_date_str) if end_date_str else today
        
        # Build query
        query = Expense.query.filter(
            Expense.is_deleted == False,
            Expense.expense_date >= start_date,
            Expense.expense_date <= end_date
        )
        
        if category_filter and category_filter != 'all':
            query = query.filter(Expense.expense_category == category_filter)
        
        if status_filter and status_filter != 'all':
            query = query.filter(Expense.payment_status == status_filter)
        
        if branch_filter and branch_filter != 'all' and branch_filter.isdigit():
            # Filter by branch_id (from dropdown selection)
            query = query.filter(Expense.branch_id == int(branch_filter))
        
        # Branch-based filtering (same as dashboard)
        user_branch_ids = []
        if user_role in ['admin', 'franchise']:
            # Admin and franchise owners can see all expenses
            pass
        else:
            # Other roles see only their branch expenses
            from models.user_model import User
            user = User.query.get(user_id)
            if user and hasattr(user, 'branch_assignments'):
                user_branch_ids = [assignment.branch_id for assignment in user.branch_assignments]
                if user_branch_ids:
                    query = query.filter(
                        or_(
                            Expense.branch_id.in_(user_branch_ids),
                            Expense.created_by == user_id  # Always show user's own expenses
                        )
                    )
                else:
                    # If no branch assignments, show only user's own expenses
                    query = query.filter(Expense.created_by == user_id)
            else:
                # Fallback to user-created expenses only
                query = query.filter(Expense.created_by == user_id)
        
        expenses = query.order_by(desc(Expense.expense_date)).all()
        
        # Generate analytics
        total_amount = sum(float(exp.total_amount) for exp in expenses)
        total_gst = sum(float(exp.gst_amount) for exp in expenses)
        
        # Category-wise analysis
        category_analysis = {}
        for exp in expenses:
            cat = exp.expense_category
            if cat not in category_analysis:
                category_analysis[cat] = {'count': 0, 'amount': 0, 'gst': 0}
            category_analysis[cat]['count'] += 1
            category_analysis[cat]['amount'] += float(exp.total_amount)
            category_analysis[cat]['gst'] += float(exp.gst_amount)
        
        # Monthly trends
        monthly_trends = {}
        for exp in expenses:
            month_key = exp.expense_date.strftime('%Y-%m')
            if month_key not in monthly_trends:
                monthly_trends[month_key] = {'count': 0, 'amount': 0}
            monthly_trends[month_key]['count'] += 1
            monthly_trends[month_key]['amount'] += float(exp.total_amount)
        
        # Payment status breakdown
        status_breakdown = {
            'Paid': {'count': 0, 'amount': 0},
            'Unpaid': {'count': 0, 'amount': 0},
            'Partially Paid': {'count': 0, 'amount': 0}
        }
        
        for exp in expenses:
            status = exp.payment_status
            if status in status_breakdown:
                status_breakdown[status]['count'] += 1
                status_breakdown[status]['amount'] += float(exp.total_amount)
        
        # Calculate unpaid amount
        unpaid_amount = status_breakdown['Unpaid']['amount'] + status_breakdown['Partially Paid']['amount']
        
        # Create summary object
        summary = {
            'total_count': len(expenses),
            'total_amount': total_amount,
            'total_gst': total_gst,
            'unpaid_amount': unpaid_amount
        }
        
        # Prepare data for charts
        category_data = {cat: data['amount'] for cat, data in category_analysis.items()}
        monthly_data = {month: data['amount'] for month, data in monthly_trends.items()}
        
        # Get available branches for filtering
        from models.branch_model import Branch
        if user_role in ['admin', 'franchise']:
            # Admin/franchise can see all branches
            available_branches = Branch.query.filter(
                Branch.is_deleted == 0,
                Branch.status == 'Active'
            ).all()
        else:
            # Other users see only their assigned branches
            available_branches = []
            from models.user_model import User
            user = User.query.get(user_id)
            if user and hasattr(user, 'branch_assignments'):
                for assignment in user.branch_assignments:
                    if assignment.branch.status == 'Active':
                        available_branches.append(assignment.branch)
        
        return render_template("expenses/reports.html",
                             expenses=expenses,
                             summary=summary,
                             start_date=start_date,
                             end_date=end_date,
                             category_filter=category_filter,
                             status_filter=status_filter,
                             branch_filter=branch_filter,
                             available_branches=available_branches,
                             category_data=category_data,
                             monthly_data=monthly_data,
                             category_analysis=category_analysis,
                             monthly_trends=monthly_trends,
                             status_breakdown=status_breakdown,
                             expense_categories=Expense.get_expense_categories(),
                             payment_statuses=Expense.get_payment_statuses())
        
    except Exception as e:
        flash(f"Error generating expense reports: {str(e)}", "error")
        
        # Create empty summary for error case
        summary = {
            'total_count': 0,
            'total_amount': 0,
            'total_gst': 0,
            'unpaid_amount': 0
        }
        
        # Get available branches for error case too
        from models.branch_model import Branch
        available_branches = Branch.query.filter(
            Branch.is_deleted == 0,
            Branch.status == 'Active'
        ).all()
        
        return render_template("expenses/reports.html",
                             expenses=[],
                             summary=summary,
                             start_date=date.today().replace(day=1),
                             end_date=date.today(),
                             category_filter='all',
                             status_filter='all',
                             branch_filter='all',
                             available_branches=available_branches,
                             category_data={},
                             monthly_data={},
                             category_analysis={},
                             monthly_trends={},
                             status_breakdown={},
                             expense_categories=Expense.get_expense_categories(),
                             payment_statuses=Expense.get_payment_statuses())

@expense_bp.route("/api/calculate_gst", methods=["POST"])
@login_required
def calculate_gst_api():
    """API endpoint to calculate GST amount"""
    try:
        data = request.get_json()
        amount = Decimal(str(data.get('amount', 0)))
        gst_percentage = Decimal(str(data.get('gst_percentage', 0)))
        
        gst_amount = (amount * gst_percentage) / 100
        total_amount = amount + gst_amount
        
        return jsonify({
            'success': True,
            'gst_amount': float(gst_amount),
            'total_amount': float(total_amount),
            'formatted_gst_amount': f"₹{gst_amount:,.2f}",
            'formatted_total_amount': f"₹{total_amount:,.2f}"
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@expense_bp.route("/download_attachment/<expense_id>")
@login_required
def download_attachment(expense_id):
    """Download expense attachment"""
    try:
        user_id = session.get("user_id")
        user_role = session.get("role")
        
        expense = Expense.query.filter(
            Expense.expense_id == expense_id,
            Expense.is_deleted == False
        ).first()
        
        if not expense:
            flash("Expense not found!", "error")
            return redirect(url_for("expenses.expense_dashboard"))
        
        # Check permission
        if user_role not in ['admin', 'franchise'] and expense.created_by != user_id:
            flash("You don't have permission to access this file!", "error")
            return redirect(url_for("expenses.expense_dashboard"))
        
        if not expense.attachment_path or not os.path.exists(expense.attachment_path):
            flash("Attachment file not found!", "error")
            return redirect(url_for("expenses.view_expense", expense_id=expense_id))
        
        from flask import send_file
        return send_file(expense.attachment_path, as_attachment=True, 
                        download_name=expense.attachment_filename)
        
    except Exception as e:
        flash(f"Error downloading attachment: {str(e)}", "error")
        return redirect(url_for("expenses.view_expense", expense_id=expense_id))

@expense_bp.route("/audit", methods=["GET"])
@login_required
def expense_audit():
    """View expense audit trail"""
    try:
        user_id = session.get("user_id")
        user_role = session.get("role")
        
        # Only admin and franchise can view audit logs
        if user_role not in ['admin', 'franchise']:
            flash("You don't have permission to view audit logs!", "error")
            return redirect(url_for("expenses.expense_dashboard"))
        
        # Get filter parameters
        expense_filter = request.args.get('expense_id')
        user_filter = request.args.get('user_id')
        action_filter = request.args.get('action_type')
        days_filter = int(request.args.get('days', 7))
        
        # Build audit query
        query = ExpenseAudit.query
        
        if expense_filter:
            query = query.filter(ExpenseAudit.expense_reference.like(f'%{expense_filter}%'))
        
        if user_filter and user_filter.isdigit():
            query = query.filter(ExpenseAudit.changed_by == int(user_filter))
        
        if action_filter and action_filter != 'all':
            query = query.filter(ExpenseAudit.action_type == action_filter)
        
        # Date range filter
        if days_filter > 0:
            from datetime import timedelta
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_filter)
            query = query.filter(ExpenseAudit.changed_at >= cutoff_date)
        
        # Get audit records
        audit_records = query.order_by(ExpenseAudit.changed_at.desc()).limit(500).all()
        
        # Get users for filter dropdown
        users = User.query.filter(User.is_deleted == False).all()
        
        # Get available action types
        action_types = ['CREATE', 'UPDATE', 'DELETE', 'APPROVE', 'REJECT']
        
        return render_template("expenses/audit.html",
                             audit_records=audit_records,
                             users=users,
                             action_types=action_types,
                             expense_filter=expense_filter,
                             user_filter=user_filter,
                             action_filter=action_filter,
                             days_filter=days_filter)
        
    except Exception as e:
        flash(f"Error loading audit trail: {str(e)}", "error")
        return redirect(url_for("expenses.expense_dashboard"))

@expense_bp.route("/audit/<int:expense_id>", methods=["GET"])
@login_required
def expense_audit_detail(expense_id):
    """View detailed audit trail for a specific expense"""
    try:
        user_id = session.get("user_id")
        user_role = session.get("role")
        
        # Get the expense
        expense = Expense.query.get(expense_id)
        if not expense:
            flash("Expense not found!", "error")
            return redirect(url_for("expenses.expense_dashboard"))
        
        # Check permission to view this expense
        if user_role not in ['admin', 'franchise'] and expense.created_by != user_id:
            flash("You don't have permission to view this expense audit!", "error")
            return redirect(url_for("expenses.expense_dashboard"))
        
        # Get audit trail for this expense
        audit_records = ExpenseAudit.get_expense_audit_trail(expense_id)
        
        return render_template("expenses/audit_detail.html",
                             expense=expense,
                             audit_records=audit_records)
        
    except Exception as e:
        flash(f"Error loading expense audit detail: {str(e)}", "error")
        return redirect(url_for("expenses.expense_dashboard"))
