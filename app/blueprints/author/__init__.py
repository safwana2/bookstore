from flask import Blueprint

# Marketplace phase (v3): author dashboard, submit book for review, royalty reports.
# Models are already marketplace-ready (AuthorProfile, Book.status workflow, OrderItem shares).
bp = Blueprint("author", __name__, url_prefix="/author")
