"""
phase2/memory/similarity.py — BM25 + TF-IDF + Thompson hybrid search.

Jina/SentenceTransformers REMOVED — was 800MB RAM on a 2GB VPS (OOM risk).
Replaced with rank_bm25 (BM25) — <10MB RAM, zero API calls, zero cost.

find_similar()  : reuse bypass (pipeline.py stage 4.5) — return format unchanged
find_for_rag()  : RAG injection (context_builder.py stage 5)
Hybrid          : 0.50 × BM25 + 0.25 × TF-IDF + 0.25 × Thompson
"""

import json
import math
import re
import sys
from pathlib import Path

import structlog

log = structlog.get_logger()

# ── Thresholds & weights ─────────────────────────────────────────────────────
_SIMILARITY_THRESHOLD = 0.45   # BM25 scores are relative — single-entry corpus scores ~0.5
_RAG_HIGH_THRESHOLD   = 0.55
_RAG_LOW_THRESHOLD    = 0.35
_TOP_K                = 3

_W_BM25     = 0.50
_W_TFIDF    = 0.25
_W_THOMPSON = 0.25


# ── Path helpers ─────────────────────────────────────────────────────────────

def _memory_path() -> Path:
    return Path(__file__).resolve().parents[2] / "memory" / "memory.jsonl"


def _thompson_state_path() -> Path:
    return Path(__file__).resolve().parents[2] / "memory" / "thompson_state.json"


# ── Thompson helpers ─────────────────────────────────────────────────────────

def _load_thompson_state() -> dict:
    path = _thompson_state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.error("similarity.thompson_load_failed", error=str(exc))
        return {}


def _thompson_success_rate(bug_signature: str, state: dict) -> float:
    arm = state.get(bug_signature)
    if arm is None:
        return 0.5
    alpha = arm.get("alpha", 1)
    beta  = arm.get("beta", 1)
    total = alpha + beta
    return alpha / total if total > 0 else 0.5


# ── Tokeniser (shared by BM25 + TF-IDF) ─────────────────────────────────────

def _tokenise(text: str) -> list[str]:
    """Split on non-alphanumeric chars, lowercase. Fast, no deps."""
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


# ── BM25 scorer ──────────────────────────────────────────────────────────────

def _bm25_scores(query: str, corpus: list[str]) -> list[float]:
    """
    Pure-Python BM25 (rank_bm25.BM25Okapi). <10MB RAM. Never raises.
    Returns list of floats same length as corpus, normalised to [0,1].
    """
    if not corpus:
        return []
    try:
        from rank_bm25 import BM25Okapi
        tokenised = [_tokenise(doc) for doc in corpus]
        bm25 = BM25Okapi(tokenised)
        scores = bm25.get_scores(_tokenise(query))
        # Clip negatives, normalise to [0,1]
        scores = [max(0.0, float(s)) for s in scores]
        max_s = max(scores) if max(scores) > 0 else 1.0
        return [s / max_s for s in scores]
    except Exception as exc:
        log.warning("similarity.bm25_error", error=str(exc))
        return [0.0] * len(corpus)


# ── TF-IDF scorer (char ngram fallback / second layer) ───────────────────────

