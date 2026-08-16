#!/usr/bin/env python3
"""Générer la série de contenu 7 jours pour Telegram + email.

Produit 7 messages courts prêts à envoyer, avec liens affiliés XEROS et CTA.
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

OUT_DIR = Path("/opt/data/xeros-app-server/static/landing/7jours-content")
OUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://deep-foxes-hope.loca.lt"
LANDING = f"{BASE_URL}/7jours-etsy-ia"
GUIDE = f"{BASE_URL}/download/guide"
APK = f"{BASE_URL}/static/xeros-app-debug.apk"

AFFILIATES = {
    "shopify": "http://shopify.pxf.io/xLARjk",
    "autods": "https://www.autods.com/0bc0",
    "legalplace": "https://c3po.link/Qds9fQBf3w",
    "arcads": "https://arcads.ai/?via=fg",
    "smartbundle": "https://app-bundle.arkanse.fr/public/affiliation?fpr=fg",
}

DAYS = [
    {
        "day": 1,
        "title": "Fondations",
        "hook": "Avant de créer un design, posez les fondations.",
        "points": [
            "Choisissez une niche cadeau (passion, humour, saisonnier).",
            "Vérifiez la concurrence sur Etsy avec 3 mots-clés.",
            "Créez le logo + bannière avec Canva ou Pollinations AI.",
        ],
        "action": "Validez votre niche et remplissez 100% du profil Etsy.",
        "affiliate_key": "shopify",
        "affiliate_text": "Boutique Shopify gratuite 3 jours",
    },
    {
        "day": 2,
        "title": "Design IA",
        "hook": "Un bon design Etsy se vend avant qu’on ne lise le titre.",
        "points": [
            "Générez 10 designs avec Pollinations AI (fond transparent).",
            "Créez 3 mockups lifestyle par produit.",
            "Testez la lisibilité en miniature.",
        ],
        "action": "Ayez 10 designs prêts à uploader demain.",
        "affiliate_key": "arcads",
        "affiliate_text": "Essayer Arcads pour vidéos UGC",
    },
    {
        "day": 3,
        "title": "SEO Etsy",
        "hook": "Sans SEO, votre listing est invisible. Avec, il est rentable.",
        "points": [
            "Titre : mot-clé principal + attribut + public + occasion.",
            "13 tags, 20 caractères max chacun.",
            "Description 1500+ caractères avec hook + CTA.",
        ],
        "action": "Optimisez 5 listings aujourd’hui.",
        "affiliate_key": None,
        "affiliate_text": None,
    },
    {
        "day": 4,
        "title": "Lancement",
        "hook": "Publier 10 listings actives dès aujourd’hui.",
        "points": [
            "10 images par listing minimum.",
            "Activez la personnalisation sur les cadeaux.",
            "Prix : t-shirt 22-24€, hoodie 39-45€.",
        ],
        "action": "Passez de 0 à 10 listings actives.",
        "affiliate_key": "autods",
        "affiliate_text": "AutoDS 30 jours pour 1€",
    },
    {
        "day": 5,
        "title": "Pinterest",
        "hook": "Pinterest = trafic gratuit scalable pour Etsy.",
        "points": [
            "Créez 5 boards thématiques.",
            "3 pins par listing (produit, idée, saisonnier).",
            "Planifiez 3-5 pins/jour.",
        ],
        "action": "Générez 30 pins et planifiez-les.",
        "affiliate_key": None,
        "affiliate_text": None,
    },
    {
        "day": 6,
        "title": "Conversion",
        "hook": "Le trafic ne paie pas les factures. La conversion oui.",
        "points": [
            "Bundles : t-shirt + mug = +35% panier moyen.",
            "Codes promo : BIENVENUE10, BUNDLE15.",
            "Personnalisation +5€ sur les cadeaux.",
        ],
        "action": "Créez 3 bundles et activez les codes promo.",
        "affiliate_key": "legalplace",
        "affiliate_text": "Micro-entreprise -25% avec THEO25",
    },
    {
        "day": 7,
        "title": "Scale",
        "hook": "Passez en mode système : automate, teste, scale.",
        "points": [
            "3 nouvelles niches par semaine.",
            "Etsy Ads : 5€/jour max sur 3 listings.",
            "Tracker vues, CTR, conversion, panier moyen.",
        ],
        "action": "Fixez vos objectifs 30 jours et planifiez le mois.",
        "affiliate_key": "smartbundle",
        "affiliate_text": "SmartBundle -30% à vie code THEO",
    },
]


def build_message(day: dict) -> str:
    lines = [
        f"📅 *JOUR {day['day']}/7 — {day['title'].upper()}*",
        "",
        f"{day['hook']}",
        "",
        "*Points clés :*",
    ]
    for p in day["points"]:
        lines.append(f"• {p}")
    lines.extend(["", f"🎯 *Action du jour :* {day['action']}"])
    if day["affiliate_key"]:
        url = AFFILIATES[day["affiliate_key"]]
        lines.extend(["", f"🛠️ *Outil du jour :* [{day['affiliate_text']}]({url})"])
    lines.extend([
        "",
        f"📥 *Télécharge le guide complet :* {LANDING}",
        f"📱 *App XEROS :* {APK}",
    ])
    return "\n".join(lines)


def main():
    today = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    schedule = []
    for day in DAYS:
        send_at = today + timedelta(days=day["day"] - 1)
        msg = build_message(day)
        entry = {
            "day": day["day"],
            "title": day["title"],
            "send_at": send_at.isoformat(),
            "telegram_message": msg,
            "email_subject": f"Jour {day['day']}/7 — {day['title']} (7 Jours Etsy IA)",
            "email_body_markdown": msg.replace("*", "**"),
        }
        schedule.append(entry)

    out_file = OUT_DIR / "schedule.json"
    out_file.write_text(json.dumps(schedule, indent=2, ensure_ascii=False))

    # Write individual markdown files for easy copy/paste
    for entry in schedule:
        (OUT_DIR / f"day{entry['day']}.md").write_text(entry["telegram_message"])

    print(f"Generated 7-day content schedule: {out_file}")
    print(f"Individual day files: {len(list(OUT_DIR.glob('day*.md')))}")

    # Preview day 1
    print("\n--- PREVIEW JOUR 1 ---\n")
    print(schedule[0]["telegram_message"])


if __name__ == "__main__":
    main()
