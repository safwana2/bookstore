"""Run with:  pip install pytest  &&  pytest -q
Covers the money path: register -> add to cart -> checkout -> entitlement -> private download."""
import io

import pytest

from app import create_app
from app.extensions import db
from app.models import AuthorProfile, Book, User
from config import TestConfig


@pytest.fixture()
def app(tmp_path):
    class Cfg(TestConfig):
        PRIVATE_STORAGE = tmp_path / "private"
        COVER_FOLDER = tmp_path / "covers"

    app = create_app(Cfg)
    with app.app_context():
        db.create_all()
        author = AuthorProfile(display_name="Test Author", slug="test-author", royalty_rate=70)
        db.session.add(author)
        db.session.flush()
        (tmp_path / "private" / "books").mkdir(parents=True, exist_ok=True)
        (tmp_path / "private" / "books" / "abc.pdf").write_bytes(b"%PDF-1.4 fake")
        db.session.add(Book(title="Paid Book", slug="paid-book", price_minor=5000, currency="GHS",
                            author_id=author.id, status="published", file_filename="abc.pdf"))
        db.session.commit()
        yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, email="a@example.com"):
    return client.post("/auth/register", data={"name": "Ama", "email": email, "password": "password123"},
                       follow_redirects=True)


def test_cannot_download_without_buying(client):
    register(client)
    assert client.get("/account/download/1").status_code == 403


def test_full_purchase_and_download(client, app):
    register(client)
    client.post("/cart/add/1")
    r = client.post("/cart/checkout", follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="a@example.com").one()
        assert user.owns(1)
        from app.models import OrderItem
        item = OrderItem.query.one()
        assert item.author_share_minor == 3500 and item.platform_share_minor == 1500
    d = client.get("/account/download/1")
    assert d.status_code == 200 and d.data.startswith(b"%PDF")


def test_fulfillment_is_idempotent(app):
    from app.services.orders import create_order, fulfill_order
    with app.app_context():
        author = AuthorProfile.query.first()
        user = User(email="b@example.com", name="B", role="customer")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
        order = create_order(user, [Book.query.first()])
        data = {"status": "success", "amount": order.total_minor, "currency": "GHS", "reference": order.reference}
        assert fulfill_order(order, data) is True
        assert fulfill_order(order, data) is False  # second call does nothing


def test_wrong_amount_is_rejected(app):
    from app.services.orders import create_order, fulfill_order
    with app.app_context():
        user = User(email="c@example.com", name="C", role="customer")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
        order = create_order(user, [Book.query.first()])
        bad = {"status": "success", "amount": 100, "currency": "GHS", "reference": order.reference}
        assert fulfill_order(order, bad) is False
        assert order.status == "pending"


def test_admin_area_blocked_for_customers(client):
    register(client)
    assert client.get("/admin/").status_code == 403


def test_webhook_rejects_bad_signature(client):
    r = client.post("/payments/webhook", data=b"{}", headers={"x-paystack-signature": "nope"})
    assert r.status_code == 401
