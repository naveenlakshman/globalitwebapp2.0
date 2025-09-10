from logging.config import fileConfig
import os
import sys
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Flask app and database
from globalit_app import create_app
from init_db import db

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# Import all models so they are registered with SQLAlchemy
from models.user_model import User
from models.student_model import Student
from models.batch_model import Batch
from models.course_model import Course
from models.branch_model import Branch
from models.payment_model import Payment
from models.installment_model import Installment
from models.invoice_model import Invoice
from models.staff_profile_model import StaffProfile
from models.expense_model import Expense
from models.lead_model import Lead
from models.attendance_audit_model import AttendanceAudit
from models.student_attendance_model import StudentAttendance
from models.batch_trainer_assignment_model import BatchTrainerAssignment
from models.student_batch_completion_model import StudentBatchCompletion
from models.communication_model import StudentNotification, StudentSupportTicket, StudentPortalSession, StudentLearningAnalytics
from models.expense_audit_model import ExpenseAudit
from models.login_logs_model import LoginLog
from models.lms_model import (
    CourseModule, CourseSection, CourseVideo, CourseMaterial, StudentModuleProgress,
    StudentSectionProgress, StudentVideoProgress, MaterialDownloadLog, MaterialAccessLog,
    VideoAccessLog, SecurityViolationLog, CourseAnnouncement, StudentAssignment,
    AssignmentSubmission, StudentNotes, LMSSettings
)
from models.lms_content_management_model import (
    VideoUpload, DocumentUpload, Quiz, QuizQuestion, QuizAttempt,
    AssignmentCreator, ContentWorkflow, FileStorage
)
from models.system_audit_logs_model import SystemAuditLog
from models.user_branch_assignment_model import UserBranchAssignment
from models.role_permission_model import RolePermission

# Set target metadata from the SQLAlchemy db object
target_metadata = db.metadata

# Flask app instance for accessing config
app = create_app()

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # Get URL from Flask app config instead of alembic.ini
    with app.app_context():
        url = app.config['SQLALCHEMY_DATABASE_URI']
        
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Use Flask app's database configuration
    with app.app_context():
        # Get the configured engine from Flask-SQLAlchemy
        connectable = db.engine
        
        with connectable.connect() as connection:
            context.configure(
                connection=connection, 
                target_metadata=target_metadata,
                # Include compare options for better migration detection
                compare_type=True,
                compare_server_default=True,
            )

            with context.begin_transaction():
                context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
