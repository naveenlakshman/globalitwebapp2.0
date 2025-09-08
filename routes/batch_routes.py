from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from models.batch_model import Batch
from models.branch_model import Branch
from models.student_model import Student
from models.user_model import User
from models.course_model import Course
from models.batch_trainer_assignment_model import BatchTrainerAssignment
from models.student_batch_completion_model import StudentBatchCompletion
from models.system_audit_logs_model import SystemAuditLog
from utils.auth import login_required
from utils.search_utils import search_students_for_batch
from init_db import db
from datetime import datetime, timezone

batch_bp = Blueprint('batches', __name__, url_prefix='/batches')

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

@batch_bp.route('/')
@login_required
def list_batches():
    """List all batches with role-based branch filtering"""
    try:
        current_user_id = session.get('user_id')
        current_user = User.query.get(current_user_id)
        
        # Base query for all batches except archived (include cancelled for audit)
        query = Batch.query.filter(Batch.status.in_(['Active', 'Completed', 'Suspended', 'Cancelled']))
        
        # Get all batches including archived for statistics display only
        all_batches_for_stats = Batch.query.all()
        
        # Apply role-based branch filtering
        if current_user.role == 'franchise':
            # Franchise owners - only their assigned branches
            user_branches = get_user_branch_ids(current_user.id)
            if user_branches:
                query = query.filter(Batch.branch_id.in_(user_branches))
            else:
                # No branch assignments, show no batches
                query = query.filter(Batch.id == -1)
        elif current_user.role == 'regional_manager':
            # Regional managers - their assigned branches (Mumbai + Delhi)
            user_branches = get_user_branch_ids(current_user.id)
            if user_branches:
                query = query.filter(Batch.branch_id.in_(user_branches))
            else:
                # No branch assignments, show no batches
                query = query.filter(Batch.id == -1)
        elif current_user.role in ['branch_manager', 'staff']:
            # Branch-level users (except trainers) - only their specific branch
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                query = query.filter_by(branch_id=user_branch_id)
        elif current_user.role == 'trainer':
            # Trainers - only their assigned batches
            trainer_assignments = BatchTrainerAssignment.get_trainer_batches(current_user.id, active_only=True)
            assigned_batch_ids = [assignment.batch_id for assignment in trainer_assignments]
            if assigned_batch_ids:
                query = query.filter(Batch.id.in_(assigned_batch_ids))
            else:
                # No batch assignments, show no batches
                query = query.filter(Batch.id == -1)
        # Admin sees all batches
        
        batches = query.order_by(Batch.start_date.desc()).all()
        
        # Get data for filters - Apply same role-based filtering
        if current_user.role == 'admin':
            # Admin sees all data
            branches = Branch.query.all()
            trainers = User.query.filter_by(role='trainer').order_by(User.full_name).all()
        elif current_user.role in ['franchise', 'regional_manager']:
            # Franchise/Regional managers - only their assigned branches
            user_branches = get_user_branch_ids(current_user.id)
            if user_branches:
                branches = Branch.query.filter(Branch.id.in_(user_branches)).all()
                # Get trainers from those branches only
                trainers = User.query.filter(
                    User.role.in_(['trainer', 'branch_manager']),
                    User.is_deleted == 0
                ).all()
                # Filter trainers by branch access
                filtered_trainers = []
                for trainer in trainers:
                    trainer_branches = get_user_branch_ids(trainer.id)
                    if any(branch_id in user_branches for branch_id in trainer_branches):
                        filtered_trainers.append(trainer)
                trainers = filtered_trainers
            else:
                branches = []
                trainers = []
        elif current_user.role in ['branch_manager', 'staff']:
            # Branch-level users (except trainers) - only their specific branch
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                branches = Branch.query.filter_by(id=user_branch_id).all()
                # Get trainers from the same branch
                trainers = User.query.filter(
                    User.role.in_(['trainer', 'branch_manager']),
                    User.is_deleted == 0
                ).all()
                # Filter trainers by branch
                filtered_trainers = []
                for trainer in trainers:
                    trainer_branches = get_user_branch_ids(trainer.id)
                    if user_branch_id in trainer_branches:
                        filtered_trainers.append(trainer)
                trainers = filtered_trainers
            else:
                branches = []
                trainers = []
        elif current_user.role == 'trainer':
            # Trainers - show only their assigned batches data
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                branches = Branch.query.filter_by(id=user_branch_id).all()
            else:
                branches = []
            # For trainers, only show themselves in the trainer filter
            trainers = [current_user]
        else:
            branches = []
            trainers = []
        
        # Get courses - only active courses
        courses = Course.query.filter_by(is_deleted=0, status='Active').order_by(Course.course_name).all()
        
        return render_template("batches/list_batches.html", 
                             batches=batches, 
                             all_batches=all_batches_for_stats,
                             branches=branches,
                             courses=courses,
                             trainers=trainers,
                             current_user=current_user)
        
    except Exception as e:
        flash(f'Error loading batches: {str(e)}', 'error')
        return redirect(url_for('dashboard_bp.franchise_dashboard'))

@batch_bp.route('/create')
@login_required
def create_batch_form():
    """Show form to create a new batch"""
    try:
        current_user = User.query.get(session['user_id'])
        
        # Get branches user can create batches for
        if current_user.role in ['franchise', 'regional_manager']:
            user_branches = get_user_branch_ids(current_user.id)
            branches = Branch.query.filter(Branch.id.in_(user_branches)).all() if user_branches else []
        elif current_user.role in ['branch_manager', 'staff']:
            # Branch-level users can only create in their branch
            user_branch_id = session.get("user_branch_id")
            branches = Branch.query.filter_by(id=user_branch_id).all() if user_branch_id else []
        else:
            # Admin sees all branches
            branches = Branch.query.all()
        
        # Get active courses for dropdown
        courses = Course.query.filter_by(is_deleted=0, status='Active').order_by(Course.course_name).all()
        
        return render_template('batches/create_batch.html', branches=branches, courses=courses)
        
    except Exception as e:
        flash(f'Error loading create form: {str(e)}', 'error')
        return redirect(url_for('batches.list_batches'))

