from flask import url_for

from ..extensions import db
from ..utils import money
from .user import utcnow

book_categories = db.Table(
    "book_categories",
    db.Column("book_id", db.Integer, db.ForeignKey("books.id"), primary_key=True),
    db.Column("category_id", db.Integer, db.ForeignKey("categories.id"), primary_key=True),
)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)


class Book(db.Model):
    __tablename__ = "books"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    slug = db.Column(db.String(270), unique=True, nullable=False)
    description = db.Column(db.Text, default="")
    price_minor = db.Column(db.Integer, nullable=False, default=0)  # money as integers!
    currency = db.Column(db.String(3), nullable=False, default="GHS")
    author_id = db.Column(db.Integer, db.ForeignKey("author_profiles.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="draft", index=True)  # draft|in_review|published|archived
    is_featured = db.Column(db.Boolean, nullable=False, default=False)
    cover_filename = db.Column(db.String(255))
    file_filename = db.Column(db.String(255))      # private: private_storage/books
    preview_filename = db.Column(db.String(255))   # private dir, but served publicly via preview route
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    published_at = db.Column(db.DateTime)

    author = db.relationship("AuthorProfile", back_populates="books")
    categories = db.relationship("Category", secondary=book_categories, backref="books")
    reviews = db.relationship("Review", back_populates="book", lazy="dynamic")

    @property
    def price_display(self):
        return "Free" if self.price_minor == 0 else money(self.price_minor, self.currency)

    @property
    def price_input(self):
        return f"{self.price_minor / 100:.2f}"

    @property
    def cover_url(self):
        if self.cover_filename:
            return url_for("static", filename=f"uploads/covers/{self.cover_filename}")
        return None

    @property
    def is_published(self):
        return self.status == "published"

    def average_rating(self):
        ratings = [r.rating for r in self.reviews]
        return round(sum(ratings) / len(ratings), 1) if ratings else None
