from flask import Blueprint, request, jsonify, render_template, redirect, url_for
from werkzeug.utils import secure_filename
from models.student_model import Student
from models.batch_model import Batch
from models.branch_model import Branch
from models.user_model import User
from models.course_model import Course
from flask import flash, session
from utils.auth import login_required
from utils.timezone_helper import parse_date_string
from init_db import db
import os
import uuid
from datetime import datetime

student_bp = Blueprint("students", __name__)
UPLOAD_FOLDER = "static/uploads"

def generate_student_id():
    """Generate a sequential student ID starting with 1516170"""
    try:
        # Get the highest existing student ID that starts with 1516170 (as a number)
        result = db.session.execute(
            db.text("SELECT student_id FROM students WHERE student_id REGEXP '^1516170[0-9]*$' ORDER BY CAST(student_id AS INTEGER) DESC LIMIT 1")
        ).fetchone()
        
        if result:
            # Extract the numeric part and increment
            last_id = int(result[0])
            next_number = last_id + 1
        else:
            # Start with 1516170 if no existing IDs found
            next_number = 1516170
        
        # Double-check that this ID doesn't exist (safety check)
        while Student.query.filter_by(student_id=str(next_number)).first():
            next_number += 1
        
        return str(next_number)
        
    except Exception as e:
        # Fallback: query differently for SQLite compatibility
        try:
            print(f"First method failed: {e}, trying alternative method...")
            # Get all student IDs that start with 1516170 and are numeric
            results = db.session.execute(
                db.text("SELECT student_id FROM students WHERE student_id LIKE '1516170%'")
            ).fetchall()
            
            if results:
                # Convert to integers and find the maximum
                numeric_ids = []
                for row in results:
                    try:
                        numeric_ids.append(int(row[0]))
                    except ValueError:
                        continue  # Skip non-numeric IDs
                
                if numeric_ids:
                    next_number = max(numeric_ids) + 1
                else:
                    next_number = 1516170  # Start with 1516170 if no valid numeric IDs
            else:
                next_number = 1516170  # Start with 1516170 if no existing IDs
            
            # Double-check that this ID doesn't exist (safety check)
            while Student.query.filter_by(student_id=str(next_number)).first():
                next_number += 1
            
            return str(next_number)
            
        except Exception as e2:
            # Final fallback to old method if everything fails
            print(f"Error generating student ID: {e2}")
            return "S" + str(uuid.uuid4().hex[:6]).upper()

@student_bp.route("/", methods=["GET"])
def get_students():
    students = Student.query.all()
    return jsonify([s.to_dict() for s in students])

@student_bp.route("/", methods=["POST"])
def create_student():
    data = request.json
    student = Student(**data)
    db.session.add(student)
    db.session.commit()
    return jsonify(student.to_dict()), 201

