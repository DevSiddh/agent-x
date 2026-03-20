"""
Thompson Sampling strategy engine for Agent-X.

Tracks per-bug-signature Beta distributions.
Learns which fix strategies succeed over time.
Requires 50+ pipeline runs to have meaningful signal.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger()


def _state_path() -> Path:
    return Path(__file__).parent.parent.parent / "memory" / "thompson_state.json"


class ThompsonSampler:
    """
    Multi-armed bandit over bug_signature arms.

    Each arm: Beta(alpha, beta)
      alpha = number of accepted fixes for this signature
      beta  = number of rejected fixes for this signature
    New arms start at Beta(1, 1) = uniform — no preference.
    """

    def __init__(self) -> None:
        # {bug_signature: {"alpha": int, "beta": int}}
        self._state: dict[str, dict[str, int]] = {}
        self.load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sample(self, bug_signature: str) -> float:
        """
        Draw a sample from Beta(alpha, beta) for this arm.
        Returns float in [0.0, 1.0].
        New / unseen signatures start at Beta(1, 1).
        """
        arm = self._get_or_create(bug_signature)
        alpha = arm["alpha"]
        beta = arm["beta"]
        value = random.betavariate(alpha, beta)
        log.info(
            "thompson.sampled",
            bug_signature=bug_signature,
            alpha=alpha,
            beta=beta,
            score=round(value, 4),
        )
        return value

    def update(self, bug_signature: str, accepted: bool) -> None:
        """
        Update arm after observing outcome.
        accepted=True  → alpha += 1 (reward)
        accepted=False → beta  += 1 (penalty)
        """
        arm = self._get_or_create(bug_signature)
        if accepted:
            arm["alpha"] += 1
        else:
            arm["beta"] += 1
        log.info(
            "thompson.updated",
            bug_signature=bug_signature,
            accepted=accepted,
            alpha=arm["alpha"],
            beta=arm["beta"],
        )
        self.save()

    # ------------------------------------------------------------------
    # Persistence (never raises — same pattern as memory store)
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load state from thompson_state.json. Silently ignores errors."""
        try:
            path = _state_path()
            if path.exists():
                raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
                self._state = raw
                log.info("thompson.loaded", arms=len(self._state))
        except Exception as exc:  # noqa: BLE001
            log.warning("thompson.load_failed", error=str(exc))
            self._state = {}

    def save(self) -> None:
        """Persist state to thompson_state.json. Silently ignores errors."""
        try:
            path = _state_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            log.warning("thompson.save_failed", error=str(exc))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create(self, bug_signature: str) -> dict[str, int]:
        if bug_signature not in self._state:
            self._state[bug_signature] = {"alpha": 1, "beta": 1}
        return self._state[bug_signature]

    def arm_count(self) -> int:
        return len(self._state)

    def get_arm(self, bug_signature: str) -> dict[str, int]:
        """Return arm state dict (alpha, beta). Creates if absent."""
        return self._get_or_create(bug_signature)


if __name__ == "__main__":
    import sys as _sys

    _sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    import tempfile

    print("=== ThompsonSampler smoke test ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_state = Path(tmpdir) / "thompson_state.json"

        # Patch _state_path in __main__ globals — methods look up globals() at call time
        _orig_fn = globals()["_state_path"]
        globals()["_state_path"] = lambda: tmp_state

        try:
            sampler = ThompsonSampler()
            sig = "synthetic:DependencyError:missing_setuptools:requirements.txt"

            for _ in range(5):
                sampler.update(sig, accepted=True)
            for _ in range(2):
                sampler.update(sig, accepted=False)

            score = sampler.sample(sig)
            arm = sampler.get_arm(sig)

            print(f"  arm alpha={arm['alpha']} beta={arm['beta']}")
            print(f"  sample score={score:.4f}")
            assert arm["alpha"] == 6, f"expected 6 got {arm['alpha']}"  # 1 + 5
            assert arm["beta"] == 3, f"expected 3 got {arm['beta']}"  # 1 + 2
            assert 0.0 <= score <= 1.0

            assert tmp_state.exists(), "state file not written"
            saved = json.loads(tmp_state.read_text())
            assert sig in saved
            print(f"  state file written: {tmp_state}")
            print("PASS")
        finally:
            globals()["_state_path"] = _orig_fn
