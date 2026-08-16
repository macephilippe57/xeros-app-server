"""XEROS Shopify Digital Auto-Download Module.

Receives Shopify `orders/paid` webhooks, identifies digital products,
generates secure expiring download tokens, sends customer email + Telegram alert.
"""
import base64
import hashlib
import hmac
import json
import os
import sqlite3
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import httpx

router = APIRouter()

# ── Telegram helper (avoids circular import with main.py) ───────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "7894537615")

async def send_telegram_message(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN:
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": text,
                    "parse_mode": "Markdown",
                },
            )
            return resp.status_code == 200
    except Exception:
        return False

# ── Config ──────────────────────────────────────────────────────
SHOPIFY_API_SECRET = os.environ.get("SHOPIFY_API_SECRET", "")
SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN", "")
SHOPIFY_ACCESS_TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
SHOPIFY_API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2026-07")

SERVER_BASE_URL = os.environ.get("XEROS_SERVER_BASE_URL", "https://puny-eagles-make.loca.lt")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "7894537615")

LOCAL_FALLBACK_PDF = Path("/opt/data/agent-etsy/digital_bundle/Raccoon_Planner_Bundle_2026.pdf")
GOOGLE_TOKEN_FILE = Path("/opt/data/google_token.json")
GOOGLE_CLIENT_SECRET_JSON = Path("/opt/data/google_client_secret.json")

DB_PATH = Path(__file__).parent / "delivery_log.db"

# Fernet key derived from SHOPIFY_API_SECRET for deterministic token signing
# This is acceptable because tokens are short-lived and scoped; rotate secret to invalidate all tokens.
_fernet_key_raw = hashlib.sha256(SHOPIFY_API_SECRET.encode()).digest()
FERNET_KEY = base64.urlsafe_b64encode(_fernet_key_raw)
fernet = Fernet(FERNET_KEY)

TOKEN_TTL_SECONDS = int(os.environ.get("DIGITAL_DOWNLOAD_TTL", 7 * 24 * 3600))  # 7 days
MAX_DOWNLOAD_USES = int(os.environ.get("DIGITAL_DOWNLOAD_MAX_USES", 10))


def _init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS delivery_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT NOT NULL,
            order_id TEXT,
            product_id TEXT,
            customer_email TEXT,
            payload TEXT,
            status TEXT,
            details TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


_init_db()


# ── Models ────────────────────────────────────────────────────────
class ShopifyOrder(BaseModel):
    id: int
    email: str | None = None
    line_items: list[dict]
    total_price: str | None = None
    currency: str | None = None


# ── Helpers ───────────────────────────────────────────────────────
def _log(event: str, order_id: str | None = None, product_id: str | None = None,
         customer_email: str | None = None, payload: str | None = None,
         status: str | None = None, details: str | None = None):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO delivery_log (event, order_id, product_id, customer_email, payload, status, details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (event, order_id, product_id, customer_email,
          payload[:2000] if payload else None, status, details[:1000] if details else None))
    conn.commit()
    conn.close()


