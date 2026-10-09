from datetime import datetime
from pathlib import Path

import click
from flask import Flask, render_template, session
from flask_login import current_user

from config import Config

from .extensions import csrf, db, limiter, login_manager, mail, migrate
from .utils import money


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # Make sure storage folders exist
    for folder in (
        Path(app.instance_path),
        app.config["PRIVATE_STORAGE"] / "books",
        app.config["PRIVATE_STORAGE"] / "previews",
        app.config["COVER_FOLDER"],
    ):
        folder.mkdir(parents=True, exist_ok=True)

    if not app.debug and not app.testing and app.config["SECRET_KEY"] == "dev-only-change-me":
        app.logger.warning("SECRET_KEY is the insecure default. Set a real one in .env before deploying!")

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)

    from . import models  # noqa: F401  (registers tables with SQLAlchemy)
    from .blueprints.account import bp as account_bp
    from .blueprints.admin import bp as admin_bp
    from .blueprints.auth import bp as auth_bp
    from .blueprints.author import bp as author_bp
    from .blueprints.cart import bp as cart_bp
    from .blueprints.payments import bp as payments_bp
    from .blueprints.public import bp as public_bp

    for bp in (public_bp, auth_bp, account_bp, cart_bp, payments_bp, admin_bp, author_bp):
        app.register_blueprint(bp)

    app.jinja_env.filters["money"] = money

    @app.context_processor
    def inject_globals():
        return {
            "site_name": app.config["SITE_NAME"],
            "cart_count": len(session.get("cart", [])),
            "current_year": datetime.now().year,
        }

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return resp

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/error.html", code=403, message="You don't have permission to view this page."), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/error.html", code=404, message="We couldn't find that page."), 404

    @app.errorhandler(413)
    def too_large(_e):
        return render_template("errors/error.html", code=413, message="That upload is too large."), 413

    register_cli(app)
    return app


def register_cli(app):
    from .models import AuthorProfile, Category, User
    from .utils import unique_slug

    @app.cli.command("init-db")
    def init_db():
        """Create all tables (quick start). For schema changes later, use `flask db` migrations."""
        db.create_all()
        click.echo("Database tables created.")

    @app.cli.command("create-admin")
    @click.argument("email")
    @click.password_option()
    @click.option("--name", default="Admin")
    def create_admin(email, password, name):
        """Create an admin user and a 'house' author profile for them."""
        email = email.strip().lower()
        if User.query.filter_by(email=email).first():
            raise click.ClickException("A user with that email already exists.")
        user = User(email=email, name=name, role="admin", is_verified=True)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        db.session.add(AuthorProfile(user_id=user.id, display_name=name,
                                     slug=unique_slug(AuthorProfile, name), royalty_rate=100))
        db.session.commit()
        click.echo(f"Admin {email} created (house author profile: {name}).")

    @app.cli.command("reset-password")
    @click.argument("email")
    @click.password_option()
    def reset_password(email, password):
        """Set a new password for an existing user (also reactivates the account)."""
        user = User.query.filter_by(email=email.strip().lower()).first()
        if not user:
            raise click.ClickException("No user with that email.")
        user.set_password(password)
        user.active = True
        db.session.commit()
        click.echo(f"Password updated for {user.email} (role: {user.role}).")

    @app.cli.command("seed-categories")
    def seed_categories():
        """Add a few starter categories."""
        for name in ("Fiction", "Non-Fiction", "Business", "Self-Help", "Education", "Poetry", "Religion", "Technology"):
            if not Category.query.filter_by(name=name).first():
                db.session.add(Category(name=name, slug=unique_slug(Category, name)))
        db.session.commit()
        click.echo("Starter categories added.")