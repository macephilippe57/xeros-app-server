#!/usr/bin/env python3
"""Génère 21 pins Canva-ready pour la série 7 Jours Etsy IA.

Sortie : JSON avec text overlays + prompt Pollinations AI pour chaque pin.
"""
import json
import urllib.parse
from pathlib import Path

OUT_DIR = Path("/opt/data/xeros-app-server/static/landing/7jours-content")
OUT_DIR.mkdir(parents=True, exist_ok=True)

DIM = {"width": 1000, "height": 1500}
BASE_PROMPT = "Pinterest pin design, clean modern aesthetic, bold typography, dark gradient background, centered visual, minimalist, high contrast, no small text, professional e-commerce look"

PINS = [
    # Hero pins
    {"name": "hero_lead_magnet", "title": "7 JOURS ETSY IA", "subtitle": "Guide gratuit pour lancer une boutique à 6 chiffres", "visual": "raccoon reading a tablet with Etsy shop analytics, cozy cottagecore office", "cta": "TÉLÉCHARGER GRATUITEMENT", "color": "pink"},
    {"name": "hero_checklist", "title": "CHECKLIST 7 JOURS", "subtitle": "Une action par jour. Pas plus.", "visual": "checklist floating with raccoon checking boxes, cozy aesthetic", "cta": "RECEVOIR LA CHECKLIST", "color": "green"},
    {"name": "hero_prompts", "title": "50 PROMPTS IA", "subtitle": "Pour designs, titres, descriptions, Pinterest", "visual": "futuristic AI brain generating t-shirt designs, neon accents", "cta": "RÉCUPÉRER LES PROMPTS", "color": "purple"},

    # Day pins
    {"name": "day1_fondations", "title": "JOUR 1 : FONDATIONS", "subtitle": "Niche, logo, identité, profil Etsy", "visual": "raccoon architect building a shop foundation, cute illustration", "cta": "COMMENCER JOUR 1", "color": "blue"},
    {"name": "day2_design", "title": "JOUR 2 : DESIGN IA", "subtitle": "Générer 10 designs en 1 heure", "visual": "raccoon using AI image generator, screens and sparkles", "cta": "VOIR LA MÉTHODE", "color": "orange"},
    {"name": "day3_seo", "title": "JOUR 3 : SEO ETSY", "subtitle": "Titres, tags, descriptions qui convertissent", "visual": "raccoon detective with magnifying glass over Etsy search", "cta": "BOOSTER SON SEO", "color": "teal"},
    {"name": "day4_lancement", "title": "JOUR 4 : LANCEMENT", "subtitle": "Publier 10 listings actives", "visual": "raccoon launching rockets made of t-shirts, celebration", "cta": "LANCER MA BOUTIQUE", "color": "red"},
    {"name": "day5_pinterest", "title": "JOUR 5 : PINTEREST", "subtitle": "Trafic gratuit automatisé", "visual": "raccoon pinning ideas on giant Pinterest board", "cta": "AUTOMATISER PINTEREST", "color": "pink"},
    {"name": "day6_conversion", "title": "JOUR 6 : CONVERSION", "subtitle": "Bundles, promos, personnalisation", "visual": "raccoon shop owner with price tags and gift bundles", "cta": "AUGMENTER LES VENTES", "color": "gold"},
    {"name": "day7_scale", "title": "JOUR 7 : SCALE", "subtitle": "Passez en mode système IA", "visual": "raccoon CEO at command center with multiple dashboards", "cta": "SCALER AVEC L’IA", "color": "indigo"},

    # Result / social proof pins
    {"name": "result_30days", "title": "OBJECTIF 30 JOURS", "subtitle": "500 vues · 25 favoris · 3-5 ventes", "visual": "raccoon celebrating with trophy and growth chart", "cta": "JE REJOINS LE DÉFI", "color": "emerald"},
    {"name": "result_no_stock", "title": "SANS STOCK", "subtitle": "Print-on-demand + IA = boutique 100% automatisable", "visual": "raccoon in warehouse with floating packages and print machines", "cta": "DÉCOUVRIR LE SYSTÈME", "color": "cyan"},
    {"name": "result_free", "title": "GRATUIT", "subtitle": "40 pages + checklist + 50 prompts IA", "visual": "raccoon offering a gift box labeled FREE, cheerful", "cta": "TÉLÉCHARGER", "color": "rose"},

    # Tool affiliate pins
    {"name": "tool_shopify", "title": "SHOPIFY 3 JOURS GRATUITS", "subtitle": "Puis 1€/mois pendant 3 mois", "visual": "Shopify logo style with raccoon shopping bag, clean e-commerce", "cta": "CRÉER MA BOUTIQUE", "color": "green", "url": "http://shopify.pxf.io/xLARjk"},
    {"name": "tool_autods", "title": "AUTODS 30 JOURS POUR 1€", "subtitle": "Automatisez votre dropshipping", "visual": "AutoDS dashboard with raccoon robot automating tasks", "cta": "ESSAYER AUTODS", "color": "blue", "url": "https://www.autods.com/0bc0"},
    {"name": "tool_legalplace", "title": "MICRO-ENTREPRISE -25%", "subtitle": "Code THEO25 chez LegalPlace", "visual": "raccoon signing documents with stamp, professional", "cta": "CRÉER MON ENTREPRISE", "color": "navy", "url": "https://c3po.link/Qds9fQBf3w"},
    {"name": "tool_arcads", "title": "ARCADS UGC VIDÉO", "subtitle": "Créez des vidéos pub avec l’IA", "visual": "raccoon filming video ad with AI camera, studio lights", "cta": "TESTER ARCADS", "color": "violet", "url": "https://arcads.ai/?via=fg"},
    {"name": "tool_smartbundle", "title": "SMARTBUNDLE -30%", "subtitle": "À vie avec le code THEO", "visual": "raccoon bundling products with discount tag, shopping theme", "cta": "ACTIVER LA RÉDUCTION", "color": "orange", "url": "https://app-bundle.arkanse.fr/public/affiliation?fpr=fg"},

    # App / Telegram CTA pins
    {"name": "app_android", "title": "XEROS ANDROID", "subtitle": "Assistant IA vocal pour Etsy & Shopify", "visual": "raccoon holding smartphone with XEROS app interface, futuristic", "cta": "TÉLÉCHARGER L’APK", "color": "slate", "url": "https://deep-foxes-hope.loca.lt/static/xeros-app-debug.apk"},
    {"name": "telegram_bot", "title": "XEROS TELEGRAM", "subtitle": "Commandez votre boutique depuis Telegram", "visual": "raccoon using Telegram chat bubbles, automation icons", "cta": "AJOUTER @xeros_jarvis_bot", "color": "sky", "url": "https://t.me/xeros_jarvis_bot"},
]


