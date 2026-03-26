"""
phase2/skills/vault.py
Bayesian Skill Vault — Agent-X v3.1.
Skills learn via Beta(α,β) Thompson Sampling.
Auto-generated from successful replans via retrospective.py.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase2.strategy.thompson import ThompsonSampler

log = structlog.get_logger()


class SkillEntry(BaseModel):
    skill_id: str
    constraint_text: str
    domain_tags: list[str] = []
    embedding: list[float] = []
    alpha: int = 1
    beta: int = 1
    source: str = ""
    created_at: str = ""


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors. Returns 0.0 on error."""
    try:
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)
    except Exception:
        return 0.0


class SkillVault:
    VAULT_PATH = _REPO_ROOT / "memory" / "skill_vault.jsonl"
    SKILL_STATE_PATH = _REPO_ROOT / "memory" / "skill_state.json"
    TRUST_GATE = 7  # α+β must reach 7 before Thompson score trusted

    def __init__(self) -> None:
        self._sampler = ThompsonSampler()

    def _load_all(self) -> list[SkillEntry]:
        """Load all entries from skill_vault.jsonl. Never raises."""
        entries: list[SkillEntry] = []
        try:
            if not self.VAULT_PATH.exists():
                return entries
            with open(self.VAULT_PATH, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entries.append(SkillEntry.model_validate_json(line))
        except Exception as exc:
            log.error("skill_vault.load_error", error=str(exc))
        return entries

    def _get_embedding(self, text: str) -> list[float]:
        """BM25 doesn't use embeddings — returns [] always. Kept for interface compat."""
        return []

    def find_relevant(self, goal: str, k: int = 10) -> list[SkillEntry]:
        """
        BM25 keyword search over skill constraint_text + domain_tags.
        Zero RAM, zero API calls. Falls back to returning all skills if BM25 fails.
        """
        entries = self._load_all()
        if not entries:
            return []
        try:
            from rank_bm25 import BM25Okapi
            import re as _re
            def _tok(t: str) -> list[str]:
                return [x for x in _re.split(r"[^a-z0-9]+", t.lower()) if x]
            corpus = [_tok(f"{e.constraint_text} {' '.join(e.domain_tags)}") for e in entries]
            bm25 = BM25Okapi(corpus)
            scores = bm25.get_scores(_tok(goal))
            ranked = sorted(zip(entries, scores), key=lambda x: x[1], reverse=True)
            return [e for e, _ in ranked[:k]]
        except Exception as exc:
            log.warning("skill_vault.bm25_error", error=str(exc))
            return entries[:k]

    def sample_top(self, skills: list[SkillEntry], n: int = 3) -> list[SkillEntry]:
        """
        Thompson-sample skills.
        Below TRUST_GATE: score = 0.5 (uniform prior).
        At/above TRUST_GATE: use Thompson sample.
        Returns top n by score.
        """
        scored: list[tuple[SkillEntry, float]] = []
        for skill in skills:
            trusted = (skill.alpha + skill.beta) >= self.TRUST_GATE
            if trusted:
                score = self._sampler.sample(skill.skill_id)
            else:
                score = 0.5
            scored.append((skill, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in scored[:n]]

    def update(self, skill_ids: list[str], won: bool) -> None:
        """Update Thompson arms for all skill_ids. Never raises."""
        try:
            for sid in skill_ids:
                self._sampler.update(sid, accepted=won)
            log.info("skill_vault.update", skill_ids=skill_ids, won=won)
        except Exception as exc:
            log.error("skill_vault.update_error", error=str(exc))

    def add_skill(self, entry: SkillEntry) -> None:
        """
        Append skill to vault. Lazy-embed if embedding is empty.
        Init Thompson arm. Never raises.
        """
        try:
            # BM25 mode — no embeddings needed, clear any stale vectors
            if entry.embedding:
                entry = entry.model_copy(update={"embedding": []})
            if not entry.created_at:
                entry = entry.model_copy(
                    update={"created_at": datetime.now(timezone.utc).date().isoformat()}
                )
            self.VAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(self.VAULT_PATH, "a", encoding="utf-8") as f:
                f.write(entry.model_dump_json() + "\n")
            # Init Thompson arm
            self._sampler._get_or_create(entry.skill_id)
            self._sampler.save()
            log.info("skill_vault.add_skill", skill_id=entry.skill_id)
        except Exception as exc:
            log.error("skill_vault.add_skill_error", skill_id=entry.skill_id, error=str(exc))

    def get_context_block(self, goal: str) -> str:
        """
        Find relevant skills, sample top 3, format as context block.
        Returns "" if vault is empty. Never raises.
        """
        try:
            relevant = self.find_relevant(goal)
            if not relevant:
                return ""
            top = self.sample_top(relevant)
            lines = []
            for skill in top:
                lines.append(f"[SKILL: {skill.skill_id}]")
                lines.append(skill.constraint_text)
                lines.append("")
            return "\n".join(lines)
        except Exception as exc:
            log.error("skill_vault.context_block_error", error=str(exc))
            return ""


if __name__ == "__main__":
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmp:
        vault = SkillVault()
        vault.VAULT_PATH = Path(tmp) / "skill_vault.jsonl"
        vault.SKILL_STATE_PATH = Path(tmp) / "skill_state.json"
        vault._sampler = ThompsonSampler()

        entry = SkillEntry(
            skill_id="avoid_circular_imports",
            constraint_text="Always import inside function body to avoid circular imports.",
            domain_tags=["fastapi", "pydantic"],
        )
        vault.add_skill(entry)
        relevant = vault.find_relevant("fastapi circular import error")
        assert len(relevant) >= 1
        top = vault.sample_top(relevant)
        assert len(top) >= 1
        block = vault.get_context_block("fastapi import error")
        assert "avoid_circular_imports" in block
        print("vault.py smoke test PASSED")
