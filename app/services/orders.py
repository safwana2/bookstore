import json
import secrets

from flask import current_app, render_template
from flask_mail import Message
from sqlalchemy.exc import IntegrityError

from ..extensions import db, mail
from ..models import Entitlement, Order, OrderItem, Payment, utcnow


def create_order(user, books):
    """Create a pending order. Prices are taken from the DB, never from the client."""
    currency = current_app.config["DEFAULT_CURRENCY"]
    order = Order(
        reference="BK-" + secrets.token_hex(8).upper(),
        user_id=user.id,
        status="pending",
        total_minor=0,
        currency=currency,
    )
    total = 0
    for book in books:
        price = book.price_minor
        author_share = price * book.author.royalty_rate // 100
        order.items.append(OrderItem(
            book_id=book.id,
            title_snapshot=book.title,
            unit_price_minor=price,
            author_share_minor=author_share,
            platform_share_minor=price - author_share,
        ))
        total += price
    order.total_minor = total
    db.session.add(order)
    db.session.commit()
    return order


def fulfill_order(order, provider_data, provider="paystack"):
    """Mark paid + grant entitlements. Idempotent: safe if webhook and callback both fire.
    Returns True if this call did the fulfilling, False if it was already done / rejected."""
    if order.status == "paid":
        return False

    if provider_data.get("status") != "success":
        return False
    if int(provider_data.get("amount", -1)) != order.total_minor:
        current_app.logger.warning("Amount mismatch on order %s", order.reference)
        return False
    if provider_data.get("currency") and provider_data["currency"] != order.currency:
        current_app.logger.warning("Currency mismatch on order %s", order.reference)
        return False

    try:
        db.session.add(Payment(
            order_id=order.id,
            provider=provider,
            provider_reference=str(provider_data.get("reference", order.reference)),
            status="success",
            amount_minor=order.total_minor,
            raw_payload=json.dumps(provider_data, default=str),
        ))
        order.status = "paid"
        order.paid_at = utcnow()
        for item in order.items:
            exists = Entitlement.query.filter_by(user_id=order.user_id, book_id=item.book_id).first()
            if exists:
                exists.revoked_at = None
            else:
                db.session.add(Entitlement(user_id=order.user_id, book_id=item.book_id, order_item_id=item.id))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()  # another request fulfilled it first
        return False

    send_order_confirmation(order)
    return True


def send_order_confirmation(order):
    if not current_app.config.get("MAIL_SERVER"):
        return
    try:
        msg = Message(
            subject=f"Your order {order.reference} is confirmed",
            recipients=[order.user.email],
            body=render_template("email/order_confirmation.txt", order=order),
        )
        mail.send(msg)
    except Exception:  # never let email problems break fulfillment
        current_app.logger.exception("Failed to send confirmation for %s", order.reference)
