# XEROS App Server Constitution

## Core Principles

### I. GODMODE Execution
Every task is executed end-to-end without unnecessary confirmations. Once credentials and goals are provided, the agent takes full ownership of implementation, deployment, and verification. Micro-confirmations are avoided unless the action is irreversible and lacks explicit prior direction.

### II. Autonomous Commerce Automation
The system automates XerosDesigns operations across Etsy, Shopify, Pinterest, Canva, and future channels. Favor fully automated flows (API + cron + webhook) over manual steps. When a platform blocks an API path, use headless browser automation or UI takeover as fallback.

### III. French-First Conciseness
Status reports to Philippe MACE are concise, in French, and action-oriented. Logs and internal docs may be in English; user-facing output is French unless explicitly requested otherwise.

### IV. Free / Offline / Local-First When Viable
Prefer free, local, or self-hosted solutions: Vosk for offline wake word, localtunnel/ngrok-free tunnels, open-source tools, and existing infrastructure. Paid SaaS is acceptable only when no viable free path exists and Philippe has approved.

### V. Test-First for Critical Paths
New endpoints, automation scripts, and revenue-impacting flows must include verification: unit test, integration test, or runtime health check. Not every UI helper needs a test, but money-moving and public API paths do.

### VI. Security by Default
Secrets live in `/opt/data/.env` or provider-specific token files, never in source code. OAuth tokens are refreshed automatically. `.env` and `*_tokens.json` files are excluded from git. No credential leaks in logs or screenshots.

### VII. One Asset, Many Channels
Reuse creative assets across platforms: one design → Etsy listing, Shopify product, Pinterest Pins, Canva templates, and Android app content. Avoid rebuilding the same artifact twice.

## Additional Constraints

- **Stack**: Python 3.11+ / FastAPI / Uvicorn for the bridge server; React/Vue optional for dashboard.
- **Telegram**: Primary notification and command surface. Webhooks route events to Telegram and the Android app.
- **Shopify**: Store `jsygq1-8a`; API version pinned in `.env`. Digital products require auto-delivery.
- **Etsy**: Shop XerosDesigns (ID 65702335); OAuth tokens auto-refresh; listings support physical + digital.
- **Pinterest**: Cookie-based autoposter capped at 3 Pins per run; no CAPTCHA manual steps in cron paths.
- **Android App**: Wake word via Vosk, voice commands, audio replies via TTS, QR-code/APK distribution.

## Development Workflow

1. **Spec** → define what to build and why
2. **Plan** → implementation plan with explicit files and dependencies
3. **Tasks** → atomic, verifiable tasks
4. **Implement** → code + test + deploy
5. **Converge** → verify against spec and document remaining work
6. **Report** → short French status to Philippe with URLs and next steps

## Governance

This constitution supersedes ad-hoc instructions. Amendments must be written, versioned, and announced. Every PR/review verifies compliance with security, French reporting, and automation-first principles.

**Version**: 1.0.0 | **Ratified**: 2026-08-16 | **Last Amended**: 2026-08-16
