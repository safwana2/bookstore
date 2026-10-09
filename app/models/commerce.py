from ..extensions import db
from ..utils import money
from .user import utcnow


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)  # pending|paid|failed|refunded
    total_minor = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    paid_at = db.Column(db.DateTime)

    user = db.relationship("User", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = db.relationship("Payment", back_populates="order")

    @property
    def total_display(self):
        return money(self.total_minor, self.currency)


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False)
    title_snapshot = db.Column(db.String(255), nullable=False)
    unit_price_minor = db.Column(db.Integer, nullable=False)
    # Royalty hook for the future marketplace:
    author_share_minor = db.Column(db.Integer, nullable=False, default=0)
    platform_share_minor = db.Column(db.Integer, nullable=False, default=0)

    order = db.relationship("Order", back_populates="items")
    book = db.relationship("Book")


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    provider = db.Column(db.String(30), nullable=False, default="paystack")
    provider_reference = db.Column(db.String(100), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    amount_minor = db.Column(db.Integer, nullable=False)
    raw_payload = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    order = db.relationship("Order", back_populates="payments")


class Entitlement(db.Model):
    """Source of truth for 'may this user download this book?'. Refund => set revoked_at."""
    __tablename__ = "entitlements"
    __table_args__ = (db.UniqueConstraint("user_id", "book_id", name="uq_user_book"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False)
    order_item_id = db.Column(db.Integer, db.ForeignKey("order_items.id"))
    granted_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    revoked_at = db.Column(db.DateTime)

    user = db.relationship("User", back_populates="entitlements")
    book = db.relationship("Book")


class Review(db.Model):
    __tablename__ = "reviews"
    __table_args__ = (db.UniqueConstraint("user_id", "book_id", name="uq_review_user_book"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    body = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    user = db.relationship("User")
    book = db.relationship("Book", back_populates="reviews")


class Coupon(db.Model):
    """Model is ready; checkout wiring is a later step."""
    __tablename__ = "coupons"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    percent_off = db.Column(db.Integer, nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    expires_at = db.Column(db.DateTime)
    max_uses = db.Column(db.Integer)
    used_count = db.Column(db.Integer, nullable=False, default=0)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(80), nullable=False, index=True)
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.String(50))
    details = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    actor = db.relationship("User")