@batch_bp.route('/create', methods=['POST'])
@login_required
def create_batch():
    """Create a new batch with validation"""
    try:
        current_user = User.query.get(session['user_id'])
        
        # Get form data
        name = request.form.get('name', '').strip()
        course_id = request.form.get('course_id')  # Changed from course_name to course_id
        branch_id = request.form.get('branch_id')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        timing = request.form.get('timing', '').strip()  # Now optional, for additional notes
        checkin_time = request.form.get('checkin_time')   # New required field
        checkout_time = request.form.get('checkout_time') # New required field
        
        # Validate required fields
        if not all([name, course_id, branch_id, start_date, checkin_time, checkout_time]):
            flash('Name, Course, Branch, Start Date, Check-in Time, and Check-out Time are required.', 'error')
            return redirect(url_for('batches.create_batch_form'))
        
        # Validate time fields
        from datetime import datetime
        try:
            if not checkin_time or not checkout_time:
                flash('Both check-in and check-out times are required.', 'error')
                return redirect(url_for('batches.create_batch_form'))
                
            checkin_dt = datetime.strptime(checkin_time.strip(), '%H:%M').time()
            checkout_dt = datetime.strptime(checkout_time.strip(), '%H:%M').time()
            
            if checkout_dt <= checkin_dt:
                flash('Check-out time must be after check-in time.', 'error')
                return redirect(url_for('batches.create_batch_form'))
        except ValueError as e:
            flash(f'Invalid time format. Please use HH:MM format (e.g., 09:30). Error: {str(e)}', 'error')
            return redirect(url_for('batches.create_batch_form'))
        
        # Get course name from course_id
        course = Course.query.get(course_id)
        if not course:
            flash('Invalid course selected.', 'error')
            return redirect(url_for('batches.create_batch_form'))
        
        # Validate branch access
        if current_user.role in ['franchise', 'regional_manager']:
            user_branches = get_user_branch_ids(current_user.id)
            if int(branch_id) not in user_branches:
                flash('You do not have permission to create batches for this branch.', 'error')
                return redirect(url_for('batches.list_batches'))
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if int(branch_id) != user_branch_id:
                flash('You can only create batches for your branch.', 'error')
                return redirect(url_for('batches.list_batches'))
        
        # Create new batch
        batch = Batch(
            name=name,
            course_id=int(course_id),         # Use course_id for proper relationship
            course_name=course.course_name,   # Keep for backward compatibility during migration
            branch_id=int(branch_id),
            start_date=start_date,
            end_date=end_date,
            timing=timing,                    # Optional additional notes
            checkin_time=checkin_dt,          # New required field
            checkout_time=checkout_dt         # New required field
        )
        
        db.session.add(batch)
        db.session.flush()  # Flush to get batch.id before commit
        
        # Handle trainer assignments
        primary_trainer_id = request.form.get('primary_trainer_id')
        assistant_trainer_id = request.form.get('assistant_trainer_id')
        trainer_notes = request.form.get('trainer_notes', '').strip()
        
        # Assign primary trainer if selected
        if primary_trainer_id:
            primary_assignment = BatchTrainerAssignment(
                batch_id=batch.id,
                trainer_id=int(primary_trainer_id),
                assigned_by=current_user.id,
                role_in_batch='Primary Trainer',
                notes=trainer_notes if trainer_notes else f'Primary trainer for {batch.name}'
            )
            db.session.add(primary_assignment)
        
        # Assign assistant trainer if selected and different from primary
        if assistant_trainer_id and assistant_trainer_id != primary_trainer_id:
            assistant_assignment = BatchTrainerAssignment(
                batch_id=batch.id,
                trainer_id=int(assistant_trainer_id),
                assigned_by=current_user.id,
                role_in_batch='Assistant Trainer',
                notes=trainer_notes if trainer_notes else f'Assistant trainer for {batch.name}'
            )
            db.session.add(assistant_assignment)
        
        db.session.commit()
        
        flash('Batch created successfully with trainer assignments!', 'success')
        return redirect(url_for('batches.view_batch', batch_id=batch.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating batch: {str(e)}', 'error')
        return redirect(url_for('batches.create_batch_form'))

@batch_bp.route('/<int:batch_id>')
@login_required
def view_batch(batch_id):
    """View batch details with associated students"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Check if batch is deleted
        if batch.is_deleted:
            flash('This batch has been deleted.', 'error')
            return redirect(url_for('batches.list_batches'))
        
        # Validate branch access
        if current_user.role in ['franchise', 'regional_manager']:
            user_branches = get_user_branch_ids(current_user.id)
            if batch.branch_id not in user_branches:
                flash('You do not have permission to view this batch.', 'error')
                return redirect(url_for('batches.list_batches'))
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if batch.branch_id != user_branch_id:
                flash('You can only view batches from your branch.', 'error')
                return redirect(url_for('batches.list_batches'))
        elif current_user.role == 'trainer':
            # Trainers can only view batches they are assigned to
            if not BatchTrainerAssignment.is_trainer_assigned_to_batch(batch_id, current_user.id):
                flash('You can only view batches you are assigned to.', 'error')
                return redirect(url_for('batches.list_batches'))
        
        # Get students in this batch
        students = Student.query.filter_by(batch_id=batch_id, is_deleted=0).order_by(Student.full_name).all()
        
        # Get trainers assigned to this batch
        trainers = BatchTrainerAssignment.get_batch_trainers(batch_id, active_only=True)
        
        # Get available trainers for assignment
        available_trainers = BatchTrainerAssignment.get_available_trainers_for_batch(batch_id, batch.branch_id)
        
        return render_template('batches/view_batch.html', 
                             batch=batch, 
                             students=students, 
                             trainers=trainers,
                             available_trainers=available_trainers)
        
    except Exception as e:
        flash(f'Error loading batch: {str(e)}', 'error')
        return redirect(url_for('batches.list_batches'))

@batch_bp.route('/<int:batch_id>/edit')
@login_required
def edit_batch_form(batch_id):
    """Show form to edit batch details"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Check if batch is deleted
        if batch.is_deleted:
            flash('This batch has been deleted and cannot be edited.', 'error')
            return redirect(url_for('batches.list_batches'))
        
        # Validate branch access
        if current_user.role in ['franchise', 'regional_manager']:
            user_branches = get_user_branch_ids(current_user.id)
            if batch.branch_id not in user_branches:
                flash('You do not have permission to edit this batch.', 'error')
                return redirect(url_for('batches.list_batches'))
            branches = Branch.query.filter(Branch.id.in_(user_branches)).all()
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if batch.branch_id != user_branch_id:
                flash('You can only edit batches from your branch.', 'error')
                return redirect(url_for('batches.list_batches'))
            branches = Branch.query.filter_by(id=user_branch_id).all()
        else:
            # Admin can edit any batch
            branches = Branch.query.all()
        
        # Get active courses for dropdown
        courses = Course.query.filter_by(is_deleted=0, status='Active').order_by(Course.course_name).all()
        
        # Get current trainer assignments
        trainer_assignments = BatchTrainerAssignment.query.filter_by(
            batch_id=batch_id, 
            is_active=1
        ).join(User, BatchTrainerAssignment.trainer_id == User.id).all()
        
        return render_template('batches/edit_batch.html', 
                             batch=batch, 
                             branches=branches, 
                             courses=courses,
                             trainer_assignments=trainer_assignments)
        
    except Exception as e:
        flash(f'Error loading edit form: {str(e)}', 'error')
        return redirect(url_for('batches.list_batches'))

@batch_bp.route('/<int:batch_id>/edit', methods=['POST'])
@login_required
def edit_batch(batch_id):
    """Update batch details with validation"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Check if batch is deleted
        if batch.is_deleted:
            flash('This batch has been deleted and cannot be edited.', 'error')
            return redirect(url_for('batches.list_batches'))
        
        # Validate current batch access
        if current_user.role in ['franchise', 'regional_manager']:
            user_branches = get_user_branch_ids(current_user.id)
            if batch.branch_id not in user_branches:
                flash('You do not have permission to edit this batch.', 'error')
                return redirect(url_for('batches.list_batches'))
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if batch.branch_id != user_branch_id:
                flash('You can only edit batches from your branch.', 'error')
                return redirect(url_for('batches.list_batches'))
        
        # Get form data
        name = request.form.get('name', '').strip()
        course_id = request.form.get('course_id')  # Changed from course_name to course_id
        new_branch_id = request.form.get('branch_id')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        timing = request.form.get('timing', '').strip()  # Now optional, for additional notes
        checkin_time = request.form.get('checkin_time', '').strip()   # New required field
        checkout_time = request.form.get('checkout_time', '').strip() # New required field
        
        # Validate required fields
        if not all([name, course_id, new_branch_id, start_date, checkin_time, checkout_time]):
            flash('Name, Course, Branch, Start Date, Check-in Time, and Check-out Time are required.', 'error')
            return redirect(url_for('batches.edit_batch_form', batch_id=batch_id))
        
        # Validate time fields
        from datetime import datetime
        try:
            if not checkin_time or not checkout_time:
                flash('Both check-in and check-out times are required.', 'error')
                return redirect(url_for('batches.edit_batch_form', batch_id=batch_id))
                
            checkin_dt = datetime.strptime(checkin_time, '%H:%M').time()
            checkout_dt = datetime.strptime(checkout_time, '%H:%M').time()
            
            if checkout_dt <= checkin_dt:
                flash('Check-out time must be after check-in time.', 'error')
                return redirect(url_for('batches.edit_batch_form', batch_id=batch_id))
        except ValueError as e:
            flash(f'Invalid time format. Please use HH:MM format (e.g., 09:30). Error: {str(e)}', 'error')
            return redirect(url_for('batches.edit_batch_form', batch_id=batch_id))
        
        # Get course name from course_id
        course = Course.query.get(course_id)
        if not course:
            flash('Invalid course selected.', 'error')
            return redirect(url_for('batches.edit_batch_form', batch_id=batch_id))
        
        # Validate new branch access
        if current_user.role in ['franchise', 'regional_manager']:
            if int(new_branch_id) not in user_branches:
                flash('You do not have permission to assign batch to this branch.', 'error')
                return redirect(url_for('batches.edit_batch_form', batch_id=batch_id))
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if int(new_branch_id) != user_branch_id:
                flash('You can only assign batches to your branch.', 'error')
                return redirect(url_for('batches.edit_batch_form', batch_id=batch_id))
        
        # Update batch
        batch.name = name
        batch.course_id = int(course_id)      # Use course_id for proper relationship  
        batch.course_name = course.course_name  # Keep for backward compatibility during migration
        batch.branch_id = int(new_branch_id)
        batch.start_date = start_date
        batch.end_date = end_date
        batch.timing = timing                 # Optional additional notes
        batch.checkin_time = checkin_dt       # New required field
        batch.checkout_time = checkout_dt     # New required field
        
        # Handle trainer assignments update
        primary_trainer_id = request.form.get('primary_trainer_id')
        assistant_trainer_id = request.form.get('assistant_trainer_id')
        trainer_notes = request.form.get('trainer_notes', '').strip()
        
        # Get all existing trainer assignments for this batch
        existing_assignments = BatchTrainerAssignment.query.filter_by(batch_id=batch_id).all()
        
        # Track trainer IDs we want to keep active
        active_trainer_ids = []
        if primary_trainer_id:
            active_trainer_ids.append(int(primary_trainer_id))
        if assistant_trainer_id and assistant_trainer_id != primary_trainer_id:
            active_trainer_ids.append(int(assistant_trainer_id))
        
        # Update existing assignments
        for assignment in existing_assignments:
            if assignment.trainer_id in active_trainer_ids:
                # This trainer should remain active, update their assignment
                assignment.is_active = 1
                assignment.assigned_by = current_user.id
                assignment.assigned_on = datetime.now(timezone.utc)
                assignment.notes = trainer_notes if trainer_notes else f'Updated assignment for {batch.name}'
                
                # Set role based on trainer type
                if primary_trainer_id and assignment.trainer_id == int(primary_trainer_id):
                    assignment.role_in_batch = 'Primary Trainer'
                elif assistant_trainer_id and assignment.trainer_id == int(assistant_trainer_id):
                    assignment.role_in_batch = 'Assistant Trainer'
                
                # Remove from active_trainer_ids since we've handled it
                active_trainer_ids.remove(assignment.trainer_id)
            else:
                # This trainer is no longer assigned, deactivate
                assignment.is_active = 0
        
        # Add new assignments for trainers not found in existing assignments
        for trainer_id in active_trainer_ids:
            if primary_trainer_id and trainer_id == int(primary_trainer_id):
                role = 'Primary Trainer'
            else:
                role = 'Assistant Trainer'
            new_assignment = BatchTrainerAssignment(
                batch_id=batch_id,
                trainer_id=trainer_id,
                assigned_by=current_user.id,
                role_in_batch=role,
                notes=trainer_notes if trainer_notes else f'{role} for {batch.name}'
            )
            db.session.add(new_assignment)
        
        db.session.commit()
        
        flash('Batch and trainer assignments updated successfully!', 'success')
        return redirect(url_for('batches.view_batch', batch_id=batch_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating batch: {str(e)}', 'error')
        return redirect(url_for('batches.edit_batch_form', batch_id=batch_id))

@batch_bp.route('/<int:batch_id>/suspend', methods=['POST'])
@login_required
def suspend_batch(batch_id):
    """Suspend a batch temporarily with reason tracking"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Get reason and notes from form
        reason = request.form.get('reason')
        notes = request.form.get('notes', '')
        expected_resume_date = request.form.get('expected_resume_date')
        
        if not reason:
            flash('Please provide a reason for suspending the batch.', 'error')
            return redirect(url_for('batches.view_batch', batch_id=batch_id))
        
        # Check if already suspended
        if batch.status == 'Suspended':
            flash('This batch is already suspended.', 'warning')
            return redirect(url_for('batches.view_batch', batch_id=batch_id))
        
        # Can only suspend active batches
        if batch.status != 'Active':
            flash('Only active batches can be suspended.', 'error')
            return redirect(url_for('batches.view_batch', batch_id=batch_id))
        
        # Validate branch access
        if current_user.role in ['franchise', 'regional_manager']:
            user_branches = get_user_branch_ids(current_user.id)
            if batch.branch_id not in user_branches:
                flash('You do not have permission to suspend this batch.', 'error')
                return redirect(url_for('batches.list_batches'))
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if batch.branch_id != user_branch_id:
                flash('You can only suspend batches from your branch.', 'error')
                return redirect(url_for('batches.list_batches'))
        
        # Suspend the batch using model method
        if batch.suspend_batch(current_user.id, reason=reason, notes=notes, expected_resume_date=expected_resume_date):
            db.session.commit()
            flash(f'⏸️ Batch "{batch.name}" has been suspended. Reason: {reason}', 'warning')
        else:
            flash('❌ Unable to suspend batch. Only active batches can be suspended.', 'error')
            
        return redirect(url_for('batches.view_batch', batch_id=batch_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error suspending batch: {str(e)}', 'error')
        return redirect(url_for('batches.view_batch', batch_id=batch_id))

@batch_bp.route('/<int:batch_id>/reactivate', methods=['POST'])
@login_required
def reactivate_batch(batch_id):
    """Reactivate a suspended batch (supports both AJAX and form submission)"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Check if suspended
        if batch.status != 'Suspended':
            message = 'Only suspended batches can be reactivated.'
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': message}), 400
            flash(message, 'error')
            return redirect(url_for('batches.view_batch', batch_id=batch_id))
        
        # Validate branch access
        if current_user.role in ['franchise', 'regional_manager']:
            user_branches = get_user_branch_ids(current_user.id)
            if batch.branch_id not in user_branches:
                message = 'You do not have permission to reactivate this batch.'
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': message}), 403
                flash(message, 'error')
                return redirect(url_for('batches.list_batches'))
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if batch.branch_id != user_branch_id:
                message = 'You can only reactivate batches from your branch.'
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': message}), 403
                flash(message, 'error')
                return redirect(url_for('batches.list_batches'))
        
        # Reactivate the batch using model method
        if batch.reactivate_batch(current_user.id):
            db.session.commit()
            message = f'Batch "{batch.name}" has been reactivated.'
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': message})
            flash(f'▶️ {message}', 'success')
        else:
            message = 'Unable to reactivate batch. Only suspended batches can be reactivated.'
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': message}), 400
            flash(f'❌ {message}', 'error')
            
        return redirect(url_for('batches.view_batch', batch_id=batch_id))
        
    except Exception as e:
        db.session.rollback()
        error_message = f'Error reactivating batch: {str(e)}'
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': error_message}), 500
        flash(error_message, 'error')
        return redirect(url_for('batches.view_batch', batch_id=batch_id))

@batch_bp.route('/<int:batch_id>/complete', methods=['POST'])
@login_required
def complete_batch(batch_id):
    """Mark a batch as completed (supports both AJAX and form submission)"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Check if already completed
        if batch.status == 'Completed':
            message = 'This batch is already marked as completed.'
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': message}), 400
            flash(message, 'warning')
            return redirect(url_for('batches.view_batch', batch_id=batch_id))
        
        # Validate branch access
        if current_user.role in ['franchise', 'regional_manager']:
            user_branches = get_user_branch_ids(current_user.id)
            if batch.branch_id not in user_branches:
                message = 'You do not have permission to complete this batch.'
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': message}), 403
                flash(message, 'error')
                return redirect(url_for('batches.list_batches'))
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if batch.branch_id != user_branch_id:
                message = 'You can only complete batches from your branch.'
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': message}), 403
                flash(message, 'error')
                return redirect(url_for('batches.list_batches'))
        
        # Mark batch as completed using model method
        if batch.complete_batch(current_user.id):
            # Create completion records for all students using the model
            completion_count = StudentBatchCompletion.create_completion_records(batch_id, current_user.id)
            
            db.session.commit()
            
            message = f'Batch "{batch.name}" marked as completed! Training history preserved for {completion_count} students.'
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': message})
            flash(f'✅ {message}', 'success')
        else:
            message = 'Unable to complete batch. It may already be completed or in wrong status.'
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': message}), 400
            flash(f'❌ {message}', 'error')
            
        return redirect(url_for('batches.view_batch', batch_id=batch_id))
        
    except Exception as e:
        db.session.rollback()
        error_message = f'Error completing batch: {str(e)}'
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': error_message}), 500
        flash(error_message, 'error')
        return redirect(url_for('batches.view_batch', batch_id=batch_id))

@batch_bp.route('/<int:batch_id>/cancel', methods=['POST'])
@login_required
def cancel_batch(batch_id):
    """Cancel a batch permanently (with reason tracking)"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Get form data
        reason = request.form.get('reason', '').strip()
        notes = request.form.get('notes', '').strip()
        confirm_cancel = request.form.get('confirm_cancel')
        
        # Validate inputs
        if not reason:
            flash('Please provide a reason for cancelling the batch.', 'error')
            return redirect(url_for('batches.view_batch', batch_id=batch_id))
            
        if not notes:
            flash('Please provide detailed explanation for cancelling the batch.', 'error')
            return redirect(url_for('batches.view_batch', batch_id=batch_id))
            
        if not confirm_cancel:
            flash('Please confirm that you understand this action cannot be undone.', 'error')
            return redirect(url_for('batches.view_batch', batch_id=batch_id))
        
        # Check if already cancelled
        if batch.status == 'Cancelled':
            flash('This batch is already cancelled.', 'warning')
            return redirect(url_for('batches.view_batch', batch_id=batch_id))
        
        # Can only cancel non-completed/non-archived batches
        if batch.status in ['Completed', 'Archived']:
            flash('Cannot cancel completed or archived batches.', 'error')
            return redirect(url_for('batches.view_batch', batch_id=batch_id))
        
        # Validate branch access
        if current_user.role in ['franchise', 'regional_manager']:
            user_branches = get_user_branch_ids(current_user.id)
            if batch.branch_id not in user_branches:
                flash('You do not have permission to cancel this batch.', 'error')
                return redirect(url_for('batches.list_batches'))
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if batch.branch_id != user_branch_id:
                flash('You can only cancel batches from your branch.', 'error')
                return redirect(url_for('batches.list_batches'))
        
        # Cancel the batch using model method
        if batch.cancel_batch(current_user.id, reason=reason, notes=notes):
            db.session.commit()
            flash(f'❌ Batch "{batch.name}" has been permanently cancelled. Reason: {reason}', 'warning')
        else:
            flash('❌ Unable to cancel batch. Only active or suspended batches can be cancelled.', 'error')
            
        return redirect(url_for('batches.view_batch', batch_id=batch_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error cancelling batch: {str(e)}', 'error')
        return redirect(url_for('batches.view_batch', batch_id=batch_id))

@batch_bp.route('/<int:batch_id>/archive', methods=['POST'])
@login_required
def archive_batch(batch_id):
    """Archive a completed batch (supports both AJAX and form submission)"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Only admins and franchise owners can archive batches
        if current_user.role not in ['admin', 'franchise']:
            message = 'Only administrators can archive batches.'
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': message}), 403
            flash(message, 'error')
            return redirect(url_for('batches.view_batch', batch_id=batch_id))
        
        # Can only archive completed batches
        if batch.status != 'Completed':
            message = 'Only completed batches can be archived.'
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': message}), 400
            flash(message, 'error')
            return redirect(url_for('batches.view_batch', batch_id=batch_id))
        
        # Validate branch access
        if current_user.role == 'franchise':
            user_branches = get_user_branch_ids(current_user.id)
            if batch.branch_id not in user_branches:
                message = 'You do not have permission to archive this batch.'
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': message}), 403
                flash(message, 'error')
                return redirect(url_for('batches.list_batches'))
        
        # Archive the batch using model method
        if batch.archive_batch(current_user.id):
            db.session.commit()
            message = f'Batch "{batch.name}" has been archived. Training history is preserved.'
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': message})
            flash(f'📦 {message}', 'success')
        else:
            message = 'Unable to archive batch. Only completed batches can be archived.'
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': message}), 400
            flash(f'❌ {message}', 'error')
            
        return redirect(url_for('batches.list_batches'))
        
    except Exception as e:
        db.session.rollback()
        error_message = f'Error archiving batch: {str(e)}'
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': error_message}), 500
        flash(error_message, 'error')
        return redirect(url_for('batches.view_batch', batch_id=batch_id))

@batch_bp.route('/<int:batch_id>/students')
@login_required
def batch_students(batch_id):
    """List all students in a specific batch"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Check if batch is deleted
        if batch.is_deleted:
            flash('This batch has been deleted.', 'error')
            return redirect(url_for('batches.list_batches'))
        
        # Validate branch access
        if not has_batch_access(current_user, batch):
            flash('You do not have permission to view this batch.', 'error')
            return redirect(url_for('batches.list_batches'))
        
        # Get students in this batch
        students = Student.query.filter_by(batch_id=batch_id, is_deleted=0).order_by(Student.full_name).all()
        
        # Get trainer assignments for this batch
        trainer_assignments = BatchTrainerAssignment.query.filter_by(
            batch_id=batch_id, 
            is_active=1
        ).join(User, BatchTrainerAssignment.trainer_id == User.id).all()
        
        # Convert students to dictionaries for JSON serialization
        students_data = [student.to_dict() for student in students]
        
        # Get attendance rate safely
        try:
            attendance_rate = batch.get_attendance_rate()
        except Exception as e:
            print(f"Error getting attendance rate: {e}")
            attendance_rate = 0
        
        return render_template('batches/batch_students.html', 
                             batch=batch, 
                             students=students, 
                             students_data=students_data,
                             attendance_rate=attendance_rate,
                             trainer_assignments=trainer_assignments)
        
    except Exception as e:
        flash(f'Error loading batch students: {str(e)}', 'error')
        return redirect(url_for('batches.list_batches'))

@batch_bp.route('/<int:batch_id>/add-students', methods=['GET', 'POST'])
@login_required
def add_students_to_batch(batch_id):
    """Add existing students to a batch"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Validate access
        if not has_batch_access(current_user, batch):
            flash('You do not have permission to modify this batch.', 'error')
            return redirect(url_for('batches.list_batches'))
        
        if request.method == 'POST':
            # Handle adding students to batch
            selected_student_ids = request.form.getlist('student_ids')
            
            if not selected_student_ids:
                flash('Please select at least one student to add.', 'warning')
                return redirect(url_for('batches.add_students_to_batch', batch_id=batch_id))
            
            added_count = 0
            course_mismatch_count = 0
            
            for student_id in selected_student_ids:
                student = Student.query.filter_by(student_id=student_id).first()
                if student and student.branch_id == batch.branch_id:
                    # ✅ BUSINESS LOGIC: Validate student is enrolled in the same course
                    if student.course_name != batch.course_name:
                        course_mismatch_count += 1
                        continue
                        
                    # Update student's batch assignment
                    student.batch_id = batch_id
                    student.course_name = batch.course_name  # Ensure consistency
                    added_count += 1
            
            db.session.commit()
            
            # Provide detailed feedback
            if added_count > 0:
                flash(f'✅ Successfully added {added_count} student(s) to {batch.name}!', 'success')
            
            if course_mismatch_count > 0:
                flash(f'⚠️ {course_mismatch_count} student(s) were not added because they are not enrolled in {batch.course_name}.', 'warning')
            
            if added_count == 0 and course_mismatch_count == 0:
                flash('❌ No students were added. Please verify student selection.', 'warning')
                
            return redirect(url_for('batches.batch_students', batch_id=batch_id))
        
        # GET request - show available students
        # BUSINESS LOGIC FIX: Only show students from the same course as the batch
        # Get students from the same branch AND same course who are not in any batch or in a different batch
        available_students = Student.query.filter(
            Student.branch_id == batch.branch_id,
            Student.course_name == batch.course_name,  # ✅ CRITICAL: Only students from same course
            Student.is_deleted == 0,
            db.or_(
                Student.batch_id.is_(None),
                Student.batch_id != batch_id
            )
        ).order_by(Student.full_name).all()
        
        # Get students currently in this batch
        current_students_in_batch = Student.query.filter_by(
            batch_id=batch_id, 
            is_deleted=0
        ).all()
        current_student_ids = [s.student_id for s in current_students_in_batch]
        
        return render_template('batches/add_students.html', 
                             batch=batch, 
                             available_students=available_students,
                             current_student_ids=current_student_ids)
        
    except Exception as e:
        flash(f'Error loading students: {str(e)}', 'error')
        return redirect(url_for('batches.batch_students', batch_id=batch_id))


@batch_bp.route('/<int:batch_id>/remove-student/<student_id>', methods=['POST'])
@login_required
def remove_student_from_batch(batch_id, student_id):
    """Remove a student from a batch"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Validate batch access
        if not has_batch_access(current_user, batch):
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        
        # Get the student
        student = Student.query.filter_by(student_id=student_id).first()
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'}), 404
        
        # Check if student is in this batch
        if student.batch_id != batch_id:
            return jsonify({'success': False, 'message': 'Student is not in this batch'}), 400
        
        # Remove student from batch (set batch_id to None)
        student.batch_id = None
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'{student.full_name} has been removed from {batch.name}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# API Routes for AJAX functionality
@batch_bp.route('/api/batches')
@login_required
def api_list_batches():
    """API endpoint to get batches as JSON"""
    try:
        current_user = User.query.get(session['user_id'])
        
        # Base query - only show active, non-deleted batches
        query = Batch.query.filter_by(is_deleted=0, status='Active')
        
        # Apply role-based filtering
        if current_user.role == 'franchise':
            user_branches = get_user_branch_ids(current_user.id)
            query = query.filter(Batch.branch_id.in_(user_branches))
        elif current_user.role == 'regional_manager':
            user_branches = get_user_branch_ids(current_user.id)
            query = query.filter(Batch.branch_id.in_(user_branches))
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                query = query.filter_by(branch_id=user_branch_id)
        elif current_user.role == 'trainer':
            # Trainers can only see their assigned batches
            trainer_assignments = BatchTrainerAssignment.get_trainer_batches(current_user.id, active_only=True)
            assigned_batch_ids = [assignment.batch_id for assignment in trainer_assignments]
            if assigned_batch_ids:
                query = query.filter(Batch.id.in_(assigned_batch_ids))
            else:
                query = query.filter(Batch.id == -1)  # No results
        
        batches = query.all()
        
        return jsonify({
            'success': True,
            'batches': [batch.to_dict() for batch in batches]
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@batch_bp.route('/api/batch/<int:batch_id>')
@login_required
def api_get_batch(batch_id):
    """API endpoint to get specific batch details"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Validate access
        if current_user.role in ['franchise', 'regional_manager']:
            user_branches = get_user_branch_ids(current_user.id)
            if batch.branch_id not in user_branches:
                return jsonify({'success': False, 'error': 'Access denied'}), 403
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if batch.branch_id != user_branch_id:
                return jsonify({'success': False, 'error': 'Access denied'}), 403
        elif current_user.role == 'trainer':
            # Trainers can only access their assigned batches
            if not BatchTrainerAssignment.is_trainer_assigned_to_batch(batch_id, current_user.id):
                return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        return jsonify({
            'success': True,
            'batch': batch.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ================================
# PHASE 3: ENHANCED ROUTES
# ================================

# Attendance Management Routes - MOVED TO student_attendance_routes.py
# Use: from routes.student_attendance_routes import attendance_bp

# Trainer Assignment Routes
@batch_bp.route('/<int:batch_id>/trainers')
@login_required  
def batch_trainers(batch_id):
    """Display trainer assignment interface"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Validate access
        if not has_batch_access(current_user, batch):
            flash('You do not have access to this batch', 'error')
            return redirect(url_for('batches.list_batches'))
        
        from models.batch_trainer_assignment_model import BatchTrainerAssignment
        
        # Get assigned trainers
        assigned_trainers = BatchTrainerAssignment.query.filter_by(
            batch_id=batch_id, 
            is_active=True
        ).all()
        
        # Get available trainers (users with trainer role in the same branch)
        available_trainers = User.query.filter(
            User.role.in_(['trainer', 'branch_manager']),
            User.is_deleted == 0
        ).all()
        
        # Filter trainers by branch access
        if current_user.role in ['franchise', 'regional_manager']:
            user_branches = get_user_branch_ids(current_user.id)
            available_trainers = [t for t in available_trainers 
                                if any(branch_id in user_branches 
                                      for branch_id in get_user_branch_ids(t.id))]
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            available_trainers = [t for t in available_trainers 
                                if user_branch_id in get_user_branch_ids(t.id)]
        
        return render_template('batches/batch_trainers.html',
                             batch=batch,
                             assigned_trainers=assigned_trainers,
                             available_trainers=available_trainers)
        
    except Exception as e:
        flash(f'Error loading trainers: {str(e)}', 'error')
        return redirect(url_for('batches.view_batch', batch_id=batch_id))

@batch_bp.route('/<int:batch_id>/trainers/assign', methods=['POST'])
@login_required
def assign_trainer(batch_id):
    """Assign a trainer to a batch"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Validate access
        if not has_batch_access(current_user, batch):
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        trainer_id = request.form.get('trainer_id')
        trainer_role = request.form.get('trainer_role', 'Primary')
        notes = request.form.get('notes', '')
        
        if not trainer_id:
            flash('Please select a trainer', 'error')
            return redirect(url_for('batches.batch_trainers', batch_id=batch_id))
        
        # Validate trainer exists and has access
        trainer = User.query.get(trainer_id)
        if not trainer or trainer.role not in ['trainer', 'branch_manager']:
            flash('Invalid trainer selected', 'error')
            return redirect(url_for('batches.batch_trainers', batch_id=batch_id))
        
        from models.batch_trainer_assignment_model import BatchTrainerAssignment
        
        # Check if trainer is already assigned
        existing_assignment = BatchTrainerAssignment.query.filter_by(
            batch_id=batch_id,
            trainer_user_id=trainer_id,
            is_active=True
        ).first()
        
        if existing_assignment:
            flash('This trainer is already assigned to this batch', 'warning')
            return redirect(url_for('batches.batch_trainers', batch_id=batch_id))
        
        # Create new assignment
        assignment = BatchTrainerAssignment(
            batch_id=batch_id,
            trainer_user_id=trainer_id,
            assigned_by_user_id=current_user.id,
            trainer_role=trainer_role,
            notes=notes
        )
        
        db.session.add(assignment)
        db.session.commit()
        
        flash(f'Trainer {trainer.full_name} assigned successfully', 'success')
        return redirect(url_for('batches.batch_trainers', batch_id=batch_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error assigning trainer: {str(e)}', 'error')
        return redirect(url_for('batches.batch_trainers', batch_id=batch_id))

@batch_bp.route('/trainers/<int:assignment_id>/remove', methods=['POST'])
@login_required
def remove_trainer(assignment_id):
    """Remove a trainer assignment via AJAX"""
    try:
        current_user = User.query.get(session['user_id'])
        from models.batch_trainer_assignment_model import BatchTrainerAssignment
        
        assignment = BatchTrainerAssignment.query.get_or_404(assignment_id)
        batch = Batch.query.get(assignment.batch_id)
        
        # Validate access
        if not has_batch_access(current_user, batch):
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        # Soft delete the assignment
        assignment.is_active = False
        assignment.removed_by_user_id = current_user.id
        assignment.removed_date = db.func.current_timestamp()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Trainer removed successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@batch_bp.route('/trainers/<int:assignment_id>/edit', methods=['POST'])
@login_required
def edit_trainer_assignment(assignment_id):
    """Edit a trainer assignment via AJAX"""
    try:
        current_user = User.query.get(session['user_id'])
        from models.batch_trainer_assignment_model import BatchTrainerAssignment
        
        assignment = BatchTrainerAssignment.query.get_or_404(assignment_id)
        batch = Batch.query.get(assignment.batch_id)
        
        # Validate access
        if not has_batch_access(current_user, batch):
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        # Get data from request
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Update assignment
        assignment.trainer_role = data.get('trainer_role', assignment.trainer_role)
        assignment.notes = data.get('notes', assignment.notes)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Trainer assignment updated successfully',
            'assignment': {
                'id': assignment.id,
                'trainer_role': assignment.trainer_role,
                'notes': assignment.notes
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# Capacity Management Routes
@batch_bp.route('/<int:batch_id>/capacity')
@login_required
def batch_capacity(batch_id):
    """Display batch capacity management interface"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Validate access
        if not has_batch_access(current_user, batch):
            flash('You do not have access to this batch', 'error')
            return redirect(url_for('batches.list_batches'))
        
        # Get current enrollment
        current_enrollment = Student.query.filter_by(batch_id=batch_id, is_deleted=0).count()
        
        # Get capacity information
        max_capacity = batch.max_capacity or 30  # Default capacity
        available_spots = max_capacity - current_enrollment
        utilization_rate = (current_enrollment / max_capacity * 100) if max_capacity > 0 else 0
        
        # Get recent enrollments
        recent_enrollments = Student.query.filter_by(batch_id=batch_id, is_deleted=0)\
                                   .order_by(Student.admission_date.desc())\
                                   .limit(10).all()
        
        return render_template('batches/batch_capacity.html',
                             batch=batch,
                             current_enrollment=current_enrollment,
                             max_capacity=max_capacity,
                             available_spots=available_spots,
                             utilization_rate=round(utilization_rate, 1),
                             recent_enrollments=recent_enrollments)
        
    except Exception as e:
        flash(f'Error loading capacity info: {str(e)}', 'error')
        return redirect(url_for('batches.view_batch', batch_id=batch_id))

@batch_bp.route('/<int:batch_id>/capacity/update', methods=['POST'])
@login_required
def update_batch_capacity(batch_id):
    """Update batch capacity limits"""
    try:
        current_user = User.query.get(session['user_id'])
        batch = Batch.query.get_or_404(batch_id)
        
        # Validate access (only managers and above)
        if current_user.role not in ['admin', 'franchise', 'regional_manager', 'branch_manager']:
            return jsonify({'success': False, 'error': 'Insufficient permissions'}), 403
        
        if not has_batch_access(current_user, batch):
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        data = request.get_json()
        max_capacity = data.get('max_capacity')
        
        if not max_capacity or max_capacity < 1:
            return jsonify({'success': False, 'error': 'Invalid capacity value'}), 400
        
        # Check if new capacity is less than current enrollment
        current_enrollment = Student.query.filter_by(batch_id=batch_id, is_deleted=0).count()
        if max_capacity < current_enrollment:
            return jsonify({
                'success': False, 
                'error': f'Cannot set capacity below current enrollment ({current_enrollment})'
            }), 400
        
        batch.max_capacity = max_capacity
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Batch capacity updated successfully',
            'new_capacity': max_capacity,
            'available_spots': max_capacity - current_enrollment
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@batch_bp.route('/search-students/<int:batch_id>')
@login_required
def search_students_api(batch_id):
    """API endpoint to search students for adding to a batch"""
    try:
        # Check if batch exists and user has access
        batch = Batch.query.get_or_404(batch_id)
        current_user = User.query.get(session.get('user_id'))
        
        if not has_batch_access(current_user, batch):
            return jsonify({'error': 'Access denied'}), 403
        
        # Get search query
        query = request.args.get('q', '').strip()
        
        # Search students using our utility function
        students = search_students_for_batch(query, batch_id, limit=20)
        
        # Format results for JSON response
        results = []
        for student in students:
            results.append({
                'student_id': student.student_id,
                'full_name': student.full_name,
                'mobile': student.mobile,
                'email': student.email,
                'current_batch': student.batch.name if student.batch else None,
                'will_transfer': bool(student.batch_id)
            })
        
        return jsonify({
            'students': results,
            'total': len(results),
            'query': query
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Add this new route before the existing routes
@batch_bp.route('/api/trainers/branch/<int:branch_id>')
@login_required
def api_trainers_by_branch(branch_id):
    """API endpoint to get trainers by branch"""
    try:
        current_user = User.query.get(session.get('user_id'))
        
        # Check if user has access to this branch
        if current_user.role in ['franchise', 'regional_manager']:
            user_branches = get_user_branch_ids(current_user.id)
            if branch_id not in user_branches:
                return jsonify({'success': False, 'message': 'Access denied'}), 403
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if branch_id != user_branch_id:
                return jsonify({'success': False, 'message': 'Access denied'}), 403
        elif current_user.role == 'trainer':
            # Trainers can only see trainers from their branch
            user_branch_id = session.get("user_branch_id")
            if branch_id != user_branch_id:
                return jsonify({'success': False, 'message': 'Access denied'}), 403
        # Admin has access to all branches
        
        # Get trainers from this branch using user_branch_assignments
        trainer_query = db.session.execute(
            db.text("""
                SELECT DISTINCT u.id, u.username, u.full_name 
                FROM users u 
                INNER JOIN user_branch_assignments uba ON u.id = uba.user_id 
                WHERE u.role = 'trainer' 
                AND u.is_deleted = 0 
                AND uba.branch_id = :branch_id 
                AND uba.is_active = 1
                ORDER BY u.full_name
            """),
            {"branch_id": branch_id}
        ).fetchall()
        
        # Format trainer data
        trainer_data = []
        for trainer_row in trainer_query:
            trainer_data.append({
                'id': trainer_row[0],
                'username': trainer_row[1],
                'full_name': trainer_row[2]
            })
        
        return jsonify({
            'success': True,
            'trainers': trainer_data,
            'total': len(trainer_data)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# Helper Functions
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
