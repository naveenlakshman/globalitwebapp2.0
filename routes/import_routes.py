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
from models.batch_model import Batch
from utils.import_validator import StudentValidator, InvoiceValidator, InstallmentValidator, PaymentValidator, BatchValidator
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

@import_bp.route('/import/batches')
@login_required
@role_required(['super_admin', 'admin', 'branch_manager'])
def batch_import():
    """Batch import interface"""
    return render_template('import/batch_import.html')

@import_bp.route('/import/courses')
@login_required
@role_required(['super_admin', 'admin', 'branch_manager'])
def course_import():
    """Course import interface"""
    return render_template('import/course_import.html')

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
        
        if import_type not in ['students', 'invoices', 'installments', 'payments', 'batches']:
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
        elif file_info['import_type'] == 'batches':
            result = process_batch_import(df, import_history, duplicate_handling)
        elif file_info['import_type'] == 'courses':
            result = process_course_import(df, import_history, duplicate_handling)
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
    
    # Get existing student data for duplicate checking
    existing_students = {s.student_id: s for s in Student.query.all()}
    existing_emails = {s.email: s for s in Student.query.filter(Student.email.isnot(None)).all()}
    existing_mobiles = {s.mobile: s for s in Student.query.filter(Student.mobile.isnot(None)).all()}
    existing_reg_nos = {s.student_reg_no: s for s in Student.query.filter(Student.student_reg_no.isnot(None)).all()}
    
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
            
            # Always generate student ID automatically (never from CSV)
            existing_ids = list(existing_students.keys())
            row_data['student_id'] = DataMapper.generate_student_id("ST", existing_ids)
            
            # Handle registration number (generate if not provided, validate if provided)
            if not row_data.get('student_reg_no'):
                # Get existing registration numbers from database + already processed in this import
                all_existing_reg_nos = [s.student_reg_no for s in Student.query.all() if s.student_reg_no]
                # Add registration numbers from already processed rows in this import
                all_existing_reg_nos.extend([s.student_reg_no for s in existing_reg_nos.values() if s.student_reg_no])
                row_data['student_reg_no'] = DataMapper.generate_student_reg_no("GIT", all_existing_reg_nos)
            else:
                # If registration number is provided, validate it's not a duplicate
                if row_data['student_reg_no'] in existing_reg_nos:
                    failed += 1
                    errors.append(f"Row {index + 1}: Registration number '{row_data['student_reg_no']}' already exists")
                    continue
            
            # Clean mobile numbers
            if row_data.get('mobile'):
                row_data['mobile'] = DataMapper.clean_mobile_number(row_data['mobile'])
            if row_data.get('guardian_mobile'):
                row_data['guardian_mobile'] = DataMapper.clean_mobile_number(row_data['guardian_mobile'])
            
            # Check for duplicates
            duplicate_student = None
            if row_data['student_id'] in existing_students:
                duplicate_student = existing_students[row_data['student_id']]
            elif row_data.get('student_reg_no') and row_data['student_reg_no'] in existing_reg_nos:
                duplicate_student = existing_reg_nos[row_data['student_reg_no']]
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
            if student.student_reg_no:
                existing_reg_nos[student.student_reg_no] = student
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

