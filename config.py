"""
Configuration module for Global IT Education Web Application
Contains all configuration settings for different environments
"""

import os
from datetime import timedelta

class Config:
    """Base configuration class with common settings"""
    
    # Basic Flask Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'globalit-secret-key-change-in-production'
    
    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///globalit_education_dev.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    @staticmethod
    def get_engine_options():
        """Get database engine options based on database type"""
        db_uri = os.environ.get('DATABASE_URL') or 'sqlite:///globalit_education_dev.db'
        
        base_options = {
            'pool_pre_ping': True,
            'pool_recycle': 3600,  # Recycle connections every hour
            'pool_size': 5,        # Connection pool size
            'max_overflow': 10,    # Allow extra connections
            'pool_timeout': 30,    # Connection timeout
            'echo': False,         # Disable SQL logging for performance
        }
        
        if db_uri.startswith('mysql'):
            # MySQL-specific configuration with SSL support
            mysql_connect_args = {
                'charset': 'utf8mb4',
                'connect_timeout': 30,
                'read_timeout': 30,
                'write_timeout': 30,
                # SSL Configuration for Production Security
                'ssl_disabled': os.environ.get('MYSQL_SSL_DISABLED', 'False').lower() == 'true',
                'ssl_verify_cert': os.environ.get('MYSQL_SSL_VERIFY_CERT', 'True').lower() == 'true',
                'ssl_verify_identity': os.environ.get('MYSQL_SSL_VERIFY_IDENTITY', 'True').lower() == 'true',
                # Connection optimization
                'autocommit': False,
                'sql_mode': 'TRADITIONAL',
                'init_command': "SET SESSION sql_mode='TRADITIONAL'",
            }
            
            # Add SSL certificate paths if provided
            ssl_ca = os.environ.get('MYSQL_SSL_CA')
            ssl_cert = os.environ.get('MYSQL_SSL_CERT')
            ssl_key = os.environ.get('MYSQL_SSL_KEY')
            
            if ssl_ca:
                mysql_connect_args['ssl_ca'] = ssl_ca
            if ssl_cert:
                mysql_connect_args['ssl_cert'] = ssl_cert
            if ssl_key:
                mysql_connect_args['ssl_key'] = ssl_key
            
            # For development, allow less strict SSL if explicitly set
            if os.environ.get('FLASK_ENV', 'production').lower() == 'development':
                mysql_connect_args['ssl_verify_cert'] = os.environ.get('MYSQL_SSL_VERIFY_CERT', 'False').lower() == 'true'
                mysql_connect_args['ssl_verify_identity'] = os.environ.get('MYSQL_SSL_VERIFY_IDENTITY', 'False').lower() == 'true'
            
            base_options['connect_args'] = mysql_connect_args
        else:
            # SQLite configuration
            base_options['connect_args'] = {
                'timeout': 30,
            }
        
        return base_options
    
    SQLALCHEMY_ENGINE_OPTIONS = get_engine_options.__func__()
    
    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # File Upload Configuration
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Upload Configuration
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    
    # Pagination Configuration (Optimized for Performance)
    POSTS_PER_PAGE = 15        # Reduced from 25
    STUDENTS_PER_PAGE = 30     # Reduced from 50  
    BATCHES_PER_PAGE = 15      # Reduced from 20
    LEADS_PER_PAGE = 20        # New setting for leads
    
    # Email Configuration (for future use)
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    
    # SMS Configuration (for future use)
    SMS_API_KEY = os.environ.get('SMS_API_KEY')
    SMS_API_URL = os.environ.get('SMS_API_URL')
    
    # MySQL SSL Configuration (Production Security)
    # Environment variables for SSL setup:
    # MYSQL_SSL_DISABLED=false          # Enable/disable SSL (default: false - SSL enabled)
    # MYSQL_SSL_VERIFY_CERT=true        # Verify server certificate (default: true)
    # MYSQL_SSL_VERIFY_IDENTITY=true    # Verify server identity (default: true)
    # MYSQL_SSL_CA=/path/to/ca.pem      # Certificate Authority file
    # MYSQL_SSL_CERT=/path/to/cert.pem  # Client certificate file
    # MYSQL_SSL_KEY=/path/to/key.pem    # Client private key file
    
    # Application Settings
    TIMEZONE = 'Asia/Kolkata'
    DATE_FORMAT = '%Y-%m-%d'
    DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
    
    # Security Settings
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour
    
    # Logging Configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
    LOG_FILE = os.environ.get('LOG_FILE') or 'globalit_app.log'
    
    # Cache Configuration (Enhanced)
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 600  # 10 minutes for better performance
    
    # Performance Settings
    ENABLE_QUERY_CACHE = True
    DASHBOARD_CACHE_TIMEOUT = 300  # 5 minutes for dashboard stats
    
    @staticmethod
    def init_app(app):
        """Initialize app-specific configuration"""
        pass

class DevelopmentConfig(Config):
    """Development environment configuration"""
    DEBUG = True
    TESTING = False
    SQLALCHEMY_ECHO = False  # Set to True to see SQL queries in console
    
    # Development-specific database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'globalit_education_dev.db')

class ProductionConfig(Config):
    """Production environment configuration"""
    DEBUG = False
    TESTING = False
    
    # Production database (use PostgreSQL or MySQL)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'globalit_education_prod.db')
    
    # Enhanced security for production
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_ENABLED = True
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Production SSL Security Validation
        cls._validate_production_security(app)
        
        # Log to stderr in production
        import logging
        from logging import StreamHandler
        file_handler = StreamHandler()
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
    
    @classmethod
    def _validate_production_security(cls, app):
        """Validate production security settings"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Check database URL for MySQL SSL
        db_url = os.environ.get('DATABASE_URL', '')
        if db_url.startswith('mysql'):
            # Check SSL configuration
            ssl_disabled = os.environ.get('MYSQL_SSL_DISABLED', 'False').lower() == 'true'
            if ssl_disabled:
                logger.warning("⚠️ WARNING: MySQL SSL is DISABLED in production! This is a security risk.")
            else:
                logger.info("✅ MySQL SSL encryption is enabled for production.")
            
            # Check SSL verification
            ssl_verify_cert = os.environ.get('MYSQL_SSL_VERIFY_CERT', 'True').lower() == 'true'
            ssl_verify_identity = os.environ.get('MYSQL_SSL_VERIFY_IDENTITY', 'True').lower() == 'true'
            
            if not ssl_verify_cert:
                logger.warning("⚠️ WARNING: MySQL SSL certificate verification is disabled!")
            if not ssl_verify_identity:
                logger.warning("⚠️ WARNING: MySQL SSL identity verification is disabled!")
            
            if ssl_verify_cert and ssl_verify_identity:
                logger.info("✅ MySQL SSL certificate and identity verification enabled.")
        
        # Check HTTPS settings
        if not app.config.get('SESSION_COOKIE_SECURE'):
            logger.warning("⚠️ WARNING: SESSION_COOKIE_SECURE should be True in production with HTTPS!")
        
        # Check secret key
        if app.config.get('SECRET_KEY') == 'globalit-secret-key-change-in-production':
            logger.error("❌ CRITICAL: Default SECRET_KEY detected! Change SECRET_KEY in production!")
        
        logger.info("🔐 Production security validation completed.")

class TestingConfig(Config):
    """Testing environment configuration"""
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False
    
    # Use in-memory database for testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

# Get configuration based on environment variable
def get_config():
    """Get configuration class based on environment"""
    env = os.environ.get('FLASK_ENV', 'development').lower()
    return config.get(env, config['default'])

# For backward compatibility, export the default config
Config = ProductionConfig
