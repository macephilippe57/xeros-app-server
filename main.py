"""
XEROS App Server — API Bridge between Android App, Hermes Agent, and Telegram
Full bidirectional sync: App ↔ Hermes ↔ Telegram
"""
import asyncio
import base64
import hashlib
import hmac
import json
import os
import sqlite3
import tempfile
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import httpx

from xeros_dashboard.dashboard_router import router as dashboard_router
from shopify_router import router as shopify_router
from digital_downloads import router as digital_downloads_router

app = FastAPI(title="XEROS App Server", version="2.1.0")
app.include_router(dashboard_router)
app.include_router(shopify_router)
app.include_router(digital_downloads_router)
app.mount("/static", StaticFiles(directory="/opt/data/xeros-app-server/static"), name="static")

# CORS — allow Android app and dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Config ──────────────────────────────────────────────────────
API_SECRET = os.environ.get("XEROS_API_SECRET", "xeros-godmode-2024")
HERMES_BIN = "/usr/local/bin/hermes"
HERMES_HOME = os.environ.get("HERMES_HOME", "/opt/data")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "7894537615")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
ELEVENLABS_VOICES_URL = "https://api.elevenlabs.io/v1/voices"
DEFAULT_ELEVENLABS_VOICE = "Rachel"  # fr-FR friendly default
FALLBACK_ELEVENLABS_VOICE = "Adam"
STATE_DB = Path(HERMES_HOME) / "state.db"

AUDIO_CACHE = Path("/opt/data/xeros-app-server/audio_cache")
AUDIO_CACHE.mkdir(parents=True, exist_ok=True)

# ── Auth ──────────────────────────────────────────────────────────

def verify_signature(body: bytes, signature: str) -> bool:
    expected = hmac.new(API_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def check_auth(request: Request):
    sig = request.headers.get("X-Signature")
    if sig is None:
        return  # dev mode
    body = await request.body()
    if not verify_signature(body, sig):
        raise HTTPException(status_code=403, detail="Invalid signature")


# ── Models ────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    voice_reply: bool = False
    voice_type: str = "default"  # 'default' (Hermes/system TTS) or 'elevenlabs' (premium)
    voice_id: str | None = None  # optional ElevenLabs voice id


class ChatResponse(BaseModel):
    reply: str
    audio_base64: str | None = None
    session_id: str
    latency_ms: float


class HistoryMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: str


# ── Telegram Bridge ───────────────────────────────────────────────

async def send_telegram_message(text: str) -> bool:
    """Send a message to Philippe via Telegram bot."""
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


async def send_telegram_voice(audio_base64: str, caption: str = "") -> bool:
    """Send a voice message to Philippe via Telegram bot."""
    if not TELEGRAM_BOT_TOKEN:
        return False
    try:
        audio_bytes = base64.b64decode(audio_base64)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVoice",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
                files={"voice": ("voice.ogg", audio_bytes, "audio/ogg")},
            )
            return resp.status_code == 200
    except Exception:
        return False


# ── Hermes Bridge ─────────────────────────────────────────────────

