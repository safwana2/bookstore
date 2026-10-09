# Flask Book Store (digital books)

Sell PDF/ePub books online: customers browse, buy with **Paystack**, then download from a private library.
Built as a modular Flask monolith, designed so a **publisher/author marketplace** can be added later without redesigning the database.

## 1. Run it on Windows (PyCharm)

1. Open this folder in PyCharm. Create a virtual environment (Python 3.10+).
2. In the PyCharm terminal:
   ```
   pip install -r requirements.txt
   copy .env.example .env
   ```
3. Edit `.env`: set `SECRET_KEY`, your `PAYSTACK_SECRET_KEY`, and (for first tests) `FAKE_PAYMENTS=1`.
4. Create the database and your admin:
   ```
   set FLASK_APP=run.py
   flask init-db
   flask create-admin you@example.com --name "Your Name"
   flask seed-categories
   ```
   (PowerShell: use `$env:FLASK_APP="run.py"` instead of `set`.)
5. Start the server: `python run.py`  -> http://127.0.0.1:5000
6. Log in, open **Admin**, add your book (cover, PDF/ePub, optional preview PDF), set status to **published**.

> `FAKE_PAYMENTS=1` only works when the app runs in debug mode (`python run.py`). It marks orders as paid instantly so you can test the whole flow. Turn it off to use real Paystack.

## 2. Paystack setup

- Put your **secret key** in `.env` (`sk_test_...` while testing).
- In the Paystack dashboard -> Settings -> API Keys & Webhooks, set the **Webhook URL** to `https://YOUR-DOMAIN/payments/webhook`.
  (For local testing use a tunnel such as ngrok. The callback page also verifies payments directly, so the flow works even without the webhook.)
- Default currency is `GHS` (change `DEFAULT_CURRENCY`). Make sure that currency is enabled on your Paystack account.
- Amounts are stored as integers in pesewas/kobo; never floats.

## 3. How the important parts work

| Concern | Where |
|---|---|
| Models (users, books, orders, entitlements, audit log) | `app/models/` |
| Payment init / verify / webhook signature | `app/services/payments.py`, `app/blueprints/payments/` |
| Fulfillment (idempotent, checks amount + currency) | `app/services/orders.py` |
| Private downloads (entitlement check) | `app/blueprints/account/routes.py` -> `download` |
| Admin (books, authors, categories, orders, refunds, customers, audit) | `app/blueprints/admin/` |
| Marketplace hooks | `AuthorProfile.royalty_rate`, `OrderItem.author_share_minor / platform_share_minor`, `Book.status` workflow, `app/blueprints/author/` (stub) |

Security already included: hashed passwords, CSRF on all forms, login rate limiting, admin-only blueprint guard, upload type checks + random file names, books stored outside `/static`, webhook HMAC check, server-side prices, audit log.

## 4. Tests

```
pip install pytest
pytest -q
```

## 5. What is NOT built yet (next steps, in order)

1. **Email verification + password reset** (`is_verified` field exists; needs tokens via `itsdangerous` + Flask-Mail).
2. **Coupons/discounts at checkout** (`Coupon` model exists; needs a code box in the cart and a discount line on `Order`).
3. **Paystack automated refunds** (refunds are currently recorded + access revoked; send the money from the Paystack dashboard).
4. **Admin extras:** edit/delete authors & categories, multiple admin roles (support/finance/content), site-content editor, analytics charts, promotions.
5. **Legal pages:** replace the placeholder text in Terms / Privacy / Refunds (have them reviewed).
6. **Production:** PostgreSQL (`DATABASE_URL`), `gunicorn`, HTTPS + `SESSION_COOKIE_SECURE=1`, S3-compatible storage for book files, Redis for rate limits/background email (Celery/RQ), backups.
7. **SEO:** sitemap.xml, robots.txt, Open Graph tags, JSON-LD Book schema.
8. **Marketplace (v3):** author dashboard, submit-for-review workflow, royalty reports and payouts.
9. **Schema changes later:** switch from `flask init-db` to migrations (`flask db init`, `flask db migrate`, `flask db upgrade`).

## 6. Project layout

```
bookstore/
  app/
    __init__.py        app factory + CLI (init-db, create-admin, seed-categories)
    extensions.py      db, login, csrf, mail, limiter
    utils.py           slugify, money helpers, admin_required
    models/            user, catalog, commerce
    services/          orders, payments, files, audit
    blueprints/        public, auth, account, cart, payments, admin, author
    templates/  static/
  private_storage/     books + previews (NOT web-accessible)
  tests/
  config.py  run.py  requirements.txt  .env.example
```
