#!/usr/bin/env bash
# =============================================================================
# vps_setup.sh — One-shot setup for Agent-X on Ubuntu VPS
# Run once as your normal user (not root):
#   bash scripts/vps_setup.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "==> Project dir: $PROJECT_DIR"

# ── 1. System deps ────────────────────────────────────────────────────────────
echo "==> Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    git python3.11 python3.11-venv python3-pip \
    tmux curl wget build-essential

# ── 2. Node.js (for Claude Code CLI) ─────────────────────────────────────────
if ! command -v node &>/dev/null; then
    echo "==> Installing Node.js 20..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
else
    echo "==> Node.js already installed: $(node --version)"
fi

# ── 3. Claude Code CLI ────────────────────────────────────────────────────────
if ! command -v claude &>/dev/null; then
    echo "==> Installing Claude Code CLI..."
    npm install -g @anthropic-ai/claude-code
else
    echo "==> Claude Code already installed: $(claude --version 2>/dev/null || echo 'ok')"
fi

# ── 4. Python virtualenv ──────────────────────────────────────────────────────
echo "==> Setting up Python venv..."
cd "$PROJECT_DIR"
python3.11 -m venv .venv
source .venv/bin/activate
pip install --quiet --upgrade pip

# ── 5. Project requirements ───────────────────────────────────────────────────
echo "==> Installing Python requirements..."
pip install --quiet -r requirements.txt

# ── 6. Telegram bot deps ──────────────────────────────────────────────────────
echo "==> Installing Telegram bot dependencies..."
pip install --quiet "python-telegram-bot[webhooks]>=20.0" python-dotenv

# ── 7. .env check ─────────────────────────────────────────────────────────────
ENV_FILE="$PROJECT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo ""
    echo "==> Creating .env template — FILL IN BEFORE RUNNING BOT:"
    cat > "$ENV_FILE" << 'EOF'
# Agent-X environment variables
ANTHROPIC_API_KEY=sk-ant-...
DEEPSEEK_API_KEY=sk-...
GITHUB_TOKEN=ghp_...
GITHUB_WEBHOOK_SECRET=testsecret123

# Telegram bot
TELEGRAM_BOT_TOKEN=         # get from @BotFather
TELEGRAM_CHAT_ID=           # get from @userinfobot (your personal chat ID)
AGENT_X_DIR=/home/youruser/agent-x   # CHANGE to actual path on VPS
EOF
    echo "    → .env created at $ENV_FILE"
else
    echo "==> .env already exists"
fi

# ── 8. systemd service ────────────────────────────────────────────────────────
SERVICE_NAME="agentx-telegram"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "==> Creating systemd service: $SERVICE_NAME"
sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=Agent-X Telegram Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/.venv/bin/python scripts/telegram_bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

echo ""
echo "==> Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env and fill in all values:"
echo "        nano $ENV_FILE"
echo ""
echo "  2. Get your Telegram chat ID:"
echo "        Message @userinfobot on Telegram → copy the id: field"
echo ""
echo "  3. Create your bot:"
echo "        Message @BotFather → /newbot → copy the token"
echo ""
echo "  4. Start the bot service:"
echo "        sudo systemctl start $SERVICE_NAME"
echo "        sudo systemctl status $SERVICE_NAME"
echo ""
echo "  5. Watch logs:"
echo "        journalctl -u $SERVICE_NAME -f"
echo ""
echo "  6. (Optional) Set up scheduled steps:"
echo "        bash scripts/install_cron.sh"
