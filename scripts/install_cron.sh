#!/usr/bin/env bash
# =============================================================================
# install_cron.sh — Schedule Agent-X steps to run overnight on VPS
#
# This installs a cron job that:
#   1. Reads docs/progress.md to find the next PENDING step
#   2. Runs it via Claude Code
#   3. Sends you a Telegram notification when done
#
# Usage:
#   bash scripts/install_cron.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CRON_SCRIPT="$SCRIPT_DIR/run_next_step.sh"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"

# ── Write the runner script ──────────────────────────────────────────────────
cat > "$CRON_SCRIPT" << 'RUNNER'
#!/usr/bin/env bash
# run_next_step.sh — find next PENDING step and run it
# Called by cron. Sends Telegram notification when done.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load env
set -a
source "$PROJECT_DIR/.env"
set +a

LOG_FILE="$PROJECT_DIR/logs/cron_$(date +%Y%m%d_%H%M%S).log"

tg_send() {
    local msg="$1"
    curl -s -X POST \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=${msg}" \
        -d "parse_mode=HTML" \
        > /dev/null 2>&1 || true
}

# Find next PENDING step from session_prompts.md
NEXT_STEP=$(grep -m1 "PENDING" "$PROJECT_DIR/docs/session_prompts.md" \
    | grep -oP '(?<=step )\S+' | head -1 || echo "")

if [ -z "$NEXT_STEP" ]; then
    tg_send "Agent-X cron: No PENDING steps found. Nothing to run."
    exit 0
fi

tg_send "Agent-X cron: Starting step $NEXT_STEP..."

# Run Claude Code non-interactively
cd "$PROJECT_DIR"
source .venv/bin/activate

claude --dangerously-skip-permissions -p "step $NEXT_STEP" \
    > "$LOG_FILE" 2>&1
RC=$?

# Get last 50 lines of output for notification
SUMMARY=$(tail -50 "$LOG_FILE" | head -c 3000)

if [ $RC -eq 0 ]; then
    tg_send "Agent-X cron: step $NEXT_STEP DONE ✓

Last output:
<pre>${SUMMARY}</pre>"
else
    tg_send "Agent-X cron: step $NEXT_STEP FAILED (exit $RC)

Last output:
<pre>${SUMMARY}</pre>"
fi

exit $RC
RUNNER

chmod +x "$CRON_SCRIPT"
echo "==> Created: $CRON_SCRIPT"

# ── Install cron entry ────────────────────────────────────────────────────────
# Default: runs at 2:00 AM every day
# Change the schedule below as needed:
#   0 2 * * *   = 2:00 AM daily
#   0 */6 * * * = every 6 hours
#   0 2 * * 1-5 = 2:00 AM weekdays only

CRON_SCHEDULE="0 2 * * *"
CRON_ENTRY="$CRON_SCHEDULE $CRON_SCRIPT >> $LOG_DIR/cron_latest.log 2>&1"

# Check if already installed
if crontab -l 2>/dev/null | grep -q "run_next_step.sh"; then
    echo "==> Cron entry already exists. Removing old entry..."
    crontab -l 2>/dev/null | grep -v "run_next_step.sh" | crontab -
fi

# Add new entry
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
echo "==> Cron installed: $CRON_SCHEDULE"

echo ""
echo "==> Cron schedule installed!"
echo ""
echo "Current crontab:"
crontab -l
echo ""
echo "To change schedule, edit crontab:"
echo "    crontab -e"
echo ""
echo "To run immediately (test):"
echo "    bash $CRON_SCRIPT"
echo ""
echo "To watch logs:"
echo "    tail -f $LOG_DIR/cron_latest.log"
