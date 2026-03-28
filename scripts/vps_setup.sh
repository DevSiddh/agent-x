#!/usr/bin/env bash
# =============================================================================
# vps_setup.sh — One-shot setup for Agent-X on Ubuntu/Debian VPS
# Run once as your normal user (not root):
#   bash scripts/vps_setup.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV="$PROJECT_DIR/.venv"
ENV_FILE="$PROJECT_DIR/.env"

echo ""
echo "============================================================"
echo " Agent-X VPS Setup"
echo " Project: $PROJECT_DIR"
echo " User:    $USER"
echo "============================================================"
echo ""

# ── 1. System deps ────────────────────────────────────────────────────────────
echo "==> [1/9] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    git python3.11 python3.11-venv python3-pip \
    tmux curl wget build-essential ca-certificates

# ── 2. uv — fast Python package manager (replaces pip for project installs) ──
echo "==> [2/9] Installing uv..."
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Add to PATH for this session
    export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
    echo 'export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"' >> ~/.bashrc
    echo "    → uv installed: $(uv --version)"
else
    echo "    → uv already installed: $(uv --version)"
fi

# ── 3. Python virtualenv ──────────────────────────────────────────────────────
echo "==> [3/9] Setting up Python venv..."
cd "$PROJECT_DIR"
python3.11 -m venv "$VENV"
source "$VENV/bin/activate"
pip install --quiet --upgrade pip

# ── 4. Project requirements via uv (fast, cached) ────────────────────────────
echo "==> [4/9] Installing Python requirements..."
if command -v uv &>/dev/null; then
    uv pip install -r "$PROJECT_DIR/requirements.txt"
else
    pip install --quiet -r "$PROJECT_DIR/requirements.txt"
fi

# ── 5. WORKSPACE_ROOT directory ───────────────────────────────────────────────
echo "==> [5/9] Creating workspace directories..."
WORKSPACE="/home/$USER/projects"
mkdir -p "$WORKSPACE"
mkdir -p "$WORKSPACE/new"          # brief intake folder
mkdir -p "$PROJECT_DIR/memory"     # memory.jsonl, registry.jsonl, state.json
echo "    → WORKSPACE_ROOT: $WORKSPACE"

# ── 6. .env setup ─────────────────────────────────────────────────────────────
echo "==> [6/9] Setting up .env..."
if [ ! -f "$ENV_FILE" ]; then
    cat > "$ENV_FILE" << ENVEOF
# ── Agent-X environment variables ──────────────────────────────────────────
DEEPSEEK_API_KEY=sk-...
GITHUB_TOKEN=ghp_...
GITHUB_WEBHOOK_SECRET=changeme123

# Telegram
TELEGRAM_BOT_TOKEN=          # get from @BotFather
TELEGRAM_CHAT_ID=            # get from @userinfobot (your personal chat ID)

# Paths
WORKSPACE_ROOT=/home/${USER}/projects
AGENT_X_DIR=${PROJECT_DIR}

# Pipeline tuning
CONFIDENCE_THRESHOLD=0.85
CHURN_THRESHOLD=15
MAX_RETRIES=3
CI_POLL_TIMEOUT=300
ERROR_WINDOW_LINES=50
WEBHOOK_PORT=8080

# Pytest timeouts (FIX-2)
TEST_TIMEOUT_FILE=30
TEST_TIMEOUT_FULL=600

# Plan checkpoint timeout (FIX-11) — seconds before auto-approve
PLAN_APPROVAL_TIMEOUT=600
ENVEOF
    echo "    → .env created — FILL IN BEFORE STARTING SERVICES:"
    echo "         nano $ENV_FILE"
else
    echo "    → .env already exists — checking for missing keys..."
    # Add any missing keys silently
    grep -q "TEST_TIMEOUT_FILE"     "$ENV_FILE" || echo "TEST_TIMEOUT_FILE=30"     >> "$ENV_FILE"
    grep -q "TEST_TIMEOUT_FULL"     "$ENV_FILE" || echo "TEST_TIMEOUT_FULL=600"    >> "$ENV_FILE"
    grep -q "PLAN_APPROVAL_TIMEOUT" "$ENV_FILE" || echo "PLAN_APPROVAL_TIMEOUT=600" >> "$ENV_FILE"
    grep -q "AGENT_X_DIR"           "$ENV_FILE" || echo "AGENT_X_DIR=${PROJECT_DIR}" >> "$ENV_FILE"
    echo "    → .env OK"
fi

# ── 7. git hooks ──────────────────────────────────────────────────────────────
echo "==> [7/9] Installing git hooks..."
if [ -f "$PROJECT_DIR/scripts/install_hooks.sh" ]; then
    bash "$PROJECT_DIR/scripts/install_hooks.sh"
    echo "    → hooks installed"
else
    echo "    → scripts/install_hooks.sh not found, skipping"
fi

# ── 8. systemd services ───────────────────────────────────────────────────────
echo "==> [8/9] Creating systemd services..."

# 8a — Telegram bot
sudo tee /etc/systemd/system/agentx-telegram.service > /dev/null << EOF
[Unit]
Description=Agent-XYZ Telegram Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$VENV/bin/python phase3/telegram_bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 8b — Webhook server (GitHub Actions → Agent-X repair pipeline)
sudo tee /etc/systemd/system/agentx-webhook.service > /dev/null << EOF
[Unit]
Description=Agent-XYZ Webhook Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$VENV/bin/python -m uvicorn phase1.webhook.server:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 8c — Streamlit dashboard
sudo tee /etc/systemd/system/agentx-dashboard.service > /dev/null << EOF
[Unit]
Description=Agent-XYZ Streamlit Dashboard
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$VENV/bin/streamlit run dashboard/app.py --server.port 8501 --server.headless true
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable agentx-telegram agentx-webhook agentx-dashboard
echo "    → 3 services registered (telegram / webhook / dashboard)"

# ── 9. verify environment ─────────────────────────────────────────────────────
echo "==> [9/9] Running verify_env.py..."
source "$VENV/bin/activate"
python "$PROJECT_DIR/scripts/verify_env.py" || true

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo " Setup complete!"
echo "============================================================"
echo ""
echo "NEXT STEPS:"
echo ""
echo "  1. Fill in your API keys:"
echo "       nano $ENV_FILE"
echo ""
echo "  2. Start all 3 services:"
echo "       sudo systemctl start agentx-telegram agentx-webhook agentx-dashboard"
echo ""
echo "  3. Check all running:"
echo "       sudo systemctl status agentx-telegram agentx-webhook agentx-dashboard"
echo ""
echo "  4. Live logs:"
echo "       journalctl -u agentx-telegram  -f    # Telegram bot"
echo "       journalctl -u agentx-webhook   -f    # GitHub webhook"
echo "       journalctl -u agentx-dashboard -f    # Streamlit UI"
echo ""
echo "  5. Test Telegram bot — send any message to your bot"
echo "     It should reply with project options or build confirmation."
echo ""
echo "  Services auto-restart on crash and survive reboots."
echo ""