@student_bp.route("/register", methods=["GET", "POST"])
def register_student():
    # Get user information from session
    user_id = session.get("user_id")
    if not user_id:
        flash("❌ Please login to access student registration", "warning")
        return redirect(url_for("auth.login"))
    
    current_user = User.query.get(user_id)
    if not current_user:
        flash("❌ Invalid session. Please login again", "danger")
        return redirect(url_for("auth.login"))
    
    if request.method == "POST":
        form = request.form
        
        # Validation
        if not form.get("full_name") or not form.get("mobile"):
            flash("❌ Full Name and Mobile are required.", "danger")
            return redirect(url_for("students.register_student"))
        
        photo_file = request.files.get("photo")
        student_id = generate_student_id()

        # ✅ Convert DOB string to Python date
        dob_str = form.get("dob")
        dob = parse_date_string(dob_str) if dob_str else None

        # Get student status (default to Active if not provided)
        status = form.get("status", "Active")

        # Handle file uploads
        photo_filename = None
        id_proof_filename = None
        
        if photo_file and photo_file.filename != "":
            filename = secure_filename(photo_file.filename)
            ext = os.path.splitext(filename)[1]
            photo_filename = f"{student_id}_photo{ext}"
            photo_file.save(os.path.join(UPLOAD_FOLDER, photo_filename))

        # Handle ID proof upload
        id_proof_file = request.files.get("id_proof")
        if id_proof_file and id_proof_file.filename != "":
            filename = secure_filename(id_proof_file.filename)
            ext = os.path.splitext(filename)[1]
            id_proof_filename = f"{student_id}_id_proof{ext}"
            id_proof_file.save(os.path.join(UPLOAD_FOLDER, id_proof_filename))

        # Get batch information to populate course_name and verify branch access
        batch_id = form.get("batch_id")
        branch_id = form.get("branch_id")
        course_name = None
        course_id = None
        
        if batch_id:
            selected_batch = Batch.query.get(batch_id)
            if selected_batch:
                course_name = selected_batch.course_name
                # Get course_id from Course table for LMS integration
                course = Course.query.filter_by(course_name=course_name).first()
                if course:
                    course_id = course.id
                    
                # Security check: Verify batch belongs to selected branch
                if str(selected_batch.branch_id) != str(branch_id):
                    flash("❌ Selected batch does not belong to the selected branch.", "danger")
                    return redirect(url_for("students.register_student"))
                    
                # Additional security: If user is not corporate admin, verify they can access this branch
                if not current_user.has_corporate_access():
                    user_branch = current_user.get_user_branch()
                    if not user_branch or str(user_branch.id) != str(branch_id):
                        flash("❌ You don't have permission to register students for this branch.", "danger")
                        return redirect(url_for("students.register_student"))

        student = Student(
            student_id=student_id,
            full_name=form.get("full_name"),
            gender=form.get("gender"),
            dob=dob,  # ✅ Use converted Python date
            mobile=form.get("mobile"),
            email=form.get("email"),
            address=form.get("address"),
            batch_id=batch_id,
            course_name=course_name,
            course_id=course_id,  # ✅ Set course_id for LMS integration
            branch_id=branch_id,
            guardian_name=form.get("guardian_name"),
            guardian_mobile=form.get("guardian_mobile"),
            qualification=form.get("qualification"),
            admission_mode=form.get("admission_mode"),
            referred_by=form.get("referred_by"),
            lead_source=form.get("lead_source", "Walk-in"),  # ✅ New field for lead tracking
            photo_filename=photo_filename,
            id_proof_filename=id_proof_filename,
            registered_by=current_user.username,
            status=status
        )

        db.session.add(student)
        db.session.commit()
        
        # ✅ Auto-create lead for direct admissions (if enabled)
        create_auto_lead = form.get("create_auto_lead") == "on"  # Checkbox in form
        if create_auto_lead:
            try:
                auto_lead = student.create_lead_from_admission(
                    created_by_user_id=current_user.id,
                    course_interest=course_name
                )
                if auto_lead:
                    db.session.commit()  # Commit the lead creation
                    success_msg = f"✅ Student registered successfully! Auto-lead created: {auto_lead.lead_sl_number}"
                else:
                    success_msg = "✅ Student registered successfully! (Auto-lead creation skipped)"
            except Exception as e:
                # Don't fail student registration if lead creation fails
                success_msg = f"✅ Student registered successfully! (Auto-lead creation failed: {str(e)})"
        else:
            success_msg = "✅ Student registered successfully!"
            
        flash(success_msg, "success")
            
        return redirect(url_for("students.register_student"))

    # GET request - determine user's branch access from session
    user_branch_id = session.get("user_branch_id")
    branch_name = session.get("branch_name")
    branches = None
    batches = []
    
    if current_user.has_corporate_access():
        # Corporate admin - show all branches
        branches = Branch.query.all()
    else:
        # Franchise user - get their specific branch
        if user_branch_id:
            # Load only active batches for their branch
            batches = Batch.query.filter_by(
                branch_id=user_branch_id, 
                is_deleted=0, 
                status='Active'
            ).all()

    return render_template("students/register.html", 
                         branches=branches,
                         batches=batches,
                         user_branch_id=user_branch_id,
                         branch_name=branch_name)

