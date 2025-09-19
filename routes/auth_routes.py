from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, flash
from models.user_model import User
from init_db import db
import hashlib
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        # Import audit logging
        from routes.audit_routes import log_user_action, create_security_alert
        
        if not username or not password:
            flash("❌ Username and password are required", "danger")
            
            # Log failed login attempt
            log_user_action(
                action="LOGIN_FAILED",
                target="AUTH_SYSTEM",
                details=f"Missing credentials for username: {username or 'Not provided'}",
                success=False,
                risk_level="MEDIUM"
            )
            
            return render_template("auth/login.html")
        
        user = User.query.filter_by(username=username).first()
        
        # Enhanced password verification supporting both MD5 (legacy) and Werkzeug (secure) hashes
        password_valid = False
        
        if user and user.password:
            # Check if it's a legacy MD5 hash (32 characters, hexadecimal)
            if len(user.password) == 32 and all(c in '0123456789abcdef' for c in user.password):
                # Legacy MD5 verification
                password_hash = hashlib.md5(password.encode()).hexdigest()
                password_valid = (user.password == password_hash)
            else:
                # Modern Werkzeug hash verification (pbkdf2, scrypt, argon2, etc.)
                password_valid = check_password_hash(user.password, password)
        
        if user and password_valid:
            # Set session data
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            session["full_name"] = user.full_name
            
            # Set branch information - handle multiple branches for franchise users
            if user.role == 'franchise':
                # For franchise users, get all assigned branches
                user_branches = user.get_all_user_branches()
                user_branch_ids = user.get_user_branch_ids()
                
                if user_branches:
                    # Store all branch IDs in session
                    session["user_branch_ids"] = user_branch_ids
                    # For backward compatibility, also store the first branch
                    session["user_branch_id"] = user_branch_ids[0]
                    session["branch_name"] = user_branches[0].branch_name
                    # Store all branch names for display
                    session["all_branch_names"] = [branch.branch_name for branch in user_branches]
                else:
                    session["user_branch_id"] = None
                    session["user_branch_ids"] = []
                    session["branch_name"] = None
                    session["all_branch_names"] = []
            else:
                # For other roles, use single branch logic
                user_branch = user.get_user_branch()
                if user_branch:
                    session["user_branch_id"] = user_branch.id
                    session["user_branch_ids"] = [user_branch.id]
                    session["branch_name"] = user_branch.branch_name
                    session["all_branch_names"] = [user_branch.branch_name]
                else:
                    session["user_branch_id"] = None
                    session["user_branch_ids"] = []
                    session["branch_name"] = None
                    session["all_branch_names"] = []
            
            flash(f"✅ Welcome back, {user.full_name}!", "success")
            
            # Log successful login
            log_user_action(
                action="LOGIN_SUCCESS",
                target="AUTH_SYSTEM",
                details=f"Successful login for role: {user.role}",
                success=True,
                risk_level="LOW"
            )
            
            # Role-based redirect logic
            if user.role == 'admin':
                return redirect(url_for("branch.list_branches"))
            elif user.role in ['regional_manager']:
                return redirect(url_for("dashboard_bp.admin_dashboard"))  # Regional managers use admin dashboard with filtering
            elif user.role == 'franchise':
                return redirect(url_for("dashboard_bp.franchise_dashboard"))  # Dedicated franchise dashboard
            elif user.role in ['branch_manager', 'manager']:
                return redirect(url_for("dashboard_bp.branch_manager_dashboard"))  # Branch manager dashboard
            elif user.role in ['staff']:
                return redirect(url_for("dashboard_bp.branch_manager_dashboard"))  # Staff use branch manager dashboard with limited access
            elif user.role == 'trainer':
                return redirect(url_for("dashboard_bp.trainer_dashboard"))  # Trainer dashboard
            elif user.role == 'student':
                return redirect(url_for("dashboard_bp.student_dashboard"))  # Student dashboard
            elif user.role == 'parent':
                return redirect(url_for("dashboard_bp.parent_dashboard"))  # Parent dashboard
            else:
                # Unknown role, redirect to login with error
                flash("❌ Unknown user role. Please contact administrator.", "warning")
                return redirect(url_for("auth.login"))
        else:
            # Log failed login attempt
            log_user_action(
                action="LOGIN_FAILED",
                target="AUTH_SYSTEM",
                details=f"Invalid credentials for username: {username}",
                success=False,
                risk_level="HIGH"
            )
            
            # Create security alert for repeated failed attempts
            # You can enhance this to track IP-based attempts
            create_security_alert(
                alert_type="FAILED_LOGIN",
                severity="MEDIUM",
                description=f"Failed login attempt for username: {username}",
                username=username
            )
            
            flash("❌ Invalid username or password", "danger")
    
    return render_template("auth/login.html")

