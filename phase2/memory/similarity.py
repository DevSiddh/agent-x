"""
phase2/memory/similarity.py — Triple-hybrid semantic search engine.

find_similar()  : reuse bypass (pipeline.py stage 4.5) — return format unchanged
find_for_rag()  : RAG injection (context_builder.py stage 5) — NEW method
Hybrid          : 0.30 × TF-IDF + 0.45 × Jina-dense + 0.25 × Thompson
Fallback        : when Jina unavailable → weights redistribute to TF-IDF + Thompson only
"""

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

log = structlog.get_logger()

# ── Thresholds & weights ─────────────────────────────────────────────────────
_SIMILARITY_THRESHOLD = 0.85   # reuse bypass threshold — unchanged (pipeline.py)
_RAG_HIGH_THRESHOLD   = 0.70   # [HIGH RELEVANCE] tag in context injection
_RAG_LOW_THRESHOLD    = 0.55   # [LOW RELEVANCE] tag — below = no injection
_TOP_K                = 3      # max entries injected per find_for_rag() call

_W_TFIDF    = 0.30
_W_DENSE    = 0.45
_W_THOMPSON = 0.25

# Module-level Jina model cache — populated by _get_embedding_model()
_MODEL = None  # type: ignore[assignment]


# ── Path helpers ─────────────────────────────────────────────────────────────

def _memory_path() -> Path:
    return Path(__file__).resolve().parents[2] / "memory" / "memory.jsonl"


def _thompson_state_path() -> Path:
    return Path(__file__).resolve().parents[2] / "memory" / "thompson_state.json"


# ── Thompson helpers ─────────────────────────────────────────────────────────

def _load_thompson_state() -> dict:
    """Load Thompson state — returns empty dict if missing/corrupt."""
    path = _thompson_state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.error("similarity.thompson_load_failed", error=str(exc))
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


# ── Jina helpers ─────────────────────────────────────────────────────────────

def _thaw(category: str, matched_pattern: str, keyword: str, affected_file: str) -> str:
    """Convert structured bug fields into natural language for Jina embedding.

    Example:
        _thaw("DependencyError", "ModuleNotFoundError", "pkg_resources", "requirements.txt")
        → "DependencyError (ModuleNotFoundError) involving pkg_resources in file requirements.txt"
    """
    return (
        f"{category} ({matched_pattern}) "
        f"involving {keyword} in file {affected_file}"
    )


