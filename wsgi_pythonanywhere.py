#!/usr/bin/env python3
"""
WSGI Configuration for PythonAnywhere Deployment
==============================================

This file should be placed at: /var/www/yourusername_pythonanywhere_com_wsgi.py

Instructions:
1. Replace 'yourusername' with your actual PythonAnywhere username
2. Update the project_home path if different
3. Ensure your virtual environment path is correct in the Web tab
4. Make sure all environment variables are set in your .env file

"""

import sys
import os
from pathlib import Path

# =============================================================================
# Configuration - UPDATE THESE PATHS
# =============================================================================

# Your PythonAnywhere username (replace 'yourusername' with actual username)
USERNAME = 'yourusername'  # <- CHANGE THIS

# Project directory on PythonAnywhere
project_home = f'/home/{USERNAME}/globalitwebapp2.0'

# Virtual environment path (should match what's set in Web tab)
venv_path = f'/home/{USERNAME}/globalitwebapp2.0/venv'

# =============================================================================
# System Path Configuration
# =============================================================================

# Add project directory to Python path
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Add virtual environment site-packages to path
site_packages = f'{venv_path}/lib/python3.10/site-packages'
if site_packages not in sys.path:
    sys.path.insert(0, site_packages)

# =============================================================================
# Environment Configuration
# =============================================================================

# Set production environment
os.environ['APP_ENV'] = 'production'
os.environ['FLASK_ENV'] = 'production'

# Load environment variables from .env file
env_file = os.path.join(project_home, '.env')
if os.path.exists(env_file):
    from dotenv import load_dotenv
    load_dotenv(env_file)
    print(f"✅ Loaded environment variables from {env_file}")
else:
    print(f"⚠️  Warning: .env file not found at {env_file}")

# =============================================================================
# Logging Configuration
# =============================================================================

import logging

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    handlers=[
        logging.FileHandler(f'{project_home}/logs/wsgi.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info("WSGI module loaded")

# =============================================================================
# Flask Application
# =============================================================================

try:
    # Import and create Flask application
    from globalit_app import create_app
    
    application = create_app()
    
    # Log successful application creation
    logger.info("✅ Flask application created successfully")
    logger.info(f"✅ Debug mode: {application.config.get('DEBUG', 'Not set')}")
    logger.info(f"✅ Database URI configured: {'DATABASE_URL' in os.environ}")
    
    # Test database connection
    try:
        with application.app_context():
            from init_db import db
            # Simple database connectivity test
            db.engine.execute('SELECT 1')
            logger.info("✅ Database connection successful")
    except Exception as db_error:
        logger.error(f"❌ Database connection failed: {db_error}")
    
except Exception as e:
    logger.error(f"❌ Failed to create Flask application: {e}")
    logger.error(f"❌ Python path: {sys.path}")
    logger.error(f"❌ Working directory: {os.getcwd()}")
    raise

# =============================================================================
# Development Testing (Only for debugging)
# =============================================================================

if __name__ == "__main__":
    # This section only runs when testing locally
    # Do not use this in production!
    print("🔧 Running in development mode")
    print(f"🔧 Project home: {project_home}")
    print(f"🔧 Python path: {sys.path}")
    print(f"🔧 Environment: {os.environ.get('APP_ENV', 'Not set')}")
    
    application.run(debug=False, host='0.0.0.0', port=5000)

# =============================================================================
# Health Check Function
# =============================================================================

def health_check():
    """
    Health check function for monitoring
    Can be called to verify application status
    """
    try:
        with application.app_context():
            from init_db import db
            # Test database
            db.engine.execute('SELECT 1')
            
            # Test basic route
            with application.test_client() as client:
                response = client.get('/')
                
            return {
                'status': 'healthy',
                'database': 'connected',
                'app': 'running',
                'environment': os.environ.get('APP_ENV', 'unknown')
            }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'environment': os.environ.get('APP_ENV', 'unknown')
        }

# =============================================================================
# PythonAnywhere Specific Optimizations
# =============================================================================

# Configure for PythonAnywhere's environment
if 'pythonanywhere' in os.environ.get('HOME', '').lower():
    # PythonAnywhere specific settings
    application.config['SEND_FILE_MAX_AGE_DEFAULT'] = 3600  # Cache static files
    
    # Enable response compression if available
    try:
        from flask_compress import Compress
        Compress(application)
        logger.info("✅ Response compression enabled")
    except ImportError:
        logger.info("ℹ️  Flask-Compress not available, skipping compression")

# Ensure proper error handling
@application.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return "Internal server error", 500

@application.errorhandler(404)
def not_found(error):
    logger.warning(f"Page not found: {error}")
    return "Page not found", 404

logger.info("🚀 WSGI configuration complete - Application ready")