def pollinations_url(visual: str, color: str) -> str:
    prompt = f"Pinterest pin vertical design, {color} color theme, {visual}, {BASE_PROMPT}"
    encoded = urllib.parse.quote(prompt)
    return f"https://image.pollinations.ai/prompt/{encoded}?width={DIM['width']}&height={DIM['height']}&nologo=true&seed=42"


def main():
    output = []
    for pin in PINS:
        entry = {
            "name": pin["name"],
            "dimensions": DIM,
            "text_layers": {
                "title": {"text": pin["title"], "font": "Bold Sans", "size": 72, "color": "#ffffff", "y": 120},
                "subtitle": {"text": pin["subtitle"], "font": "Regular Sans", "size": 36, "color": "#e4e4e7", "y": 240},
                "cta": {"text": pin["cta"], "font": "Bold Sans", "size": 44, "color": "#ffffff", "y": 1320, "bg": "#ff4d6d"},
            },
            "image_prompt": pollinations_url(pin["visual"], pin["color"]),
            "affiliate_url": pin.get("url", "https://deep-foxes-hope.loca.lt/7jours-etsy-ia"),
            "board_suggestions": ["Etsy Tips", "AI Business", "Print on Demand", "Side Hustle 2026", "Etsy Marketing"],
        }
        output.append(entry)

    out_file = OUT_DIR / "pins_7days.json"
    out_file.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    # Download first 3 pins as examples
    import requests
    examples_dir = OUT_DIR / "pin_examples"
    examples_dir.mkdir(exist_ok=True)
    for i, pin in enumerate(output[:3], 1):
        try:
            r = requests.get(pin["image_prompt"], timeout=120)
            if r.status_code == 200 and len(r.content) > 5000:
                (examples_dir / f"{pin['name']}.png").write_bytes(r.content)
                print(f"Downloaded {pin['name']} ({len(r.content)} bytes)")
        except Exception as e:
            print(f"Failed {pin['name']}: {e}")

    print(f"\nGenerated {len(output)} pin specs: {out_file}")
    print(f"Example images saved in: {examples_dir}")


if __name__ == "__main__":
    main()