@student_bp.route("/list", methods=["GET"])
@login_required
def list_students():
    """List all students with role-based branch filtering"""
    try:
        from flask import session
        from init_db import db
        
        current_user_id = session.get('user_id')
        current_user = User.query.get(current_user_id)
        
        # Base query for active students
        query = Student.query.filter_by(is_deleted=0)
        
        # Apply role-based branch filtering
        if current_user.role == 'franchise':
            # Franchise owners - get their branch from session first, then database
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                query = query.filter_by(branch_id=user_branch_id)
            else:
                # Query user_branch_assignments table
                user_branches = db.session.execute(
                    db.text("SELECT branch_id FROM user_branch_assignments WHERE user_id = :user_id AND is_active = 1"),
                    {"user_id": current_user_id}
                ).fetchall()
                
                if user_branches:
                    branch_ids = [row[0] for row in user_branches]
                    query = query.filter(Student.branch_id.in_(branch_ids))
                elif current_user.branch_id:
                    # Fallback to user's direct branch_id
                    query = query.filter_by(branch_id=current_user.branch_id)
                
        elif current_user.role == 'regional_manager':
            # Regional managers - check user_branch_assignments table
            user_branches = db.session.execute(
                db.text("SELECT branch_id FROM user_branch_assignments WHERE user_id = :user_id AND is_active = 1"),
                {"user_id": current_user_id}
            ).fetchall()
            
            if user_branches:
                branch_ids = [row[0] for row in user_branches]
                query = query.filter(Student.branch_id.in_(branch_ids))
            # Otherwise show all (admin-like access for regional managers)
            
        elif current_user.role in ['branch_manager', 'staff', 'trainer']:
            # Branch-level users - only their specific branch
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                query = query.filter_by(branch_id=user_branch_id)
            elif current_user.branch_id:
                query = query.filter_by(branch_id=current_user.branch_id)
        # Admin sees all students
        
        # Add course filtering if course_id parameter is provided
        course_id = request.args.get('course_id')
        if course_id:
            try:
                course_id = int(course_id)
                query = query.filter_by(course_id=course_id)
                print(f"DEBUG: Filtering by course_id: {course_id}")
            except ValueError:
                print(f"DEBUG: Invalid course_id parameter: {course_id}")
        
        students = query.order_by(Student.admission_date.desc()).all()
        
        # Debug: Print student count
        print(f"DEBUG: Found {len(students)} students for user role {current_user.role}")
        for student in students[:3]:  # Print first 3 students
            print(f"  - {student.student_id}: {student.full_name} (Branch: {student.branch_id})")
        
        # Get branch information for display
        branches = {branch.id: branch.branch_name for branch in Branch.query.all()}
        
        return render_template("students/list_students.html", students=students, branches=branches)
        
    except Exception as e:
        flash(f'Error loading students: {str(e)}', 'error')
        # return redirect(url_for('dashboard_bp.franchise_owner_dashboard'))

