"""
Database initialization module for Global IT Web Application
Handles SQLAlchemy setup and database creation
"""

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from datetime import datetime, timezone
from sqlalchemy import text
import os

# Initialize SQLAlchemy instance
db = SQLAlchemy()

def init_database(app):
    """
    Initialize database with the Flask app
    """
    with app.app_context():
        # Import all models to ensure they're registered with SQLAlchemy
        from models.user_model import User
        from models.student_model import Student
        from models.batch_model import Batch
        from models.branch_model import Branch
        from models.invoice_model import Invoice
        from models.payment_model import Payment
        from models.installment_model import Installment
        from models.login_logs_model import LoginLog
        from models.system_audit_logs_model import SystemAuditLog
        from models.expense_model import Expense
        from models.user_branch_assignment_model import UserBranchAssignment
        from models.lead_model import Lead
        from models.course_model import Course
        from models.staff_profile_model import StaffProfile
        from models.student_attendance_model import StudentAttendance
        from models.student_batch_completion_model import StudentBatchCompletion
        from models.batch_trainer_assignment_model import BatchTrainerAssignment
        from models.attendance_audit_model import AttendanceAudit
        from models.expense_audit_model import ExpenseAudit
        
        # Import LMS models (Course Delivery)
        from models.lms_model import (
            CourseModule, CourseSection, CourseVideo, CourseMaterial,
            StudentModuleProgress, StudentSectionProgress, StudentVideoProgress,
            MaterialDownloadLog, MaterialAccessLog, VideoAccessLog, SecurityViolationLog,
            CourseAnnouncement, StudentAssignment, AssignmentSubmission, StudentNotes, LMSSettings
        )
        
        # Import LMS Content Management models (Admin Content Management)
        from models.lms_content_management_model import (
            VideoUpload, DocumentUpload, Quiz, QuizQuestion, QuizAttempt,
            AssignmentCreator, ContentWorkflow, FileStorage
        )
        
        # Import the RolePermission model
        from models.role_permission_model import RolePermission
        
        # Create all tables
        db.create_all()
        
        # 🔧 MIGRATION: Add 'status' column to installments if missing (using SQLAlchemy)
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            columns = inspector.get_columns('installments')
            column_names = [col['name'] for col in columns]
            
            if 'status' not in column_names:
                # Use database-agnostic approach for adding column
                if 'mysql' in str(db.engine.url).lower():
                    db.session.execute(text("ALTER TABLE installments ADD COLUMN status VARCHAR(20) DEFAULT 'Pending'"))
                else:
                    db.session.execute(text("ALTER TABLE installments ADD COLUMN status TEXT DEFAULT 'Pending'"))
                db.session.commit()
                print("✅ 'status' column added to installments table.")
            else:
                print("ℹ️ 'status' column already exists in installments table.")
        except Exception as e:
            print(f"⚠️ Error while checking/adding status column: {e}")
            db.session.rollback()
        
        # 🔧 MIGRATION: Add invoice detail columns if missing (using SQLAlchemy)
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            columns = inspector.get_columns('invoices')
            column_names = [col['name'] for col in columns]
            
            invoice_columns_to_add = [
                ("invoice_date", "DATE"),
                ("due_date", "DATE"), 
                ("payment_terms", "VARCHAR(100)" if 'mysql' in str(db.engine.url).lower() else "TEXT")
            ]
            
            for column_name, column_type in invoice_columns_to_add:
                if column_name not in column_names:
                    db.session.execute(text(f"ALTER TABLE invoices ADD COLUMN {column_name} {column_type}"))
                    db.session.commit()
                    print(f"✅ '{column_name}' column added to invoices table.")
                else:
                    print(f"ℹ️ '{column_name}' column already exists in invoices table.")
        except Exception as e:
            print(f"⚠️ Error while checking/adding invoice columns: {e}")
            db.session.rollback()
        
        # Create default admin user if it doesn't exist
        create_default_admin()
        
        # Initialize role permissions system
        init_role_permissions()
        
        # Initialize default courses from Excel
        from utils.courses import init_courses_from_excel
        init_courses_from_excel()
        
        # Initialize LMS default settings
        try:
            LMSSettings.initialize_default_security_settings()
            print("✅ LMS default settings initialized")
        except Exception as e:
            print(f"⚠️ Could not initialize LMS settings: {str(e)}")
        
        # Create default branches
        create_default_branches()
        
        # Create default staff members
        create_default_staff()
        
        print("✅ Database initialized successfully!")

