from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, desc, func
from sqlalchemy.orm import joinedload
from init_db import db
from models.user_model import User
from models.student_model import Student
from models.branch_model import Branch
from models.batch_model import Batch
from models.sms_automation_model import SMSTemplate, SMSLog, SMSAutomationRule, SMSCampaign
from routes.auth_routes import login_required
from utils.sms_service_2factor import get_sms_service, send_bulk_sms, SMS_TEMPLATES
from init_db import db
import json

sms_routes = Blueprint('sms', __name__, url_prefix='/sms')

@sms_routes.route('/dashboard')
@login_required
def sms_dashboard():
    """SMS Automation Dashboard"""
    # Check permissions
    if session.get('role') not in ['admin', 'branch_manager']:
        flash('Access denied. Insufficient permissions.', 'error')
        return redirect(url_for('dashboard_bp.admin_dashboard'))
    
    # Get recent SMS statistics
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # SMS stats
    today_sms = SMSLog.query.filter(func.date(SMSLog.sent_at) == today).count()
    week_sms = SMSLog.query.filter(func.date(SMSLog.sent_at) >= week_ago).count()
    month_sms = SMSLog.query.filter(func.date(SMSLog.sent_at) >= month_ago).count()
    
    # Success rate
    total_sms = SMSLog.query.count()
    sent_sms = SMSLog.query.filter(SMSLog.status == 'sent').count()
    success_rate = round((sent_sms / total_sms * 100) if total_sms > 0 else 0, 1)
    
    # Recent SMS logs
    recent_logs = SMSLog.query.order_by(desc(SMSLog.sent_at)).limit(10).all()
    
    # Active templates
    active_templates = SMSTemplate.query.filter(SMSTemplate.is_active == True).count()
    
    # Active automation rules
    active_rules = SMSAutomationRule.query.filter(SMSAutomationRule.is_active == True).count()
    
    # Get account balance from 2Factor.in
    sms_service = get_sms_service()
    balance_info = sms_service.get_account_balance()
    
    return render_template('sms/dashboard.html',
                         today_sms=today_sms,
                         week_sms=week_sms,
                         month_sms=month_sms,
                         success_rate=success_rate,
                         recent_logs=recent_logs,
                         active_templates=active_templates,
                         active_rules=active_rules,
                         balance_info=balance_info,
                         total_sms=total_sms)

@sms_routes.route('/templates')
@login_required
def sms_templates():
    """SMS Templates Management"""
    if session.get('role') not in ['admin', 'branch_manager']:
        flash('Access denied. Insufficient permissions.', 'error')
        return redirect(url_for('dashboard_bp.admin_dashboard'))
    
    templates = SMSTemplate.query.order_by(SMSTemplate.created_at.desc()).all()
    predefined_templates = SMS_TEMPLATES
    
    return render_template('sms/templates.html', 
                         templates=templates,
                         predefined_templates=predefined_templates)

