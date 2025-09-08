from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from init_db import db
from models.user_model import User
from models.branch_model import Branch
from models.user_branch_assignment_model import UserBranchAssignment
from models.staff_profile_model import StaffProfile
from utils.auth import login_required
from utils.role_permissions import get_user_accessible_branches
from sqlalchemy import text
from datetime import datetime, timezone
import os
import re
import os
import uuid

staff_bp = Blueprint('staff', __name__, url_prefix='/staff')

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

def has_staff_management_access(user_role):
    """Check if user has access to staff management"""
    return user_role in ['admin', 'franchise', 'franchise_owner', 'regional_manager']

@staff_bp.route('/')
@login_required
def list_staff():
    """List all staff members based on user access"""
    if not session.get('user_id'):
        flash('Please log in to access this page.', 'error')
        return redirect(url_for('auth.login'))
    
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    # Check permissions
    if not has_staff_management_access(user_role):
        flash('Access denied. You do not have permission to manage staff.', 'error')
        return redirect(url_for('dashboard_bp.trainer_dashboard'))
    
    try:
        # Get accessible branches for filtering
        if user_role == 'admin':
            accessible_branches = [b.id for b in Branch.query.filter_by(is_deleted=0).all()]
        else:
            accessible_branches = get_user_accessible_branches(user_id)
        
        # Get staff members based on user access
        if user_role == 'admin':
            # Admin can see all staff
            staff_members = User.query.filter(
                User.is_deleted == 0,
                User.role.in_(['trainer', 'branch_manager', 'staff', 'franchise', 'franchise_owner', 'regional_manager'])
            ).all()
        else:
            # Get staff from accessible branches only
            staff_members = []
            if accessible_branches:
                # Get users assigned to accessible branches
                assignments = UserBranchAssignment.query.filter(
                    UserBranchAssignment.branch_id.in_(accessible_branches),
                    UserBranchAssignment.is_active == 1
                ).all()
                
                user_ids = [a.user_id for a in assignments]
                if user_ids:
                    staff_members = User.query.filter(
                        User.id.in_(user_ids),
                        User.is_deleted == 0,
                        User.role.in_(['trainer', 'branch_manager', 'staff', 'franchise', 'franchise_owner'])
                    ).all()
        
        # Get branch information for each staff member
        staff_with_branches = []
        for staff in staff_members:
            # Get branch assignments for this user
            user_branches = get_user_branch_ids(staff.id)
            branch_names = []
            if user_branches:
                branches = Branch.query.filter(Branch.id.in_(user_branches)).all()
                branch_names = [b.branch_name for b in branches]
            
            staff_with_branches.append({
                'user': staff,
                'branches': branch_names
            })
        
        # Get branches for add staff form
        if user_role == 'admin':
            available_branches = Branch.query.filter_by(is_deleted=0).all()
        else:
            available_branches = Branch.query.filter(
                Branch.id.in_(accessible_branches),
                Branch.is_deleted == 0
            ).all()
        
        return render_template('staff/list.html', 
                             staff_members=staff_with_branches,
                             available_branches=available_branches,
                             user_role=user_role)
    
    except Exception as e:
        flash(f'Error loading staff members: {str(e)}', 'error')
        return redirect(url_for('dashboard_bp.franchise_dashboard'))

@staff_bp.route('/add', methods=['POST'])
@login_required
def add_staff():
    """Add a new staff member"""
    if not session.get('user_id'):
        flash('Please log in to access this page.', 'error')
        return redirect(url_for('auth.login'))
    
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    # Check permissions
    if not has_staff_management_access(user_role):
        flash('Access denied. You do not have permission to add staff.', 'error')
        return redirect(url_for('staff.list_staff'))
    
    try:
        # Get form data
        username = request.form.get('username', '').strip()
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', '').strip()
        branch_ids = request.form.getlist('branch_ids[]')
        notes = request.form.get('notes', '').strip()
        
        # Validation
        if not all([username, full_name, password, role]):
            flash('All required fields must be filled.', 'error')
            return redirect(url_for('staff.list_staff'))
        
        # Validate username format
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            flash('Username can only contain letters, numbers, and underscores.', 'error')
            return redirect(url_for('staff.list_staff'))
        
        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please choose a different username.', 'error')
            return redirect(url_for('staff.list_staff'))
        
        # Validate password length
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return redirect(url_for('staff.list_staff'))
        
        # Validate role
        allowed_roles = ['trainer', 'branch_manager', 'staff']
        if user_role == 'admin':
            allowed_roles.extend(['franchise', 'franchise_owner', 'regional_manager'])
        
        if role not in allowed_roles:
            flash('Invalid role selected.', 'error')
            return redirect(url_for('staff.list_staff'))
        
        # Validate branch access
        accessible_branches = get_user_accessible_branches(user_id) if user_role != 'admin' else [b.id for b in Branch.query.filter_by(is_deleted=0).all()]
        
        for branch_id in branch_ids:
            if int(branch_id) not in accessible_branches:
                flash('You do not have permission to assign staff to selected branches.', 'error')
                return redirect(url_for('staff.list_staff'))
        
        # Create new user
        hashed_password = generate_password_hash(password)
        new_user = User(
            username=username,
            password=hashed_password,
            full_name=full_name,
            role=role
        )
        
        db.session.add(new_user)
        db.session.flush()  # Get the user ID
        
        # Create branch assignments
        for branch_id in branch_ids:
            assignment = UserBranchAssignment(
                user_id=new_user.id,
                branch_id=int(branch_id),
                role_at_branch=role,  # Store the role in role_at_branch field
                assigned_by=user_id,
                notes=notes
            )
            db.session.add(assignment)
        
        db.session.commit()
        
        flash(f'Staff member {full_name} ({username}) added successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding staff member: {str(e)}', 'error')
    
    return redirect(url_for('staff.list_staff'))

