from flask import Flask
from flask_cors import CORS
from config import Config
from init_db import db, init_database  # ✅ Import both db and init function
from utils.timezone_helper import utc_to_ist, register_template_filters
from datetime import datetime

def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")

    # Load config
    app.config.from_object(Config)

    # Debug print
    print("DB Path:", app.config["SQLALCHEMY_DATABASE_URI"])

    # Initialize DB and CORS
    db.init_app(app)
    CORS(app)

    # Custom Jinja2 filter for datetime formatting
    @app.template_filter('format_datetime')
    def format_datetime_filter(value, format_string=None):
        if not value:
            return 'N/A'
        if isinstance(value, str):
            return value
        try:
            if format_string:
                return utc_to_ist(value).strftime(format_string)
            else:
                return utc_to_ist(value).strftime("%Y-%m-%d %H:%M:%S")
        except:
            return str(value)

    # Custom Jinja2 filter for date difference calculation
    @app.template_filter('date_diff')
    def date_diff_filter(date_to, date_from):
        try:
            from datetime import datetime
            if isinstance(date_to, str):
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            if isinstance(date_from, str):
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            return (date_to - date_from).days
        except:
            return 0
    
    # Custom Jinja2 filter for safe date formatting
    @app.template_filter('format_date')
    def format_date_filter(value, format_string='%d %b %Y'):
        """Safely format date values, handling both datetime objects and strings"""
        if not value:
            return 'N/A'
        try:
            from datetime import datetime
            if isinstance(value, str):
                # Try to parse the string date
                date_obj = datetime.strptime(value, '%Y-%m-%d')
                return date_obj.strftime(format_string)
            elif hasattr(value, 'strftime'):
                # It's a datetime object
                return value.strftime(format_string)
            else:
                return str(value)
        except:
            return str(value) if value else 'N/A'
    
    # Custom Jinja2 filter for converting newlines to HTML breaks
    @app.template_filter('nl2br')
    def nl2br_filter(value):
        """Convert newlines to HTML <br> tags"""
        if not value:
            return ''
        from markupsafe import Markup
        return Markup(str(value).replace('\n', '<br>\n'))

    # Register enhanced timezone template filters for Indian format
    register_template_filters(app)
    
    # Add global timezone configuration for PythonAnywhere deployment
    @app.context_processor
    def inject_timezone_helpers():
        """Inject timezone helper functions into all templates"""
        from utils.timezone_helper import format_datetime_indian, format_date_indian, get_current_ist_formatted
        return {
            'format_datetime_indian': format_datetime_indian,
            'format_date_indian': format_date_indian,
            'current_ist_time': get_current_ist_formatted,
            'timezone_note': 'All times shown in Indian Standard Time (IST)'
        }

    # Initialize database tables
    with app.app_context():
        init_database(app)
        
        # Apply database optimizations
        try:
            from utils.cache_utils import optimize_db_connection
            optimize_db_connection()
        except Exception as e:
            print(f"Warning: Database optimization failed: {e}")

    # Performance monitoring setup
    @app.before_request
    def before_request():
        from time import time
        from flask import g
        g.start_time = time()

    @app.after_request
    def after_request(response):
        from time import time
        from flask import g, request
        if hasattr(g, 'start_time'):
            duration = time() - g.start_time
            # Log slow requests (>2 seconds)
            if duration > 2.0:
                app.logger.warning(f"Slow request: {duration:.2f}s - {request.endpoint}")
        return response

    # Register Blueprints
    from routes.student_routes import student_bp
    from routes.invoice_routes import invoice_bp
    from routes.dashboard_routes import dashboard_bp
    from routes.lms_routes import lms_bp  # Add LMS routes
    from routes.lms_content_management_routes import lms_content_management  # Add LMS Content Management
    from routes.auth_routes import auth_bp
    from routes.installment_routes import installment_bp
    from routes.branch_routes import branch_bp
    from routes.audit_routes import audit_bp
    # from routes.sms_routes import sms_routes  # Temporarily disabled - SMS models removed
    from routes.finance_routes import finance_bp
    from routes.batch_routes import batch_bp
    from routes.student_attendance_routes import attendance_bp
    from routes.staff_routes import staff_bp
    from routes.lead_routes import lead_bp
    from routes.expense_routes import expense_bp
    from routes.course_routes import course_bp
    from routes.student_portal_routes import student_portal_bp  # NEW: Student Portal
    from routes.import_routes import import_bp  # NEW: Import functionality

    app.register_blueprint(student_bp, url_prefix="/students")
    app.register_blueprint(invoice_bp, url_prefix="/invoices")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(installment_bp, url_prefix="/installments")
    app.register_blueprint(branch_bp)
    app.register_blueprint(audit_bp, url_prefix="/audit")
    # app.register_blueprint(sms_routes, url_prefix="/sms")  # Temporarily disabled - SMS models removed
    app.register_blueprint(finance_bp)
    app.register_blueprint(batch_bp)
    app.register_blueprint(attendance_bp, url_prefix="/attendance")
    app.register_blueprint(staff_bp, url_prefix="/staff")
    app.register_blueprint(lead_bp, url_prefix="/leads")
    app.register_blueprint(expense_bp, url_prefix="/expenses")
    app.register_blueprint(course_bp, url_prefix="/courses")
    app.register_blueprint(lms_bp)  # Register LMS routes
    app.register_blueprint(lms_content_management)  # Register LMS Content Management
    app.register_blueprint(student_portal_bp)  # NEW: Register Student Portal
    app.register_blueprint(import_bp)  # NEW: Register Import routes

    # Add root route for intelligent redirection
    @app.route("/")
    def index():
        from flask import session, redirect, url_for, render_template
        
        # If user is logged in, redirect to their appropriate dashboard
        if session.get("user_id"):
            role = session.get("role")
            if role == 'admin':
                return redirect(url_for("branch.list_branches"))
            elif role == 'franchise':
                return redirect(url_for("dashboard_bp.franchise_dashboard"))
            elif role == 'branch_manager':
                return redirect(url_for("dashboard_bp.branch_manager_dashboard"))
            elif role == 'trainer':
                return redirect(url_for("dashboard_bp.trainer_dashboard"))
            elif role == 'student':
                return redirect(url_for("student_portal.dashboard"))  # NEW: Redirect to student portal
            elif role == 'parent':
                return redirect(url_for("dashboard_bp.parent_dashboard"))
            else:
                # Unknown role, redirect to login
                return redirect(url_for("auth.login"))
        else:
            # Not logged in, redirect to login page
            return redirect(url_for("auth.login"))

    return app
