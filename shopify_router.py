"""Routes OAuth et Admin API Shopify pour XEROS."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/shopify", tags=["shopify"])

SHOPIFY_API_KEY = os.environ.get("SHOPIFY_API_KEY", "")
SHOPIFY_API_SECRET = os.environ.get("SHOPIFY_API_SECRET", "")
SHOPIFY_SCOPES = os.environ.get(
    "SHOPIFY_SCOPES",
    "read_products,write_products,read_inventory,write_inventory,read_orders,write_orders,read_customers,write_customers,read_content,write_content,read_themes,write_themes,read_script_tags,write_script_tags,read_fulfillments,write_fulfillments",
)
PUBLIC_TUNNEL = os.environ.get("XEROS_SERVER_BASE_URL", "https://puny-eagles-make.loca.lt")


def _shopify_token_url(shop: str) -> str:
    return f"https://{shop}/admin/oauth/access_token"


@router.get("/auth")
async def shopify_auth(shop: str = Query(default="jsygq1-8a.myshopify.com")):
    """Redirige vers Shopify pour autoriser l'app xeros-agent."""
    if not SHOPIFY_API_KEY:
        raise HTTPException(status_code=500, detail="SHOPIFY_API_KEY non configuré")

    redirect_uri = f"{PUBLIC_TUNNEL}/shopify/callback"
    scopes = SHOPIFY_SCOPES.replace(",", "+")
    auth_url = (
        f"https://{shop}/admin/oauth/authorize?"
        f"client_id={SHOPIFY_API_KEY}"
        f"&scope={scopes}"
        f"&redirect_uri={redirect_uri}"
    )
    return RedirectResponse(auth_url)


@router.post("/webhook")
async def shopify_webhook(request: Request):
    """Reçoit les webhooks Shopify et notifie Telegram."""
    payload = await request.json()
    topic = request.headers.get("X-Shopify-Topic", "unknown")
    shop = request.headers.get("X-Shopify-Shop-Domain", "unknown")

    # Format message
    order_id = payload.get("id", "")
    order_name = payload.get("name", "")
    total = payload.get("current_total_price", payload.get("total_price", "?"))
    customer = payload.get("customer", {})
    customer_email = customer.get("email", "inconnu")
    line_items = payload.get("line_items", [])
    items_text = "\n".join(
        f"- {item.get('quantity', 1)}x {item.get('title', 'Produit')}" for item in line_items[:5]
    ) or "Produit non détaillé"

    msg = f"""🛒 *Shopify {topic}*

Boutique: `{shop}`
Commande: `{order_name}`
Client: `{customer_email}`
Total: *{total} €*

Articles:
{items_text}
"""

    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    telegram_chat = os.environ.get("TELEGRAM_CHAT_ID", "7894537615")
    if telegram_token and telegram_chat:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                await client.post(
                    f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                    json={"chat_id": telegram_chat, "text": msg, "parse_mode": "Markdown"},
                )
        except Exception as exc:
            print(f"[TELEGRAM ERROR] {exc}")

    print(f"[SHOPIFY WEBHOOK] {shop} {topic}: {payload}")
    return {"received": True, "topic": topic}


async def _telegram_send(text: str):
    """Helper pour envoyer un message Telegram."""
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    telegram_chat = os.environ.get("TELEGRAM_CHAT_ID", "7894537615")
    if not telegram_token or not telegram_chat:
        return
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            await client.post(
                f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                json={"chat_id": telegram_chat, "text": text, "parse_mode": "Markdown"},
            )
    except Exception as exc:
        print(f"[TELEGRAM ERROR] {exc}")


