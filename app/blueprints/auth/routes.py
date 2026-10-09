from email_validator import EmailNotValidError, validate_email
from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user

from ...extensions import db, limiter
from ...models import User
from ...utils import is_safe_redirect
from . import bp


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("public.home"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:120]
        password = request.form.get("password", "")
        try:
            email = validate_email(request.form.get("email", "").strip(), check_deliverability=False).normalized.lower()
        except EmailNotValidError:
            flash("Please enter a valid email address.", "danger")
            return render_template("auth/register.html"), 400
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return render_template("auth/register.html"), 400
        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "danger")
            return render_template("auth/register.html"), 400
        user = User(email=email, name=name, role="customer")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Welcome! Your account is ready.", "success")
        return redirect(url_for("public.home"))
    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("public.home"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and user.active and user.check_password(request.form.get("password", "")):
            cart = session.get("cart", [])  # keep guest cart across login
            login_user(user, remember=bool(request.form.get("remember")))
            session["cart"] = cart
            nxt = request.args.get("next")
            return redirect(nxt if is_safe_redirect(nxt) else url_for("public.home"))
        flash("Invalid email or password.", "danger")
        return render_template("auth/login.html"), 401
    return render_template("auth/login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("public.home"))