async def call_hermes(prompt: str, timeout: int = 120) -> str:
    """Call Hermes CLI and return the response text."""
    env = os.environ.copy()
    env["HERMES_HOME"] = HERMES_HOME

    proc = await asyncio.create_subprocess_exec(
        HERMES_BIN, "chat", "-q", prompt, "-Q", "-s", "xeros-jarvis",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return "⏰ Hermes a mis trop de temps à répondre."

    if proc.returncode != 0:
        err = stderr.decode()[:500]
        return f"❌ Erreur Hermes: {err}"

    raw = stdout.decode().strip()
    lines = raw.split("\n")
    # Remove session_id line and Pliny divider
    cleaned = []
    for l in lines:
        if l.startswith("session_id:"):
            continue
        if ".-.-.-.-<|LOVE PLINY LOVE|>-.-.-.-." in l:
            continue
        cleaned.append(l)
    return "\n".join(cleaned).strip()


async def text_to_speech(text: str) -> str | None:
    """Convert text to speech using Hermes TTS, return base64 MP3."""
    try:
        env = os.environ.copy()
        env["HERMES_HOME"] = HERMES_HOME
        out_path = AUDIO_CACHE / f"tts_{int(time.time()*1000)}.mp3"

        proc = await asyncio.create_subprocess_exec(
            HERMES_BIN, "tts", text,
            "--output", str(out_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        await asyncio.wait_for(proc.communicate(), timeout=30)

        if out_path.exists() and out_path.stat().st_size > 0:
            with open(out_path, "rb") as f:
                return base64.b64encode(f.read()).decode()
    except Exception:
        pass
    return None


async def text_to_speech_elevenlabs(text: str, voice_id: str | None = None) -> str | None:
    """Convert text to speech using ElevenLabs API, return base64 MP3."""
    if not ELEVENLABS_API_KEY:
        return None
    selected_voice = voice_id or DEFAULT_ELEVENLABS_VOICE
    url = ELEVENLABS_TTS_URL.format(voice_id=selected_voice)
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY,
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                return base64.b64encode(resp.content).decode()
            # Try fallback voice once if the requested voice was invalid
            if voice_id and voice_id != FALLBACK_ELEVENLABS_VOICE:
                return await text_to_speech_elevenlabs(text, FALLBACK_ELEVENLABS_VOICE)
    except Exception:
        pass
    return None


async def synthesize_voice(text: str, voice_type: str = "default", voice_id: str | None = None) -> str | None:
    """Generate TTS audio. ElevenLabs if requested+available, otherwise local fallback."""
    if voice_type == "elevenlabs":
        audio_b64 = await text_to_speech_elevenlabs(text, voice_id)
        if audio_b64:
            return audio_b64
    return await text_to_speech(text)


async def list_elevenlabs_voices() -> list[dict]:
    """Fetch available ElevenLabs voices."""
    if not ELEVENLABS_API_KEY:
        return []
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                ELEVENLABS_VOICES_URL,
                headers={"xi-api-key": ELEVENLABS_API_KEY},
            )
            if resp.status_code == 200:
                data = resp.json()
                voices = []
                for v in data.get("voices", []):
                    voices.append({
                        "voice_id": v.get("voice_id"),
                        "name": v.get("name"),
                        "category": v.get("category"),
                        "description": v.get("description"),
                        "labels": v.get("labels", {}),
                        "preview_url": v.get("preview_url"),
                    })
                return voices
    except Exception:
        pass
    return []


# ── Lead Capture ───────────────────────────────────────────────────

LEADS_DB = Path(HERMES_HOME) / "xeros_leads.jsonl"
LEADS_DB.parent.mkdir(parents=True, exist_ok=True)

class LeadRequest(BaseModel):
    name: str
    email: str
    source: str = "unknown"
    funnel: str = "xeros"
    tags: list[str] | None = None


def save_lead(lead: dict):
    lead["created_at"] = datetime.utcnow().isoformat()
    with open(LEADS_DB, "a", encoding="utf-8") as f:
        f.write(json.dumps(lead, ensure_ascii=False) + "\n")


async def notify_new_lead(name: str, email: str, source: str):
    text = f"🎯 *Nouveau lead XEROS*\n• {name}\n• {email}\n• Source: `{source}`"
    await send_telegram_message(text)


# ── History Sync ──────────────────────────────────────────────────

def get_telegram_history(limit: int = 50) -> list[HistoryMessage]:
    """Read recent Telegram conversation history from Hermes state DB."""
    messages = []
    try:
        if not STATE_DB.exists():
            print(f"[HISTORY] DB not found at {STATE_DB}", flush=True)
            return messages

        conn = sqlite3.connect(str(STATE_DB))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT m.role, m.content, m.timestamp
            FROM messages m
            JOIN sessions s ON m.session_id = s.id
            WHERE s.source = 'telegram'
              AND s.chat_id = ?
              AND m.role IN ('user', 'assistant')
              AND m.content IS NOT NULL
              AND m.content != ''
            ORDER BY m.id DESC
            LIMIT ?
        """, (TELEGRAM_CHAT_ID, limit))
        rows = cursor.fetchall()
        conn.close()

        for row in reversed(rows):
            messages.append(HistoryMessage(
                role=row["role"],
                content=row["content"][:2000],
                timestamp=str(row["timestamp"] or ""),
            ))
    except Exception as e:
        print(f"[HISTORY ERROR] {e}", flush=True)
    return messages


# ── Endpoints ─────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "hermes": "connected",
        "telegram": "configured" if TELEGRAM_BOT_TOKEN else "missing_token",
        "timestamp": time.time(),
    }


@app.post("/chat")
async def chat(req: ChatRequest, request: Request):
    """
    Text chat with Hermes.
    Response goes to: App (direct) + Telegram (mirror).
    """
    await check_auth(request)
    t0 = time.time()

    # Forward user message to Telegram for history
    await send_telegram_message(f"📱 *Depuis l'app:* {req.message}")

    # Get Hermes response
    reply = await call_hermes(req.message)
    audio_b64 = None

    if req.voice_reply:
        audio_b64 = await synthesize_voice(reply, voice_type=req.voice_type, voice_id=req.voice_id)

    # Mirror response to Telegram
    await send_telegram_message(f"🤖 *XEROS:* {reply}")

    latency = (time.time() - t0) * 1000

    return ChatResponse(
        reply=reply,
        audio_base64=audio_b64,
        session_id=req.session_id or f"xeros_{int(t0)}",
        latency_ms=round(latency, 1),
    )


@app.post("/voice")
async def voice(
    audio: UploadFile = File(...),
    voice_type: str = Form("default"),
    voice_id: str | None = Form(None),
    request: Request = None,
):
    """
    Voice command from Android app.
    Audio → transcription → Hermes → TTS response.
    Mirrored to Telegram.
    """
    await check_auth(request)
    t0 = time.time()

    # Save uploaded audio
    audio_bytes = await audio.read()
    audio_path = AUDIO_CACHE / f"input_{int(t0)}.wav"
    with open(audio_path, "wb") as f:
        f.write(audio_bytes)

    # Transcribe using Hermes STT
    env = os.environ.copy()
    env["HERMES_HOME"] = HERMES_HOME

    proc = await asyncio.create_subprocess_exec(
        HERMES_BIN, "stt", str(audio_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    except asyncio.TimeoutError:
        proc.kill()
        return JSONResponse({"error": "Transcription timeout"}, status_code=500)

    transcript = stdout.decode().strip()
    if not transcript:
        transcript = "Je n'ai pas compris l'audio."

    # Forward to Telegram
    await send_telegram_message(f"🎤 *Depuis l'app (vocal):* {transcript}")

    # Chat with Hermes
    reply = await call_hermes(transcript)

    # TTS
    audio_b64 = await synthesize_voice(reply, voice_type=voice_type, voice_id=voice_id)

    # Mirror to Telegram
    await send_telegram_message(f"🤖 *XEROS:* {reply}")

    latency = (time.time() - t0) * 1000

    return {
        "transcript": transcript,
        "reply": reply,
        "audio_base64": audio_b64,
        "voice_type": voice_type,
        "latency_ms": round(latency, 1),
    }


@app.get("/voices")
async def voices():
    """List available ElevenLabs voices. Falls back to local static defaults if key missing."""
    voices = await list_elevenlabs_voices()
    if not voices:
        voices = [
            {"voice_id": "Rachel", "name": "Rachel", "category": "premade", "description": "ElevenLabs default female voice."},
            {"voice_id": "Adam", "name": "Adam", "category": "premade", "description": "ElevenLabs default male voice."},
        ]
    return {"voices": voices, "default": DEFAULT_ELEVENLABS_VOICE, "source": "elevenlabs" if ELEVENLABS_API_KEY else "static"}


@app.post("/quick")
async def quick(req: ChatRequest, request: Request):
    """Quick text-only chat, no TTS, no Telegram mirror."""
    await check_auth(request)
    t0 = time.time()
    reply = await call_hermes(req.message)
    latency = (time.time() - t0) * 1000
    return {"reply": reply, "latency_ms": round(latency, 1)}


@app.get("/history")
async def history(limit: int = Query(default=50, le=200)):
    """Get recent Telegram conversation history for the Android app."""
    messages = get_telegram_history(limit)
    return {
        "messages": [m.model_dump() for m in messages],
        "count": len(messages),
    }


@app.get("/7jours-etsy-ia")
async def landing_page():
    """Serve the 7 Jours Etsy IA landing page."""
    return FileResponse("/opt/data/xeros-app-server/static/landing/7jours-etsy-ia.html")


@app.get("/download/guide")
async def download_guide():
    """Serve the free guide PDF/Markdown."""
    return FileResponse("/opt/data/xeros-app-server/static/landing/7jours-etsy-ia-guide.md")


@app.post("/lead")
async def lead(req: LeadRequest, request: Request):
    """Capture a lead from the landing page and send to Telegram."""
    await check_auth(request)
    if "@" not in req.email or "." not in req.email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Email invalide")

    lead_doc = {
        "name": req.name.strip(),
        "email": req.email.strip().lower(),
        "source": req.source,
        "funnel": req.funnel,
        "tags": req.tags or [],
        "ip": request.client.host if request.client else None,
    }
    save_lead(lead_doc)
    await notify_new_lead(req.name, req.email, req.source)

    # Auto-send welcome via Telegram to lead email conceptually
    return {"status": "ok", "message": "Lead enregistré"}


@app.get("/leads")
async def leads(limit: int = Query(default=50, le=500)):
    """Admin endpoint to list captured leads."""
    if not LEADS_DB.exists():
        return {"leads": [], "count": 0}
    lines = LEADS_DB.read_text(encoding="utf-8").strip().split("\n")
    leads = [json.loads(line) for line in lines if line.strip()]
    return {"leads": leads[-limit:], "count": len(leads)}


@app.post("/telegram/forward")
async def telegram_forward(req: ChatRequest, request: Request):
    """
    Forward a message FROM Telegram TO the app.
    Used when Philippe sends a message on Telegram and wants it in the app.
    This is called by a webhook or cron when new Telegram messages arrive.
    """
    await check_auth(request)
    # This endpoint is for the app to poll or receive push notifications
    # about new Telegram messages
    return {"status": "ok", "message": req.message}


# ── Main ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8645, log_level="info")
