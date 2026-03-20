# Agent-X Makefile
# Run these before EVERY dev session to avoid stale state errors
# Usage: make clean && make test

.PHONY: clean install test run reset help

# ── Default ───────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "Agent-X commands:"
	@echo "  make clean    Kill ports + wipe stale cache (run this first)"
	@echo "  make install  Fresh venv + pip install"
	@echo "  make test     Clean state then run full pytest"
	@echo "  make run      Clean start webhook server"
	@echo "  make reset    Nuclear reset (clean + reinstall venv)"
	@echo ""

# ── Clean — kill stale state ──────────────────────────────────────────────────
clean:
	@echo "[clean] Killing stale processes..."
	-pkill -f "uvicorn" 2>/dev/null || true
	-pkill -f "python phase1" 2>/dev/null || true
	-pkill -f "python phase2" 2>/dev/null || true

	@echo "[clean] Clearing __pycache__ and .pyc files..."
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -not -path "./.venv/*" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -not -path "./.venv/*" -delete 2>/dev/null || true

	@echo "[clean] Removing runtime files..."
	rm -f phase1/webhook/queue.db
	rm -f report.json
	rm -f .pytest_cache -rf 2>/dev/null || true

	@echo "[clean] Done — stale state cleared"

# ── Install — fresh venv ──────────────────────────────────────────────────────
install:
	@echo "[install] Creating virtual environment..."
	python -m venv .venv

	@echo "[install] Installing dependencies..."
	.venv/Scripts/pip install --upgrade pip
	.venv/Scripts/pip install -r requirements.txt

	@echo "[install] Done — run: .venv/Scripts/activate"

# ── Test — clean run ──────────────────────────────────────────────────────────
test: clean
	@echo "[test] Running full test suite..."
	.venv/Scripts/pytest tests/ -v --tb=short
	@echo "[test] Done"

# ── Run — clean server start ──────────────────────────────────────────────────
run: clean
	@echo "[run] Starting webhook server..."
	.venv/Scripts/uvicorn phase1.webhook.server:app --port 8080 --reload

# ── CI — run GitHub Actions locally before pushing ───────────────────────────
ci:
	@echo "[ci] Running GitHub Actions locally with act..."
	bash scripts/run_act.sh

# ── Hooks — install git hooks once ───────────────────────────────────────────
hooks:
	@echo "[hooks] Installing git hooks..."
	bash scripts/install_hooks.sh

# ── Reset — nuclear option ────────────────────────────────────────────────────
reset: clean
	@echo "[reset] Removing virtual environment..."
	rm -rf .venv
	@echo "[reset] Reinstalling from scratch..."
	$(MAKE) install
	@echo "[reset] Full reset complete"
