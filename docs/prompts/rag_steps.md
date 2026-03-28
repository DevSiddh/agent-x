# Agent-X | RAG Upgrade Steps
# Architecture locked 2026-03-22 — full Gemini review (5 questions) complete
# Source: docs/rag_upgrade_analysis.md — read before touching anything

---

## STEP RAG — v2.1 RAG Upgrade (triple-hybrid semantic search)
**Built:** phase2/memory/similarity.py rewritten — _thaw(), _get_embedding_model() (lazy Jina), _score_entries(), find_for_rag(). phase2/context_builder.py updated — uses find_for_rag(), _action_tag(), HIGH/LOW relevance tags. requirements.txt: sentence-transformers + einops added.
**Done condition:** All tests pass. Context output has [HIGH RELEVANCE] or [LOW RELEVANCE] tags. find_similar() return format unchanged — pipeline.py untouched.
**Key decisions:**
- Triple hybrid: 0.30×TF-IDF + 0.45×Jina-dense + 0.25×Thompson
- Jina model: jinaai/jina-embeddings-v2-small-code (lazy-loaded, never raises)
- Tier 1 bypass ≥0.85 (find_similar) | HIGH tag 0.70–0.84 | LOW tag 0.55–0.69 | nothing <0.55
- Δ = s_dense - s_tfidf logged per entry (monitoring signal). Weights fixed until n=500.
**Status: DONE**

---

## STEP CLS — Embedding Classifier Fallback
**Built:** phase2/classifier/semantic_fallback.py — EmbeddingClassifier, build_centroids(), classify(). classify_with_fallback() added to regex_pass.py below existing classify(). pipeline.py: 1 line change — classify → classify_with_fallback.
**Done condition:** All tests pass. Novel errors trigger semantic pass. classifier.regex_miss + classifier.semantic_hit logged on fallback path.
**Key decisions:**
- Pass 1 (regex) always runs. Pass 2 (embedding) only when regex confidence < 0.85.
- Confidence = min(0.87, S_max + 0.5×(S_max - S_next)). Floor 0.55. Cap 0.87 (below regex 0.90–0.99).
- Reuses Jina model from similarity.py — no second model loaded.
**Status: DONE**

---

## STEP RAG-NEG — Negative RAG (Contrastive Memory / Autopsy Protocol)
# Prerequisite: Step RAG DONE
# Gate: memory.jsonl has >= 10 entries where decision=rejected AND rejection_reason=logic_issue
# Do NOT build until gate is met — format_error rejections pollute Agent-Y reasoning

