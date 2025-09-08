from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for
from models.system_audit_logs_model import SystemAuditLog, SecurityAlert
from models.user_model import User
from init_db import db
from datetime import datetime, timedelta
from utils.timezone_helper import get_current_ist_datetime, get_current_ist_formatted, format_datetime_indian
import csv
import io
from flask import make_response

audit_bp = Blueprint("audit", __name__)

@audit_bp.route("/logs")
def audit_logs():
    """Admin interface for viewing audit logs"""
    # Check if user is admin
    if not session.get("user_id") or session.get("role") != 'admin':
        flash("❌ Access denied. Admin privileges required.", "danger")
        return redirect(url_for("auth.login"))
    
    # Get filters from request
    page = request.args.get('page', 1, type=int)
    per_page = 50
    action_filter = request.args.get('action', '')
    user_filter = request.args.get('user', '')
    risk_filter = request.args.get('risk', '')
    success_filter = request.args.get('success', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # Build query
    query = SystemAuditLog.query
    
    if action_filter:
        query = query.filter(SystemAuditLog.action.contains(action_filter))
    
    if user_filter:
        query = query.filter(SystemAuditLog.username.contains(user_filter))
    
    if risk_filter:
        query = query.filter(SystemAuditLog.risk_level == risk_filter)
    
    if success_filter:
        success_bool = success_filter.lower() == 'true'
        query = query.filter(SystemAuditLog.success == success_bool)
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(SystemAuditLog.timestamp >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(SystemAuditLog.timestamp < to_date)
        except ValueError:
            pass
    
    # Order by latest first and paginate
    logs = query.order_by(SystemAuditLog.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get summary statistics
    total_logs = SystemAuditLog.query.count()
    failed_actions = SystemAuditLog.query.filter_by(success=False).count()
    high_risk_actions = SystemAuditLog.query.filter(
        SystemAuditLog.risk_level.in_(['HIGH', 'CRITICAL'])
    ).count()
    
    # Get recent security alerts
    recent_alerts = SecurityAlert.query.filter_by(resolved=False)\
        .order_by(SecurityAlert.created_at.desc()).limit(5).all()
    
    return render_template("audit/audit_logs.html",
                           logs=logs,
                           total_logs=total_logs,
                           failed_actions=failed_actions,
                           high_risk_actions=high_risk_actions,
                           recent_alerts=recent_alerts,
                           filters={
                               'action': action_filter,
                               'user': user_filter,
                               'risk': risk_filter,
                               'success': success_filter,
                               'date_from': date_from,
                               'date_to': date_to
                           })

@audit_bp.route("/export")
def export_logs():
    """Export audit logs to CSV"""
    # Check if user is admin
    if not session.get("user_id") or session.get("role") != 'admin':
        flash("❌ Access denied. Admin privileges required.", "danger")
        return redirect(url_for("auth.login"))
    
    # Get all logs (or apply filters if needed)
    logs = SystemAuditLog.query.order_by(SystemAuditLog.timestamp.desc()).limit(1000).all()
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow([
        'ID', 'User ID', 'Username', 'Action', 'Target', 'IP Address',
        'Success', 'Risk Level', 'Details', 'Timestamp'
    ])
    
    # Write data
    for log in logs:
        writer.writerow([
            log.id,
            log.user_id or '',
            log.username or '',
            log.action or '',
            log.target or '',
            log.ip_address or '',
            'Yes' if log.success else 'No',
            log.risk_level or '',
            log.details or '',
            log.to_dict()['formatted_time']
        ])
    
    # Create response
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=audit_logs_{get_current_ist_datetime().strftime("%Y%m%d_%H%M%S")}.csv'
    
    return response

@audit_bp.route("/alerts")
def security_alerts():
    """View and manage security alerts"""
    # Check if user is admin
    if not session.get("user_id") or session.get("role") != 'admin':
        flash("❌ Access denied. Admin privileges required.", "danger")
        return redirect(url_for("auth.login"))
    
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    alerts = SecurityAlert.query.order_by(
        SecurityAlert.resolved.asc(),  # Unresolved first
        SecurityAlert.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    # Get alert statistics
    total_alerts = SecurityAlert.query.count()
    unresolved_alerts = SecurityAlert.query.filter_by(resolved=False).count()
    critical_alerts = SecurityAlert.query.filter_by(
        severity='CRITICAL', resolved=False
    ).count()
    
    return render_template("audit/security_alerts.html",
                           alerts=alerts,
                           total_alerts=total_alerts,
                           unresolved_alerts=unresolved_alerts,
                           critical_alerts=critical_alerts)

@audit_bp.route("/alerts/<int:alert_id>/resolve", methods=["POST"])
def resolve_alert(alert_id):
    """Mark a security alert as resolved"""
    # Check if user is admin
    if not session.get("user_id") or session.get("role") != 'admin':
        return jsonify({"error": "Access denied"}), 403
    
    alert = SecurityAlert.query.get_or_404(alert_id)
    alert.resolved = True
    alert.resolved_by = session.get("user_id")
    alert.resolved_at = get_current_ist_datetime()
    
    try:
        db.session.commit()
        return jsonify({"success": True, "message": "Alert resolved successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# Helper function to track user actions (to be imported by other modules)
def log_user_action(action, target=None, details=None, success=True, risk_level='LOW'):
    """Log user actions with current session context"""
    from flask import request, session
    
    SystemAuditLog.log_action(
        user_id=session.get("user_id"),
        username=session.get("username"),
        action=action,
        target=target,
        ip_address=request.remote_addr if request else None,
        user_agent=request.headers.get('User-Agent') if request else None,
        details=details,
        success=success,
        risk_level=risk_level,
        session_id=session.get("_id") if session else None
    )

def create_security_alert(alert_type, severity, description, user_id=None, username=None):
    """Create a security alert"""
    from flask import request, session
    
    alert = SecurityAlert(
        alert_type=alert_type,
        severity=severity,
        user_id=user_id or session.get("user_id"),
        username=username or session.get("username"),
        ip_address=request.remote_addr if request else None,
        description=description
    )
    
    db.session.add(alert)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Failed to create security alert: {e}")