def process_batch_import(df, import_history, duplicate_handling):
    """Process batch data import"""
    try:
        from datetime import datetime, timezone
        
        successful_imports = 0
        failed_imports = 0
        skipped_imports = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                row_data = row.to_dict()
                
                # Validate the row
                is_valid, validation_errors = BatchValidator.validate_row(row_data, index + 1)
                
                if not is_valid:
                    failed_imports += 1
                    errors.extend([f"Row {index + 1}: {error}" for error in validation_errors])
                    continue
                
                # Check for existing batch (by name and branch combination)
                existing_batch = None
                if row_data.get('name') and row_data.get('branch_id'):
                    existing_batch = Batch.query.filter_by(
                        name=row_data['name'],
                        branch_id=int(row_data['branch_id'])
                    ).first()
                
                if existing_batch:
                    if duplicate_handling == 'skip':
                        skipped_imports += 1
                        continue
                    elif duplicate_handling == 'update':
                        batch = existing_batch
                    else:  # error
                        failed_imports += 1
                        errors.append(f"Row {index + 1}: Batch '{row_data['name']}' already exists in branch {row_data['branch_id']}")
                        continue
                else:
                    batch = Batch()
                
                # Map and convert data
                field_mapping = {
                    'name': 'name',  # Batch model uses 'name', not 'batch_name'
                    'course_id': 'course_id',
                    'course_name': 'course_name',
                    'branch_id': 'branch_id',
                    'start_date': 'start_date',
                    'end_date': 'end_date',
                    'timing': 'timing',
                    'checkin_time': 'checkin_time',
                    'checkout_time': 'checkout_time',
                    'max_capacity': 'max_capacity',
                    'status': 'status'
                }
                
                for csv_field, model_field in field_mapping.items():
                    if csv_field in row_data and row_data[csv_field]:
                        value = row_data[csv_field]
                        
                        # Convert dates
                        if csv_field in ['start_date', 'end_date']:
                            converted_date = DataMapper.convert_indian_date_format(str(value), include_time=False)
                            if converted_date:
                                setattr(batch, model_field, datetime.strptime(converted_date, '%Y-%m-%d').date())
                        # Convert time fields (checkin_time, checkout_time)
                        elif csv_field in ['checkin_time', 'checkout_time']:
                            converted_time = DataMapper.convert_time_format(str(value))
                            if converted_time:
                                # Convert string time to time object
                                time_obj = datetime.strptime(converted_time, '%H:%M:%S').time()
                                setattr(batch, model_field, time_obj)
                        # Convert integers
                        elif csv_field in ['course_id', 'branch_id', 'max_capacity']:
                            setattr(batch, model_field, int(value))
                        # Convert boolean
                        elif csv_field == 'is_deleted':
                            setattr(batch, model_field, str(value).lower() in ['true', '1', 'yes'])
                        else:
                            setattr(batch, model_field, str(value))
                
                # Set default status if not provided
                if not hasattr(batch, 'status') or not batch.status:
                    batch.status = 'Active'
                
                # Save the batch
                if not existing_batch:
                    db.session.add(batch)
                
                db.session.commit()
                successful_imports += 1
                
            except Exception as e:
                db.session.rollback()
                failed_imports += 1
                errors.append(f"Row {index + 1}: Error processing batch - {str(e)}")
                continue
        
        # Update import history
        import_history.successful_records = successful_imports
        import_history.failed_records = failed_imports
        import_history.skipped_records = skipped_imports
        import_history.error_details = '\n'.join(errors) if errors else None
        import_history.import_status = 'completed' if failed_imports == 0 else 'partial'
        import_history.completed_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        return {
            'success': True,
            'message': 'Batch import completed',
            'data': {
                'successful': successful_imports,
                'failed': failed_imports,
                'skipped': skipped_imports,
                'errors': errors[:10],  # Limit errors shown
                'total_errors': len(errors)
            }
        }
        
    except Exception as e:
        db.session.rollback()
        import_history.import_status = 'failed'
        import_history.error_details = f"Import failed: {str(e)}"
        db.session.commit()
        
        return {
            'success': False,
            'message': f'Batch import failed: {str(e)}',
            'data': {
                'successful': 0,
                'failed': 0,
                'skipped': 0,
                'errors': [str(e)],
                'total_errors': 1
            }
        }