def _tfidf_scores(query: str, corpus: list[str]) -> list[float]:
    """sklearn TF-IDF char_wb ngram(2,4). Returns list normalised [0,1]."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity as cos_sim
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
        matrix = vec.fit_transform(corpus + [query])
        scores = cos_sim(matrix[-1], matrix[:-1])[0].tolist()
        return [float(s) for s in scores]
    except Exception as exc:
        log.warning("similarity.tfidf_error", error=str(exc))
        return [0.0] * len(corpus)


# ── MemoryEngine ─────────────────────────────────────────────────────────────

class MemoryEngine:
    """
    BM25 + TF-IDF + Thompson hybrid search over accepted memory entries.
    Hybrid score = 0.50 × BM25 + 0.25 × TF-IDF + 0.25 × Thompson
    Zero neural networks. Zero API calls. ~10MB RAM.
    """

    def _load_successful(self) -> list[dict]:
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
        Score all entries.
        Returns list of (entry, hybrid_score, s_bm25, s_tfidf).
        query = full natural-language string for BM25
        """
        if not entries:
            return []

        # Build query string — natural language for BM25
        query = f"{category} {matched_pattern} {keyword} {affected_file} {query_sig}"

        # Build corpus — combine bug_signature + patch_applied snippet
        corpus = []
        for e in entries:
            sig = e.get("bug_signature", "")
            patch_snippet = (e.get("patch_applied") or "")[:200]
            corpus.append(f"{sig} {patch_snippet}")

        bm25   = _bm25_scores(query, corpus)
        tfidf  = _tfidf_scores(query_sig, [e.get("bug_signature", "") for e in entries])
        thompson_state = _load_thompson_state()

        results: list[tuple[dict, float, float, float]] = []
        for i, entry in enumerate(entries):
            s_bm25   = bm25[i]
            s_tfidf  = tfidf[i]
            s_thompson = _thompson_success_rate(
                entry.get("bug_signature", ""), thompson_state
            )
            # File match boost
            boost = 0.05 if affected_file and affected_file in entry.get("bug_signature", "") else 0.0
            hybrid = _W_BM25 * s_bm25 + _W_TFIDF * s_tfidf + _W_THOMPSON * s_thompson + boost
            results.append((entry, min(hybrid, 1.0), s_bm25, s_tfidf))

        return results

    def find_similar(
        self,
        query_sig: str,
        affected_file: str = "",
        category: str = "",
        matched_pattern: str = "",
        keyword: str = "",
    ) -> dict | None:
        """
        Reuse bypass — return best match above _SIMILARITY_THRESHOLD.
        Return format unchanged from original (pipeline.py stage 4.5).
        """
        entries = self._load_successful()
        if not entries:
            return None

        scored = self._score_entries(
            entries, query_sig, category, matched_pattern, keyword, affected_file
        )
        if not scored:
            return None

        best_entry, best_score, s_bm25, s_tfidf = max(scored, key=lambda x: x[1])

        if best_score < _SIMILARITY_THRESHOLD:
            log.info(
                "similarity.no_match",
                query=query_sig[:60],
                best_score=round(best_score, 3),
                threshold=_SIMILARITY_THRESHOLD,
            )
            return None

        log.info(
            "similarity.match_found",
            query=query_sig[:60],
            match=best_entry.get("bug_signature", "")[:60],
            score=round(best_score, 3),
            bm25=round(s_bm25, 3),
            tfidf=round(s_tfidf, 3),
        )
        return {
            "patch": best_entry.get("patch_applied", ""),
            "match_score": round(best_score, 3),
            "metadata": best_entry,
        }

    def find_for_rag(
        self,
        query_sig: str,
        affected_file: str = "",
        category: str = "",
        matched_pattern: str = "",
        keyword: str = "",
        top_k: int = _TOP_K,
    ) -> list[dict]:
        """
        RAG injection — return top_k entries above _RAG_LOW_THRESHOLD.
        Each result tagged [HIGH RELEVANCE] or [LOW RELEVANCE].
        """
        entries = self._load_successful()
        if not entries:
            return []

        scored = self._score_entries(
            entries, query_sig, category, matched_pattern, keyword, affected_file
        )

        above = [(e, s, b, t) for e, s, b, t in scored if s >= _RAG_LOW_THRESHOLD]
        above.sort(key=lambda x: x[1], reverse=True)
        top = above[:top_k]

        results = []
        for entry, score, s_bm25, s_tfidf in top:
            tag = "[HIGH RELEVANCE]" if score >= _RAG_HIGH_THRESHOLD else "[LOW RELEVANCE]"
            results.append({
                "patch": entry.get("patch_applied", ""),
                "score": round(score, 3),
                "tag": tag,
                "metadata": entry,
            })

        log.info(
            "similarity.rag_results",
            query=query_sig[:60],
            returned=len(results),
            top_score=round(top[0][1], 3) if top else 0,
        )
        return results


if __name__ == "__main__":
    engine = MemoryEngine()
    result = engine.find_similar(
        query_sig="synthetic:DependencyError:pkg_resources:requirements.txt",
        affected_file="requirements.txt",
        category="DependencyError",
        matched_pattern="ModuleNotFoundError",
        keyword="pkg_resources",
    )
    print(f"find_similar: {result['match_score'] if result else 'no match'}")
    rag = engine.find_for_rag(
        query_sig="synthetic:DependencyError:pkg_resources:requirements.txt",
        affected_file="requirements.txt",
        category="DependencyError",
    )
    print(f"find_for_rag: {len(rag)} results")
    print("similarity.py smoke test PASSED")
