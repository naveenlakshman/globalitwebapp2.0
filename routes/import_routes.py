from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from werkzeug.utils import secure_filename
import os
import pandas as pd
from datetime import datetime, timezone
from init_db import db
from models.import_history_model import ImportHistory
from models.student_model import Student
from models.invoice_model import Invoice
from models.installment_model import Installment
from models.payment_model import Payment
from models.course_model import Course
from models.branch_model import Branch
from utils.import_validator import StudentValidator, InvoiceValidator, InstallmentValidator, PaymentValidator
from utils.csv_processor import CSVProcessor, DataMapper
from utils.auth import login_required, role_required

import_bp = Blueprint('import', __name__)

# Configuration
UPLOAD_FOLDER = 'uploads/imports'
ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_upload_folder():
    """Ensure upload folder exists"""
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

@import_bp.route('/import/dashboard')
@login_required
@role_required(['super_admin', 'admin', 'branch_manager'])
def import_dashboard():
    """Main import dashboard"""
    try:
        # Get recent import history
        recent_imports = ImportHistory.query.order_by(ImportHistory.created_at.desc()).limit(10).all()
        
        # Get import statistics
        import_stats = {
            'total_imports': ImportHistory.query.count(),
            'successful_imports': ImportHistory.query.filter_by(import_status='completed').count(),
            'failed_imports': ImportHistory.query.filter_by(import_status='failed').count(),
            'pending_imports': ImportHistory.query.filter_by(import_status='pending').count()
        }
        
        return render_template('import/import_dashboard.html', 
                             recent_imports=recent_imports,
                             import_stats=import_stats)
    except Exception as e:
        flash(f'Error loading import dashboard: {str(e)}', 'error')
        return redirect(url_for('dashboard.admin_dashboard'))

@import_bp.route('/import/students')
@login_required
@role_required(['super_admin', 'admin', 'branch_manager'])
def student_import():
    """Student import interface"""
    return render_template('import/student_import.html')

@import_bp.route('/import/invoices')
@login_required
@role_required(['super_admin', 'admin', 'branch_manager'])
def invoice_import():
    """Invoice import interface"""
    return render_template('import/invoice_import.html')

@import_bp.route('/import/installments')
@login_required
@role_required(['super_admin', 'admin', 'branch_manager'])
def installment_import():
    """Installment import interface"""
    return render_template('import/installment_import.html')

@import_bp.route('/import/payments')
@login_required
@role_required(['super_admin', 'admin', 'branch_manager'])
def payment_import():
    """Payment import interface"""
    return render_template('import/payment_import.html')