@router.post("/set-token")
async def shopify_set_token(request: Request):
    """Recevoir manuellement un Admin API access token (shpat_ ou atkn_)."""
    body = await request.json()
    token = body.get("token", "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="token manquant")

    env_path = Path("/opt/data/.env")
    lines = []
    found = False
    if env_path.exists():
        for line in env_path.read_text().splitlines(keepends=True):
            if line.startswith("SHOPIFY_ACCESS_TOKEN="):
                lines.append(f"SHOPIFY_ACCESS_TOKEN={token}\n")
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f"SHOPIFY_ACCESS_TOKEN={token}\n")
    env_path.write_text("".join(lines))

    # Test immédiat
    try:
        import httpx
        resp = httpx.post(
            f"https://jsygq1-8a.myshopify.com/admin/api/2026-07/graphql.json",
            json={"query": "{ shop { name } }"},
            headers={"Content-Type": "application/json", "X-Shopify-Access-Token": token},
            timeout=10,
        )
        if resp.status_code == 200:
            shop_name = resp.json().get("data", {}).get("shop", {}).get("name", "inconnu")
            return {"status": "ok", "shop": shop_name, "token_prefix": token[:15]}
        else:
            return {"status": "stored", "warning": "token sauvegardé mais connexion échoue", "http": resp.status_code}
    except Exception as e:
        return {"status": "stored", "warning": str(e)}


@router.get("/callback")
async def shopify_callback(
    request: Request,
    code: str | None = Query(default=None),
    id_token: str | None = Query(default=None),
    shop: str | None = Query(default=None),
):
    """Callback OAuth Shopify : échange le code contre un token d'accès et le sauvegarde.
    En mode embedded, reçoit un id_token ; affiche une page d'instructions."""
    if id_token and not code:
        # Mode embedded : pas d'échange automatique possible sans clé publique Shopify.
        return {
            "status": "embedded_callback",
            "shop": shop,
            "message": "L'app est installée en mode embedded. Veuillez générer le Admin API access token dans Shopify et l'envoyer via POST /shopify/set-token",
            "set_token_url": f"{PUBLIC_TUNNEL}/shopify/set-token",
        }

    if not code or not shop:
        raise HTTPException(status_code=400, detail="code ou shop manquant")

    if not SHOPIFY_API_KEY or not SHOPIFY_API_SECRET:
        raise HTTPException(status_code=500, detail="Credentials Shopify manquants")

    redirect_uri = f"{PUBLIC_TUNNEL}/shopify/callback"
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            _shopify_token_url(shop),
            data={
                "client_id": SHOPIFY_API_KEY,
                "client_secret": SHOPIFY_API_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Échec échange token: {resp.text[:500]}")

    data = resp.json()
    access_token = data.get("access_token")
    scope = data.get("scope")

    if access_token:
        env_path = Path("/opt/data/.env")
        lines = []
        found = False
        if env_path.exists():
            for line in env_path.read_text().splitlines(keepends=True):
                if line.startswith("SHOPIFY_ACCESS_TOKEN="):
                    lines.append(f"SHOPIFY_ACCESS_TOKEN={access_token}\n")
                    found = True
                else:
                    lines.append(line)
        if not found:
            lines.append(f"SHOPIFY_ACCESS_TOKEN={access_token}\n")
        env_path.write_text("".join(lines))

        try:
            from main import send_telegram_message
            await send_telegram_message(f"🔐 Shopify token reçu pour {shop}\nPréfixe: {access_token[:10]}...\nScopes: {scope}")
        except Exception:
            pass

    return {
        "status": "ok",
        "shop": shop,
        "scope": scope,
        "access_token_prefix": access_token[:15] if access_token else None,
        "message": "Token sauvegardé dans /opt/data/.env",
    }


@router.get("/products")
async def shopify_products(shop: str = Query(default="jsygq1-8a.myshopify.com"), limit: int = 10):
    """Liste les produits via l'Admin REST API (fallback rapide)."""
    token = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
    if not token:
        raise HTTPException(status_code=401, detail="SHOPIFY_ACCESS_TOKEN manquant")

    url = f"https://{shop}/admin/api/2026-07/products.json?limit={limit}"
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            url,
            headers={"X-Shopify-Access-Token": token},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.get("/shop")
async def shopify_shop_info(shop: str = Query(default="jsygq1-8a.myshopify.com")):
    """Infos basiques du shop."""
    token = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
    if not token:
        raise HTTPException(status_code=401, detail="SHOPIFY_ACCESS_TOKEN manquant")

    url = f"https://{shop}/admin/api/2026-07/shop.json"
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, headers={"X-Shopify-Access-Token": token})
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()
