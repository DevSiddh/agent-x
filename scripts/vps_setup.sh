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
WORKSPACE_ROOT=/home/youruser/projects   # CHANGE: where Orchestrator creates new projects
EOF
    echo "    → .env created at $ENV_FILE"
else
    echo "==> .env already exists"
fi

# ── 8. systemd services (3 services — telegram, webhook, dashboard) ───────────

# ── 8a. Telegram bot ──────────────────────────────────────────────────────────
echo "==> Creating systemd service: agentx-telegram"
sudo tee /etc/systemd/system/agentx-telegram.service > /dev/null << EOF
[Unit]
Description=Agent-XYZ Telegram Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/.venv/bin/python phase3/telegram_bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# ── 8b. Webhook server (FastAPI) ──────────────────────────────────────────────
echo "==> Creating systemd service: agentx-webhook"
sudo tee /etc/systemd/system/agentx-webhook.service > /dev/null << EOF
[Unit]
Description=Agent-XYZ Webhook Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/.venv/bin/python -m uvicorn phase2.webhook.server:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# ── 8c. Streamlit dashboard ───────────────────────────────────────────────────
echo "==> Creating systemd service: agentx-dashboard"
sudo tee /etc/systemd/system/agentx-dashboard.service > /dev/null << EOF
[Unit]
Description=Agent-XYZ Streamlit Dashboard
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/.venv/bin/streamlit run dashboard/app.py --server.port 8501 --server.headless true
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable agentx-telegram agentx-webhook agentx-dashboard

echo ""
echo "==> Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Fill in .env:"
echo "        nano $ENV_FILE"
echo ""
echo "  2. Start all 3 services:"
echo "        sudo systemctl start agentx-telegram agentx-webhook agentx-dashboard"
echo ""
echo "  3. Check all are running:"
echo "        sudo systemctl status agentx-telegram agentx-webhook agentx-dashboard"
echo ""
echo "  4. Watch logs per service:"
echo "        journalctl -u agentx-telegram -f"
echo "        journalctl -u agentx-webhook -f"
echo "        journalctl -u agentx-dashboard -f"
echo ""
echo "  5. Services auto-start on reboot. Closing terminal = nothing dies."
echo ""
echo "  NOTE: Webhook server path assumes phase2/webhook/server.py:app"
echo "        Dashboard path assumes dashboard/app.py"
echo "        Adjust ExecStart in /etc/systemd/system/ if paths differ."