@import_bp.route('/import/upload', methods=['POST'])
@login_required
@role_required(['super_admin', 'admin', 'branch_manager'])
def upload_file():
    """Handle file upload and initial processing"""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'})
        
        file = request.files['file']
        import_type = request.form.get('import_type')
        
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'})
        
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'message': 'Only CSV files are allowed'})
        
        if import_type not in ['students', 'invoices', 'installments', 'payments']:
            return jsonify({'success': False, 'message': 'Invalid import type'})
        
        # Ensure upload folder exists
        ensure_upload_folder()
        
        # Read and validate CSV BEFORE saving (to avoid file pointer issues)
        success, df, message = CSVProcessor.read_csv_file(file)
        if not success:
            return jsonify({'success': False, 'message': message})
        
        # Save file after successful CSV reading
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{import_type}_{timestamp}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        # Reset file pointer to beginning before saving
        file.seek(0)
        file.save(filepath)
        
        # Get required columns based on import type
        required_columns = get_required_columns(import_type)
        
        # Validate CSV structure
        is_valid, missing_columns = CSVProcessor.validate_csv_structure(df, required_columns)
        if not is_valid:
            return jsonify({
                'success': False, 
                'message': f'Missing required columns: {", ".join(missing_columns)}'
            })
        
        # Get sample data for preview
        sample_data = CSVProcessor.get_sample_data(df, 5)
        
        # Get column mapping suggestions
        model_fields = get_model_fields(import_type)
        column_suggestions = CSVProcessor.get_column_mapping_suggestions(df.columns.tolist(), model_fields)
        
        # Store file info in session for later processing
        session['import_file_info'] = {
            'filename': filename,
            'filepath': filepath,
            'import_type': import_type,
            'total_rows': len(df),
            'columns': df.columns.tolist()
        }
        
        return jsonify({
            'success': True,
            'message': f'File uploaded successfully. Found {len(df)} records.',
            'data': {
                'sample_data': sample_data,
                'columns': df.columns.tolist(),
                'column_suggestions': column_suggestions,
                'total_rows': len(df),
                'required_columns': required_columns
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error uploading file: {str(e)}'})

@import_bp.route('/import/process', methods=['POST'])
@login_required
@role_required(['super_admin', 'admin', 'branch_manager'])
def process_import():
    """Process the import with user-defined column mapping"""
    try:
        # Get file info from session
        file_info = session.get('import_file_info')
        if not file_info:
            return jsonify({'success': False, 'message': 'No file information found. Please upload file again.'})
        
        # Get form data
        column_mapping = request.json.get('column_mapping', {})
        duplicate_handling = request.json.get('duplicate_handling', 'skip')  # skip, update, error
        import_notes = request.json.get('notes', '')
        
        # Create import history record
        import_history = ImportHistory(
            import_type=file_info['import_type'],
            filename=file_info['filename'],
            total_records=file_info['total_rows'],
            duplicate_handling=duplicate_handling,
            import_notes=import_notes,
            imported_by=session.get('username', 'Unknown'),
            branch_id=session.get('branch_id') if session.get('role') == 'branch_manager' else None
        )
        db.session.add(import_history)
        db.session.commit()
        
        # Read the CSV file again
        with open(file_info['filepath'], 'r', encoding='utf-8') as f:
            df = pd.read_csv(f)
        
        # Clean the dataframe
        df = CSVProcessor.clean_dataframe(df)
        
        # Map columns
        df = CSVProcessor.map_columns(df, column_mapping)
        
        # Process based on import type
        if file_info['import_type'] == 'students':
            result = process_student_import(df, import_history, duplicate_handling)
        elif file_info['import_type'] == 'invoices':
            result = process_invoice_import(df, import_history, duplicate_handling)
        elif file_info['import_type'] == 'installments':
            result = process_installment_import(df, import_history, duplicate_handling)
        elif file_info['import_type'] == 'payments':
            result = process_payment_import(df, import_history, duplicate_handling)
        else:
            return jsonify({'success': False, 'message': 'Invalid import type'})
        
        # Clean up session
        session.pop('import_file_info', None)
        
        return jsonify(result)
        
    except Exception as e:
        # Update import history with error
        if 'import_history' in locals():
            import_history.import_status = 'failed'
            import_history.add_error(f"Processing error: {str(e)}")
        
        return jsonify({'success': False, 'message': f'Error processing import: {str(e)}'})

def process_student_import(df, import_history, duplicate_handling):
    """Process student data import"""
    successful = 0
    failed = 0
    skipped = 0
    errors = []
    
    # Get existing student IDs for duplicate checking
    existing_students = {s.student_id: s for s in Student.query.all()}
    existing_emails = {s.email: s for s in Student.query.filter(Student.email.isnot(None)).all()}
    existing_mobiles = {s.mobile: s for s in Student.query.filter(Student.mobile.isnot(None)).all()}
    
    # Field type mapping for data conversion
    field_types = {
        'branch_id': 'integer',
        'course_id': 'integer',
        'batch_id': 'integer',
        'dob': 'date',
        'admission_date': 'datetime',
        'lms_enrolled': 'boolean',
        'portal_access_enabled': 'boolean'
    }
    
    for index, row in df.iterrows():
        try:
            row_data = row.to_dict()
            
            # Validate row data
            is_valid, validation_errors = StudentValidator.validate_row(row_data, index + 1)
            if not is_valid:
                failed += 1
                errors.append(f"Row {index + 1}: {'; '.join(validation_errors)}")
                continue
            
            # Convert data types
            row_data = DataMapper.convert_to_database_format(row_data, field_types)
            
            # Generate student ID if not provided
            if not row_data.get('student_id'):
                existing_ids = list(existing_students.keys())
                row_data['student_id'] = DataMapper.generate_student_id("ST", existing_ids)
            
            # Clean mobile numbers
            if row_data.get('mobile'):
                row_data['mobile'] = DataMapper.clean_mobile_number(row_data['mobile'])
            if row_data.get('guardian_mobile'):
                row_data['guardian_mobile'] = DataMapper.clean_mobile_number(row_data['guardian_mobile'])
            
            # Check for duplicates
            duplicate_student = None
            if row_data['student_id'] in existing_students:
                duplicate_student = existing_students[row_data['student_id']]
            elif row_data.get('email') and row_data['email'] in existing_emails:
                duplicate_student = existing_emails[row_data['email']]
            elif row_data.get('mobile') and row_data['mobile'] in existing_mobiles:
                duplicate_student = existing_mobiles[row_data['mobile']]
            
            if duplicate_student:
                if duplicate_handling == 'skip':
                    skipped += 1
                    continue
                elif duplicate_handling == 'error':
                    failed += 1
                    errors.append(f"Row {index + 1}: Duplicate student found (ID: {duplicate_student.student_id})")
                    continue
                elif duplicate_handling == 'update':
                    # Update existing student
                    for key, value in row_data.items():
                        if hasattr(duplicate_student, key) and value:
                            setattr(duplicate_student, key, value)
                    successful += 1
                    continue
            
            # Create new student
            student = Student(**row_data)
            db.session.add(student)
            
            # Update tracking dictionaries
            existing_students[student.student_id] = student
            if student.email:
                existing_emails[student.email] = student
            if student.mobile:
                existing_mobiles[student.mobile] = student
            
            successful += 1
            
        except Exception as e:
            failed += 1
            errors.append(f"Row {index + 1}: {str(e)}")
    
    # Commit all changes
    try:
        db.session.commit()
        status = 'completed' if failed == 0 else 'partial'
    except Exception as e:
        db.session.rollback()
        status = 'failed'
        errors.append(f"Database commit error: {str(e)}")
    
    # Update import history
    import_history.update_progress(successful, failed, skipped, status)
    if errors:
        import_history.add_error('\n'.join(errors))
    
    return {
        'success': status != 'failed',
        'message': f'Import completed. Success: {successful}, Failed: {failed}, Skipped: {skipped}',
        'data': {
            'successful': successful,
            'failed': failed,
            'skipped': skipped,
            'errors': errors[:10],  # Limit errors shown
            'total_errors': len(errors)
        }
    }

def process_invoice_import(df, import_history, duplicate_handling):
    """Process invoice data import"""
    # Similar structure to student import but for invoices
    # Implementation would follow the same pattern
    pass

def process_installment_import(df, import_history, duplicate_handling):
    """Process installment data import"""
    # Similar structure to student import but for installments
    pass

def process_payment_import(df, import_history, duplicate_handling):
    """Process payment data import"""
    # Similar structure to student import but for payments
    pass

def get_required_columns(import_type):
    """Get required columns for each import type"""
    requirements = {
        'students': ['full_name', 'mobile'],
        'invoices': ['student_id', 'total_amount', 'enrollment_date'],
        'installments': ['invoice_id', 'due_date', 'amount'],
        'payments': ['amount', 'mode']
    }
    return requirements.get(import_type, [])

def get_model_fields(import_type):
    """Get model fields for each import type"""
    fields = {
        'students': ['student_id', 'full_name', 'gender', 'dob', 'mobile', 'email', 'address', 
                    'guardian_name', 'guardian_mobile', 'qualification', 'course_name', 'batch_id', 
                    'branch_id', 'lead_source', 'status', 'admission_date'],
        'invoices': ['student_id', 'course_id', 'total_amount', 'paid_amount', 'due_amount', 
                    'discount', 'enrollment_date', 'invoice_date', 'due_date', 'payment_terms'],
        'installments': ['invoice_id', 'installment_number', 'due_date', 'amount', 'paid_amount', 
                        'status', 'late_fee', 'discount_amount', 'notes'],
        'payments': ['invoice_id', 'installment_id', 'amount', 'mode', 'utr_number', 'notes', 
                    'payment_date', 'discount_amount']
    }
    return fields.get(import_type, [])

@import_bp.route('/import/history')
@login_required
@role_required(['super_admin', 'admin', 'branch_manager'])
def import_history():
    """View import history"""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = 10
        
        # Build query based on user role
        query = ImportHistory.query
        if session.get('role') == 'branch_manager':
            query = query.filter_by(branch_id=session.get('branch_id'))
        
        # Apply filters
        import_type = request.args.get('import_type')
        if import_type:
            query = query.filter_by(import_type=import_type)
        
        status = request.args.get('status')
        if status:
            query = query.filter_by(import_status=status)
        
        # Get paginated results
        imports = query.order_by(ImportHistory.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return render_template('import/import_history.html', imports=imports)
        
    except Exception as e:
        flash(f'Error loading import history: {str(e)}', 'error')
        return redirect(url_for('import.import_dashboard'))

@import_bp.route('/import/download_template/<import_type>')
@login_required
@role_required(['super_admin', 'admin', 'branch_manager'])
def download_template(import_type):
    """Download CSV template for import type"""
    try:
        templates = {
            'students': 'students_sample.csv',
            'invoices': 'invoices_sample.csv',
            'installments': 'installments_sample.csv',
            'payments': 'payments_sample.csv'
        }
        
        if import_type not in templates:
            flash('Invalid template type', 'error')
            return redirect(url_for('import.import_dashboard'))
        
        # Use absolute path to avoid path resolution issues
        app_root = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(app_root)
        template_path = os.path.join(project_root, 'data_templates', templates[import_type])
        
        if os.path.exists(template_path):
            from flask import send_file
            return send_file(template_path, as_attachment=True, download_name=templates[import_type])
        else:
            flash(f'Template file not found at: {template_path}', 'error')
            return redirect(url_for('import.import_dashboard'))
            
    except Exception as e:
        flash(f'Error downloading template: {str(e)}', 'error')
        return redirect(url_for('import.import_dashboard'))
