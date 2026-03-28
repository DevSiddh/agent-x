# Telegram → Claude Code Bridge | Setup Guide
# One-time setup, then run forever on VPS

---

## What This Does

Phone sends `/step E1` →
VPS runs `claude -p "step E1"` in your project dir →
Output streams back to your Telegram chat.

Cron runs the next PENDING step at 2 AM every night.
Sends you a Telegram message with result when done.

---

## Step 1 — Get Telegram credentials (5 mins)

**Create a bot:**
1. Open Telegram → search `@BotFather`
2. Send `/newbot` → follow prompts
3. Copy the **token** (looks like `7123456789:AAH...`)

**Get your chat ID:**
1. Open Telegram → search `@userinfobot`
2. Send `/start`
3. Copy the `id:` field (a number like `912345678`)

---

## Step 2 — Set up VPS (10 mins)

SSH into your VPS and run:

```bash
# Clone the project (if not already on VPS)
git clone https://github.com/DevSiddh/-agent-x-test-repo.git  # or copy via scp

# Run one-shot setup
cd agent-x
bash scripts/vps_setup.sh
```

---

## Step 3 — Fill in .env

```bash
nano .env
```

Add these values:

```
ANTHROPIC_API_KEY=sk-ant-...
DEEPSEEK_API_KEY=sk-...
GITHUB_TOKEN=ghp_...
GITHUB_WEBHOOK_SECRET=testsecret123

TELEGRAM_BOT_TOKEN=7123456789:AAH...    ← from BotFather
TELEGRAM_CHAT_ID=912345678              ← from @userinfobot
WORKSPACE_ROOT=/home/youruser/projects  ← where Orchestrator creates new projects
```

---

## Step 4 — Start the bot

```bash
# Start as a background service (survives logout + reboots)
sudo systemctl start agentx-telegram
sudo systemctl status agentx-telegram

# Watch logs
journalctl -u agentx-telegram -f
```

---

## Step 5 — Test from phone

Open your bot in Telegram and send:
```
/help
/status
/memory 5
/step E1
```

---

## Step 6 — Install nightly cron (optional)

```bash
bash scripts/install_cron.sh
```

Default schedule: **2:00 AM every day** — auto-runs the next PENDING step.

Change schedule:
```bash
crontab -e
# e.g., every 6 hours:  0 */6 * * * /path/to/run_next_step.sh
```

---

## Commands Reference

| Command       | What it does                                |
|---------------|---------------------------------------------|
| `/step E1`    | Run step E1 (any step name works)           |
| `/step C3b`   | Run step C3b                                |
| `/audit`      | Run the audit checklist                     |
| `/status`     | Show progress.md summary (last 30 lines)    |
| `/memory 10`  | Show last 10 memory.jsonl entries           |
| `/ps`         | Show running Claude processes on VPS        |
| `/kill`       | Kill active Claude session                  |
| `/help`       | Show all commands                           |

---

## How Claude runs non-interactively

```bash
# What the bot runs under the hood:
claude --dangerously-skip-permissions -p "step E1"
```

`--dangerously-skip-permissions` means Claude won't ask for confirmations.
This is safe on the VPS because the project has a pre-commit hook blocking
destructive commands (rm -rf, reset --hard, etc.).

---

## Troubleshooting

**Bot not responding:**
```bash
journalctl -u agentx-telegram -f
# Look for: "TELEGRAM_BOT_TOKEN not set" or network errors
```

**Claude not found:**
```bash
which claude   # should be /usr/local/bin/claude
# If missing: npm install -g @anthropic-ai/claude-code
```

**Permission errors:**
```bash
# The .env file should only be readable by your user:
chmod 600 .env
```

**Cron not running:**
```bash
crontab -l                           # check entry exists
tail -f logs/cron_latest.log         # watch output
bash scripts/run_next_step.sh        # test manually
```
