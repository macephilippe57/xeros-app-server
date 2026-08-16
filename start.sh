#!/bin/bash
# XEROS App Server — Quick Start Script (with Telegram sync)
# Usage: ./start.sh

cd "$(dirname "$0")"

# Load Telegram token from .env
export TELEGRAM_BOT_TOKEN=$(grep TELEGRAM_BOT_TOKEN /opt/data/.env | cut -d= -f2)
export HERMES_HOME=/opt/data
export XEROS_API_SECRET=xeros-godmode-2024

echo "⚡ XEROS App Server v2.0"
echo "========================"
echo "Telegram: ${TELEGRAM_BOT_TOKEN:0:15}..."
echo ""

# Check if already running
if pgrep -f "xeros-app-server/main.py" > /dev/null; then
    echo "⚠ Server already running. PID: $(pgrep -f xeros-app-server/main.py)"
    echo "  Restart? (y/n)"
    read -r answer
    if [ "$answer" != "y" ]; then
        exit 0
    fi
    pkill -f "xeros-app-server/main.py"
    sleep 2
fi

# Start server
echo "▶ Starting server on port 8645..."
.venv/bin/python main.py &
SERVER_PID=$!
sleep 2

# Start public tunnel
export PATH=/opt/data/node-tools/node_modules/.bin:$PATH
if ! pgrep -f "lt --port 8645" > /dev/null; then
    echo "▶ Starting public tunnel..."
    nohup lt --port 8645 > tunnel.log 2>&1 &
    echo $! > tunnel.pid
    sleep 3
fi

# Health check
HEALTH=$(curl -s http://localhost:8645/health 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "✅ Server running (PID: $SERVER_PID)"
    echo "   Health: $HEALTH"
    echo ""
    echo "📱 Configure your Android app with:"
    echo "   Server: http://$(hostname -I | awk '{print $1}'):8645"
    echo "   Secret: xeros-godmode-2024"
    echo ""
    echo "🔄 Sync active: App ↔ Hermes ↔ Telegram (chat 7894537615)"
else
    echo "❌ Server failed to start"
    exit 1
fi
