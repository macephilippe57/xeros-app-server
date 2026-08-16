#!/usr/bin/env python3
"""Register Shopify orders/paid webhook for digital auto-delivery.
Idempotent: updates existing webhook if address already registered.
"""
import os
import sys

import httpx

SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN", "")
SHOPIFY_ACCESS_TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
SHOPIFY_API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2026-07")
SERVER_BASE_URL = os.environ.get("XEROS_SERVER_BASE_URL", "https://puny-eagles-make.loca.lt")
WEBHOOK_TOPIC = "orders/paid"
WEBHOOK_ADDRESS = f"{SERVER_BASE_URL}/webhooks/shopify/order-paid"


def list_webhooks():
    url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/{SHOPIFY_API_VERSION}/webhooks.json"
    headers = {"X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN}
    r = httpx.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json().get("webhooks", [])


def create_webhook():
    url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/{SHOPIFY_API_VERSION}/webhooks.json"
    headers = {"X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN, "Content-Type": "application/json"}
    payload = {"webhook": {"topic": WEBHOOK_TOPIC, "address": WEBHOOK_ADDRESS, "format": "json"}}
    r = httpx.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return r.json().get("webhook", {})


def update_webhook(webhook_id: int):
    url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/{SHOPIFY_API_VERSION}/webhooks/{webhook_id}.json"
    headers = {"X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN, "Content-Type": "application/json"}
    payload = {"webhook": {"id": webhook_id, "address": WEBHOOK_ADDRESS}}
    r = httpx.put(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return r.json().get("webhook", {})


def main():
    if not all([SHOPIFY_STORE_DOMAIN, SHOPIFY_ACCESS_TOKEN]):
        print("ERROR: SHOPIFY_STORE_DOMAIN and SHOPIFY_ACCESS_TOKEN required", file=sys.stderr)
        sys.exit(1)

    print(f"Target webhook: {WEBHOOK_TOPIC} -> {WEBHOOK_ADDRESS}")
    existing = [w for w in list_webhooks() if w.get("topic") == WEBHOOK_TOPIC]

    if existing:
        w = existing[0]
        wid = w["id"]
        current_addr = w.get("address", "")
        print(f"Found existing webhook #{wid} -> {current_addr}")
        if current_addr == WEBHOOK_ADDRESS:
            print("Already up to date. No change.")
            return
        updated = update_webhook(wid)
        print(f"Updated webhook #{updated.get('id')} -> {updated.get('address')}")
    else:
        created = create_webhook()
        print(f"Created webhook #{created.get('id')} -> {created.get('address')}")


if __name__ == "__main__":
    main()