```
You are adding Negative RAG (Contrastive Memory) to Agent-X.
Read CLAUDE.md, docs/progress.md before touching anything.
Step RAG must be DONE.

GATE CHECK — run before writing a single line:
  python -c "
  import json
  from pathlib import Path
  entries = [json.loads(l) for l in Path('memory/memory.jsonl').read_text().splitlines() if l.strip()]
  count = sum(1 for e in entries if e.get('decision')=='rejected' and e.get('rejection_reason')=='logic_issue')
  print(f'logic_issue rejections: {count}')
  print('GATE MET' if count >= 10 else 'GATE NOT MET — stop')
  "
If < 10 → STOP. Do not build.

CONTEXT (why rejection_reason routing matters — E1 categories):
  logic_issue    ← pytest failed after patch — INJECT as [FAILED APPROACH] autopsy
  security_issue ← bandit rejected — INJECT as [SECURITY BLOCK] autopsy
  prompt_issue   ← bad diff header — BLOCK (pipeline artifact, not a reasoning failure)
  size_issue     ← patch too long — BLOCK (pipeline limit, not a reasoning failure)
  context_issue  ← wrong file path — BLOCK (pipeline artifact, not a reasoning failure)
  flaky          ← flaky test — BLOCK (not a logic failure)
  Only logic_issue and security_issue reach Agent-Y. All others are silently filtered.

PART 1 — Add rejection_reason to MemoryEntry

File: phase2/memory/store.py
  Add field to MemoryEntry:
    rejection_reason: str = ""
    # valid values: "test_failure" | "format_error" | "security_reject" | "flaky" | ""

File: phase2/pipeline.py — populate at each rejection point (use E1 category names exactly):
  apply_patch fails            → rejection_reason = "prompt_issue"     (format/diff error)
  sanitiser rejects size       → rejection_reason = "size_issue"       (patch too long)
  bandit rejects               → rejection_reason = "security_issue"   (unsafe pattern)
  run_tests_stable flaky       → rejection_reason = "flaky"            (not a logic failure)
  after.passed == False        → rejection_reason = "logic_issue"      (genuine logic failure)
  check_regression returns True → rejection_reason = "logic_issue"     (genuine logic failure)

  NOTE: values match E1 category names exactly — no translation layer needed.

PART 2 — Add find_rejected_for_rag() to MemoryEngine

File: phase2/memory/similarity.py

  def find_rejected_for_rag(
      self,
      category: str,
      matched_pattern: str,
      keyword: str,
      affected_file: str,
      bug_signature: str,
  ) -> list[tuple[dict, float]]:
      """
      Find top-2 REJECTED entries above _RAG_LOW_THRESHOLD (0.55).
      Only injects entries where rejection_reason in ("logic_issue", "security_issue").
      Blocks: prompt_issue, context_issue, size_issue, flaky — pipeline artifacts.
      Returns list of (entry_dict, hybrid_score) — caller uses rejection_reason to pick tag.
      Called by context_builder.py only.
      """
      # Logic: filter decision="rejected" AND rejection_reason in ("logic_issue","security_issue")
      # Score via _score_entries — same hybrid formula
      # Filter: hybrid_score >= _RAG_LOW_THRESHOLD
      # Return up to 2 entries (1 logic + 1 security if both present)

PART 3 — Update context_builder.py

After "## Past Similar Fixes" section:

  # E1-routed Autopsy tags — aligned with failure_classifier.py categories
  _AUTOPSY_TAGS: dict[str, str] = {
      "logic_issue":    "[FAILED APPROACH: Pytest failed. Do not repeat this logic.]",
      "security_issue": "[SECURITY BLOCK: Bandit rejected. Avoid hardcoded/unsafe patterns.]",
  }

  rejected_results = engine.find_rejected_for_rag(
      category=classifier_result.category,
      matched_pattern=classifier_result.matched_pattern,
      keyword=classifier_result.keyword,
      affected_file=classifier_result.affected_file,
      bug_signature=classifier_result.bug_signature,
  )
  if rejected_results:
      autopsy_entries: list[str] = []
      for i, (entry_dict, score) in enumerate(rejected_results, 1):
          reason = entry_dict.get("rejection_reason", "logic_issue")
          tag = _AUTOPSY_TAGS.get(reason, _AUTOPSY_TAGS["logic_issue"])
          patch_preview = (entry_dict.get("patch_applied") or "").strip()
          if len(patch_preview) > 500:
              patch_preview = patch_preview[:500] + "\n... (truncated)"
          autopsy_entries.append(
              f"### Failed Attempt {i} {tag} (rejected)\n"
              f"```diff\n{patch_preview}\n```"
          )
          log.info("context_builder.autopsy_injected", reason=reason, score=round(score, 4))
      sections.append("## Past Failed Attempts (Autopsy)\n" + "\n\n".join(autopsy_entries))

Slot accounting:
  Accepted fixes : up to 3 (find_for_rag — _TOP_K unchanged)
  Rejected entries: up to 2 extra slots (1 logic_issue + 1 security_issue if both present)
  Total context  : 5 entries max — accepted + autopsy do NOT share the cap

DONE WHEN:
- Gate met: >= 10 logic_issue rejections in memory.jsonl
- pytest tests/ → all pass, zero regressions
- rejection_reason populated correctly at all 5 pipeline exit points
- context output contains "## Past Failed Attempts (Autopsy)" when test_failure entry found
- format_error and security_reject entries NEVER appear in Autopsy section
- docs/progress.md updated: Step RAG-NEG DONE
```
