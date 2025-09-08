import logging
import os
from datetime import datetime

# Setup logging configuration
def setup_logging():
    """Setup logging configuration for the application"""
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Configure logging
    log_file = os.path.join(logs_dir, 'sms.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

# Setup logging when module is imported
setup_logging()

# Get logger instance
logger = logging.getLogger('SMS_SERVICE')

def log_info(message):
    """Log info level message"""
    logger.info(message)

def log_error(message):
    """Log error level message"""
    logger.error(message)

def log_warning(message):
    """Log warning level message"""
    logger.warning(message)

def log_debug(message):
    """Log debug level message"""
    logger.debug(message)