@staff_bp.route('/create')
@login_required
def create_staff():
    """Display the enhanced create staff form"""
    if not session.get('user_id'):
        flash('Please log in to access this page.', 'error')
        return redirect(url_for('auth.login'))
    
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    # Check permissions
    if not has_staff_management_access(user_role):
        flash('Access denied. You do not have permission to create staff.', 'error')
        return redirect(url_for('staff.list_staff'))
    
    try:
        # Get available branches for assignment
        if user_role == 'admin':
            available_branches = Branch.query.filter_by(is_deleted=0).all()
        else:
            accessible_branches = get_user_accessible_branches(user_id)
            available_branches = Branch.query.filter(
                Branch.id.in_(accessible_branches),
                Branch.is_deleted == 0
            ).all()
        
        return render_template('staff/create_staff.html', 
                             available_branches=available_branches,
                             user_role=user_role)
    
    except Exception as e:
        flash(f'Error loading create staff page: {str(e)}', 'error')
        return redirect(url_for('staff.list_staff'))

@staff_bp.route('/create', methods=['POST'])
@login_required
def create_staff_post():
    """Process the enhanced create staff form submission"""
    if not session.get('user_id'):
        flash('Please log in to access this page.', 'error')
        return redirect(url_for('auth.login'))
    
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    # Check permissions
    if not has_staff_management_access(user_role):
        flash('Access denied. You do not have permission to create staff.', 'error')
        return redirect(url_for('staff.list_staff'))
    
    try:
        # Get basic form data
        username = request.form.get('username', '').strip()
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        role = request.form.get('role', '').strip()
        designation = request.form.get('designation', '').strip()
        branch_ids = request.form.getlist('branch_ids[]')
        
        # Validation
        if not all([username, full_name, password, role]):
            flash('All required fields must be filled.', 'error')
            return redirect(url_for('staff.create_staff'))
        
        # Validate password match
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('staff.create_staff'))
        
        # Validate username format
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            flash('Username can only contain letters, numbers, and underscores.', 'error')
            return redirect(url_for('staff.create_staff'))
        
        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please choose a different username.', 'error')
            return redirect(url_for('staff.create_staff'))
        
        # Validate password length
        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return redirect(url_for('staff.create_staff'))
        
        # Validate role
        allowed_roles = ['trainer', 'branch_manager', 'staff']
        if user_role == 'admin':
            allowed_roles.extend(['franchise', 'franchise_owner', 'regional_manager'])
        
        if role not in allowed_roles:
            flash('Invalid role selected.', 'error')
            return redirect(url_for('staff.create_staff'))
        
        # Validate branch access
        accessible_branches = get_user_accessible_branches(user_id) if user_role != 'admin' else [b.id for b in Branch.query.filter_by(is_deleted=0).all()]
        
        for branch_id in branch_ids:
            if int(branch_id) not in accessible_branches:
                flash('You do not have permission to assign staff to selected branches.', 'error')
                return redirect(url_for('staff.create_staff'))
        
        # Helper function to convert date strings to date objects
        def parse_date(date_string):
            if date_string and date_string.strip():
                try:
                    return datetime.strptime(date_string.strip(), '%Y-%m-%d').date()
                except ValueError:
                    return None
            return None
        
        # Helper function to convert numeric strings
        def parse_int(value):
            if value and str(value).strip():
                try:
                    return int(value)
                except ValueError:
                    return None
            return None
        
        # Create new user
        hashed_password = generate_password_hash(password)
        new_user = User(
            username=username,
            password=hashed_password,
            full_name=full_name,
            role=role
        )
        
        db.session.add(new_user)
        db.session.flush()  # Get the user ID
        
        # Create comprehensive staff profile
        staff_profile = StaffProfile(
            user_id=new_user.id,
            designation=designation,
            # Personal Information
            date_of_birth=parse_date(request.form.get('date_of_birth')),
            gender=request.form.get('gender') or None,
            marital_status=request.form.get('marital_status') or None,
            blood_group=request.form.get('blood_group') or None,
            
            # Contact Information
            primary_mobile=request.form.get('primary_mobile', '').strip(),
            secondary_mobile=request.form.get('secondary_mobile', '').strip(),
            personal_email=request.form.get('personal_email', '').strip(),
            official_email=request.form.get('official_email', '').strip(),
            
            # Address Information
            current_address=request.form.get('current_address', '').strip(),
            permanent_address=request.form.get('permanent_address', '').strip(),
            city=request.form.get('city', '').strip(),
            state=request.form.get('state', '').strip(),
            pincode=request.form.get('pincode', '').strip(),
            
            # Emergency Contact
            emergency_contact_name=request.form.get('emergency_contact_name', '').strip(),
            emergency_contact_relation=request.form.get('emergency_contact_relation', '').strip(),
            emergency_contact_mobile=request.form.get('emergency_contact_mobile', '').strip(),
            emergency_contact_address=request.form.get('emergency_contact_address', '').strip(),
            
            # Professional Information
            joining_date=parse_date(request.form.get('joining_date')),
            employment_type=request.form.get('employment_type') or None,
            department=request.form.get('department', '').strip(),
            years_of_experience=parse_int(request.form.get('years_of_experience')),
            
            # Education & Qualifications
            highest_qualification=request.form.get('highest_qualification') or None,
            specialization=request.form.get('specialization', '').strip(),
            university_college=request.form.get('university_college', '').strip(),
            graduation_year=parse_int(request.form.get('graduation_year')),
            
            # Skills & Expertise
            technical_skills=request.form.get('technical_skills', '').strip(),
            teaching_subjects=request.form.get('teaching_subjects', '').strip(),
            languages_known=request.form.get('languages_known', '').strip(),
            
            # Bank & Identity Details
            pan_number=request.form.get('pan_number', '').strip().upper(),
            aadhar_number=request.form.get('aadhar_number', '').strip(),
            bank_account_number=request.form.get('bank_account_number', '').strip(),
            bank_name=request.form.get('bank_name', '').strip(),
            bank_ifsc=request.form.get('bank_ifsc', '').strip().upper(),
            
            # Additional Information
            notes=request.form.get('notes', '').strip(),
            hobbies_interests=request.form.get('hobbies_interests', '').strip(),
            
            # Auto-generated fields
            employee_id=StaffProfile.generate_employee_id(),
            created_by_user_id=user_id
        )
        
        # Handle file uploads
        upload_folder = os.path.join('static', 'uploads', 'staff')
        os.makedirs(upload_folder, exist_ok=True)
        
        # Profile photo
        if 'profile_photo' in request.files:
            file = request.files['profile_photo']
            if file and file.filename:
                filename = secure_filename(f"{new_user.id}_{uuid.uuid4().hex[:8]}_{file.filename}")
                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)
                staff_profile.profile_photo = f"uploads/staff/{filename}"
        
        # Resume file
        if 'resume_file' in request.files:
            file = request.files['resume_file']
            if file and file.filename:
                filename = secure_filename(f"resume_{new_user.id}_{uuid.uuid4().hex[:8]}_{file.filename}")
                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)
                staff_profile.resume_file = f"uploads/staff/{filename}"
        
        # ID proof file
        if 'id_proof_file' in request.files:
            file = request.files['id_proof_file']
            if file and file.filename:
                filename = secure_filename(f"id_proof_{new_user.id}_{uuid.uuid4().hex[:8]}_{file.filename}")
                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)
                staff_profile.id_proof_file = f"uploads/staff/{filename}"
        
        # Address proof file
        if 'address_proof_file' in request.files:
            file = request.files['address_proof_file']
            if file and file.filename:
                filename = secure_filename(f"address_proof_{new_user.id}_{uuid.uuid4().hex[:8]}_{file.filename}")
                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)
                staff_profile.address_proof_file = f"uploads/staff/{filename}"
        
        db.session.add(staff_profile)
        
        # Create branch assignments
        for branch_id in branch_ids:
            assignment = UserBranchAssignment(
                user_id=new_user.id,
                branch_id=int(branch_id),
                role_at_branch=role,
                assigned_by=user_id,
                notes=f"Staff created via enhanced form. Designation: {designation}"
            )
            db.session.add(assignment)
        
        db.session.commit()
        
        flash(f'Staff member {full_name} ({new_user.username}) created successfully with comprehensive profile!', 'success')
        return redirect(url_for('staff.list_staff'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating staff member: {str(e)}', 'error')
        return redirect(url_for('staff.create_staff'))

@staff_bp.route('/view/<int:user_id>')
@login_required
def view_staff(user_id):
    """View detailed staff member profile"""
    if not session.get('user_id'):
        flash('Please log in to access this page.', 'error')
        return redirect(url_for('auth.login'))
    
    user_role = session.get('role')
    current_user_id = session.get('user_id')
    
    # Check permissions
    if not has_staff_management_access(user_role):
        flash('Access denied. You do not have permission to view staff details.', 'error')
        return redirect(url_for('staff.list_staff'))
    
    try:
        staff_member = User.query.get_or_404(user_id)
        
        # Check if current user can view this staff member
        staff_branches = get_user_branch_ids(user_id)
        accessible_branches = get_user_accessible_branches(current_user_id) if user_role != 'admin' else [b.id for b in Branch.query.filter_by(is_deleted=0).all()]
        
        if user_role != 'admin' and not any(branch_id in accessible_branches for branch_id in staff_branches):
            flash('Access denied. You cannot view this staff member.', 'error')
            return redirect(url_for('staff.list_staff'))
        
        # Get staff profile
        staff_profile = StaffProfile.query.filter_by(user_id=user_id).first()
        
        # Get branch assignments
        branch_assignments = UserBranchAssignment.query.filter_by(user_id=user_id, is_active=1).all()
        branches = [assignment.branch.branch_name for assignment in branch_assignments] if branch_assignments else []
        
        # Prepare comprehensive staff data
        staff_data = {
            'user_id': staff_member.id,
            'username': staff_member.username,
            'full_name': staff_member.full_name,
            'role': staff_member.role,
            'is_active': True,  # Default active status
            'branches': branches
        }
        
        # Add staff profile data if exists
        if staff_profile:
            staff_data.update({
                'employee_id': staff_profile.employee_id,
                'primary_mobile': staff_profile.primary_mobile,
                'secondary_mobile': staff_profile.secondary_mobile,
                'personal_email': staff_profile.personal_email,
                'official_email': staff_profile.official_email,
                'designation': staff_profile.designation,
                'department': staff_profile.department,
                'joining_date': staff_profile.joining_date.strftime('%Y-%m-%d') if staff_profile.joining_date else None,
                'date_of_birth': staff_profile.date_of_birth.strftime('%Y-%m-%d') if staff_profile.date_of_birth else None,
                'gender': staff_profile.gender,
                'marital_status': staff_profile.marital_status,
                'blood_group': staff_profile.blood_group,
                'nationality': staff_profile.nationality,
                'current_address': staff_profile.current_address,
                'permanent_address': staff_profile.permanent_address,
                'city': staff_profile.city,
                'state': staff_profile.state,
                'country': staff_profile.country,
                'pincode': staff_profile.pincode,
                'emergency_contact_name': staff_profile.emergency_contact_name,
                'emergency_contact_mobile': staff_profile.emergency_contact_mobile,
                'emergency_contact_relation': staff_profile.emergency_contact_relation,
                'employment_type': staff_profile.employment_type,
                'basic_salary': float(staff_profile.basic_salary) if staff_profile.basic_salary else None,
                'gross_salary': float(staff_profile.gross_salary) if staff_profile.gross_salary else None,
                'work_location': staff_profile.work_location,
                'technical_skills': staff_profile.technical_skills,
                'soft_skills': staff_profile.soft_skills,
                'languages_known': staff_profile.languages_known,
                'teaching_subjects': staff_profile.teaching_subjects,
                'years_of_experience': staff_profile.years_of_experience,
                'previous_experience': staff_profile.previous_experience,
                'highest_qualification': staff_profile.highest_qualification,
                'university_college': staff_profile.university_college,
                'graduation_year': staff_profile.graduation_year,
                'specialization': staff_profile.specialization,
                'additional_certifications': staff_profile.additional_certifications,
                'bank_name': staff_profile.bank_name,
                'bank_account_number': staff_profile.bank_account_number,
                'bank_ifsc': staff_profile.bank_ifsc,
                'pan_number': staff_profile.pan_number,
                'aadhar_number': staff_profile.aadhar_number,
                'notes': staff_profile.notes,
                'hobbies_interests': staff_profile.hobbies_interests,
                'profile_photo': staff_profile.profile_photo,
                'is_active': staff_profile.is_active
            })
        
        return render_template('staff/view_staff.html', staff=staff_data)
    
    except Exception as e:
        flash(f'Error loading staff member: {str(e)}', 'error')
        return redirect(url_for('staff.list_staff'))

@staff_bp.route('/edit/<int:user_id>')
@login_required
def edit_staff(user_id):
    """Edit staff member details"""
    if not session.get('user_id'):
        flash('Please log in to access this page.', 'error')
        return redirect(url_for('auth.login'))
    
    user_role = session.get('role')
    current_user_id = session.get('user_id')
    
    # Check permissions
    if not has_staff_management_access(user_role):
        flash('Access denied. You do not have permission to edit staff.', 'error')
        return redirect(url_for('staff.list_staff'))
    
    try:
        staff_member = User.query.get_or_404(user_id)
        
        # Check if current user can edit this staff member
        staff_branches = get_user_branch_ids(user_id)
        accessible_branches = get_user_accessible_branches(current_user_id) if user_role != 'admin' else [b.id for b in Branch.query.filter_by(is_deleted=0).all()]
        
        if user_role != 'admin' and not any(branch_id in accessible_branches for branch_id in staff_branches):
            flash('Access denied. You cannot edit this staff member.', 'error')
            return redirect(url_for('staff.list_staff'))
        
        # Get staff profile
        staff_profile = StaffProfile.query.filter_by(user_id=user_id).first()
        
        # Get staff's current branch assignments
        current_assignments = UserBranchAssignment.query.filter_by(
            user_id=user_id,
            is_active=1
        ).all()
        
        # Get available branches for assignment
        if user_role == 'admin':
            available_branches = Branch.query.filter_by(is_deleted=0).all()
        else:
            available_branches = Branch.query.filter(
                Branch.id.in_(accessible_branches),
                Branch.is_deleted == 0
            ).all()
        
        return render_template('staff/edit_staff.html',
                             staff_member=staff_member,
                             staff_profile=staff_profile,
                             current_assignments=current_assignments,
                             available_branches=available_branches,
                             user_role=user_role)
    
    except Exception as e:
        flash(f'Error loading staff member: {str(e)}', 'error')
        return redirect(url_for('staff.list_staff'))

@staff_bp.route('/update/<int:user_id>', methods=['POST'])
@login_required
def update_staff(user_id):
    """Update staff member details - comprehensive update handling all form fields"""
    print(f"DEBUG: Update staff called for user_id: {user_id}")
    print(f"DEBUG: Request method: {request.method}")
    print(f"DEBUG: Form data keys: {list(request.form.keys())}")
    
    if not session.get('user_id'):
        flash('Please log in to access this page.', 'error')
        return redirect(url_for('auth.login'))
    
    user_role = session.get('role')
    current_user_id = session.get('user_id')
    
    # Check permissions
    if not has_staff_management_access(user_role):
        flash('Access denied. You do not have permission to update staff.', 'error')
        return redirect(url_for('staff.list_staff'))
    
    try:
        staff_member = User.query.get_or_404(user_id)
        
        # Helper function to convert date strings to date objects
        def parse_date(date_string):
            if date_string and date_string.strip():
                try:
                    return datetime.strptime(date_string.strip(), '%Y-%m-%d').date()
                except ValueError:
                    return None
            return None
        
        # Helper function to convert numeric strings
        def parse_int(value):
            if value and str(value).strip():
                try:
                    return int(value.strip())
                except (ValueError, TypeError):
                    return None
            return None
        
        # Get basic form data
        full_name = request.form.get('full_name', '').strip()
        role = request.form.get('role', '').strip()
        designation = request.form.get('designation', '').strip()
        branch_ids = request.form.getlist('branch_ids[]')
        
        # Password fields
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        # Validation
        if not all([full_name, role]):
            flash('Full name and role are required.', 'error')
            return redirect(url_for('staff.edit_staff', user_id=user_id))
        
        # Validate password if provided
        if password or confirm_password:
            if password != confirm_password:
                flash('Passwords do not match.', 'error')
                return redirect(url_for('staff.edit_staff', user_id=user_id))
            
            if len(password) < 6:
                flash('Password must be at least 6 characters long.', 'error')
                return redirect(url_for('staff.edit_staff', user_id=user_id))
        
        # Validate role
        allowed_roles = ['trainer', 'branch_manager', 'staff']
        if user_role == 'admin':
            allowed_roles.extend(['franchise', 'franchise_owner', 'regional_manager'])
        
        if role not in allowed_roles:
            flash('Invalid role selected.', 'error')
            return redirect(url_for('staff.edit_staff', user_id=user_id))
        
        # Validate branch access
        accessible_branches = get_user_accessible_branches(current_user_id) if user_role != 'admin' else [b.id for b in Branch.query.filter_by(is_deleted=0).all()]
        
        for branch_id in branch_ids:
            if int(branch_id) not in accessible_branches:
                flash('You do not have permission to assign staff to selected branches.', 'error')
                return redirect(url_for('staff.edit_staff', user_id=user_id))
        
        # Update user basic details
        staff_member.full_name = full_name
        staff_member.role = role
        
        # Update password if provided
        if password:
            staff_member.password = generate_password_hash(password)
        
        # Get or create staff profile
        staff_profile = StaffProfile.query.filter_by(user_id=user_id).first()
        if not staff_profile:
            staff_profile = StaffProfile(
                user_id=user_id,
                employee_id=StaffProfile.generate_employee_id() if hasattr(StaffProfile, 'generate_employee_id') else f"EMP-{user_id}",
                created_by_user_id=current_user_id
            )
            db.session.add(staff_profile)
        
        # Update staff profile with all form data
        staff_profile.designation = designation
        staff_profile.updated_by_user_id = current_user_id
        staff_profile.updated_at = datetime.now(timezone.utc)
        
        # Personal Information
        staff_profile.date_of_birth = parse_date(request.form.get('date_of_birth'))
        staff_profile.gender = request.form.get('gender') or None
        staff_profile.marital_status = request.form.get('marital_status') or None
        staff_profile.blood_group = request.form.get('blood_group') or None
        
        # Contact Information
        staff_profile.primary_mobile = request.form.get('primary_mobile', '').strip()
        staff_profile.secondary_mobile = request.form.get('secondary_mobile', '').strip()
        staff_profile.personal_email = request.form.get('personal_email', '').strip()
        staff_profile.official_email = request.form.get('official_email', '').strip()
        
        # Address Information
        staff_profile.current_address = request.form.get('current_address', '').strip()
        staff_profile.permanent_address = request.form.get('permanent_address', '').strip()
        staff_profile.city = request.form.get('city', '').strip()
        staff_profile.state = request.form.get('state', '').strip()
        staff_profile.pincode = request.form.get('pincode', '').strip()
        
        # Emergency Contact
        staff_profile.emergency_contact_name = request.form.get('emergency_contact_name', '').strip()
        staff_profile.emergency_contact_relation = request.form.get('emergency_contact_relation', '').strip()
        staff_profile.emergency_contact_mobile = request.form.get('emergency_contact_mobile', '').strip()
        staff_profile.emergency_contact_address = request.form.get('emergency_contact_address', '').strip()
        
        # Professional Information
        staff_profile.joining_date = parse_date(request.form.get('joining_date'))
        staff_profile.employment_type = request.form.get('employment_type') or None
        staff_profile.department = request.form.get('department', '').strip()
        staff_profile.years_of_experience = parse_int(request.form.get('years_of_experience'))
        
        # Education & Qualifications
        staff_profile.highest_qualification = request.form.get('highest_qualification') or None
        staff_profile.specialization = request.form.get('specialization', '').strip()
        staff_profile.university_college = request.form.get('university_college', '').strip()
        staff_profile.graduation_year = parse_int(request.form.get('graduation_year'))
        
        # Skills & Expertise
        staff_profile.technical_skills = request.form.get('technical_skills', '').strip()
        staff_profile.teaching_subjects = request.form.get('teaching_subjects', '').strip()
        staff_profile.languages_known = request.form.get('languages_known', '').strip()
        
        # Bank & Identity Details
        staff_profile.pan_number = request.form.get('pan_number', '').strip().upper()
        staff_profile.aadhar_number = request.form.get('aadhar_number', '').strip()
        staff_profile.bank_account_number = request.form.get('bank_account_number', '').strip()
        staff_profile.bank_name = request.form.get('bank_name', '').strip()
        staff_profile.bank_ifsc = request.form.get('bank_ifsc', '').strip().upper()
        
        # Additional Information
        staff_profile.notes = request.form.get('notes', '').strip()
        staff_profile.hobbies_interests = request.form.get('hobbies_interests', '').strip()
        
        # Handle file uploads
        import os
        from werkzeug.utils import secure_filename
        
        upload_folder = os.path.join('static', 'uploads', 'staff')
        os.makedirs(upload_folder, exist_ok=True)
        
        # Profile photo
        if 'profile_photo' in request.files:
            file = request.files['profile_photo']
            if file and file.filename:
                filename = secure_filename(f"{user_id}_{int(datetime.now().timestamp())}_{file.filename}")
                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)
                staff_profile.profile_photo = f"uploads/staff/{filename}"
        
        # Resume file
        if 'resume_file' in request.files:
            file = request.files['resume_file']
            if file and file.filename:
                filename = secure_filename(f"resume_{user_id}_{int(datetime.now().timestamp())}_{file.filename}")
                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)
                staff_profile.resume_file = f"uploads/staff/{filename}"
        
        # ID proof file
        if 'id_proof_file' in request.files:
            file = request.files['id_proof_file']
            if file and file.filename:
                filename = secure_filename(f"id_proof_{user_id}_{int(datetime.now().timestamp())}_{file.filename}")
                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)
                staff_profile.id_proof_file = f"uploads/staff/{filename}"
        
        # Update branch assignments
        # Get current assignments
        current_assignments = UserBranchAssignment.query.filter_by(
            user_id=user_id
        ).all()
        
        # Create a set of current branch IDs for comparison
        current_branch_ids = {int(branch_id) for branch_id in branch_ids}
        existing_assignments = {assignment.branch_id: assignment for assignment in current_assignments}
        
        # Handle each existing assignment
        for branch_id, assignment in existing_assignments.items():
            if branch_id in current_branch_ids:
                # Update existing assignment
                assignment.is_active = 1
                assignment.role_at_branch = role
                assignment.assigned_by = current_user_id
                assignment.notes = f"Updated via edit form. Designation: {designation}"
                assignment.assigned_on = datetime.now(timezone.utc)
                current_branch_ids.remove(branch_id)  # Remove from new assignments needed
            else:
                # Deactivate assignment for branches not selected
                assignment.is_active = 0
        
        # Create new assignments for branches not previously assigned
        for branch_id in current_branch_ids:
            assignment = UserBranchAssignment(
                user_id=user_id,
                branch_id=int(branch_id),
                role_at_branch=role,
                assigned_by=current_user_id,
                notes=f"Assigned via edit form. Designation: {designation}"
            )
            db.session.add(assignment)
        
        db.session.commit()
        
        flash(f'Staff member {full_name} updated successfully with all details!', 'success')
        return redirect(url_for('staff.view_staff', user_id=user_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating staff member: {str(e)}', 'error')
        return redirect(url_for('staff.edit_staff', user_id=user_id))

@staff_bp.route('/deactivate/<int:user_id>', methods=['POST'])
@login_required
def deactivate_staff(user_id):
    """Deactivate a staff member"""
    if not session.get('user_id'):
        flash('Please log in to access this page.', 'error')
        return redirect(url_for('auth.login'))
    
    user_role = session.get('role')
    current_user_id = session.get('user_id')
    
    # Check permissions
    if not has_staff_management_access(user_role):
        error_msg = 'Access denied. You do not have permission to deactivate staff.'
        flash(error_msg, 'error')
        if request.is_json or request.headers.get('Content-Type') == 'application/json':
            return jsonify({'success': False, 'message': error_msg}), 403
        return redirect(url_for('staff.list_staff'))
    
    try:
        staff_member = User.query.get_or_404(user_id)
        
        # Check if current user can deactivate this staff member
        staff_branches = get_user_branch_ids(user_id)
        accessible_branches = get_user_accessible_branches(current_user_id) if user_role != 'admin' else [b.id for b in Branch.query.filter_by(is_deleted=0).all()]
        
        if user_role != 'admin' and not any(branch_id in accessible_branches for branch_id in staff_branches):
            error_msg = 'Access denied. You cannot deactivate this staff member.'
            flash(error_msg, 'error')
            if request.is_json or request.headers.get('Content-Type') == 'application/json':
                return jsonify({'success': False, 'message': error_msg}), 403
            return redirect(url_for('staff.list_staff'))
        
        # Business Logic Validations
        
        # 1. Prevent self-deactivation
        if user_id == current_user_id:
            error_msg = 'You cannot deactivate your own account.'
            flash(error_msg, 'error')
            if request.is_json or request.headers.get('Content-Type') == 'application/json':
                return jsonify({'success': False, 'message': error_msg}), 400
            return redirect(url_for('staff.list_staff'))
        
        # 2. Prevent franchise owners from deactivating other franchise owners or admins
        if user_role in ['franchise', 'franchise_owner'] and staff_member.role in ['franchise', 'franchise_owner', 'admin', 'regional_manager']:
            error_msg = 'You do not have permission to deactivate franchise owners, admins, or regional managers.'
            flash(error_msg, 'error')
            if request.is_json or request.headers.get('Content-Type') == 'application/json':
                return jsonify({'success': False, 'message': error_msg}), 403
            return redirect(url_for('staff.list_staff'))
        
        # 3. Prevent regional managers from deactivating franchise owners or admins
        if user_role == 'regional_manager' and staff_member.role in ['franchise', 'franchise_owner', 'admin']:
            error_msg = 'You do not have permission to deactivate franchise owners or admins.'
            flash(error_msg, 'error')
            if request.is_json or request.headers.get('Content-Type') == 'application/json':
                return jsonify({'success': False, 'message': error_msg}), 403
            return redirect(url_for('staff.list_staff'))
        
        # 4. Only admins can deactivate franchise owners
        if staff_member.role in ['franchise', 'franchise_owner'] and user_role != 'admin':
            error_msg = 'Only administrators can deactivate franchise owners.'
            flash(error_msg, 'error')
            if request.is_json or request.headers.get('Content-Type') == 'application/json':
                return jsonify({'success': False, 'message': error_msg}), 403
            return redirect(url_for('staff.list_staff'))
        
        # Soft delete the user
        staff_member.is_deleted = 1
        
        # Deactivate all branch assignments
        assignments = UserBranchAssignment.query.filter_by(
            user_id=user_id,
            is_active=1
        ).all()
        
        for assignment in assignments:
            assignment.is_active = 0
        
        db.session.commit()
        
        flash(f'Staff member {staff_member.full_name} has been deactivated.', 'success')
        
        # Return JSON for AJAX requests
        if request.is_json or request.headers.get('Content-Type') == 'application/json':
            return jsonify({
                'success': True, 
                'message': f'Staff member {staff_member.full_name} has been deactivated.',
                'user_id': user_id
            })
        
    except Exception as e:
        db.session.rollback()
        error_message = f'Error deactivating staff member: {str(e)}'
        flash(error_message, 'error')
        
        # Return JSON for AJAX requests
        if request.is_json or request.headers.get('Content-Type') == 'application/json':
            return jsonify({'success': False, 'message': error_message}), 500
    
    return redirect(url_for('staff.list_staff'))

@staff_bp.route('/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_staff(user_id):
    """Permanently delete a staff member - BACKEND ONLY with business logic protection"""
    if not session.get('user_id'):
        error_msg = 'Please log in to access this page.'
        flash(error_msg, 'error')
        if request.is_json or request.headers.get('Content-Type') == 'application/json':
            return jsonify({'success': False, 'message': error_msg}), 401
        return redirect(url_for('auth.login'))
    
    user_role = session.get('role')
    current_user_id = session.get('user_id')
    
    # Check permissions
    if not has_staff_management_access(user_role):
        error_msg = 'Access denied. You do not have permission to delete staff.'
        flash(error_msg, 'error')
        if request.is_json or request.headers.get('Content-Type') == 'application/json':
            return jsonify({'success': False, 'message': error_msg}), 403
        return redirect(url_for('staff.list_staff'))
    
    try:
        staff_member = User.query.get_or_404(user_id)
        
        # Check if current user can delete this staff member
        staff_branches = get_user_branch_ids(user_id)
        accessible_branches = get_user_accessible_branches(current_user_id) if user_role != 'admin' else [b.id for b in Branch.query.filter_by(is_deleted=0).all()]
        
        if user_role != 'admin' and not any(branch_id in accessible_branches for branch_id in staff_branches):
            error_msg = 'Access denied. You cannot delete this staff member.'
            flash(error_msg, 'error')
            if request.is_json or request.headers.get('Content-Type') == 'application/json':
                return jsonify({'success': False, 'message': error_msg}), 403
            return redirect(url_for('staff.list_staff'))
        
        # Business Logic Validations - Same as deactivate but for deletion
        
        # 1. Prevent self-deletion
        if user_id == current_user_id:
            error_msg = 'You cannot delete your own account.'
            flash(error_msg, 'error')
            if request.is_json or request.headers.get('Content-Type') == 'application/json':
                return jsonify({'success': False, 'message': error_msg}), 400
            return redirect(url_for('staff.list_staff'))
        
        # 2. Prevent franchise owners from deleting other franchise owners or admins
        if user_role in ['franchise', 'franchise_owner'] and staff_member.role in ['franchise', 'franchise_owner', 'admin', 'regional_manager']:
            error_msg = 'You do not have permission to delete franchise owners, admins, or regional managers.'
            flash(error_msg, 'error')
            if request.is_json or request.headers.get('Content-Type') == 'application/json':
                return jsonify({'success': False, 'message': error_msg}), 403
            return redirect(url_for('staff.list_staff'))
        
        # 3. Prevent regional managers from deleting franchise owners or admins
        if user_role == 'regional_manager' and staff_member.role in ['franchise', 'franchise_owner', 'admin']:
            error_msg = 'You do not have permission to delete franchise owners or admins.'
            flash(error_msg, 'error')
            if request.is_json or request.headers.get('Content-Type') == 'application/json':
                return jsonify({'success': False, 'message': error_msg}), 403
            return redirect(url_for('staff.list_staff'))
        
        # 4. Only admins can delete franchise owners
        if staff_member.role in ['franchise', 'franchise_owner'] and user_role != 'admin':
            error_msg = 'Only administrators can delete franchise owners.'
            flash(error_msg, 'error')
            if request.is_json or request.headers.get('Content-Type') == 'application/json':
                return jsonify({'success': False, 'message': error_msg}), 403
            return redirect(url_for('staff.list_staff'))
        
        # Store staff member name for success message
        staff_name = staff_member.full_name or staff_member.username
        
        # Delete related records first (cascade)
        
        # 1. Delete branch assignments
        UserBranchAssignment.query.filter_by(user_id=user_id).delete()
        
        # 2. Delete staff profile if exists
        StaffProfile.query.filter_by(user_id=user_id).delete()
        
        # 3. Delete the user record
        db.session.delete(staff_member)
        
        db.session.commit()
        
        success_msg = f'Staff member {staff_name} has been permanently deleted.'
        flash(success_msg, 'success')
        
        # Return JSON for AJAX requests
        if request.is_json or request.headers.get('Content-Type') == 'application/json':
            return jsonify({
                'success': True, 
                'message': success_msg,
                'user_id': user_id
            })
        
    except Exception as e:
        db.session.rollback()
        error_message = f'Error deleting staff member: {str(e)}'
        flash(error_message, 'error')
        
        # Return JSON for AJAX requests
        if request.is_json or request.headers.get('Content-Type') == 'application/json':
            return jsonify({'success': False, 'message': error_message}), 500
    
    return redirect(url_for('staff.list_staff'))

@staff_bp.route('/api/user-info/<int:user_id>')
@login_required
def get_user_info(user_id):
    """Get user information for AJAX requests"""
    if not session.get('user_id'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_role = session.get('role')
    
    # Check permissions
    if not has_staff_management_access(user_role):
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        user = User.query.get_or_404(user_id)
        
        # Get user's branch assignments
        assignments = UserBranchAssignment.query.filter_by(
            user_id=user_id,
            is_active=1
        ).all()
        
        branch_info = []
        for assignment in assignments:
            branch = Branch.query.get(assignment.branch_id)
            if branch:
                branch_info.append({
                    'id': branch.id,
                    'name': branch.branch_name
                })
        
        # Get staff profile if exists
        staff_profile = StaffProfile.query.filter_by(user_id=user_id).first()
        profile_data = {}
        if staff_profile:
            profile_data = {
                'employee_id': staff_profile.employee_id,
                'designation': staff_profile.designation,
                'primary_mobile': staff_profile.primary_mobile,
                'personal_email': staff_profile.personal_email,
                'joining_date': staff_profile.joining_date.strftime('%Y-%m-%d') if staff_profile.joining_date else None,
                'department': staff_profile.department,
                'profile_photo': staff_profile.profile_photo
            }
        
        return jsonify({
            'id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'role': user.role,
            'branches': branch_info,
            'profile': profile_data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@staff_bp.route('/api/profile/<int:user_id>')
@login_required
def get_staff_profile_api(user_id):
    """API endpoint to get staff profile details for modal display"""
    try:
        # Get user and their profile
        user = User.query.get_or_404(user_id)
        staff_profile = StaffProfile.query.filter_by(user_id=user_id).first()
        
        # Get branch assignments
        branch_assignments = UserBranchAssignment.query.filter_by(user_id=user_id).all()
        branches = [assignment.branch.branch_name for assignment in branch_assignments] if branch_assignments else []
        
        # Prepare profile data
        profile_data = {
            'user_id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'role': user.role,
            'is_active': True,  # Default active status
            'branches': branches
        }
        
        # Add staff profile data if exists
        if staff_profile:
            profile_data.update({
                'employee_id': staff_profile.employee_id,
                'primary_mobile': staff_profile.primary_mobile,
                'secondary_mobile': staff_profile.secondary_mobile,
                'personal_email': staff_profile.personal_email,
                'official_email': staff_profile.official_email,
                'designation': staff_profile.designation,
                'department': staff_profile.department,
                'joining_date': staff_profile.joining_date.strftime('%Y-%m-%d') if staff_profile.joining_date else None,
                'date_of_birth': staff_profile.date_of_birth.strftime('%Y-%m-%d') if staff_profile.date_of_birth else None,
                'gender': staff_profile.gender,
                'marital_status': staff_profile.marital_status,
                'blood_group': staff_profile.blood_group,
                'nationality': staff_profile.nationality,
                'current_address': staff_profile.current_address,
                'permanent_address': staff_profile.permanent_address,
                'city': staff_profile.city,
                'state': staff_profile.state,
                'country': staff_profile.country,
                'pincode': staff_profile.pincode,
                'emergency_contact_name': staff_profile.emergency_contact_name,
                'emergency_contact_mobile': staff_profile.emergency_contact_mobile,
                'emergency_contact_relation': staff_profile.emergency_contact_relation,
                'employment_type': staff_profile.employment_type,
                'basic_salary': float(staff_profile.basic_salary) if staff_profile.basic_salary else None,
                'gross_salary': float(staff_profile.gross_salary) if staff_profile.gross_salary else None,
                'work_location': staff_profile.work_location,
                'technical_skills': staff_profile.technical_skills,
                'soft_skills': staff_profile.soft_skills,
                'languages_known': staff_profile.languages_known,
                'teaching_subjects': staff_profile.teaching_subjects,
                'years_of_experience': staff_profile.years_of_experience,
                'previous_experience': staff_profile.previous_experience,
                'highest_qualification': staff_profile.highest_qualification,
                'university_college': staff_profile.university_college,
                'graduation_year': staff_profile.graduation_year,
                'specialization': staff_profile.specialization,
                'additional_certifications': staff_profile.additional_certifications,
                'bank_name': staff_profile.bank_name,
                'bank_account_number': staff_profile.bank_account_number,
                'bank_ifsc': staff_profile.bank_ifsc,
                'pan_number': staff_profile.pan_number,
                'aadhar_number': staff_profile.aadhar_number,
                'notes': staff_profile.notes,
                'hobbies_interests': staff_profile.hobbies_interests,
                'profile_photo': staff_profile.profile_photo,
                'is_active': staff_profile.is_active
            })
        
        return jsonify({
            'success': True,
            'profile': profile_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
