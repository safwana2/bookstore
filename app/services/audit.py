import json

from flask_login import current_user

from ..extensions import db
from ..models import AuditLog


def log(action, target_type=None, target_id=None, **details):
    """Record an important action. Call BEFORE db.session.commit() so it commits atomically."""
    actor_id = current_user.id if current_user and current_user.is_authenticated else None
    db.session.add(AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        details=json.dumps(details, default=str),
    ))
