from flask import abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required

from ...extensions import db
from ...models import AuthorProfile, Book, Category, Review
from ...services.files import previews_dir
from ...utils import to_minor
from . import bp


def _published():
    return Book.query.filter_by(status="published")


@bp.route("/")
def home():
    featured = _published().filter_by(is_featured=True).order_by(Book.published_at.desc()).limit(8).all()
    latest = _published().order_by(Book.published_at.desc()).limit(8).all()
    return render_template("home.html", featured=featured, latest=latest)


@bp.route("/books")
def catalog():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    author = request.args.get("author", "").strip()
    sort = request.args.get("sort", "newest")
    page = request.args.get("page", 1, type=int)

    query = _published()
    if q:
        like = f"%{q}%"
        query = query.join(AuthorProfile).filter(db.or_(Book.title.ilike(like), Book.description.ilike(like), AuthorProfile.display_name.ilike(like)))
    if category:
        query = query.filter(Book.categories.any(Category.slug == category))
    if author:
        query = query.filter(Book.author.has(AuthorProfile.slug == author))
    try:
        if request.args.get("min_price"):
            query = query.filter(Book.price_minor >= to_minor(request.args["min_price"]))
        if request.args.get("max_price"):
            query = query.filter(Book.price_minor <= to_minor(request.args["max_price"]))
    except ValueError:
        flash("Price filters must be numbers.", "warning")

    order = {
        "price_asc": Book.price_minor.asc(),
        "price_desc": Book.price_minor.desc(),
        "title": Book.title.asc(),
    }.get(sort, Book.published_at.desc())
    pagination = query.order_by(order).paginate(page=page, per_page=current_app.config["BOOKS_PER_PAGE"], error_out=False)

    return render_template(
        "catalog.html",
        pagination=pagination,
        categories=Category.query.order_by(Category.name).all(),
        authors=AuthorProfile.query.order_by(AuthorProfile.display_name).all(),
        args=request.args,
        query_args={k: v for k, v in request.args.items() if k != "page"},
    )


@bp.route("/books/<slug>")
def book_detail(slug):
    book = Book.query.filter_by(slug=slug).first_or_404()
    if not book.is_published and not (current_user.is_authenticated and current_user.is_admin):
        abort(404)
    owned = current_user.is_authenticated and current_user.owns(book.id)
    reviews = book.reviews.order_by(Review.created_at.desc()).all()
    return render_template("book_detail.html", book=book, owned=owned, reviews=reviews)


@bp.route("/books/<slug>/preview")
def preview(slug):
    book = Book.query.filter_by(slug=slug, status="published").first_or_404()
    if not book.preview_filename:
        abort(404)
    return send_from_directory(previews_dir(), book.preview_filename, mimetype="application/pdf", as_attachment=False)


@bp.route("/books/<slug>/review", methods=["POST"])
@login_required
def review(slug):
    book = Book.query.filter_by(slug=slug, status="published").first_or_404()
    if not current_user.owns(book.id):
        flash("Only buyers can review a book.", "warning")
        return redirect(url_for("public.book_detail", slug=slug))
    rating = request.form.get("rating", type=int)
    if rating not in range(1, 6):
        flash("Choose a rating from 1 to 5.", "warning")
        return redirect(url_for("public.book_detail", slug=slug))
    existing = Review.query.filter_by(user_id=current_user.id, book_id=book.id).first()
    body = request.form.get("body", "").strip()[:2000]
    if existing:
        existing.rating, existing.body = rating, body
    else:
        db.session.add(Review(user_id=current_user.id, book_id=book.id, rating=rating, body=body))
    db.session.commit()
    flash("Thanks for your review!", "success")
    return redirect(url_for("public.book_detail", slug=slug))


@bp.route("/about")
def about():
    return render_template("page.html", title="About", body="Write your story here.")


@bp.route("/terms")
def terms():
    return render_template("page.html", title="Terms of Service", body="Add your terms of service here (have a lawyer review them).")


@bp.route("/privacy")
def privacy():
    return render_template("page.html", title="Privacy Policy", body="Add your privacy policy here (have a lawyer review it).")


@bp.route("/refunds")
def refunds():
    return render_template("page.html", title="Refund Policy", body="Add your refund policy here.")
