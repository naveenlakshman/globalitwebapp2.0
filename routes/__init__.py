from .auth_routes import auth_bp
from .student_routes import student_bp
from .invoice_routes import invoice_bp
from .dashboard_routes import dashboard_bp
from .batch_routes import batch_bp
from .student_attendance_routes import attendance_bp
from .staff_routes import staff_bp
# from .sms_routes import sms_routes  # Temporarily disabled - SMS models removed
from .installment_routes import installment_bp
from .finance_routes import finance_bp
from .branch_routes import branch_bp
from .audit_routes import audit_bp
from .lead_routes import lead_bp


def init_routes(app):
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(student_bp, url_prefix="/students")
    app.register_blueprint(invoice_bp, url_prefix="/invoices")
    app.register_blueprint(dashboard_bp, url_prefix="/")
    app.register_blueprint(batch_bp, url_prefix="/batches")
    app.register_blueprint(attendance_bp, url_prefix="/attendance")
    app.register_blueprint(staff_bp, url_prefix="/staff")
    # app.register_blueprint(sms_routes, url_prefix="/sms")  # Temporarily disabled - SMS models removed
    app.register_blueprint(installment_bp, url_prefix="/installments")
    app.register_blueprint(finance_bp, url_prefix="/finance")
    app.register_blueprint(branch_bp, url_prefix="/branches")
    app.register_blueprint(audit_bp, url_prefix="/audit")
    app.register_blueprint(lead_bp)  # Lead routes already have url_prefix="/leads" in blueprint definition