def process_course_import(df, import_history, duplicate_handling):
    """Process course data import"""
    try:
        from datetime import datetime, timezone
        from models.course_model import Course
        from utils.import_validator import CourseValidator
        
        successful_imports = 0
        failed_imports = 0
        skipped_imports = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                row_data = row.to_dict()
                
                # Validate the row
                is_valid, validation_errors = CourseValidator.validate_row(row_data, index + 1)
                
                if not is_valid:
                    failed_imports += 1
                    errors.extend([f"Row {index + 1}: {error}" for error in validation_errors])
                    continue
                
                # Check for existing course (by course_name or course_code)
                existing_course = None
                if row_data.get('course_name'):
                    existing_course = Course.query.filter_by(
                        course_name=row_data['course_name']
                    ).first()
                elif row_data.get('course_code'):
                    existing_course = Course.query.filter_by(
                        course_code=row_data['course_code']
                    ).first()
                
                if existing_course:
                    if duplicate_handling == 'skip':
                        skipped_imports += 1
                        continue
                    elif duplicate_handling == 'update':
                        course = existing_course
                    else:  # 'replace'
                        course = existing_course
                else:
                    course = Course()
                
                # Map and convert data
                field_mapping = {
                    'course_name': 'course_name',
                    'course_code': 'course_code',
                    'category': 'category',
                    'duration': 'duration',
                    'duration_in_hours': 'duration_in_hours',
                    'duration_in_days': 'duration_in_days',
                    'fee': 'fee',
                    'registration_fee': 'registration_fee',
                    'material_fee': 'material_fee',
                    'certification_fee': 'certification_fee',
                    'early_bird_discount': 'early_bird_discount',
                    'group_discount': 'group_discount',
                    'description': 'description',
                    'course_outline': 'course_outline',
                    'prerequisites': 'prerequisites',
                    'learning_outcomes': 'learning_outcomes',
                    'software_requirements': 'software_requirements',
                    'target_audience': 'target_audience',
                    'career_opportunities': 'career_opportunities',
                    'difficulty_level': 'difficulty_level',
                    'delivery_mode': 'delivery_mode',
                    'batch_size_min': 'batch_size_min',
                    'batch_size_max': 'batch_size_max',
                    'has_certification': 'has_certification',
                    'certification_body': 'certification_body',
                    'assessment_type': 'assessment_type',
                    'passing_criteria': 'passing_criteria',
                    'typical_schedule': 'typical_schedule',
                    'flexible_timing': 'flexible_timing',
                    'is_featured': 'is_featured',
                    'is_popular': 'is_popular',
                    'display_order': 'display_order',
                    'course_image': 'course_image',
                    'brochure_path': 'brochure_path',
                    'status': 'status',
                    'created_by': 'created_by'
                }
                
                for csv_field, model_field in field_mapping.items():
                    if csv_field in row_data and row_data[csv_field] is not None:
                        value = row_data[csv_field]
                        
                        # Skip empty values
                        if str(value).strip() == '' or str(value).lower() == 'nan':
                            continue
                        
                        # Convert numeric fields
                        if csv_field in ['duration_in_hours', 'duration_in_days', 'batch_size_min', 'batch_size_max', 'display_order']:
                            setattr(course, model_field, int(float(value)))
                        elif csv_field in ['fee', 'registration_fee', 'material_fee', 'certification_fee', 'early_bird_discount', 'group_discount']:
                            setattr(course, model_field, float(value))
                        # Convert boolean fields
                        elif csv_field in ['has_certification', 'flexible_timing', 'is_featured', 'is_popular']:
                            bool_value = str(value).lower() in ['true', '1', 'yes']
                            setattr(course, model_field, bool_value)
                        # String fields
                        else:
                            setattr(course, model_field, str(value))
                
                # Set defaults if not provided
                if not hasattr(course, 'category') or not course.category:
                    course.category = 'Other'
                if not hasattr(course, 'difficulty_level') or not course.difficulty_level:
                    course.difficulty_level = 'Beginner'
                if not hasattr(course, 'delivery_mode') or not course.delivery_mode:
                    course.delivery_mode = 'Classroom'
                if not hasattr(course, 'assessment_type') or not course.assessment_type:
                    course.assessment_type = 'Both'
                if not hasattr(course, 'status') or not course.status:
                    course.status = 'Active'
                if not hasattr(course, 'batch_size_min') or course.batch_size_min is None:
                    course.batch_size_min = 5
                if not hasattr(course, 'batch_size_max') or course.batch_size_max is None:
                    course.batch_size_max = 30
                
                # Save the course
                if not existing_course:
                    db.session.add(course)
                
                db.session.commit()
                successful_imports += 1
                
            except Exception as e:
                db.session.rollback()
                failed_imports += 1
                errors.append(f"Row {index + 1}: Error processing course - {str(e)}")
                continue
        
        # Update import history
        import_history.successful_records = successful_imports
        import_history.failed_records = failed_imports
        import_history.skipped_records = skipped_imports
        import_history.error_details = '\n'.join(errors) if errors else None
        import_history.import_status = 'completed' if failed_imports == 0 else 'partial'
        import_history.completed_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        return {
            'success': True,
            'message': 'Course import completed',
            'data': {
                'successful': successful_imports,
                'failed': failed_imports,
                'skipped': skipped_imports,
                'errors': errors[:10],  # Limit errors shown
                'total_errors': len(errors)
            }
        }
        
    except Exception as e:
        db.session.rollback()
        import_history.import_status = 'failed'
        import_history.error_details = f"Import failed: {str(e)}"
        db.session.commit()
        
        return {
            'success': False,
            'message': f'Course import failed: {str(e)}',
            'data': {
                'successful': 0,
                'failed': 0,
                'skipped': 0,
                'errors': [str(e)],
                'total_errors': 1
            }
        }