@sms_routes.route('/templates/create', methods=['GET', 'POST'])
@login_required
def create_template():
    """Create SMS Template"""
    if session.get('role') not in ['admin', 'branch_manager']:
        flash('Access denied. Insufficient permissions.', 'error')
        return redirect(url_for('dashboard_bp.admin_dashboard'))
    
    if request.method == 'POST':
        try:
            template = SMSTemplate(
                name=request.form['name'],
                content=request.form['content'],
                message_type=request.form['message_type'],
                variables=request.form.get('variables', ''),
                is_active=bool(request.form.get('is_active')),
                created_by=session['user_id']
            )
            
            db.session.add(template)
            db.session.commit()
            
            flash('SMS template created successfully!', 'success')
            return redirect(url_for('sms.sms_templates'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating template: {str(e)}', 'error')
    
    return render_template('sms/create_template.html')

@sms_routes.route('/templates/<int:template_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_template(template_id):
    """Edit SMS Template"""
    if session.get('role') not in ['admin', 'branch_manager']:
        flash('Access denied. Insufficient permissions.', 'error')
        return redirect(url_for('dashboard_bp.admin_dashboard'))
    
    template = SMSTemplate.query.get_or_404(template_id)
    
    if request.method == 'POST':
        try:
            template.name = request.form['name']
            template.content = request.form['content']
            template.message_type = request.form['message_type']
            template.variables = request.form.get('variables', '')
            template.is_active = bool(request.form.get('is_active'))
            template.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            flash('SMS template updated successfully!', 'success')
            return redirect(url_for('sms.sms_templates'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating template: {str(e)}', 'error')
    
    return render_template('sms/edit_template.html', template=template)

@sms_routes.route('/send')
@login_required
def send_sms_page():
    """Send SMS Page"""
    if session.get('role') not in ['admin', 'branch_manager']:
        flash('Access denied. Insufficient permissions.', 'error')
        return redirect(url_for('dashboard_bp.admin_dashboard'))
    
    # Get templates for selection
    templates = SMSTemplate.query.filter(SMSTemplate.is_active == True).all()
    
    # Get branches for filtering
    branches = Branch.query.filter(Branch.status == 'Active').all()
    
    return render_template('sms/send_sms.html', 
                         templates=templates,
                         branches=branches)

@sms_routes.route('/send/individual', methods=['POST'])
@login_required
def send_individual_sms():
    """Send SMS to individual recipient"""
    if session.get('role') not in ['admin', 'branch_manager']:
        return jsonify({'success': False, 'error': 'Access denied'})
    
    try:
        phone_number = request.form['phone_number']
        message = request.form['message']
        template_id = request.form.get('template_id')
        
        sms_service = get_sms_service()
        result = sms_service.send_transactional_sms(
            phone_number=phone_number,
            message=message,
            template_id=template_id,
            message_type='individual',
            sent_by=session['user_id']
        )
        
        if result['success']:
            flash('SMS sent successfully!', 'success')
        else:
            flash(f'Error sending SMS: {result["error"]}', 'error')
            
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@sms_routes.route('/send/bulk', methods=['POST'])
@login_required
def send_bulk_sms_route():
    """Send bulk SMS"""
    if session.get('role') not in ['admin', 'branch_manager']:
        return jsonify({'success': False, 'error': 'Access denied'})
    
    try:
        message = request.form['message']
        template_id = request.form.get('template_id')
        recipient_type = request.form['recipient_type']
        
        phone_numbers = []
        
        if recipient_type == 'all_students':
            students = Student.query.filter(Student.is_deleted == 0).all()
            phone_numbers = [s.mobile for s in students if s.mobile]
            
        elif recipient_type == 'branch_students':
            branch_id = request.form['branch_id']
            students = Student.query.filter(
                and_(Student.is_deleted == 0, Student.branch_id == branch_id)
            ).all()
            phone_numbers = [s.mobile for s in students if s.mobile]
            
        elif recipient_type == 'custom_list':
            # Parse phone numbers from textarea
            phone_list = request.form['phone_numbers'].strip()
            phone_numbers = [phone.strip() for phone in phone_list.split('\n') if phone.strip()]
        
        if not phone_numbers:
            return jsonify({'success': False, 'error': 'No valid phone numbers found'})
        
        # Send bulk SMS
        results = send_bulk_sms(
            phone_numbers=phone_numbers,
            message=message,
            template_id=template_id,
            message_type='bulk',
            sent_by=session['user_id']
        )
        
        flash(f'Bulk SMS completed: {results["sent"]} sent, {results["failed"]} failed', 'info')
        return jsonify({'success': True, 'results': results})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@sms_routes.route('/logs')
@login_required
def sms_logs():
    """SMS Logs with filtering"""
    if session.get('role') not in ['admin', 'branch_manager']:
        flash('Access denied. Insufficient permissions.', 'error')
        return redirect(url_for('dashboard_bp.admin_dashboard'))
    
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Build query with filters
    query = SMSLog.query
    
    # Date filter
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    if date_from:
        query = query.filter(SMSLog.sent_at >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(SMSLog.sent_at <= datetime.strptime(date_to + ' 23:59:59', '%Y-%m-%d %H:%M:%S'))
    
    # Status filter
    status = request.args.get('status')
    if status:
        query = query.filter(SMSLog.status == status)
    
    # Message type filter
    message_type = request.args.get('message_type')
    if message_type:
        query = query.filter(SMSLog.message_type == message_type)
    
    # Phone number search
    phone_search = request.args.get('phone_search')
    if phone_search:
        query = query.filter(SMSLog.phone_number.contains(phone_search))
    
    logs = query.order_by(desc(SMSLog.sent_at)).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get available message types for filter dropdown
    message_types = db.session.query(SMSLog.message_type).distinct().all()
    message_types = [mt[0] for mt in message_types if mt[0]]
    
    # Prepare filter values for template
    filters = {
        'date_from': date_from,
        'date_to': date_to,
        'status': status,
        'type': message_type
    }
    
    return render_template('sms/logs.html', 
                         logs=logs, 
                         filters=filters,
                         message_types=message_types)

@sms_routes.route('/automation-rules')
@login_required
def automation_rules():
    """SMS Automation Rules Management"""
    if session.get('role') not in ['admin']:
        flash('Access denied. Admin access required.', 'error')
        return redirect(url_for('dashboard_bp.admin_dashboard'))
    
    rules = SMSAutomationRule.query.order_by(SMSAutomationRule.created_at.desc()).all()
    return render_template('sms/automation_rules.html', rules=rules)

@sms_routes.route('/automation-rules/create', methods=['GET', 'POST'])
@login_required
def create_automation_rule():
    """Create SMS Automation Rule"""
    if session.get('role') not in ['admin']:
        flash('Access denied. Admin access required.', 'error')
        return redirect(url_for('dashboard_bp.admin_dashboard'))
    
    if request.method == 'POST':
        try:
            rule = SMSAutomationRule(
                name=request.form['name'],
                trigger_event=request.form['trigger_event'],
                conditions=request.form.get('conditions', '{}'),
                template_id=request.form.get('template_id') or None,
                custom_message=request.form.get('custom_message'),
                is_active=bool(request.form.get('is_active')),
                created_by=session['user_id']
            )
            
            db.session.add(rule)
            db.session.commit()
            
            flash('Automation rule created successfully!', 'success')
            return redirect(url_for('sms.automation_rules'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating automation rule: {str(e)}', 'error')
    
    templates = SMSTemplate.query.filter(SMSTemplate.is_active == True).all()
    return render_template('sms/create_automation_rule.html', templates=templates)

@sms_routes.route('/campaigns')
@login_required
def sms_campaigns():
    """SMS Campaigns Management"""
    if session.get('role') not in ['admin', 'branch_manager']:
        flash('Access denied. Insufficient permissions.', 'error')
        return redirect(url_for('dashboard_bp.admin_dashboard'))
    
    campaigns = SMSCampaign.query.order_by(SMSCampaign.created_at.desc()).all()
    return render_template('sms/campaigns.html', campaigns=campaigns)

@sms_routes.route('/api/template/<int:template_id>')
@login_required
def get_template_content(template_id):
    """Get template content via API"""
    template = SMSTemplate.query.get_or_404(template_id)
    return jsonify({
        'content': template.content,
        'variables': template.variables.split(',') if template.variables else []
    })

@sms_routes.route('/api/balance')
@login_required
def get_sms_balance():
    """Get SMS account balance"""
    if session.get('role') not in ['admin', 'branch_manager']:
        return jsonify({'success': False, 'error': 'Access denied'})
    
    sms_service = get_sms_service()
    balance_info = sms_service.get_account_balance()
    return jsonify(balance_info)

@sms_routes.route('/api/stats')
@login_required
def get_sms_stats():
    """Get SMS statistics for dashboard"""
    if session.get('role') not in ['admin', 'branch_manager']:
        return jsonify({'success': False, 'error': 'Access denied'})
    
    try:
        # Get stats for last 7 days
        stats = []
        for i in range(7):
            date = datetime.now().date() - timedelta(days=i)
            count = SMSLog.query.filter(func.date(SMSLog.sent_at) == date).count()
            stats.append({
                'date': date.strftime('%Y-%m-%d'),
                'count': count
            })
        
        return jsonify({'success': True, 'stats': stats})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
