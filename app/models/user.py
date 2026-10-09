from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db, login_manager


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False, default="")
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="customer")  # customer | admin | author
    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    author_profile = db.relationship("AuthorProfile", back_populates="user", uselist=False)
    orders = db.relationship("Order", back_populates="user", lazy="dynamic")
    entitlements = db.relationship("Entitlement", back_populates="user", lazy="dynamic")

    @property
    def is_active(self):  # Flask-Login hook
        return self.active

    @property
    def is_admin(self):
        return self.role == "admin"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def owns(self, book_id):
        return (
            self.entitlements.filter_by(book_id=book_id, revoked_at=None).first() is not None
        )


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class AuthorProfile(db.Model):
    """Marketplace-ready: every book belongs to an author profile.
    In v1 there is one 'house' author (you) with royalty_rate=100."""
    __tablename__ = "author_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=True)
    display_name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(160), unique=True, nullable=False)
    bio = db.Column(db.Text, default="")
    royalty_rate = db.Column(db.Integer, nullable=False, default=100)  # percent of sale the author keeps
    payout_details = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    user = db.relationship("User", back_populates="author_profile")
    books = db.relationship("Book", back_populates="author", lazy="dynamic")