def _verify_shopify_hmac(body: bytes, signature: str | None) -> bool:
    if not SHOPIFY_API_SECRET or not signature:
        return False
    digest = hmac.new(
        SHOPIFY_API_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={digest}", signature)


def _make_download_token(order_id: int, product_id: int, file_url: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=TOKEN_TTL_SECONDS)
    data = {
        "order_id": order_id,
        "product_id": product_id,
        "file_url": file_url,
        "expires_at": expires_at.isoformat(),
        "uses_left": MAX_DOWNLOAD_USES,
    }
    return fernet.encrypt(json.dumps(data).encode()).decode()


def _decode_token(token: str) -> dict:
    try:
        raw = fernet.decrypt(token.encode(), ttl=TOKEN_TTL_SECONDS)
        data = json.loads(raw.decode())
        if data.get("uses_left", 0) <= 0:
            raise ValueError("No uses left")
        return data
    except InvalidToken as exc:
        raise ValueError("Invalid or expired token") from exc


def _is_digital_product(product: dict) -> tuple[bool, str | None]:
    """Detect digital product via metafield or tags. Returns (is_digital, file_url_or_gid)."""
    tags = {t.lower() for t in product.get("tags", [])}
    if "digital" in tags:
        return True, None
    metafields = product.get("metafields", [])
    for mf in metafields:
        if mf.get("namespace") == "xeros" and mf.get("key") == "digital_download_file":
            value = mf.get("value", "")
            return True, value
    return False, None


def _fetch_product(product_id: int) -> dict:
    base_url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/{SHOPIFY_API_VERSION}"
    headers = {"X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN}
    r = httpx.get(f"{base_url}/products/{product_id}.json", headers=headers, timeout=30)
    r.raise_for_status()
    product = r.json().get("product", {})
    # Fetch metafields separately since REST product endpoint does not include them by default
    try:
        m = httpx.get(f"{base_url}/products/{product_id}/metafields.json", headers=headers, timeout=30)
        m.raise_for_status()
        product["metafields"] = m.json().get("metafields", [])
    except Exception:
        product["metafields"] = []
    return product


def _resolve_file_url(file_reference: str) -> str | None:
    """Resolve Shopify GenericFile GID or direct CDN URL."""
    if not file_reference:
        return None
    if file_reference.startswith("gid://shopify/GenericFile/"):
        file_id = file_reference.split("/")[-1]
        query = """
        query {
          file(id: "gid://shopify/GenericFile/%s") {
            id
            ... on GenericFile { url }
          }
        }
        """ % file_id
        url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
        headers = {
            "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
            "Content-Type": "application/json",
        }
        r = httpx.post(url, headers=headers, json={"query": query}, timeout=30)
        r.raise_for_status()
        data = r.json().get("data", {}).get("file", {})
        return data.get("url")
    if file_reference.startswith("http"):
        return file_reference
    return None


GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
GMAIL_SENDER = os.environ.get("GMAIL_SENDER", "macephilippe57@gmail.com")


def _send_email(to: str, subject: str, body_html: str) -> bool:
    """Send email via Gmail SMTP using app password."""
    return _send_smtp_email(to, subject, body_html)


def _send_smtp_email(to: str, subject: str, body_html: str) -> bool:
    """Send email via Gmail SMTP using app password."""
    if not GMAIL_APP_PASSWORD:
        _log("email_failed", customer_email=to, details="GMAIL_APP_PASSWORD not set")
        return False
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["From"] = f"XerosDesigns <{GMAIL_SENDER}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body_html, "html"))

        password_clean = GMAIL_APP_PASSWORD.replace(" ", "")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(GMAIL_SENDER, password_clean)
            server.sendmail(GMAIL_SENDER, [to], msg.as_string())
        return True
    except Exception as exc:
        _log("email_failed", customer_email=to, details=str(exc)[:500])
        return False


def _send_gmail_email(to: str, subject: str, body_html: str) -> bool:
    """Send email via Gmail API using existing token file."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from google.auth.transport.requests import Request as GoogleRequest
        import google.auth.exceptions

        token_data = json.loads(GOOGLE_TOKEN_FILE.read_text())
        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes", []),
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            token_data["token"] = creds.token
            token_data["expiry"] = creds.expiry.isoformat() if creds.expiry else None
            GOOGLE_TOKEN_FILE.write_text(json.dumps(token_data, indent=2))

        service = build("gmail", "v1", credentials=creds)
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        msg = MIMEMultipart("alternative")
        msg["to"] = to
        msg["subject"] = subject
        msg.attach(MIMEText(body_html, "html"))
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True
    except Exception as exc:
        _log("email_failed", customer_email=to, details=str(exc))
        return False


def _email_body(product_title: str, download_url: str, expiry_text: str) -> str:
    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #4A3728; background: #FFF8E7; padding: 24px;">
      <h2 style="color: #6B5344;">Merci pour votre achat ! 🦝</h2>
      <p>Vous avez acheté <strong>{product_title}</strong> sur XerosDesigns.</p>
      <p>Cliquez sur le lien ci-dessous pour télécharger votre fichier digital :</p>
      <p><a href="{download_url}" style="font-size: 18px; color: #6B5344; font-weight: bold;">⬇ Télécharger maintenant</a></p>
      <p>Ce lien est valable {expiry_text} et limité en nombre de téléchargements.</p>
      <p>Si vous avez des questions, répondez à cet email ou contactez-nous via Telegram.</p>
      <hr/>
      <p style="font-size: 12px; color: #999;">XerosDesigns — Noisseville, France</p>
    </body>
    </html>
    """


# ── Endpoints ─────────────────────────────────────────────────────
@router.post("/webhooks/shopify/order-paid")
async def shopify_order_paid(request: Request, x_shopify_hmac_sha256: str | None = Header(default=None)):
    body = await request.body()
    if not _verify_shopify_hmac(body, x_shopify_hmac_sha256):
        _log("webhook_rejected", status="invalid_hmac")
        raise HTTPException(status_code=401, detail="Invalid HMAC")

    try:
        data = json.loads(body.decode("utf-8"))
    except Exception:
        _log("webhook_rejected", status="bad_json")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    order_id = data.get("id")
    customer_email = data.get("email")
    line_items = data.get("line_items", [])
    currency = data.get("currency", "EUR")
    total_price = data.get("total_price", "0.00")

    _log("order_paid", order_id=str(order_id), customer_email=customer_email,
         payload=json.dumps({"total_price": total_price, "currency": currency}))

    if not customer_email:
        _log("email_skipped", order_id=str(order_id), status="missing_email")

    digital_count = 0
    for item in line_items:
        product_id = item.get("product_id")
        if not product_id:
            continue
        try:
            product = _fetch_product(product_id)
        except Exception as exc:
            _log("product_fetch_failed", order_id=str(order_id), product_id=str(product_id),
                 details=str(exc))
            continue

        is_digital, file_ref = _is_digital_product(product)
        if not is_digital:
            continue

        file_url = _resolve_file_url(file_ref) if file_ref else None
        if not file_url:
            # fallback to local file path
            file_url = str(LOCAL_FALLBACK_PDF) if LOCAL_FALLBACK_PDF.exists() else None

        if not file_url:
            _log("download_failed", order_id=str(order_id), product_id=str(product_id),
                 status="no_file")
            continue

        token = _make_download_token(order_id, product_id, file_url)
        download_url = f"{SERVER_BASE_URL}/download/{urllib.parse.quote(token)}"
        product_title = item.get("name", product.get("title", "Votre produit digital"))
        expiry_text = f"{TOKEN_TTL_SECONDS // 86400} jours"

        if customer_email:
            html = _email_body(product_title, download_url, expiry_text)
            email_ok = _send_email(customer_email, f"Votre téléchargement — {product_title}", html)
            _log("email_sent" if email_ok else "email_failed",
                 order_id=str(order_id), product_id=str(product_id),
                 customer_email=customer_email, status="ok" if email_ok else "failed")
        else:
            email_ok = False

        await send_telegram_message(
            f"🛒 *Vente digital Shopify*\n"
            f"• Commande: `{order_id}`\n"
            f"• Produit: {product_title}\n"
            f"• Client: {customer_email or 'email manquant'}\n"
            f"• Montant: {total_price} {currency}\n"
            f"• Email: {'✅ envoyé' if email_ok else '❌ échoué/manquant'}\n"
            f"• Lien: {download_url}"
        )
        digital_count += 1

    return JSONResponse({
        "status": "ok",
        "order_id": order_id,
        "digital_items_processed": digital_count,
    })


@router.get("/download/{token}")
async def download_file(token: str):
    try:
        data = _decode_token(token)
    except ValueError as exc:
        _log("download_rejected", status=str(exc))
        raise HTTPException(status_code=410, detail=str(exc))

    file_url = data.get("file_url", "")
    order_id = data.get("order_id", "")
    product_id = data.get("product_id", "")

    # Decrement uses
    data["uses_left"] = data.get("uses_left", 0) - 1
    new_token = fernet.encrypt(json.dumps(data).encode()).decode()

    _log("download_served", order_id=str(order_id), product_id=str(product_id),
         status="ok", details=f"uses_left={data['uses_left']}")

    if file_url.startswith("http"):
        # stream from CDN
        try:
            r = httpx.get(file_url, timeout=60, follow_redirects=True)
            r.raise_for_status()
            filename = Path(urllib.parse.urlparse(file_url).path).name or "download.pdf"
            return Response(
                content=r.content,
                media_type="application/octet-stream",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except Exception as exc:
            _log("cdn_download_failed", order_id=str(order_id), product_id=str(product_id),
                 details=str(exc))
            # fallback local
            if LOCAL_FALLBACK_PDF.exists():
                return FileResponse(LOCAL_FALLBACK_PDF, filename=LOCAL_FALLBACK_PDF.name)
            raise HTTPException(status_code=502, detail="File unavailable")

    # local file path
    path = Path(file_url)
    if path.exists():
        return FileResponse(path, filename=path.name)

    _log("download_rejected", order_id=str(order_id), product_id=str(product_id),
         status="file_not_found")
    raise HTTPException(status_code=404, detail="File not found")


@router.get("/webhooks/shopify/delivery-log")
async def delivery_log(limit: int = 50):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM delivery_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return JSONResponse({"log": [dict(r) for r in rows]})