def create_default_admin():
    """
    Create a default admin user if no users exist
    """
    from models.user_model import User
    
    # Check if any users exist
    if User.query.count() == 0:
        admin_user = User(
            username="admin",
            password=generate_password_hash("admin123"),  # Change this in production!
            full_name="System Administrator",
            role="admin"
        )
        
        db.session.add(admin_user)
        db.session.commit()
        print("✅ Default admin user created (username: admin, password: admin123)")
        print("⚠️  IMPORTANT: Change the default password in production!")

def create_default_branches():
    """
    Create default branches if none exist
    """
    from models.branch_model import Branch
    from datetime import date
    
    # Check if any branches exist
    if Branch.query.count() == 0:
        # Define the default branches
        default_branches = [
            {
                'branch_name': 'Global IT Head Office',
                'branch_code': 'GIT_HO',
                'address': 'No 04,SCFSC Bank Building, 1st Main, T g Extension, Opp B m Lab',
                'city': 'Hoskote',
                'state': 'Karnataka',
                'pincode': '562114',
                'phone': '9071717161',
                'email': 'headoffice@globaliteducation.com',
                'manager_name': 'Chaithra',
                'manager_phone': '9071717161',
                'branch_type': 'Franchise',
                'status': 'Active',
                'opening_date': date(2010, 1, 1),
                'franchise_fee': 150000.0,
                'monthly_fee': 35000.0,
                'gst_number': '29AMEPL6934C2ZZ',
                'pan_number': 'AMEPL6934C',
                'is_deleted': 0
            },
            {
                'branch_name': 'Global IT Hoskote Branch',
                'branch_code': 'GIT_HOS',
                'address': '2nd Floor, J C Galaxy Building, College Road, Opp Ayyappaswamy Temple',
                'city': 'Hoskote',
                'state': 'Karnataka',
                'pincode': '562114',
                'phone': '9071717161',
                'email': 'hoskote@globaliteducation.com',
                'manager_name': 'Nandini',
                'manager_phone': '9071717162',
                'branch_type': 'Franchise',
                'status': 'Active',
                'opening_date': date(2020, 1, 1),
                'franchise_fee': 150000.0,
                'monthly_fee': 35000.0,
                'gst_number': '29AMEPL6934C2ZZ',
                'pan_number': 'AMEPL6934C',
                'is_deleted': 0
            }
        ]
        
        # Create and add the branches
        for branch_data in default_branches:
            branch = Branch(**branch_data)
            db.session.add(branch)
        
        db.session.commit()
        print(f"✅ {len(default_branches)} default branches created")
        print("   - Global IT Head Office")
        print("   - Global IT Hoskote Branch")
    else:
        print(f"ℹ️ Branches already exist ({Branch.query.count()} branches found)")



