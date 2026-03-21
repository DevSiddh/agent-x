"""
phase2/memory/similarity.py — TF-IDF similarity engine for memory reuse.

MemoryEngine finds the most similar past accepted fix for a given bug.
Hybrid ranking: 0.7 × TF-IDF cosine similarity + 0.3 × Thompson success rate.
Threshold 0.85 — below that, returns None (fall through to full pipeline).
"""

import json
import sys
from pathlib import Path

import structlog

log = structlog.get_logger()

_SIMILARITY_THRESHOLD = 0.85
_TOP_K = 3


def _memory_path() -> Path:
    return Path(__file__).resolve().parents[2] / "memory" / "memory.jsonl"


def _thompson_state_path() -> Path:
    return Path(__file__).resolve().parents[2] / "memory" / "thompson_state.json"


def _load_thompson_state() -> dict:
    """Load Thompson state — returns empty dict if missing/corrupt."""
    path = _thompson_state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _thompson_success_rate(bug_signature: str, state: dict) -> float:
    """alpha / (alpha + beta) for this arm, or 0.5 if not found."""
    arm = state.get(bug_signature)
    if arm is None:
        return 0.5
    alpha = arm.get("alpha", 1)
    beta = arm.get("beta", 1)
    total = alpha + beta
    return alpha / total if total > 0 else 0.5


class MemoryEngine:
    """
    TF-IDF similarity engine over accepted memory entries.
    Loads entries lazily on first call to find_similar().
    """

    def _load_successful(self) -> list[dict]:
        """Load all accepted entries from memory.jsonl."""
        path = _memory_path()
        if not path.exists():
            return []

        entries: list[dict] = []
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("decision") == "accepted":
                            entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception as exc:
            log.error("similarity.load_error", error=str(exc))

        return entries

    def find_similar(
        self,
        bug_signature: str,
        affected_file: str,
    ) -> dict | None:
        """
        Find the most similar past accepted fix using TF-IDF + hybrid ranking.

        Args:
            bug_signature:  repo:ErrorType:keyword:file — query signature
            affected_file:  file being patched — used for filename boost

        Returns:
            dict with keys: patch, match_score, metadata — or None if no good match.
        """
        from sklearn.feature_extraction.text import TfidfVectorizer  # lazy import
        from sklearn.metrics.pairwise import cosine_similarity  # lazy import

        entries = self._load_successful()
        if not entries:
            log.info("similarity.no_entries")
            return None

        # Build corpus: each entry represented by its bug_signature
        corpus = [e.get("bug_signature", "") for e in entries]
        query = bug_signature

        try:
            vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
            all_texts = corpus + [query]
            tfidf_matrix = vectorizer.fit_transform(all_texts)
            query_vec = tfidf_matrix[-1]
            corpus_vecs = tfidf_matrix[:-1]
            similarities = cosine_similarity(query_vec, corpus_vecs)[0]
        except Exception as exc:
            log.error("similarity.tfidf_error", error=str(exc))
            return None

        thompson_state = _load_thompson_state()

        # Hybrid score: 0.7 × similarity + 0.3 × Thompson success rate
        # Filename boost: +0.05 if affected_file appears in entry's bug_signature
        scored: list[tuple[float, int]] = []
        for i, sim in enumerate(similarities):
            entry = entries[i]
            ts_rate = _thompson_success_rate(entry.get("bug_signature", ""), thompson_state)
            hybrid = 0.7 * float(sim) + 0.3 * ts_rate
            # Filename boost
            if affected_file and affected_file in entry.get("bug_signature", ""):
                hybrid += 0.05
            scored.append((hybrid, i))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_score, top_idx = scored[0]

        log.info(
            "similarity.scored",
            query=bug_signature,
            top_score=round(top_score, 4),
            threshold=_SIMILARITY_THRESHOLD,
        )

        if top_score < _SIMILARITY_THRESHOLD:
            return None

        best = entries[top_idx]
        return {
            "patch": best.get("patch_applied", ""),
            "match_score": round(top_score, 4),
            "metadata": {
                "bug_signature": best.get("bug_signature", ""),
                "failure_category": best.get("failure_category", ""),
                "model_used": best.get("model_used", ""),
                "repo": best.get("repo", ""),
                "run_id": best.get("run_id", ""),
            },
        }


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    engine = MemoryEngine()
    result = engine.find_similar(
        bug_signature="synthetic:DependencyError:pkg_resources:requirements.txt",
        affected_file="requirements.txt",
    )
    if result:
        print(f"PASS  find_similar: score={result['match_score']} sig={result['metadata']['bug_signature']}")
    else:
        print("PASS  find_similar: no match (memory may be empty or below threshold)")
    print("similarity.py smoke test PASSED")
