import json

from flask import current_app, flash, redirect, request, session, url_for
from flask_login import login_required

from ...extensions import csrf
from ...models import Order
from ...services import payments
from ...services.orders import fulfill_order
from . import bp


@bp.route("/callback")
@login_required
def callback():
    """Customer returns from Paystack. We do NOT trust the redirect: we ask Paystack."""
    reference = request.args.get("reference") or request.args.get("trxref", "")
    order = Order.query.filter_by(reference=reference).first()
    if not order:
        flash("We could not find that order.", "danger")
        return redirect(url_for("cart.view"))
    try:
        data = payments.verify_transaction(reference)
    except payments.PaymentError as exc:
        flash(f"{exc} If you were charged, your books will appear in your library shortly.", "warning")
        return redirect(url_for("account.orders"))
    if fulfill_order(order, data) or order.status == "paid":
        session["cart"] = []
        flash("Payment successful — your books are ready!", "success")
        return redirect(url_for("account.library"))
    flash("Payment was not completed.", "danger")
    return redirect(url_for("cart.view"))


@bp.route("/webhook", methods=["POST"])
@csrf.exempt  # called by Paystack servers, authenticated by HMAC signature instead of CSRF token
def webhook():
    raw = request.get_data()
    if not payments.valid_webhook_signature(raw, request.headers.get("x-paystack-signature", "")):
        return "invalid signature", 401
    event = json.loads(raw or b"{}")
    if event.get("event") == "charge.success":
        data = event.get("data", {})
        order = Order.query.filter_by(reference=data.get("reference")).first()
        if order:
            fulfill_order(order, data)
        else:
            current_app.logger.warning("Webhook for unknown reference %s", data.get("reference"))
    return "ok", 200  # always 200 for valid signatures so Paystack stops retrying
