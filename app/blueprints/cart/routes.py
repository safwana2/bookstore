from flask import current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from ...extensions import db
from ...models import Book
from ...services import payments
from ...services.orders import create_order, fulfill_order
from . import bp


def _cart_ids():
    return [i for i in session.get("cart", []) if isinstance(i, int)]


def _cart_books():
    ids = _cart_ids()
    if not ids:
        return []
    books = Book.query.filter(Book.id.in_(ids), Book.status == "published").all()
    if current_user.is_authenticated:  # never charge for something already owned
        books = [b for b in books if not current_user.owns(b.id)]
    return books


@bp.route("/")
def view():
    books = _cart_books()
    session["cart"] = [b.id for b in books]  # drop stale entries
    total = sum(b.price_minor for b in books)
    return render_template("cart/cart.html", books=books, total=total, currency=current_app.config["DEFAULT_CURRENCY"])


@bp.route("/add/<int:book_id>", methods=["POST"])
def add(book_id):
    book = db.session.get(Book, book_id)
    if not book or not book.is_published:
        flash("That book is not available.", "warning")
        return redirect(url_for("public.catalog"))
    if current_user.is_authenticated and current_user.owns(book.id):
        flash("You already own this book — find it in your library.", "info")
        return redirect(url_for("account.library"))
    cart = _cart_ids()
    if book.id not in cart:
        cart.append(book.id)
    session["cart"] = cart
    flash(f"Added “{book.title}” to your cart.", "success")
    return redirect(request.referrer or url_for("cart.view"))


@bp.route("/remove/<int:book_id>", methods=["POST"])
def remove(book_id):
    session["cart"] = [i for i in _cart_ids() if i != book_id]
    return redirect(url_for("cart.view"))


@bp.route("/checkout", methods=["POST"])
@login_required
def checkout():
    books = _cart_books()
    if not books:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("cart.view"))

    order = create_order(current_user, books)

    # Free books need no payment provider.
    if order.total_minor == 0:
        fulfill_order(order, {"status": "success", "amount": 0, "currency": order.currency,
                              "reference": order.reference}, provider="free")
        session["cart"] = []
        flash("Your free books were added to your library.", "success")
        return redirect(url_for("account.library"))

    # Local-testing shortcut: only honoured in debug mode, never in production.
    if current_app.config["FAKE_PAYMENTS"] and (current_app.debug or current_app.testing):
        fulfill_order(order, {"status": "success", "amount": order.total_minor, "currency": order.currency,
                              "reference": order.reference}, provider="fake")
        session["cart"] = []
        flash("Test payment accepted (FAKE_PAYMENTS is on).", "info")
        return redirect(url_for("account.library"))

    try:
        url = payments.initialize_transaction(order, current_user.email, url_for("payments.callback", _external=True))
    except payments.PaymentError as exc:
        order.status = "failed"
        db.session.commit()
        flash(str(exc), "danger")
        return redirect(url_for("cart.view"))
    return redirect(url)
