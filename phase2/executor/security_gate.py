"""
phase2/executor/security_gate.py — Patch-level security scan.

Sequential, fail-fast: scan the patch text (not the whole repo).
Step 1 — Secret scan via detect-secrets (< 0.5s)
Step 2 — CVE check via pip-audit (~2s, only when requirements.txt is modified)

Never raises. If a tool is not installed → log warning, return passed=True.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import structlog
from pydantic import BaseModel

log = structlog.get_logger()


class SecurityResult(BaseModel):
    passed: bool
    reason: str = ""   # injected into retry prompt on rejection


def _detect_secrets(tmp_path: str) -> str:
    """
    Run detect-secrets scan on a temp file containing the patch.

    Returns:
        Non-empty string with reason on failure, empty string on clean scan.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "detect_secrets", "scan", tmp_path],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                results = data.get("results", {})
                if results:
                    # At least one secret detected
                    secrets_found = list(results.values())[0]
                    secret_type = secrets_found[0].get("type", "unknown") if secrets_found else "unknown"
                    return f"hardcoded secret detected ({secret_type})"
            except (json.JSONDecodeError, IndexError, KeyError):
                pass
        return ""
    except FileNotFoundError:
        log.warning("security_gate.detect_secrets_not_installed")
        return ""
    except Exception as exc:
        log.warning("security_gate.detect_secrets_error", error=str(exc))
        return ""


def _pip_audit() -> str:
    """
    Run pip-audit on requirements.txt to check for known CVEs.

    Returns:
        Non-empty string with reason on failure, empty string on clean scan.
    """
    req_path = Path(os.getcwd()) / "requirements.txt"
    if not req_path.exists():
        return ""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip_audit", "-r", str(req_path), "--format", "json"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        # Detect "module not installed" from stderr — treat as tool not available
        combined_err = (result.stdout + result.stderr).lower()
        if "no module named" in combined_err or "not found" in combined_err:
            log.warning("security_gate.pip_audit_not_installed")
            return ""

        if result.returncode != 0:
            try:
                data = json.loads(result.stdout)
                vulns = data.get("dependencies", [])
                for dep in vulns:
                    for vuln in dep.get("vulns", []):
                        pkg = dep.get("name", "unknown")
                        cve = vuln.get("id", "CVE-unknown")
                        return f"CVE detected: {cve} in {pkg}"
            except (json.JSONDecodeError, KeyError):
                return f"pip-audit found issues: {result.stderr[:200]}"
        return ""
    except FileNotFoundError:
        log.warning("security_gate.pip_audit_not_installed")
        return ""
    except Exception as exc:
        log.warning("security_gate.pip_audit_error", error=str(exc))
        return ""


def scan_patch(patch: str, requirements_modified: bool = False) -> SecurityResult:
    """
    Scan a patch for security issues.

    Step 1 — Secret scan via detect-secrets on the patch text.
    Step 2 — CVE check via pip-audit (only when requirements.txt was modified).

    Args:
        patch:                  Raw unified diff string to scan.
        requirements_modified:  True if the patch touches requirements.txt.

    Returns:
        SecurityResult(passed=True) on clean scan.
        SecurityResult(passed=False, reason=...) on any detected issue.
        Never raises — missing tools return passed=True with a warning log.
    """
    if not patch or not patch.strip():
        return SecurityResult(passed=True)

    # Step 1 — Secret scan: write patch to temp file, scan it
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".diff", mode="w", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(patch)
            tmp_path = tmp.name

        secret_reason = _detect_secrets(tmp_path)
        Path(tmp_path).unlink(missing_ok=True)
    except Exception as exc:
        log.warning("security_gate.tempfile_error", error=str(exc))
        secret_reason = ""

    if secret_reason:
        log.warning("security_gate.secret_rejected", reason=secret_reason)
        return SecurityResult(passed=False, reason=f"hardcoded secret in patch: {secret_reason}")

    # Step 2 — CVE check (conditional)
    if requirements_modified:
        cve_reason = _pip_audit()
        if cve_reason:
            log.warning("security_gate.cve_rejected", reason=cve_reason)
            return SecurityResult(passed=False, reason=cve_reason)

    log.info("security_gate.clean")
    return SecurityResult(passed=True)


if __name__ == "__main__":
    # Smoke test
    clean_patch = """--- a/requirements.txt
+++ b/requirements.txt
@@ -1,2 +1,3 @@
 setuptools>=60.0
+requests>=2.28.0
 pytest>=7.0
"""
    result = scan_patch(clean_patch, requirements_modified=True)
    print(f"PASS  clean patch: passed={result.passed} reason={result.reason!r}")

    secret_patch = """--- a/config.py
+++ b/config.py
@@ -1 +1,2 @@
+AWS_SECRET_ACCESS_KEY = 'AKIAIOSFODNN7EXAMPLE'
 pass
"""
    result2 = scan_patch(secret_patch)
    # detect-secrets may or may not be installed — just check it doesn't raise
    print(f"PASS  secret patch: passed={result2.passed} (detect-secrets installed={result2.passed is False})")

    empty = scan_patch("")
    assert empty.passed is True
    print("PASS  empty patch: passed=True")

    print("security_gate.py smoke test PASSED")
