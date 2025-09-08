"""
Configuration module for Global IT Education Web Application
"""
import os
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "globalit-secret-key-change-in-production")

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")  # overridden per env
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # overridden in ProductionConfig

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = UPLOAD_DIR

    POSTS_PER_PAGE = 25
    STUDENTS_PER_PAGE = 50
    BATCHES_PER_PAGE = 20

    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() in {"true", "on", "1"}
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")

    SMS_API_KEY = os.environ.get("SMS_API_KEY")
    SMS_API_URL = os.environ.get("SMS_API_URL")

    TIMEZONE = "Asia/Kolkata"
    DATE_FORMAT = "%Y-%m-%d"
    DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_FILE = os.environ.get("LOG_FILE", "globalit_app.log")

    @staticmethod
    def init_app(app):
        os.makedirs(UPLOAD_DIR, exist_ok=True)


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TESTING = False
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DEV_DATABASE_URL",
        f"sqlite:///{os.path.join(BASE_DIR, 'globalit_education_dev.db')}",
    )


class ProductionConfig(BaseConfig):
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    # Just read from env; do NOT raise here
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}


def get_config():
    """Select config via APP_ENV (production|development|testing)."""
    env = os.environ.get("APP_ENV", os.environ.get("FLASK_ENV", "development")).lower()
    return config.get(env, config["default"])

# ---- Backward compatibility for "from config import Config"
# Make sure there's a *class* named Config to import.
_Selected = get_config()
class Config(_Selected):  # noqa: N801  (keep this name!)
    """Selected environment config (alias for backward compatibility)."""
    pass

__all__ = [
    "BaseConfig",
    "DevelopmentConfig",
    "ProductionConfig",
    "TestingConfig",
    "get_config",
    "Config",
]
