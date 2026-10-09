from flask import Blueprint

bp = Blueprint("account", __name__, url_prefix="/account")

from . import routes  # noqa: E402,F401