@auth_bp.route("/logout")
def logout():
    # Get user info before clearing session
    user_name = session.get("full_name", session.get("username", "User"))
    user_id = session.get("user_id")
    username = session.get("username")
    
    # Import audit logging
    from routes.audit_routes import log_user_action
    
    # Log logout action
    if user_id and username:
        log_user_action(
            action="LOGOUT",
            target="AUTH_SYSTEM", 
            details=f"User logout: {user_name}",
            success=True,
            risk_level="LOW"
        )
    
    # Clear session
    session.clear()
    
    # Show logout page instead of redirect
    flash(f"✅ Goodbye {user_name}! You have been logged out successfully.", "success")
    return render_template("auth/logout.html")

@auth_bp.route("/change-password", methods=["GET", "POST"])
def change_password():
    """Allow users to change their password"""
    if not session.get("user_id"):
        flash("❌ Please login to access this page", "warning")
        return redirect(url_for("auth.login"))
    
    user_id = session.get("user_id")
    user = User.query.get(user_id)
    
    if not user:
        flash("❌ User not found", "danger")
        return redirect(url_for("auth.login"))
    
    if request.method == "POST":
        current_password = request.form.get("current_password", "").strip()
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        
        # Import audit logging
        from routes.audit_routes import log_user_action
        
        # Validation
        if not all([current_password, new_password, confirm_password]):
            flash("❌ All fields are required", "danger")
            return render_template("auth/change_password.html", user=user)
        
        if new_password != confirm_password:
            flash("❌ New passwords do not match", "danger")
            return render_template("auth/change_password.html", user=user)
        
        if len(new_password) < 6:
            flash("❌ New password must be at least 6 characters long", "danger")
            return render_template("auth/change_password.html", user=user)
        
        # Check if current password is correct
        password_valid = False
        if user.password:
            # Check if it's a legacy MD5 hash (32 characters, hexadecimal)
            if len(user.password) == 32 and all(c in '0123456789abcdef' for c in user.password):
                # Legacy MD5 verification
                password_hash = hashlib.md5(current_password.encode()).hexdigest()
                password_valid = (user.password == password_hash)
            else:
                # Modern Werkzeug hash verification
                password_valid = check_password_hash(user.password, current_password)
        
        if not password_valid:
            flash("❌ Current password is incorrect", "danger")
            log_user_action(
                action="PASSWORD_CHANGE_FAILED",
                target="USER_ACCOUNT",
                details=f"Failed password change attempt - wrong current password",
                success=False,
                risk_level="MEDIUM"
            )
            return render_template("auth/change_password.html", user=user)
        
        # Update password with secure hash
        user.password = generate_password_hash(new_password)
        
        try:
            db.session.commit()
            
            # Log successful password change
            log_user_action(
                action="PASSWORD_CHANGE_SUCCESS",
                target="USER_ACCOUNT",
                details=f"Password successfully changed",
                success=True,
                risk_level="LOW"
            )
            
            flash("✅ Password changed successfully! Please login again for security.", "success")
            
            # Force logout for security
            session.clear()
            return redirect(url_for("auth.login"))
            
        except Exception as e:
            db.session.rollback()
            flash("❌ Error updating password. Please try again.", "danger")
            log_user_action(
                action="PASSWORD_CHANGE_FAILED",
                target="USER_ACCOUNT",
                details=f"Database error during password change: {str(e)}",
                success=False,
                risk_level="HIGH"
            )
            return render_template("auth/change_password.html", user=user)
    
    return render_template("auth/change_password.html", user=user)

def get_current_user():
    """Helper function to get current logged-in user"""
    user_id = session.get("user_id")
    if user_id:
        return User.query.get(user_id)
    return None

def login_required(f):
    """Decorator to require login for certain routes"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            flash("❌ Please login to access this page", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function
