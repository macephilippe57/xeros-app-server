#!/bin/bash
# XEROS App Server - Cloudflare tunnel wrapper
set -e
cd "$(dirname "$0")"
export HERMES_HOME=/opt/data
export XEROS_API_SECRET=xeros-godmode-2024
export TELEGRAM_BOT_TOKEN=$(grep TELEGRAM_BOT_TOKEN /opt/data/.env | cut -d= -f2)

echo "⚡ XEROS App Server v2.1 (Cloudflare tunnel)"
echo "============================================"

# Check if server already running
if pgrep -f "xeros-app-server/main.py" > /dev/null; then
    echo "⚠ Server already running. PID: $(pgrep -f xeros-app-server/main.py)"
else
    echo "▶ Starting server on port 8645..."
    .venv/bin/python main.py &
    SERVER_PID=$!
    sleep 2
    echo $SERVER_PID > server.pid
fi

# Start cloudflared tunnel if not running
if ! pgrep -f "cloudflared tunnel run xeros-exec" > /dev/null; then
    echo "▶ Starting Cloudflare tunnel xeros-exec → 127.0.0.1:8645..."
    nohup /opt/data/cloudflared tunnel run --credentials-file /opt/data/.cloudflare/xeros-exec.json xeros-exec > cloudflare_tunnel.log 2>&1 &
    echo $! > cloudflare_tunnel.pid
    sleep 3
else
    echo "✅ Cloudflare tunnel already running"
fi

# Health check
HEALTH=$(curl -s http://localhost:8645/health 2>/dev/null || true)
if [ -n "$HEALTH" ]; then
    echo "✅ Server running"
    echo "   Health: $HEALTH"
    echo ""
    echo "📱 Fixed public URL: https://xeros-app.xeroscorp.cloud"
    echo "📱 Fallback localtunnel URL: $(cat tunnel.log 2>/dev/null || echo 'not running')"
    echo "   Secret: xeros-godmode-2024"
else
    echo "❌ Server failed to start"
    exit 1
fi