def _get_embedding_model():  # → SentenceTransformer | None
    """Lazy-load Jina model — cached at module level after first call. Never raises."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    try:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer(
            "jinaai/jina-embeddings-v2-small-code", trust_remote_code=True
        )
        return _MODEL
    except Exception as exc:
        log.warning("similarity.jina_unavailable", error=str(exc))
        return None


# ── MemoryEngine ─────────────────────────────────────────────────────────────

class MemoryEngine:
    """
    Triple-hybrid semantic search over accepted memory entries.

    Hybrid score = 0.30 × TF-IDF + 0.45 × Jina-dense + 0.25 × Thompson
    When Jina is unavailable, weights redistribute:
        hybrid = (0.30/0.55) × TF-IDF + (0.25/0.55) × Thompson
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

    def _score_entries(
        self,
        entries: list[dict],
        query_sig: str,
        category: str,
        matched_pattern: str,
        keyword: str,
        affected_file: str,
    ) -> list[tuple[dict, float, float, float]]:
        """
        Score all entries. Returns list of (entry, hybrid_score, s_tfidf, s_dense).
        Used by both find_similar() and find_for_rag().

        TF-IDF : over raw bug_signature strings (char_wb, ngram 2-4)
        Dense  : over thawed strings via Jina model
        Hybrid : _W_TFIDF×s_tfidf + _W_DENSE×s_dense + _W_THOMPSON×thompson_rate
        Boost  : +0.05 if affected_file in entry bug_signature

        If Jina unavailable → s_dense=0.0, weights auto-redistribute:
            hybrid = (0.30/(0.30+0.25))×s_tfidf + (0.25/(0.30+0.25))×thompson_rate
        """
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        if not entries:
            return []

        # ── TF-IDF over raw bug_signature strings ─────────────────────────
        corpus = [e.get("bug_signature", "") for e in entries]
        try:
            vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
            all_texts = corpus + [query_sig]
            tfidf_matrix = vectorizer.fit_transform(all_texts)
            query_vec = tfidf_matrix[-1]
            corpus_vecs = tfidf_matrix[:-1]
            tfidf_scores: list[float] = cosine_similarity(query_vec, corpus_vecs)[0].tolist()
        except Exception as exc:
            log.error("similarity.tfidf_error", error=str(exc))
            tfidf_scores = [0.0] * len(entries)

        # ── Jina dense over thawed strings ────────────────────────────────
        model = _get_embedding_model()
        dense_scores: list[float] = [0.0] * len(entries)
        if model is not None:
            try:
                query_thawed = _thaw(category, matched_pattern, keyword, affected_file)
                corpus_thawed: list[str] = []
                for e in entries:
                    parts = e.get("bug_signature", ":::").split(":", 3)
                    e_cat = parts[1] if len(parts) > 1 else category
                    e_kw  = parts[2] if len(parts) > 2 else keyword
                    e_af  = parts[3] if len(parts) > 3 else affected_file
                    # matched_pattern not stored in memory — use keyword as proxy
                    corpus_thawed.append(_thaw(e_cat, e_kw, e_kw, e_af))

                q_emb = model.encode([query_thawed], normalize_embeddings=True)
                c_embs = model.encode(corpus_thawed, normalize_embeddings=True)
                dense_scores = cosine_similarity(q_emb, c_embs)[0].tolist()
            except Exception as exc:
                log.warning("similarity.dense_error", error=str(exc))

        # ── Hybrid scoring ────────────────────────────────────────────────
        thompson_state = _load_thompson_state()
        results: list[tuple[dict, float, float, float]] = []

        for i, entry in enumerate(entries):
            s_tfidf = float(tfidf_scores[i])
            s_dense = float(dense_scores[i])
            ts_rate = _thompson_success_rate(entry.get("bug_signature", ""), thompson_state)

            if model is not None:
                hybrid = _W_TFIDF * s_tfidf + _W_DENSE * s_dense + _W_THOMPSON * ts_rate
            else:
                # Redistribute weights between TF-IDF and Thompson
                w_tfidf = _W_TFIDF / (_W_TFIDF + _W_THOMPSON)
                w_ts    = _W_THOMPSON / (_W_TFIDF + _W_THOMPSON)
                hybrid  = w_tfidf * s_tfidf + w_ts * ts_rate

            # Filename boost: +0.05 if affected_file appears in entry's bug_signature
            if affected_file and affected_file in entry.get("bug_signature", ""):
                hybrid += 0.05

            results.append((entry, hybrid, s_tfidf, s_dense))

        return results

    def find_similar(
        self,
        bug_signature: str,
        affected_file: str,
    ) -> dict | None:
        """
        Reuse bypass — finds single best accepted entry above _SIMILARITY_THRESHOLD (0.85).
        Called by pipeline.py stage 4.5. Return format UNCHANGED.

        Returns:
            dict with keys: patch, match_score, metadata — or None if no good match.
        """
        entries = self._load_successful()
        if not entries:
            log.info("similarity.no_entries")
            return None

        # Parse category and keyword from bug_signature for dense thawing.
        # Format: repo:Category:keyword:file
        parts = bug_signature.split(":", 3)
        category = parts[1] if len(parts) > 1 else ""
        keyword  = parts[2] if len(parts) > 2 else ""
        # matched_pattern not available here — use keyword as fallback for thaw

        scored = self._score_entries(
            entries,
            query_sig=bug_signature,
            category=category,
            matched_pattern=keyword,
            keyword=keyword,
            affected_file=affected_file,
        )
        if not scored:
            return None

        scored.sort(key=lambda x: x[1], reverse=True)
        top_entry, top_score, _s_tfidf, _s_dense = scored[0]

        log.info(
            "similarity.scored",
            query=bug_signature,
            top_score=round(top_score, 4),
            threshold=_SIMILARITY_THRESHOLD,
        )

        if top_score < _SIMILARITY_THRESHOLD:
            return None

        return {
            "patch": top_entry.get("patch_applied", ""),
            "match_score": round(top_score, 4),
            "metadata": {
                "bug_signature":  top_entry.get("bug_signature", ""),
                "failure_category": top_entry.get("failure_category", ""),
                "model_used":     top_entry.get("model_used", ""),
                "repo":           top_entry.get("repo", ""),
                "run_id":         top_entry.get("run_id", ""),
            },
        }

    def find_for_rag(
        self,
        category: str,
        matched_pattern: str,
        keyword: str,
        affected_file: str,
        bug_signature: str,
    ) -> list[tuple[dict, float]]:
        """
        RAG injection — returns up to _TOP_K accepted entries with scores >= _RAG_LOW_THRESHOLD.
        Sorted by hybrid_score descending.
        Logs Δ = s_dense - s_tfidf for monitoring.
        Called by context_builder.py only. Never called by pipeline.py.

        Returns:
            list of (entry_dict, hybrid_score) — empty if nothing crosses 0.55.
        """
        entries = self._load_successful()
        if not entries:
            return []

        scored = self._score_entries(
            entries,
            query_sig=bug_signature,
            category=category,
            matched_pattern=matched_pattern,
            keyword=keyword,
            affected_file=affected_file,
        )

        results: list[tuple[dict, float]] = []
        for entry, hybrid, s_tfidf, s_dense in scored:
            delta = s_dense - s_tfidf
            log.info(
                "similarity.rag_candidate",
                score=round(hybrid, 4),
                delta=round(delta, 4),
                sig=entry.get("bug_signature", ""),
            )
            if hybrid >= _RAG_LOW_THRESHOLD:
                results.append((entry, hybrid))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:_TOP_K]


# ── Smoke test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    engine = MemoryEngine()
    result = engine.find_similar(
        bug_signature="synthetic:DependencyError:pkg_resources:requirements.txt",
        affected_file="requirements.txt",
    )
    if result:
        print(
            f"PASS  find_similar: score={result['match_score']} "
            f"sig={result['metadata']['bug_signature']}"
        )
    else:
        print("PASS  find_similar: no match (memory may be empty or below threshold)")

    rag = engine.find_for_rag(
        category="DependencyError",
        matched_pattern="ModuleNotFoundError",
        keyword="pkg_resources",
        affected_file="requirements.txt",
        bug_signature="synthetic:DependencyError:pkg_resources:requirements.txt",
    )
    print(f"PASS  find_for_rag: {len(rag)} entries returned")
    print("similarity.py smoke test PASSED")
