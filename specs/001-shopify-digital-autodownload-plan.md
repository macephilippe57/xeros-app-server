# Implementation Plan: Shopify Digital Auto-Download Endpoint

**Spec**: `specs/001-shopify-digital-autodownload.md`

**Branch**: `001-shopify-digital-autodownload`

**Created**: 2026-08-16

**Approach**: Extend `xeros-app-server` with a dedicated `digital_downloads` router, SQLite log, secure token generation, and customer email delivery.

## Phase 1 — Foundation

| # | Task | Files | Verification |
|---|---|---|---|
| 1.1 | Create `digital_downloads.py` router module | `digital_downloads.py` | File exists, imports succeed |
| 1.2 | Add SQLite schema for `delivery_log` table | `digital_downloads.py` | Table created on startup, `sqlite3 .schema` shows table |
| 1.3 | Load Shopify secrets from `.env` | `digital_downloads.py` | `SHOPIFY_API_SECRET` and `SHOPIFY_STORE_DOMAIN` available |
| 1.4 | Register router in `main.py` | `main.py` | `app.include_router(digital_downloads_router)` present |

## Phase 2 — Webhook Receiver

| # | Task | Files | Verification |
|---|---|---|---|
| 2.1 | Implement `POST /webhooks/shopify/order-paid` | `digital_downloads.py` | Returns 200 for valid payload |
| 2.2 | Verify Shopify HMAC signature | `digital_downloads.py` | Invalid HMAC returns 401 |
| 2.3 | Parse line items and detect digital products | `digital_downloads.py` | Product with `xeros.digital_download_file` metafield or `digital` tag triggers processing |
| 2.4 | Log every webhook to `delivery_log` | `digital_downloads.py` | Row inserted with `event=order_paid` |

## Phase 3 — Token & Download Endpoint

| # | Task | Files | Verification |
|---|---|---|---|
| 3.1 | Add Fernet/JWT token generator with expiry and max uses | `digital_downloads.py` | Token encodes order_id, product_id, expires_at, uses_left |
| 3.2 | Implement `GET /download/{token}` | `digital_downloads.py` | Valid token streams file, invalid returns 410 |
| 3.3 | Record token usage in `delivery_log` | `digital_downloads.py` | Each download increments counter |
| 3.4 | Support local file fallback if Shopify CDN URL fails | `digital_downloads.py` | Serves local PDF when CDN unavailable |

## Phase 4 — Customer Notification

| # | Task | Files | Verification |
|---|---|---|---|
| 4.1 | Build email body template in French | `templates/download_email.html` (or inline string) | Contains product title, download link, expiry |
| 4.2 | Send email via Gmail API using `/opt/data/google_token.json` | `digital_downloads.py` | Test email delivered to a test address |
| 4.3 | If Gmail unavailable, fallback to Telegram-only notification with manual link | `digital_downloads.py` | Telegram message includes customer email and manual download URL |
| 4.4 | Send Telegram sale notification | `digital_downloads.py` | Message sent to configured chat |

## Phase 5 — Shopify Webhook Registration

| # | Task | Files | Verification |
|---|---|---|---|
| 5.1 | Add script `scripts/register_shopify_webhook.py` | `scripts/register_shopify_webhook.py` | Webhook `orders/paid` registered pointing to server URL |
| 5.2 | Make script idempotent | `scripts/register_shopify_webhook.py` | Re-running updates existing webhook instead of duplicating |

## Phase 6 — Testing & Deployment

| # | Task | Files | Verification |
|---|---|---|---|
| 6.1 | Add `tests/test_digital_downloads.py` with mocked Shopify payload | `tests/test_digital_downloads.py` | `pytest` passes |
| 6.2 | Run health check and manual curl test | server | `POST /webhooks/shopify/order-paid` returns 200 for valid HMAC |
| 6.3 | Restart server via `start.sh` | `start.sh` | Service starts, router loaded |
| 6.4 | Register webhook with Shopify | `scripts/register_shopify_webhook.py` | Webhook visible in Shopify admin |

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Google OAuth token not refreshed yet | Use local PDF fallback + Telegram notification until OAuth is approved |
| Shopify webhook HMAC tricky | Use exact raw body bytes, not parsed JSON |
| Email deliverability | Use Gmail API with existing token or plaintext email via Python `smtplib` as fallback |

## Dependencies

- `cryptography` (Fernet tokens) — install if missing
- `google-auth`, `google-auth-oauthlib`, `google-api-python-client` for Gmail API
- Existing FastAPI/httpx stack

## Definition of Done

- `POST /webhooks/shopify/order-paid` receives and validates Shopify webhooks
- Digital products are auto-detected
- Customer receives an email with a unique download link
- Telegram sale notification is sent
- `GET /download/{token}` serves the file securely with expiry
- Tests pass and server is redeployed