@student_bp.route("/api/student/<string:student_id>")
@login_required
def api_get_student(student_id):
    """API endpoint to get specific student details"""
    try:
        from flask import session
        from init_db import db
        
        current_user_id = session.get('user_id')
        current_user = User.query.get(current_user_id)
        student = Student.query.filter_by(student_id=student_id).first_or_404()
        
        # Validate access based on role
        if current_user.role == 'franchise':
            # Check branch access using session or database
            user_branch_id = session.get("user_branch_id")
            has_access = False
            
            if user_branch_id and student.branch_id == user_branch_id:
                has_access = True
            else:
                # Query user_branch_assignments table
                user_branches = db.session.execute(
                    db.text("SELECT branch_id FROM user_branch_assignments WHERE user_id = :user_id AND is_active = 1"),
                    {"user_id": current_user_id}
                ).fetchall()
                
                if user_branches:
                    branch_ids = [row[0] for row in user_branches]
                    has_access = student.branch_id in branch_ids
                elif current_user.branch_id:
                    has_access = student.branch_id == current_user.branch_id
                
            if not has_access:
                return jsonify({'success': False, 'error': 'Access denied'}), 403
                
        elif current_user.role == 'regional_manager':
            # Regional managers - check user_branch_assignments table
            user_branches = db.session.execute(
                db.text("SELECT branch_id FROM user_branch_assignments WHERE user_id = :user_id AND is_active = 1"),
                {"user_id": current_user_id}
            ).fetchall()
            
            if user_branches:
                branch_ids = [row[0] for row in user_branches]
                if student.branch_id not in branch_ids:
                    return jsonify({'success': False, 'error': 'Access denied'}), 403
            # Otherwise allow access (admin-like for regional managers)
            
        elif current_user.role in ['branch_manager', 'staff', 'trainer']:
            user_branch_id = session.get("user_branch_id")
            if user_branch_id and student.branch_id != user_branch_id:
                return jsonify({'success': False, 'error': 'Access denied'}), 403
            elif current_user.branch_id and student.branch_id != current_user.branch_id:
                return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        return jsonify({
            'success': True,
            'student': student.to_dict()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@student_bp.route("/view/<string:student_id>")
@login_required
def view_student(student_id):
    """View individual student details page"""
    try:
        from flask import session
        from init_db import db
        from models.branch_model import Branch
        
        current_user_id = session.get('user_id')
        current_user = User.query.get(current_user_id)
        student = Student.query.filter_by(student_id=student_id).first_or_404()
        
        # Validate access based on role (same logic as API endpoint)
        if current_user.role == 'franchise':
            # Check branch access using session or database
            user_branch_id = session.get("user_branch_id")
            has_access = False
            
            if user_branch_id and student.branch_id == user_branch_id:
                has_access = True
            else:
                # Query user_branch_assignments table
                user_branches = db.session.execute(
                    db.text("SELECT branch_id FROM user_branch_assignments WHERE user_id = :user_id AND is_active = 1"),
                    {"user_id": current_user_id}
                ).fetchall()
                
                if user_branches:
                    branch_ids = [row[0] for row in user_branches]
                    has_access = student.branch_id in branch_ids
                elif current_user.branch_id:
                    has_access = student.branch_id == current_user.branch_id
                
            if not has_access:
                flash('Access denied. You can only view students from your branch.', 'error')
                return redirect(url_for('students.list_students'))
                
        elif current_user.role == 'regional_manager':
            # Regional managers - check user_branch_assignments table
            user_branches = db.session.execute(
                db.text("SELECT branch_id FROM user_branch_assignments WHERE user_id = :user_id AND is_active = 1"),
                {"user_id": current_user_id}
            ).fetchall()
            
            if user_branches:
                branch_ids = [row[0] for row in user_branches]
                if student.branch_id not in branch_ids:
                    flash('Access denied. You can only view students from your assigned branches.', 'error')
                    return redirect(url_for('students.list_students'))
            # Otherwise allow access (admin-like for regional managers)
            
        elif current_user.role in ['branch_manager', 'staff', 'trainer']:
            user_branch_id = session.get("user_branch_id")
            if user_branch_id and student.branch_id != user_branch_id:
                flash('Access denied. You can only view students from your branch.', 'error')
                return redirect(url_for('students.list_students'))
            elif current_user.branch_id and student.branch_id != current_user.branch_id:
                flash('Access denied. You can only view students from your branch.', 'error')
                return redirect(url_for('students.list_students'))
        
        # Get branch name for display
        branch = Branch.query.get(student.branch_id)
        branch_name = branch.branch_name if branch else "Unknown Branch"
        
        return render_template("students/view.html", student=student, branch_name=branch_name)
        
    except Exception as e:
        flash(f'Error loading student details: {str(e)}', 'error')
        return redirect(url_for('students.list_students'))

@student_bp.route("/edit/<string:student_id>", methods=["GET", "POST"])
@login_required
def edit_student(student_id):
    """Edit student details"""
    try:
        from flask import session
        from init_db import db
        from models.branch_model import Branch
        from models.batch_model import Batch
        from datetime import datetime
        
        current_user_id = session.get('user_id')
        current_user = User.query.get(current_user_id)
        student = Student.query.filter_by(student_id=student_id).first_or_404()
        
        # Validate access based on role (same logic as view_student)
        if current_user.role == 'franchise':
            user_branch_id = session.get("user_branch_id")
            has_access = False
            
            if user_branch_id and student.branch_id == user_branch_id:
                has_access = True
            else:
                user_branches = db.session.execute(
                    db.text("SELECT branch_id FROM user_branch_assignments WHERE user_id = :user_id AND is_active = 1"),
                    {"user_id": current_user_id}
                ).fetchall()
                
                if user_branches:
                    branch_ids = [row[0] for row in user_branches]
                    has_access = student.branch_id in branch_ids
                elif current_user.branch_id:
                    has_access = student.branch_id == current_user.branch_id
                
            if not has_access:
                flash('Access denied. You can only edit students from your branch.', 'error')
                return redirect(url_for('students.list_students'))
                
        elif current_user.role == 'regional_manager':
            user_branches = db.session.execute(
                db.text("SELECT branch_id FROM user_branch_assignments WHERE user_id = :user_id AND is_active = 1"),
                {"user_id": current_user_id}
            ).fetchall()
            
            if user_branches:
                branch_ids = [row[0] for row in user_branches]
                if student.branch_id not in branch_ids:
                    flash('Access denied. You can only edit students from your assigned branches.', 'error')
                    return redirect(url_for('students.list_students'))
                    
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if user_branch_id and student.branch_id != user_branch_id:
                flash('Access denied. You can only edit students from your branch.', 'error')
                return redirect(url_for('students.list_students'))
            elif current_user.branch_id and student.branch_id != current_user.branch_id:
                flash('Access denied. You can only edit students from your branch.', 'error')
                return redirect(url_for('students.list_students'))
        
        elif current_user.role == 'trainer':
            # Trainers cannot edit student information - read-only access
            flash('Access denied. Trainers cannot edit student information. Contact your branch manager for student updates.', 'error')
            return redirect(url_for('students.view_student', student_id=student_id))
        
        if request.method == "POST":
            # Handle form submission
            form = request.form
            
            # Update student information
            student.full_name = form.get("full_name")
            student.gender = form.get("gender")
            student.mobile = form.get("mobile")
            student.email = form.get("email")
            student.address = form.get("address")
            student.guardian_name = form.get("guardian_name")
            student.guardian_mobile = form.get("guardian_mobile")
            student.qualification = form.get("qualification")
            student.admission_mode = form.get("admission_mode")
            student.referred_by = form.get("referred_by")
            student.status = form.get("status", "Active")  # ✅ Update status
            
            # Handle DOB update
            dob_str = form.get("dob")
            if dob_str:
                student.dob = parse_date_string(dob_str)
            
            # Handle batch change
            new_batch_id = form.get("batch_id")
            if new_batch_id and new_batch_id != str(student.batch_id):
                new_batch = Batch.query.get(new_batch_id)
                if new_batch and new_batch.branch_id == student.branch_id:
                    student.batch_id = new_batch_id
                    student.course_name = new_batch.course_name
                else:
                    flash("Selected batch is not valid for this student's branch.", "error")
                    
            db.session.commit()
            flash("✅ Student details updated successfully!", "success")
            return redirect(url_for('students.view_student', student_id=student_id))
        
        # GET request - load data for form
        branch = Branch.query.get(student.branch_id)
        branch_name = branch.branch_name if branch else "Unknown Branch"
        
        # Get available active batches for the student's branch
        batches = Batch.query.filter_by(
            branch_id=student.branch_id, 
            is_deleted=0, 
            status='Active'
        ).all()
        
        return render_template("students/edit.html", 
                             student=student, 
                             branch_name=branch_name,
                             batches=batches)
        
    except Exception as e:
        flash(f'Error editing student: {str(e)}', 'error')
        return redirect(url_for('students.list_students'))

@student_bp.route("/api/batches", methods=["GET"])
@login_required
def api_get_batches():
    """API endpoint to get active batches for a specific branch"""
    try:
        branch_id = request.args.get('branch_id')
        if not branch_id:
            return jsonify({'success': False, 'error': 'Branch ID is required'}), 400
        
        # Get current user for security checks
        current_user_id = session.get('user_id')
        current_user = User.query.get(current_user_id)
        
        # Security check: Verify user can access this branch
        if not current_user.has_corporate_access():
            user_branch_id = session.get("user_branch_id")
            if str(user_branch_id) != str(branch_id):
                return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        # Get only active batches for the branch
        batches = Batch.query.filter_by(
            branch_id=branch_id, 
            is_deleted=0, 
            status='Active'
        ).all()
        
        return jsonify({
            'success': True,
            'batches': [batch.to_dict() for batch in batches]
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500