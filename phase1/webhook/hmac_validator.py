"""
HMAC-SHA256 signature validator for GitHub webhooks.
Reads body + signature header directly from the FastAPI Request object.
"""

import hashlib
import hmac
import os

import structlog
from fastapi import Request

log = structlog.get_logger()


async def validate(request: Request) -> bool:
    """
    Validate a GitHub webhook HMAC-SHA256 signature.

    Reads raw body from request (FastAPI caches it, safe to re-read downstream).
    Reads X-Hub-Signature-256 from request headers.

    Args:
        request: The incoming FastAPI Request object.

    Returns:
        True if signature is valid, False otherwise.

    Raises:
        EnvironmentError: If GITHUB_WEBHOOK_SECRET is not set.
    """
    secret_str = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    if not secret_str:
        raise EnvironmentError("GITHUB_WEBHOOK_SECRET is not set")

    sig_header = request.headers.get("X-Hub-Signature-256", "")
    if not sig_header:
        log.warning("hmac.missing_signature")
        return False

    body = await request.body()
    expected = "sha256=" + hmac.new(secret_str.encode(), body, hashlib.sha256).hexdigest()
    result = hmac.compare_digest(expected, sig_header)

    if not result:
        log.warning("hmac.signature_mismatch")

    return result


if __name__ == "__main__":
    import asyncio
    import hashlib
    import hmac as _hmac
    import json

    # ── Smoke test ────────────────────────────────────────────────────────────
    os.environ["GITHUB_WEBHOOK_SECRET"] = "smoke-secret"

    payload = json.dumps({"action": "completed"}).encode()
    secret  = b"smoke-secret"
    good_sig = "sha256=" + _hmac.new(secret, payload, hashlib.sha256).hexdigest()
    bad_sig  = "sha256=deadbeef"

    class _MockRequest:
        """Minimal stub that mimics FastAPI Request for smoke testing."""
        def __init__(self, body: bytes, sig: str) -> None:
            self._body = body
            self.headers = {"X-Hub-Signature-256": sig}

        async def body(self) -> bytes:
            return self._body

    async def _run() -> None:
        ok  = await validate(_MockRequest(payload, good_sig))   # type: ignore[arg-type]
        bad = await validate(_MockRequest(payload, bad_sig))    # type: ignore[arg-type]
        missing = await validate(_MockRequest(payload, ""))     # type: ignore[arg-type]

        assert ok  is True,  f"Expected True, got {ok}"
        assert bad is False, f"Expected False, got {bad}"
        assert missing is False, f"Expected False for missing sig, got {missing}"
        print("hmac_validator smoke test PASSED")

    asyncio.run(_run())
