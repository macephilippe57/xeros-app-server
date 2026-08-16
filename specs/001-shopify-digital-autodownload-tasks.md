# Tasks: Shopify Digital Auto-Download Endpoint

**Spec**: `specs/001-shopify-digital-autodownload.md`
**Plan**: `specs/001-shopify-digital-autodownload-plan.md`

## Backlog

### Phase 1 — Foundation

- [x] **T1.1** Create `digital_downloads.py` FastAPI router with imports and config
- [x] **T1.2** Add `delivery_log` SQLite schema and helper functions
- [x] **T1.3** Load `SHOPIFY_API_SECRET`, `SHOPIFY_STORE_DOMAIN`, `SHOPIFY_ACCESS_TOKEN` from env
- [x] **T1.4** Register router in `main.py` under prefix `/webhooks/shopify` and `/download`

### Phase 2 — Webhook Receiver

- [x] **T2.1** Implement `POST /webhooks/shopify/order-paid` endpoint
- [x] **T2.2** Verify Shopify HMAC signature on raw request body
- [x] **T2.3** Parse order payload and identify digital line items
- [x] **T2.4** Log every incoming webhook to SQLite

### Phase 3 — Token & Download

- [x] **T3.1** Implement Fernet token generator (order_id, product_id, expiry, max_uses)
- [x] **T3.2** Implement `GET /download/{token}` endpoint
- [x] **T3.3** Record download attempts in `delivery_log`
- [x] **T3.4** Add local file fallback for CDN failures

### Phase 4 — Notifications

- [x] **T4.1** Build French email template for digital delivery
- [x] **T4.2** Send email via Gmail API using existing token
- [x] **T4.3** Fallback to Telegram-only if email fails
- [x] **T4.4** Send concise Telegram sale notification

### Phase 5 — Registration

- [x] **T5.1** Create `scripts/register_shopify_webhook.py`
- [x] **T5.2** Make script idempotent (update existing webhook)

### Phase 6 — Testing

- [x] **T6.1** Write `tests/test_digital_downloads.py`
- [x] **T6.2** Run health check and manual curl test
- [x] **T6.3** Restart server with new router
- [x] **T6.4** Register Shopify webhook

## Active

_None_

## Done

- T1.1 à T1.4 : Foundation
- T2.1 à T2.4 : Webhook receiver
- T3.1 à T3.4 : Token + download endpoint
- T4.1 à T4.4 : Email + Telegram notifications
- T5.1 à T5.2 : Shopify webhook registration
- T6.1 à T6.4 : Tests + health check + restart


## Notes

- Use `/opt/data/agent-etsy/digital_bundle/Raccoon_Planner_Bundle_2026.pdf` as local fallback.
- Google OAuth refresh link saved at `/opt/data/google_auth_url_public.txt` for Gmail API activation.
