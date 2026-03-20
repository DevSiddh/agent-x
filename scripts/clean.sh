#!/bin/bash
# Agent-X Nuclear Clean Script
# Run this whenever you hit: stale code, port errors, module errors, wrong behavior
# Usage: bash scripts/clean.sh

echo ""
echo "=== Agent-X Clean ==="
echo ""

# 1 — Kill stale processes
echo "[1/5] Killing stale processes..."
pkill -f "uvicorn" 2>/dev/null && echo "  killed uvicorn" || echo "  no uvicorn running"
pkill -f "python phase1" 2>/dev/null && echo "  killed phase1" || echo "  no phase1 running"
pkill -f "python phase2" 2>/dev/null && echo "  killed phase2" || echo "  no phase2 running"

# 2 — Free port 8080
echo "[2/5] Freeing port 8080..."
PID=$(netstat -ano 2>/dev/null | grep ":8080" | grep "LISTENING" | awk '{print $5}' | head -1)
if [ -n "$PID" ]; then
    taskkill //PID $PID //F 2>/dev/null && echo "  freed port 8080 (PID $PID)"
else
    echo "  port 8080 already free"
fi

# 3 — Clear __pycache__ and .pyc
echo "[3/5] Clearing Python cache..."
find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -not -path "./.venv/*" -delete 2>/dev/null
find . -type f -name "*.pyo" -not -path "./.venv/*" -delete 2>/dev/null
echo "  cleared __pycache__ and .pyc files"

# 4 — Remove runtime files
echo "[4/5] Removing runtime files..."
rm -f phase1/webhook/queue.db && echo "  removed queue.db" || true
rm -f report.json && echo "  removed report.json" || true
rm -rf .pytest_cache && echo "  removed .pytest_cache" || true

# 5 — Verify venv is active
echo "[5/5] Checking environment..."
if [ -d ".venv" ]; then
    echo "  venv exists"
    PYTHON=".venv/Scripts/python"
    VERSION=$($PYTHON --version 2>&1)
    echo "  $VERSION"
else
    echo "  WARNING: no .venv found — run: make install"
fi

echo ""
echo "=== Clean complete. Run: make test ==="
echo ""