def create_default_staff():
    """
    Create default staff members if they don't exist
    """
    from models.user_model import User
    from models.staff_profile_model import StaffProfile
    from models.branch_model import Branch
    from models.user_branch_assignment_model import UserBranchAssignment
    from datetime import date
    
    # Staff data from the provided information
    staff_data = [
        {
            'employee_id': 'GIT01',
            'doj': '01-12-2021',
            'name': 'Chaithra S N',
            'dob': '31-03-1996',
            'pan_number': 'ATSPN9967C',
            'bank_account': '1633110010054860',
            'ifsc_code': 'UJVN0001633',
            'role': 'branch_manager',
            'employment_type': 'Full Time',
            'email': 'chaithranammu143@gmail.com',
            'aadhar_number': '534050068306',
            'branch_code': 'GIT_HO',
            'username': 'chaithra',
            'password': 'git01123'
        },
        {
            'employee_id': 'GIT03',
            'doj': '01-01-2022',
            'name': 'Nandhini R',
            'dob': '25-07-1992',
            'pan_number': 'GEWPR8523B',
            'bank_account': '7102500102690100',
            'ifsc_code': 'KARB0000710',
            'role': 'branch_manager',
            'employment_type': 'Full Time',
            'email': 'nnandugowda25@gmail.com',
            'aadhar_number': '817614418106',
            'branch_code': 'GIT_HOS',
            'username': 'nandhini',
            'password': 'git03123'
        },
        {
            'employee_id': 'GIT07',
            'doj': '31-03-2025',
            'name': 'M M MEGHANA',
            'dob': '15-05-2000',
            'pan_number': 'HRZPM6936A',
            'bank_account': '3372500101944900',
            'ifsc_code': 'KARB0000645',
            'role': 'trainer',
            'employment_type': 'Full Time',
            'email': 'murthymeghana678@gmail.com',
            'aadhar_number': '707059005522',
            'branch_code': 'GIT_HOS',
            'username': 'mmmeghan',
            'password': 'git07123'
        },
        {
            'employee_id': 'GIT01_trainer',
            'doj': '01-12-2021',
            'name': 'Chaithra S N',
            'dob': '31-03-1996',
            'pan_number': 'ATSPN9967C',
            'bank_account': '1633110010054860',
            'ifsc_code': 'UJVN0001633',
            'role': 'trainer',
            'employment_type': 'Full Time',
            'email': 'chaithranammu143@gmail.com',
            'aadhar_number': '534050068306',
            'branch_code': 'GIT_HO',
            'username': 'chaithra_trainer',
            'password': 'git01123'
        },
        {
            'employee_id': 'GIT03_trainer',
            'doj': '01-01-2022',
            'name': 'Nandhini R',
            'dob': '25-07-1992',
            'pan_number': 'GEWPR8523B',
            'bank_account': '7102500102690100',
            'ifsc_code': 'KARB0000710',
            'role': 'trainer',
            'employment_type': 'Full Time',
            'email': 'nnandugowda25@gmail.com',
            'aadhar_number': '817614418106',
            'branch_code': 'GIT_HOS',
            'username': 'nandhini_trainer',
            'password': 'git03123'
        }
    ]
    
    def parse_date(date_str):
        """Parse date string in DD-MM-YYYY format to date object"""
        try:
            return datetime.strptime(date_str, '%d-%m-%Y').date()
        except:
            return None
    
    # Check if staff already exist
    existing_staff_count = StaffProfile.query.filter(
        StaffProfile.employee_id.in_(['GIT01', 'GIT03', 'GIT07','GIT01_trainer', 'GIT03_trainer'])
    ).count()
    
    if existing_staff_count > 0:
        print(f"ℹ️ Default staff already exist ({existing_staff_count} staff found)")
        return
    
    created_count = 0
    
    try:
        for staff_info in staff_data:
            # Check if user already exists
            existing_user = User.query.filter_by(username=staff_info['username']).first()
            if existing_user:
                print(f"⚠️  User {staff_info['username']} already exists, skipping...")
                continue
            
            # Find branch by branch_code
            branch = Branch.query.filter_by(branch_code=staff_info['branch_code']).first()
            if not branch:
                print(f"❌ Branch with code {staff_info['branch_code']} not found, skipping {staff_info['name']}...")
                continue
            
            # Create new user
            new_user = User(
                username=staff_info['username'],
                password=generate_password_hash(staff_info['password']),
                full_name=staff_info['name'],
                role=staff_info['role']
            )
            
            db.session.add(new_user)
            db.session.flush()  # Get the user ID
            
            # Create staff profile
            staff_profile = StaffProfile(
                user_id=new_user.id,
                employee_id=staff_info['employee_id'],
                date_of_birth=parse_date(staff_info['dob']),
                joining_date=parse_date(staff_info['doj']),
                employment_type=staff_info['employment_type'],
                personal_email=staff_info['email'].strip(),
                official_email=staff_info['email'].strip(),
                pan_number=staff_info['pan_number'],
                aadhar_number=staff_info['aadhar_number'],
                bank_account_number=staff_info['bank_account'],
                bank_ifsc=staff_info['ifsc_code'],
                designation=staff_info['role'].replace('_', ' ').title(),
                created_by_user_id=1  # Admin user
            )
            
            db.session.add(staff_profile)
            
            # Create branch assignment
            assignment = UserBranchAssignment(
                user_id=new_user.id,
                branch_id=branch.id,
                role_at_branch=staff_info['role'],
                assigned_by=1,  # Admin user
                notes=f"Default staff member. Employee ID: {staff_info['employee_id']}"
            )
            
            db.session.add(assignment)
            created_count += 1
            
        # Commit all changes
        db.session.commit()
        
        if created_count > 0:
            print(f"✅ {created_count} default staff members created")
            print("   - Chaithra S N (Branch Manager - Head Office)")
            print("   - Nandhini R (Branch Manager - Hoskote)")
            print("   - M M MEGHANA (Trainer - Hoskote)")
            print("⚠️  Default passwords: git01123, git03123, git07123")
            print("⚠️  IMPORTANT: Change default passwords in production!")
        
    except Exception as e:
        print(f"⚠️ Error creating default staff: {e}")
        db.session.rollback()

