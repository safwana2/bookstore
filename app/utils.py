import re
import unicodedata
from decimal import Decimal, InvalidOperation
from functools import wraps
from urllib.parse import urlparse

from flask import abort
from flask_login import current_user


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "item"


def unique_slug(model, text, exclude_id=None):
    base = slugify(text)
    slug, n = base, 2
    while True:
        q = model.query.filter_by(slug=slug)
        if exclude_id:
            q = q.filter(model.id != exclude_id)
        if not q.first():
            return slug
        slug = f"{base}-{n}"
        n += 1


def to_minor(value):
    """'12.50' -> 1250. Raises ValueError on bad input."""
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError):
        raise ValueError("Invalid price")
    if amount < 0:
        raise ValueError("Price cannot be negative")
    return int((amount * 100).quantize(Decimal("1")))


def money(minor, currency="GHS"):
    return f"{currency} {Decimal(minor) / 100:,.2f}"


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return current_app_login_required()
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def current_app_login_required():
    from flask import current_app
    return current_app.login_manager.unauthorized()


admin_required = roles_required("admin")


def is_safe_redirect(target):
    if not target:
        return False
    parsed = urlparse(target)
    return not parsed.netloc and not parsed.scheme and target.startswith("/") and not target.startswith("//")
