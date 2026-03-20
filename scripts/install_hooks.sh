#!/bin/bash
# Install git hooks for Agent-X
# Run once: bash scripts/install_hooks.sh

HOOKS_DIR=".git/hooks"

echo ""
echo "=== Installing Agent-X git hooks ==="

# ── pre-push hook ─────────────────────────────────────────────────────────────
cat > "$HOOKS_DIR/pre-push" << 'EOF'
#!/bin/bash
# Agent-X pre-push hook
# Runs before every git push — blocks if tests fail

echo ""
echo "=== Pre-push: Agent-X checks ==="
echo ""

# 1 — Block push to main directly
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
    echo "BLOCKED: Direct push to $BRANCH is not allowed."
    echo "Use a shadow branch: agent-x/fix-<step>"
    echo ""
    exit 1
fi

# 2 — Clear stale cache before testing
echo "[1/3] Clearing stale cache..."
find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -not -path "./.venv/*" -delete 2>/dev/null || true

# 3 — Verify environment
echo "[2/3] Verifying environment..."
if [ -f ".venv/Scripts/python" ]; then
    PYTHON=".venv/Scripts/python"
elif [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python"
fi

$PYTHON scripts/verify_env.py
if [ $? -ne 0 ]; then
    echo ""
    echo "BLOCKED: Environment check failed. Fix errors before pushing."
    echo ""
    exit 1
fi

# 4 — Run tests
echo "[3/3] Running tests..."
if [ -f ".venv/Scripts/pytest" ]; then
    PYTEST=".venv/Scripts/pytest"
elif [ -f ".venv/bin/pytest" ]; then
    PYTEST=".venv/bin/pytest"
else
    PYTEST="pytest"
fi

GITHUB_WEBHOOK_SECRET=test-secret $PYTEST tests/ --tb=short -q
if [ $? -ne 0 ]; then
    echo ""
    echo "BLOCKED: Tests failed. Fix before pushing."
    echo "Run: make test  to see full output"
    echo ""
    exit 1
fi

echo ""
echo "All checks passed. Pushing to GitHub..."
echo ""
exit 0
EOF

chmod +x "$HOOKS_DIR/pre-push"
echo "  pre-push hook installed"

# ── pre-commit hook ───────────────────────────────────────────────────────────
cat > "$HOOKS_DIR/pre-commit" << 'EOF'
#!/bin/bash
# Agent-X pre-commit hook
# Blocks commits with .env or secrets

echo "[pre-commit] Checking for secrets..."

# Block .env files
if git diff --cached --name-only | grep -E "^\.env$|^\.env\.local$"; then
    echo ""
    echo "BLOCKED: .env file staged for commit — secrets must not be committed."
    echo "Run: git reset HEAD .env"
    echo ""
    exit 1
fi

# Block files with hardcoded API keys (basic check)
if git diff --cached | grep -E "(DEEPSEEK_API_KEY|GITHUB_TOKEN)\s*=\s*['\"][a-zA-Z0-9_-]{10,}"; then
    echo ""
    echo "BLOCKED: Possible hardcoded secret detected in diff."
    echo "Use os.environ only — no hardcoded keys."
    echo ""
    exit 1
fi

echo "[pre-commit] Clean. Proceeding."
exit 0
EOF

chmod +x "$HOOKS_DIR/pre-commit"
echo "  pre-commit hook installed"

echo ""
echo "=== Hooks installed ==="
echo ""
echo "pre-push  → blocks push to main, runs clean + verify + tests"
echo "pre-commit → blocks .env commits and hardcoded secrets"
echo ""
