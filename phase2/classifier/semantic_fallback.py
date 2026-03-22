"""
phase2/classifier/semantic_fallback.py — Centroid-based semantic classifier.

Fallback when RegexClassifier confidence < 0.85.
Builds per-category centroids from accepted memory.jsonl entries.
Classifies by cosine similarity to closest centroid.
Reuses Jina model from similarity.py — never loads a second model.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

import structlog

import phase2.memory.similarity as _sim_mod
from phase2.classifier.regex_pass import ClassifierResult

log = structlog.get_logger()

_MIN_ENTRIES_PER_CATEGORY = 5    # below this → centroid unreliable → skip category
_CONFIDENCE_CAP   = 0.87         # never claims same certainty as regex (0.90-0.99)
_CONFIDENCE_FLOOR = 0.55         # below this → return None → observer mode
_ALPHA            = 0.5          # margin amplifier in confidence formula


def _memory_path() -> Path:
    """Path to memory.jsonl — same root as similarity.py uses."""
    return _sim_mod._memory_path()


class EmbeddingClassifier:
    """
    Centroid-based semantic classifier.
    Fallback when RegexClassifier confidence < 0.85.

    Builds centroids per category from accepted memory.jsonl entries
    (min 5 per category — below that the centroid is unreliable).
    Classifies by cosine similarity to the closest centroid.
    Confidence = min(0.87, S_max + 0.5 × (S_max − S_next))

    Reuses Jina model from phase2.memory.similarity — no second model loaded.
    All methods never raise — caller always gets None on failure.
    """

    def __init__(self) -> None:
        self._centroids: dict[str, object] | None = None        # np.ndarray per cat
        self._category_keywords: dict[str, str] = {}

    def build_centroids(self, memory_path: Path) -> dict[str, list[float]]:
        """
        Load accepted entries from memory.jsonl.
        Group by failure_category.
        Embed thawed bug fields for each entry via Jina.
        Average embeddings per category → normalised centroid vector.
        Skip any category with < _MIN_ENTRIES_PER_CATEGORY entries.

        Returns {category: centroid_vector} — empty dict if no model available.
        Never raises.
        """
        model = _sim_mod._get_embedding_model()
        if model is None:
            return {}

        # Load accepted entries grouped by category
        entries_by_cat: dict[str, list[dict]] = {}
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
                            if cat:
                                entries_by_cat.setdefault(cat, []).append(entry)
                    except json.JSONDecodeError:
                        continue
        except OSError as exc:
            log.error("semantic_fallback.memory_load_error", error=str(exc))
            return {}

        import numpy as np

        centroids: dict[str, list[float]] = {}
        for cat, entries in entries_by_cat.items():
            if len(entries) < _MIN_ENTRIES_PER_CATEGORY:
                log.info(
                    "semantic_fallback.category_skipped",
                    category=cat,
                    count=len(entries),
                    min_required=_MIN_ENTRIES_PER_CATEGORY,
                )
                continue

            # Thaw each entry for embedding
            texts: list[str] = []
            keywords: list[str] = []
            for e in entries:
                parts = e.get("bug_signature", ":::").split(":", 3)
                e_kw = parts[2] if len(parts) > 2 else ""
                e_af = parts[3] if len(parts) > 3 else ""
                texts.append(_sim_mod._thaw(cat, e_kw, e_kw, e_af))
                if e_kw:
                    keywords.append(e_kw)

            try:
                embeddings = model.encode(texts, normalize_embeddings=True)
                centroid = np.array(embeddings).mean(axis=0)
                norm = np.linalg.norm(centroid)
                if norm > 0:
                    centroid = centroid / norm
                centroids[cat] = centroid.tolist()

                if keywords:
                    self._category_keywords[cat] = Counter(keywords).most_common(1)[0][0]
            except Exception as exc:
                log.warning("semantic_fallback.centroid_error", category=cat, error=str(exc))

        return centroids

    def classify(
        self,
        error_lines: list[str],
        repo: str,
    ) -> ClassifierResult | None:
        """
        Classify error_lines using centroid similarity.

        Steps:
          1. Get Jina model — if unavailable → return None immediately
          2. Build centroids from memory.jsonl (lazy — once per instance)
          3. Embed cleaned error_lines (join first 20, strip file paths + hex addresses)
          4. Cosine similarity vs all centroids
          5. Confidence = min(_CONFIDENCE_CAP, S_max + _ALPHA*(S_max − S_next))
          6. If Confidence < _CONFIDENCE_FLOOR → return None
          7. Return ClassifierResult with matched_pattern="semantic_centroid"

        Never raises.
        """
        model = _sim_mod._get_embedding_model()
        if model is None:
            return None

        # Build centroids lazily (once per EmbeddingClassifier instance)
        if self._centroids is None:
            built = self.build_centroids(_memory_path())
            import numpy as np
            self._centroids = {k: np.array(v) for k, v in built.items()}

        if not self._centroids:
            return None

        # Build cleaned query text
        query_text = " ".join(error_lines[:20])
        query_text = re.sub(r"0x[0-9a-fA-F]+", "", query_text)
        query_text = re.sub(r'File "[^"]*"', "", query_text)

        try:
            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity

            q_emb = model.encode([query_text], normalize_embeddings=True)

            # Compute cosine similarity vs each centroid
            similarities: dict[str, float] = {}
            for cat, centroid in self._centroids.items():
                sim = float(
                    cosine_similarity(q_emb, centroid.reshape(1, -1))[0][0]
                )
                similarities[cat] = sim

        except Exception as exc:
            log.warning("semantic_fallback.classify_error", error=str(exc))
            return None

        if not similarities:
            return None

        sorted_sims = sorted(similarities.items(), key=lambda x: x[1], reverse=True)
        best_cat, s_max = sorted_sims[0]
        s_next = sorted_sims[1][1] if len(sorted_sims) > 1 else 0.0

        confidence = min(_CONFIDENCE_CAP, s_max + _ALPHA * (s_max - s_next))

        if confidence < _CONFIDENCE_FLOOR:
            log.info(
                "semantic_fallback.below_floor",
                confidence=round(confidence, 4),
                floor=_CONFIDENCE_FLOOR,
            )
            return None

        keyword = self._category_keywords.get(best_cat, "semantic")

        log.info(
            "semantic_fallback.classified",
            category=best_cat,
            confidence=round(confidence, 4),
            s_max=round(s_max, 4),
            s_next=round(s_next, 4),
        )

        return ClassifierResult(
            category=best_cat,
            confidence=confidence,
            matched_pattern="semantic_centroid",
            keyword=keyword,
            affected_file="",
            bug_signature=f"{repo}:{best_cat}:semantic:unknown",
        )


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    engine = EmbeddingClassifier()
    result = engine.classify(
        ["ModuleNotFoundError: No module named 'some_new_package'"],
        "test/repo",
    )
    if result:
        print(
            f"PASS  classify: category={result.category} "
            f"confidence={result.confidence:.2f}"
        )
    else:
        print("PASS  classify: returned None (model unavailable or no centroid match)")
    print("semantic_fallback.py smoke test PASSED")