def init_role_permissions():
    """
    Initialize role permissions table and populate with default permissions
    This runs automatically on database initialization using SQLAlchemy ORM
    """
    try:
        # Import the RolePermission model
        from models.role_permission_model import RolePermission
        
        # Check if permissions already exist
        existing_count = RolePermission.query.count()
        
        if existing_count == 0:
            # Create default role permissions using the model's method
            RolePermission.create_default_permissions()
            print(f"✅ Role permissions system initialized with default permissions")
        else:
            print(f"ℹ️ Role permissions already exist ({existing_count} permissions found)")
            
    except Exception as e:
        print(f"⚠️ Error initializing role permissions: {e}")
        db.session.rollback()

def drop_all_tables():
    """
    Drop all tables - use with caution!
    """
    db.drop_all()
    print("⚠️  All tables dropped!")

def recreate_database():
    """
    Drop and recreate all tables - use with caution!
    """
    drop_all_tables()
    init_database()
    print("✅ Database recreated successfully!")

def create_sample_data():
    """
    Create sample data for testing (optional)
    """
    from models.batch_model import Batch
    from models.student_model import Student
    from models.invoice_model import Invoice
    
    # Create sample batch
    if Batch.query.count() == 0:
        sample_batch = Batch(
            name="Python Full Stack - Batch 1",
            course_name="Python Full Stack Development",
            start_date=datetime.now(timezone.utc).date(),
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(sample_batch)
        db.session.commit()
        print("✅ Sample batch created")
    
    # Create sample student
    if Student.query.count() == 0:
        sample_student = Student(
            student_id="GIT001",
            full_name="John Doe",
            gender="Male",
            mobile="9876543210",
            email="john.doe@example.com",
            address="123 Main Street, City",
            admission_date=datetime.now(timezone.utc),
            batch_id=1
        )
        db.session.add(sample_student)
        db.session.commit()
        print("✅ Sample student created")

if __name__ == "__main__":
    # This allows running init_db.py directly for database setup
    from globalit_app import create_app
    
    app = create_app()
    
    with app.app_context():
        print("🚀 Starting database initialization...")
        
        # Check if database file exists
        db_path = app.config.get('SQLALCHEMY_DATABASE_URI')
        if db_path and db_path.startswith('sqlite:///'):
            db_file_path = db_path.replace('sqlite:///', '')
            if os.path.exists(db_file_path):
                print(f"📁 Database file exists at: {db_file_path}")
            else:
                print(f"📁 Creating new database at: {db_file_path}")
                # Ensure the directory exists
                os.makedirs(os.path.dirname(db_file_path), exist_ok=True)
        
        # Initialize database
        init_database(app)
        
        # Optionally create sample data
        response = input("Do you want to create sample data? (y/n): ")
        if response.lower() == 'y':
            create_sample_data()
        
        print("🎉 Database setup completed!")
