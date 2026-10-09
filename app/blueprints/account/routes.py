from flask import abort, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required

from ...extensions import db
from ...models import Book, Entitlement, Order
from ...services.files import books_dir
from . import bp


@bp.route("/library")
@login_required
def library():
    entitlements = (
        Entitlement.query.filter_by(user_id=current_user.id, revoked_at=None)
        .order_by(Entitlement.granted_at.desc()).all()
    )
    return render_template("account/library.html", entitlements=entitlements)


@bp.route("/orders")
@login_required
def orders():
    items = current_user.orders.order_by(Order.created_at.desc()).all()
    return render_template("account/orders.html", orders=items)


@bp.route("/download/<int:book_id>")
@login_required
def download(book_id):
    """Private download: only users with an active entitlement may fetch the file."""
    book = db.session.get(Book, book_id) or abort(404)
    if not current_user.owns(book.id):
        abort(403)
    if not book.file_filename:
        abort(404)
    ext = book.file_filename.rsplit(".", 1)[-1]
    return send_from_directory(books_dir(), book.file_filename, as_attachment=True, download_name=f"{book.slug}.{ext}")


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:120]
        current, new = request.form.get("current_password", ""), request.form.get("new_password", "")
        current_user.name = name
        if new:
            if not current_user.check_password(current):
                flash("Current password is incorrect.", "danger")
                return render_template("account/profile.html"), 400
            if len(new) < 8:
                flash("New password must be at least 8 characters.", "danger")
                return render_template("account/profile.html"), 400
            current_user.set_password(new)
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("account.profile"))
    return render_template("account/profile.html")
