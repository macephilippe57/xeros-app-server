# Feature Specification: Shopify Digital Auto-Download Endpoint

**Feature Branch**: `001-shopify-digital-autodownload`

**Created**: 2026-08-16

**Status**: Draft

**Input**: User description: "Endpoint Shopify qui envoie automatiquement le fichier digital après achat"

## User Scenarios & Testing

### User Story 1 - Customer Receives File After Purchase (Priority: P1)

A customer buys the Raccoon Planner Bundle 2026 on Shopify. Immediately after payment confirmation, the system sends an email or message containing a secure, unique download link to the purchased PDF and wall art files. No manual action is required from the seller.

**Why this priority**: This is the core value proposition of a digital product. Without auto-delivery, the product is not truly autopilot and requires manual intervention for every sale.

**Independent Test**: Place a test order for the digital product; verify that an email with a working download link is received within 60 seconds of order confirmation.

**Acceptance Scenarios**:

1. **Given** a Shopify order for a product tagged as digital is paid, **When** the order/paid webhook fires, **Then** the customer receives an email with a unique download link.
2. **Given** the same product has a metafield `xeros.digital_download_file` set, **When** the webhook is processed, **Then** the linked file from Shopify Files API is attached or linked in the customer message.

---

### User Story 2 - Seller Gets Telegram Confirmation (Priority: P2)

Philippe receives a short Telegram notification for each digital sale, including order ID, product, customer email, and revenue.

**Why this priority**: Keeps the seller informed without logging into Shopify admin. Aligns with existing Telegram webhook infrastructure.

**Independent Test**: Trigger a test webhook and verify a message is delivered to the configured Telegram chat.

**Acceptance Scenarios**:

1. **Given** a digital order is processed, **When** the download email is sent, **Then** a Telegram notification is also sent to the configured chat.

---

### User Story 3 - Download Link Expires Securely (Priority: P3)

Each generated download link is unique per order, time-limited (e.g., 7 days or 10 downloads), and cannot be reused by another customer.

**Why this priority**: Reduces piracy risk and unauthorized sharing of digital assets. Standard practice for digital goods.

**Independent Test**: Generate a download token, use it once, wait for expiry, and confirm reuse is rejected.

**Acceptance Scenarios**:

1. **Given** a valid download token, **When** used within expiry window, **Then** the file is served.
2. **Given** an expired or invalid token, **When** accessed, **Then** the system returns 410/403 and logs the attempt.

---

### Edge Cases

- What happens when the customer email is missing or invalid? → Log + Telegram alert, no crash.
- What happens if the Shopify webhook is replayed? → Idempotent processing; do not resend duplicate emails.
- What happens if the file is missing from Shopify CDN? → Fallback to local file path if available; otherwise alert seller.
- What happens if the order contains both physical and digital products? → Auto-download only for digital line items.

## Requirements

### Functional Requirements

- **FR-001**: System MUST expose a `POST /webhooks/shopify/order-paid` endpoint to receive Shopify `orders/paid` webhooks.
- **FR-002**: System MUST verify the webhook HMAC signature using `SHOPIFY_API_SECRET`.
- **FR-003**: System MUST identify line items whose product has the `xeros.digital_download_file` metafield or a `digital` tag.
- **FR-004**: System MUST generate a unique, signed, expiring download URL for each eligible line item.
- **FR-005**: System MUST send an email to the customer with the product title, download link, and expiry details.
- **FR-006**: System MUST send a Telegram notification to the configured chat summarizing the sale.
- **FR-007**: System MUST expose a `GET /download/{token}` endpoint that validates the token, records usage, and serves the file.
- **FR-008**: System MUST store webhook and delivery events in a local SQLite log for audit and debugging.

### Key Entities

- **OrderWebhook**: Shopify payload containing order id, email, line_items, total_price.
- **DigitalProduct**: Shopify product with metafield `xeros.digital_download_file` pointing to a GenericFile GID or CDN URL.
- **DownloadToken**: Signed JWT/fernet blob with order_id, product_id, expires_at, max_uses.
- **DeliveryLog**: SQLite row recording webhook received, email sent, Telegram sent, download events.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A paid test order results in a customer email within 60 seconds in 5/5 attempts.
- **SC-002**: The Telegram notification is delivered within 10 seconds of webhook processing.
- **SC-003**: An invalid or expired download token returns an HTTP error in under 100ms.
- **SC-004**: Replay of the same webhook payload does not create duplicate emails.

## Assumptions

- Shopify webhook secret and store domain are available in `/opt/data/.env`.
- The Telegram chat ID and bot token are already configured in the existing FastAPI server.
- Email sending can use the Google Gmail API once OAuth is refreshed, or fallback to a simple SMTP/sendgrid-free approach.
- The Shopify Files API CDN URL for the digital file is publicly accessible; if not, a local copy of the PDF is available at `/opt/data/agent-etsy/digital_bundle/Raccoon_Planner_Bundle_2026.pdf`.
