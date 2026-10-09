import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv is optional
    pass

BASE_DIR = Path(__file__).resolve().parent


def _flag(name, default="0"):
    return os.environ.get(name, default).lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    SITE_NAME = os.environ.get("SITE_NAME", "My Book Store")
    DEFAULT_CURRENCY = os.environ.get("DEFAULT_CURRENCY", "GHS")

    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL")
        or "sqlite:///" + (BASE_DIR / "instance" / "bookstore.db").as_posix()
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Files: books/previews are PRIVATE (never under /static). Covers are public.
    PRIVATE_STORAGE = BASE_DIR / "private_storage"
    COVER_FOLDER = BASE_DIR / "app" / "static" / "uploads" / "covers"
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100 MB per request
    ALLOWED_COVER_EXT = {"png", "jpg", "jpeg", "webp"}
    ALLOWED_BOOK_EXT = {"pdf", "epub"}
    ALLOWED_PREVIEW_EXT = {"pdf"}

    # Payments
    PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")
    FAKE_PAYMENTS = _flag("FAKE_PAYMENTS")

    # Email
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = _flag("MAIL_USE_TLS", "1")
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "store@example.com")

    # Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _flag("SESSION_COOKIE_SECURE")  # set 1 in production (HTTPS)
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")

    BOOKS_PER_PAGE = 12


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    WTF_CSRF_ENABLED = False
    FAKE_PAYMENTS = 1
    RATELIMIT_ENABLED = False