def get_required_columns(import_type):
    """Get required columns for each import type"""
    requirements = {
        'students': ['full_name', 'mobile'],
        'invoices': ['student_id', 'total_amount', 'enrollment_date'],
        'installments': ['invoice_id', 'due_date', 'amount'],
        'payments': ['amount', 'mode'],
        'batches': ['name', 'course_id', 'branch_id', 'start_date'],
        'courses': ['course_name', 'duration', 'fee']
    }
    return requirements.get(import_type, [])

def get_model_fields(import_type):
    """Get model fields for each import type"""
    fields = {
        'students': ['student_reg_no', 'full_name', 'gender', 'dob', 'mobile', 'email', 'address', 
                    'guardian_name', 'guardian_mobile', 'qualification', 'course_name', 'batch_id', 
                    'branch_id', 'lead_source', 'status', 'admission_date', 'admission_mode', 'referred_by'],
        'invoices': ['student_id', 'course_id', 'total_amount', 'paid_amount', 'due_amount', 
                    'discount', 'enrollment_date', 'invoice_date', 'due_date', 'payment_terms'],
        'installments': ['invoice_id', 'installment_number', 'due_date', 'amount', 'paid_amount', 
                        'status', 'late_fee', 'discount_amount', 'notes'],
        'payments': ['invoice_id', 'installment_id', 'amount', 'mode', 'utr_number', 'notes', 
                    'payment_date', 'discount_amount'],
        'batches': ['id', 'name', 'course_id', 'course_name', 'branch_id', 'start_date', 'end_date', 
                   'timing', 'checkin_time', 'checkout_time', 'max_capacity', 'status', 'completion_date',
                   'archived_at', 'archived_by', 'suspended_at', 'suspended_by', 'suspension_reason',
                   'suspension_notes', 'expected_resume_date', 'cancelled_at', 'cancelled_by',
                   'cancellation_reason', 'cancellation_notes', 'created_at', 'is_deleted'],
        'courses': ['id', 'course_name', 'course_code', 'category', 'duration', 'duration_in_hours',
                   'duration_in_days', 'fee', 'registration_fee', 'material_fee', 'certification_fee',
                   'early_bird_discount', 'group_discount', 'description', 'course_outline',
                   'prerequisites', 'learning_outcomes', 'software_requirements', 'target_audience',
                   'career_opportunities', 'difficulty_level', 'delivery_mode', 'batch_size_min',
                   'batch_size_max', 'has_certification', 'certification_body', 'assessment_type',
                   'passing_criteria', 'typical_schedule', 'flexible_timing', 'is_featured',
                   'is_popular', 'display_order', 'course_image', 'brochure_path', 'status', 'created_by']
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
            'payments': 'payments_sample.csv',
            'batches': 'batches_sample.csv',
            'courses': 'courses_sample.csv'
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
