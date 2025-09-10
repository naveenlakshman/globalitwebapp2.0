#!/usr/bin/env python3
"""
Database initialization script for PythonAnywhere deployment
Fixed Flask app context and MySQL compatibility issues
"""

import os
import sys
from datetime import datetime, timezone

def init_database():
    """Initialize database with proper Flask app context"""
    try:
        # Set environment to production for PythonAnywhere
        os.environ['APP_ENV'] = 'production'
        
        # Load environment variables from .env file
        try:
            from dotenv import load_dotenv
            load_dotenv()
            print("✅ Environment variables loaded from .env file")
        except ImportError:
            print("⚠️  python-dotenv not installed, using system environment")
        
        # Import Flask app
        from globalit_app import create_app
        app = create_app()
        
        print(f"🚀 Starting database initialization...")
        print(f"📊 Environment: {os.environ.get('APP_ENV', 'development')}")
        
        # Get database URI safely for logging (hide password)
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        if 'mysql' in db_uri:
            # Hide password for logging
            import re
            safe_uri = re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', db_uri)
            print(f"🗄️ Database: {safe_uri}")
        else:
            print(f"🗄️ Database: {db_uri}")
        
        # Work within Flask app context
        with app.app_context():
            from init_db import db
            
            # Import all models to ensure they're registered
            print("📋 Importing models...")
            from models.user_model import User
            from models.student_model import Student
            from models.course_model import Course
            from models.branch_model import Branch
            from models.batch_model import Batch
            from models.invoice_model import Invoice
            from models.installment_model import Installment
            from models.payment_model import Payment
            from models.role_permission_model import RolePermission
            
            # Try to import optional models
            try:
                from models.import_history_model import ImportHistory
                from models.lms_content_management_model import LmsContent
                from models.attendance_audit_model import AttendanceAudit
                from models.system_audit_logs_model import SystemAuditLog
            except ImportError as e:
                print(f"ℹ️  Optional model import skipped: {e}")
            
            print("📋 Creating database tables...")
            
            # Create all tables
            db.create_all()
            print("✅ Database tables created successfully!")
            
            # Initialize data
            init_role_permissions(db)
            init_courses(db)
            init_lms_settings(db)
            init_branches(db)
            init_default_staff(db)
            
            print("✅ Database initialized successfully!")
            return True
            
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def init_role_permissions(db):
    """Initialize role permissions using SQLAlchemy ORM"""
    from models.role_permission_model import RolePermission
    
    # Check if permissions already exist
    existing_count = RolePermission.query.count()
    if existing_count > 0:
        print(f"ℹ️ Role permissions already exist ({existing_count} permissions found)")
        return
    
    print("📋 Creating role permissions...")
    
    # Define comprehensive permissions
    permissions_data = [
        # Dashboard permissions
        ('admin', 'dashboard', 'full'),
        ('regional_manager', 'dashboard', 'view'),
        ('branch_manager', 'dashboard', 'view'),
        ('staff', 'dashboard', 'view'),
        ('trainer', 'dashboard', 'view'),
        
        # Student management
        ('admin', 'students', 'full'),
        ('regional_manager', 'students', 'edit'),
        ('branch_manager', 'students', 'edit'),
        ('staff', 'students', 'view'),
        ('trainer', 'students', 'view'),
        
        # Course management
        ('admin', 'courses', 'full'),
        ('regional_manager', 'courses', 'view'),
        ('branch_manager', 'courses', 'view'),
        ('staff', 'courses', 'view'),
        ('trainer', 'courses', 'view'),
        
        # Batch management
        ('admin', 'batches', 'full'),
        ('regional_manager', 'batches', 'edit'),
        ('branch_manager', 'batches', 'edit'),
        ('trainer', 'batches', 'view'),
        ('staff', 'batches', 'view'),
        
        # Financial management
        ('admin', 'finance', 'full'),
        ('regional_manager', 'finance', 'edit'),
        ('branch_manager', 'finance', 'edit'),
        ('staff', 'finance', 'view'),
        
        # Import functionality
        ('admin', 'import', 'full'),
        ('regional_manager', 'import', 'edit'),
        ('branch_manager', 'import', 'edit'),
        
        # Reports
        ('admin', 'reports', 'full'),
        ('regional_manager', 'reports', 'view'),
        ('branch_manager', 'reports', 'view'),
        ('staff', 'reports', 'view'),
        
        # User management
        ('admin', 'users', 'full'),
        ('regional_manager', 'users', 'view'),
        ('branch_manager', 'users', 'view'),
        
        # Branch management
        ('admin', 'branches', 'full'),
        ('regional_manager', 'branches', 'view'),
        
        # LMS Content Management
        ('admin', 'lms_content', 'full'),
        ('regional_manager', 'lms_content', 'edit'),
        ('branch_manager', 'lms_content', 'edit'),
        ('trainer', 'lms_content', 'edit'),
        
        # Attendance Management
        ('admin', 'attendance', 'full'),
        ('regional_manager', 'attendance', 'edit'),
        ('branch_manager', 'attendance', 'edit'),
        ('trainer', 'attendance', 'edit'),
        ('staff', 'attendance', 'view'),
        
        # Communication
        ('admin', 'communication', 'full'),
        ('regional_manager', 'communication', 'edit'),
        ('branch_manager', 'communication', 'edit'),
        ('trainer', 'communication', 'view'),
        
        # Audit logs
        ('admin', 'audit', 'full'),
        ('regional_manager', 'audit', 'view'),
    ]
    
    # Create permissions
    for role, module, permission_level in permissions_data:
        role_perm = RolePermission(
            role=role,
            module=module,
            permission_level=permission_level,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(role_perm)
    
    db.session.commit()
    print(f"✅ Created {len(permissions_data)} role permissions")

def init_courses(db):
    """Initialize default courses"""
    from models.course_model import Course
    
    existing_count = Course.query.count()
    if existing_count > 0:
        print(f"ℹ️ Courses already exist ({existing_count} courses found)")
        return
    
    print("📚 Creating default courses...")
    
    courses = [
        {
            'course_name': 'Full Stack Development',
            'course_code': 'FSD001',
            'duration_in_days': 180,
            'fee': 50000.00,
            'description': 'Complete web development course covering frontend and backend technologies'
        },
        {
            'course_name': 'Python Programming',
            'course_code': 'PY001',
            'duration_in_days': 90,
            'fee': 25000.00,
            'description': 'Comprehensive Python programming course'
        },
        {
            'course_name': 'Data Science with Python',
            'course_code': 'DS001',
            'duration_in_days': 120,
            'fee': 40000.00,
            'description': 'Data Science with Python and Machine Learning'
        },
        {
            'course_name': 'Digital Marketing',
            'course_code': 'DM001',
            'duration_in_days': 60,
            'fee': 15000.00,
            'description': 'Complete digital marketing course'
        },
        {
            'course_name': 'Java Programming',
            'course_code': 'JAVA001',
            'duration_in_days': 90,
            'fee': 30000.00,
            'description': 'Core Java to Advanced Java programming'
        },
        {
            'course_name': 'React.js Development',
            'course_code': 'REACT001',
            'duration_in_days': 75,
            'fee': 35000.00,
            'description': 'Modern frontend development with React.js'
        },
        {
            'course_name': 'Database Administration',
            'course_code': 'DBA001',
            'duration_in_days': 60,
            'fee': 28000.00,
            'description': 'MySQL and database administration'
        },
        {
            'course_name': 'DevOps Engineering',
            'course_code': 'DEVOPS001',
            'duration_in_days': 100,
            'fee': 45000.00,
            'description': 'DevOps tools and practices'
        },
        {
            'course_name': 'Mobile App Development',
            'course_code': 'MOBILE001',
            'duration_in_days': 120,
            'fee': 42000.00,
            'description': 'Android and iOS app development'
        },
        {
            'course_name': 'Cloud Computing (AWS)',
            'course_code': 'CLOUD001',
            'duration_in_days': 90,
            'fee': 38000.00,
            'description': 'Amazon Web Services cloud computing'
        },
        {
            'course_name': 'Cybersecurity Fundamentals',
            'course_code': 'CYBER001',
            'duration_in_days': 80,
            'fee': 32000.00,
            'description': 'Information security and ethical hacking'
        },
        {
            'course_name': 'UI/UX Design',
            'course_code': 'UIUX001',
            'duration_in_days': 70,
            'fee': 26000.00,
            'description': 'User interface and user experience design'
        }
    ]
    
    for course_data in courses:
        course = Course(**course_data)
        db.session.add(course)
    
    db.session.commit()
    print(f"✅ Created {len(courses)} courses")

def init_lms_settings(db):
    """Initialize LMS settings"""
    try:
        # Try to initialize LMS settings if the model exists
        from models.lms_content_management_model import LmsContent
        
        existing_count = LmsContent.query.count()
        if existing_count == 0:
            print("📚 Initializing LMS content settings...")
            # Add default LMS settings here if needed
            print("✅ LMS settings initialized")
        else:
            print(f"ℹ️ LMS content already exists ({existing_count} items found)")
            
    except ImportError:
        print("ℹ️ LMS content model not available, skipping LMS settings initialization")

def init_branches(db):
    """Initialize default branches"""
    from models.branch_model import Branch
    
    existing_count = Branch.query.count()
    if existing_count > 0:
        print(f"ℹ️ Branches already exist ({existing_count} branches found)")
        return
    
    print("🏢 Creating default branches...")
    
    branches = [
        {
            'branch_name': 'Main Branch - Bangalore',
            'branch_code': 'BLR-MAIN',
            'address': 'Koramangala, Bangalore, Karnataka 560034',
            'phone': '080-12345678',
            'email': 'bangalore@globalit.com',
            'is_active': True
        },
        {
            'branch_name': 'Delhi Branch',
            'branch_code': 'DEL-001',
            'address': 'Connaught Place, New Delhi, Delhi 110001',
            'phone': '011-87654321',
            'email': 'delhi@globalit.com',
            'is_active': True
        },
        {
            'branch_name': 'Mumbai Branch',
            'branch_code': 'MUM-001',
            'address': 'Andheri East, Mumbai, Maharashtra 400069',
            'phone': '022-11223344',
            'email': 'mumbai@globalit.com',
            'is_active': True
        }
    ]
    
    for branch_data in branches:
        branch = Branch(**branch_data)
        db.session.add(branch)
    
    db.session.commit()
    print(f"✅ Created {len(branches)} branches")

def init_default_staff(db):
    """Initialize default staff users"""
    from models.user_model import User
    from werkzeug.security import generate_password_hash
    
    existing_count = User.query.count()
    if existing_count > 0:
        print(f"ℹ️ Default staff already exist ({existing_count} users found)")
        return
    
    print("👥 Creating default staff...")
    
    # Default users
    default_users = [
        {
            'username': 'admin',
            'email': 'admin@globalit.com',
            'password': 'admin123',
            'full_name': 'System Administrator',
            'role': 'admin',
            'branch_id': 1,
            'mobile': '9999999999',
            'is_active': True
        },
        {
            'username': 'manager_blr',
            'email': 'manager.blr@globalit.com',
            'password': 'manager123',
            'full_name': 'Bangalore Branch Manager',
            'role': 'branch_manager',
            'branch_id': 1,
            'mobile': '9888888888',
            'is_active': True
        },
        {
            'username': 'regional_mgr',
            'email': 'regional@globalit.com',
            'password': 'regional123',
            'full_name': 'Regional Manager',
            'role': 'regional_manager',
            'branch_id': 1,
            'mobile': '9777777777',
            'is_active': True
        },
        {
            'username': 'staff001',
            'email': 'staff001@globalit.com',
            'password': 'staff123',
            'full_name': 'Staff Member 1',
            'role': 'staff',
            'branch_id': 1,
            'mobile': '9666666666',
            'is_active': True
        },
        {
            'username': 'trainer001',
            'email': 'trainer001@globalit.com',
            'password': 'trainer123',
            'full_name': 'Senior Trainer',
            'role': 'trainer',
            'branch_id': 1,
            'mobile': '9555555555',
            'is_active': True
        }
    ]
    
    for user_data in default_users:
        password = user_data.pop('password')
        user = User(**user_data)
        user.password_hash = generate_password_hash(password)
        db.session.add(user)
    
    db.session.commit()
    print("✅ Created default users:")
    for user_data in default_users:
        print(f"   👤 {user_data['username']} ({user_data['role']})")

def test_database_connection():
    """Test database connectivity"""
    try:
        os.environ['APP_ENV'] = 'production'
        
        from globalit_app import create_app
        app = create_app()
        
        with app.app_context():
            from init_db import db
            
            # Test connection
            result = db.session.execute('SELECT 1').fetchone()
            if result:
                print("✅ Database connection test successful!")
                return True
            else:
                print("❌ Database connection test failed!")
                return False
                
    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 PythonAnywhere Database Initialization Script")
    print("=" * 50)
    
    # Test database connection first
    print("\n1️⃣ Testing database connection...")
    if not test_database_connection():
        print("❌ Database connection failed. Please check your .env file and MySQL database configuration.")
        sys.exit(1)
    
    # Initialize database
    print("\n2️⃣ Initializing database...")
    success = init_database()
    
    if success:
        print("\n🎉 Database initialization completed successfully!")
        print("\n📋 Default Login Credentials:")
        print("   👤 Username: admin")
        print("   🔑 Password: admin123")
        print("   🌐 Role: admin")
        print("\n⚠️  IMPORTANT: Change the default password after first login!")
        print("\n🚀 Your GlobalIT LMS is ready for deployment!")
        print("   Next steps:")
        print("   1. Configure your web app in PythonAnywhere Web tab")
        print("   2. Set up the WSGI file")
        print("   3. Configure static files")
        print("   4. Reload your web app")
    else:
        print("\n❌ Database initialization failed!")
        print("   Please check the error messages above and:")
        print("   1. Verify your .env file configuration")
        print("   2. Ensure MySQL database exists and is accessible")
        print("   3. Check your database credentials")
        sys.exit(1)
