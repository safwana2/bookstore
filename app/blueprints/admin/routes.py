from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func

from ...extensions import db
from ...models import AuditLog, AuthorProfile, Book, Category, Entitlement, Order, User, utcnow
from ...services import audit
from ...services.files import delete_quietly, books_dir, previews_dir, save_book_file, save_cover, save_preview
from ...utils import admin_required, to_minor, unique_slug
from . import bp
from flask import current_app


@bp.before_request
@admin_required
def _guard():
    """Every route in this blueprint requires an admin."""


@bp.route("/")
def dashboard():
    revenue = db.session.query(func.coalesce(func.sum(Order.total_minor), 0)).filter(Order.status == "paid").scalar()
    stats = {
        "revenue": revenue,
        "orders": Order.query.filter_by(status="paid").count(),
        "customers": User.query.filter_by(role="customer").count(),
        "books": Book.query.count(),
        "published": Book.query.filter_by(status="published").count(),
    }
    recent = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    top = (
        db.session.query(Book.title, func.count(Entitlement.id).label("sales"))
        .join(Entitlement, Entitlement.book_id == Book.id)
        .group_by(Book.id).order_by(func.count(Entitlement.id).desc()).limit(5).all()
    )
    return render_template("admin/dashboard.html", stats=stats, recent=recent, top=top,
                           currency=current_app.config["DEFAULT_CURRENCY"])


# ---------- Books ----------
@bp.route("/books")
def books():
    return render_template("admin/books.html", books=Book.query.order_by(Book.created_at.desc()).all())


def _fill_book(book):
    """Apply the submitted form to a Book. Raises ValueError with a friendly message."""
    f = request.form
    title = f.get("title", "").strip()
    if not title:
        raise ValueError("Title is required.")
    author = db.session.get(AuthorProfile, f.get("author_id", type=int) or 0)
    if not author:
        raise ValueError("Choose an author (create one first under Authors).")
    status = f.get("status", "draft")
    if status not in ("draft", "in_review", "published", "archived"):
        raise ValueError("Invalid status.")

    book.title = title
    book.description = f.get("description", "").strip()
    book.price_minor = to_minor(f.get("price", "0") or "0")
    book.currency = current_app.config["DEFAULT_CURRENCY"]
    book.author_id = author.id
    book.is_featured = bool(f.get("is_featured"))
    book.categories = Category.query.filter(Category.id.in_(request.form.getlist("categories", type=int))).all()

    if status == "published" and book.status != "published":
        book.published_at = utcnow()
    book.status = status
    if not book.slug:
        book.slug = unique_slug(Book, title)

    cover = save_cover(request.files.get("cover"))
    if cover:
        delete_quietly(current_app.config["COVER_FOLDER"], book.cover_filename)
        book.cover_filename = cover
    bookfile = save_book_file(request.files.get("book_file"))
    if bookfile:
        delete_quietly(books_dir(), book.file_filename)
        book.file_filename = bookfile
    preview = save_preview(request.files.get("preview_file"))
    if preview:
        delete_quietly(previews_dir(), book.preview_filename)
        book.preview_filename = preview

    if book.status == "published" and not book.file_filename:
        raise ValueError("Upload the book file (PDF/ePub) before publishing.")


@bp.route("/books/new", methods=["GET", "POST"])
def book_new():
    book = Book()
    if request.method == "POST":
        try:
            _fill_book(book)
            db.session.add(book)
            db.session.flush()
            audit.log("book.create", "book", book.id, title=book.title, price=book.price_minor)
            db.session.commit()
            flash("Book saved.", "success")
            return redirect(url_for("admin.books"))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    return render_template("admin/book_form.html", book=book, authors=AuthorProfile.query.all(),
                           categories=Category.query.order_by(Category.name).all())


