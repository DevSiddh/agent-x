#!/bin/bash
# Run GitHub Actions locally using act
# Catches runner errors BEFORE they hit GitHub
#
# Install act first (one time):
#   Windows: choco install act-cli
#   OR download from: https://github.com/nektos/act/releases
#
# Usage:
#   bash scripts/run_act.sh          → simulate push event
#   bash scripts/run_act.sh --list   → list all jobs
#   bash scripts/run_act.sh --job test → run specific job

echo ""
echo "=== Agent-X Local CI Runner (act) ==="
echo ""

# Check act is installed
if ! command -v act &> /dev/null; then
    echo "act not installed. Install it first:"
    echo ""
    echo "  Windows (chocolatey):  choco install act-cli"
    echo "  Windows (winget):      winget install nektos.act"
    echo "  Manual:                https://github.com/nektos/act/releases"
    echo ""
    echo "Then re-run: bash scripts/run_act.sh"
    echo ""
    exit 1
fi

# Load secrets from .env if present
SECRETS=""
if [ -f ".env" ]; then
    echo "Loading secrets from .env..."
    SECRETS="--secret-file .env"
fi

# Run act with ubuntu-latest simulation
echo "Simulating GitHub Actions push event..."
echo "This matches exactly what GitHub will run."
echo ""

act push \
    $SECRETS \
    --platform ubuntu-latest=catthehacker/ubuntu:act-latest \
    --workflows .github/workflows/ci.yml \
    "$@"

EXIT=$?

echo ""
if [ $EXIT -eq 0 ]; then
    echo "LOCAL CI PASSED — safe to push to GitHub"
else
    echo "LOCAL CI FAILED — fix before pushing"
    echo "Same error would appear on GitHub"
fi
echo ""
exit $EXIT
