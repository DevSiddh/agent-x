"""
phase2/classifier/semantic_fallback.py — BM25-based semantic fallback classifier.

Jina/SentenceTransformers REMOVED — replaced with BM25 keyword matching.
Fallback when RegexClassifier confidence < 0.85.
Groups accepted memory entries by category, scores via BM25 keyword overlap.
Zero RAM overhead. No API calls. No neural networks.
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import structlog

import phase2.memory.similarity as _sim_mod
from phase2.classifier.regex_pass import ClassifierResult

log = structlog.get_logger()

_MIN_ENTRIES_PER_CATEGORY = 3    # lowered from 5 — BM25 works with fewer examples
_CONFIDENCE_CAP   = 0.87
_CONFIDENCE_FLOOR = 0.55


def _memory_path() -> Path:
    return _sim_mod._memory_path()


def _tokenise(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


class EmbeddingClassifier:
    """
    BM25-based semantic fallback classifier.
    Builds per-category keyword profiles from accepted memory entries.
    Classifies by BM25 score against category profiles.
    Zero RAM. Zero API calls.
    """

    def __init__(self) -> None:
        self._category_docs: dict[str, list[str]] = {}

    def build_centroids(self, memory_path: Path) -> dict[str, list[str]]:
        """
        Load accepted entries, group bug_signatures by category.
        Returns {category: [bug_signature strings]} — empty if no data.
        Never raises.
        """
        entries_by_cat: dict[str, list[str]] = defaultdict(list)
        if not memory_path.exists():
            return {}
        try:
            with open(memory_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("decision") == "accepted":
                            cat = entry.get("failure_category", "")
                            sig = entry.get("bug_signature", "")
                            if cat and sig:
                                entries_by_cat[cat].append(sig)
                    except json.JSONDecodeError:
                        continue
        except Exception as exc:
            log.error("semantic_fallback.load_error", error=str(exc))
            return {}

        # Filter categories with enough entries
        result = {
            cat: sigs
            for cat, sigs in entries_by_cat.items()
            if len(sigs) >= _MIN_ENTRIES_PER_CATEGORY
        }
        log.info("semantic_fallback.centroids_built", categories=list(result.keys()))
        return result

    def classify(self, error_lines: list[str], memory_path: Path | None = None) -> ClassifierResult | None:
        """
        Classify error lines using BM25 against category profiles.
        Returns ClassifierResult or None if no confident match.
        Never raises.
        """
        try:
            mp = memory_path or _memory_path()
            if not self._category_docs:
                self._category_docs = self.build_centroids(mp)

            if not self._category_docs:
                log.info("semantic_fallback.no_centroids")
                return None

            from rank_bm25 import BM25Okapi

            query_text = " ".join(error_lines[:20])
            query_tokens = _tokenise(query_text)

            # Build one "document" per category = all signatures joined
            categories = list(self._category_docs.keys())
            corpus = [
                _tokenise(" ".join(self._category_docs[cat]))
                for cat in categories
            ]

            bm25 = BM25Okapi(corpus)
            scores = bm25.get_scores(query_tokens)
            scores = [max(0.0, float(s)) for s in scores]

            if not any(s > 0 for s in scores):
                log.info("semantic_fallback.no_match")
                return None

            # Normalise
            max_s = max(scores)
            norm = [s / max_s for s in scores]

            best_idx = norm.index(max(norm))
            best_cat = categories[best_idx]
            best_score = norm[best_idx]

            # Confidence: scale BM25 score to [_CONFIDENCE_FLOOR, _CONFIDENCE_CAP]
            confidence = _CONFIDENCE_FLOOR + best_score * (_CONFIDENCE_CAP - _CONFIDENCE_FLOOR)
            confidence = min(_CONFIDENCE_CAP, confidence)

            if confidence < _CONFIDENCE_FLOOR:
                log.info("semantic_fallback.below_floor", confidence=round(confidence, 3))
                return None

            # Extract keyword from best matching signature
            best_sigs = self._category_docs[best_cat]
            all_tokens = _tokenise(" ".join(best_sigs))
            common = Counter(t for t in all_tokens if len(t) > 3).most_common(1)
            keyword = common[0][0] if common else best_cat.lower()

            log.info(
                "semantic_fallback.classified",
                category=best_cat,
                confidence=round(confidence, 3),
                keyword=keyword,
            )

            return ClassifierResult(
                category=best_cat,
                confidence=confidence,
                matched_pattern="semantic_bm25",
                keyword=keyword,
                affected_file="unknown",
                bug_signature=f"unknown:{best_cat}:{keyword}:unknown",
                ecosystem="unknown",
            )

        except Exception as exc:
            log.error("semantic_fallback.error", error=str(exc))
            return None


def classify_semantic(
    error_lines: list[str],
    memory_path: Path | None = None,
) -> ClassifierResult | None:
    """Module-level convenience wrapper. Never raises."""
    return EmbeddingClassifier().classify(error_lines, memory_path)