@bp.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
def book_edit(book_id):
    book = db.session.get(Book, book_id) or abort(404)
    if request.method == "POST":
        old_price, old_status = book.price_minor, book.status
        try:
            _fill_book(book)
            audit.log("book.update", "book", book.id, title=book.title,
                      price_before=old_price, price_after=book.price_minor,
                      status_before=old_status, status_after=book.status)
            db.session.commit()
            flash("Book updated.", "success")
            return redirect(url_for("admin.books"))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    return render_template("admin/book_form.html", book=book, authors=AuthorProfile.query.all(),
                           categories=Category.query.order_by(Category.name).all())


@bp.route("/books/<int:book_id>/archive", methods=["POST"])
def book_archive(book_id):
    """We archive instead of deleting so past orders and customer libraries stay intact."""
    book = db.session.get(Book, book_id) or abort(404)
    book.status = "archived"
    audit.log("book.archive", "book", book.id, title=book.title)
    db.session.commit()
    flash("Book archived (customers who bought it keep access).", "info")
    return redirect(url_for("admin.books"))


# ---------- Authors & categories ----------
@bp.route("/authors", methods=["GET", "POST"])
def authors():
    if request.method == "POST":
        name = request.form.get("display_name", "").strip()
        if name:
            rate = min(max(request.form.get("royalty_rate", 100, type=int), 0), 100)
            a = AuthorProfile(display_name=name, slug=unique_slug(AuthorProfile, name),
                              bio=request.form.get("bio", "").strip(), royalty_rate=rate)
            db.session.add(a)
            db.session.flush()
            audit.log("author.create", "author", a.id, name=name, royalty_rate=rate)
            db.session.commit()
            flash("Author added.", "success")
        return redirect(url_for("admin.authors"))
    return render_template("admin/authors.html", authors=AuthorProfile.query.order_by(AuthorProfile.display_name).all())


@bp.route("/categories", methods=["GET", "POST"])
def categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name and not Category.query.filter(func.lower(Category.name) == name.lower()).first():
            c = Category(name=name, slug=unique_slug(Category, name))
            db.session.add(c)
            db.session.flush()
            audit.log("category.create", "category", c.id, name=name)
            db.session.commit()
            flash("Category added.", "success")
        return redirect(url_for("admin.categories"))
    return render_template("admin/categories.html", categories=Category.query.order_by(Category.name).all())


# ---------- Orders, refunds, customers, audit ----------
@bp.route("/orders")
def orders():
    return render_template("admin/orders.html", orders=Order.query.order_by(Order.created_at.desc()).limit(200).all())


@bp.route("/orders/<int:order_id>/refund", methods=["POST"])
def order_refund(order_id):
    """Marks the order refunded and revokes access. Return the money from the Paystack dashboard
    (automated refunds via the Paystack API are a later step)."""
    order = db.session.get(Order, order_id) or abort(404)
    if order.status != "paid":
        flash("Only paid orders can be refunded.", "warning")
        return redirect(url_for("admin.orders"))
    order.status = "refunded"
    for item in order.items:
        ent = Entitlement.query.filter_by(user_id=order.user_id, book_id=item.book_id).first()
        if ent:
            ent.revoked_at = utcnow()
    audit.log("order.refund", "order", order.id, reference=order.reference, total=order.total_minor)
    db.session.commit()
    flash("Order marked refunded and access revoked. Remember to send the money back via Paystack.", "info")
    return redirect(url_for("admin.orders"))


@bp.route("/customers")
def customers():
    return render_template("admin/customers.html", users=User.query.order_by(User.created_at.desc()).limit(300).all())


@bp.route("/customers/<int:user_id>/toggle", methods=["POST"])
def customer_toggle(user_id):
    user = db.session.get(User, user_id) or abort(404)
    from flask_login import current_user
    if user.id == current_user.id:
        flash("You cannot deactivate yourself.", "warning")
    else:
        user.active = not user.active
        audit.log("user.toggle_active", "user", user.id, active=user.active)
        db.session.commit()
    return redirect(url_for("admin.customers"))


@bp.route("/audit")
def audit_log():
    return render_template("admin/audit.html", logs=AuditLog.query.order_by(AuditLog.created_at.desc()).limit(300).all())
