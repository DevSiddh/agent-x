# Agent-X | RAG Upgrade Analysis
# Written: 2026-03-22 — CH Y SAI SIDDHARDHA
# Purpose: evaluate whether current RAG is at maximum effectiveness
# Status: ARCHITECTURE LOCKED — full Gemini review (5 questions) complete 2026-03-22
# Build prompt: docs/prompts/rag_steps.md → say "step RAG"

## LOCKED ARCHITECTURE (implement exactly — do not re-evaluate)
| Component | Decision |
|-----------|----------|
| Model | jinaai/jina-embeddings-v2-small-code (NOT all-MiniLM-L6-v2) |
| Thaw | "{category} ({matched_pattern}) involving {keyword} in file {affected_file}" |
| Formula | 0.30 × TF-IDF + 0.45 × jina-dense + 0.25 × Thompson |
| TF-IDF | KEPT — exact-match anchor (do not remove) |
| Tier bypass | ≥ 0.85 → find_similar() unchanged — pipeline.py untouched |
| Tier HIGH | 0.70–0.84 → [HIGH RELEVANCE: Adapt this pattern] |
| Tier LOW | 0.55–0.69 → [LOW RELEVANCE: Loose inspiration only. DO NOT copy directly.] |
| Tier zero | < 0.55 → nothing injected |
| Max entries | 3 (find_for_rag — new method, separate from find_similar) |
| Monitoring | Δ = S_dense - S_tfidf logged per scored entry |
| Weight review | Manual — only when n=500 AND repeated Δ>0.40 on failures |
| Parked | Negative RAG (gate: 10+ test_failure), Web fallback (D0), AST Graph (D0.5) |

---

---

## Current State (Passive RAG)

```
Bug comes in
    → fixed query (bug_signature string)
    → TF-IDF keyword match
    → top-5 by similarity × Thompson score
    → always injected into context (no quality check)
    → Agent-Y uses it regardless of relevance
```

Files: phase2/memory/similarity.py + phase2/context_builder.py
RAG limit: 5 entries (raised from 3 at C0)
Ranking: hybrid = TF-IDF similarity × Thompson win_rate

---

## Gap 1 — TF-IDF misses semantic equivalence (biggest gap)

```
"cannot import setuptools"       → DependencyError
"No module named pkg_resources"  → DependencyError (same fix, different words)

TF-IDF score between these: LOW  (keyword mismatch)
Semantic embedding score:    HIGH (same meaning)

Impact: past fix for one doesn't surface for the other
        Agent-Y starts from scratch instead of reusing known solution
        Patch quality drops on semantically equivalent but lexically different bugs
```

**Proposed fix:** sentence-transformers (all-MiniLM-L6-v2)
- Runs locally — zero API cost
- 384-dimensional embeddings
- Replace TF-IDF cosine similarity with embedding cosine similarity
- Keep hybrid ranking (embedding_similarity × Thompson) — same logic, better vectors
- Already in roadmap as Step 12 (deferred at v1.4) — gate now met (101+ real entries)

---

## Gap 2 — Fixed k=5 regardless of quality

```
Current: always return top 5 entries
Problem: if best match scores 0.40 (low relevance) → 5 mediocre entries injected
         → noise > signal → context_builder pollutes Agent-Y's reasoning

Better:  dynamic k — return entries WHERE similarity > threshold (e.g. 0.70)
         sometimes 1 entry, sometimes 3, sometimes 0
         "no RAG" is better than "bad RAG"
```

**Proposed fix:** change `get_similar(top_k=5)` to `get_similar(min_score=0.70)`
- 5 extra lines in similarity.py
- Build in same session as embedding upgrade

---

## Gap 3 — No agent decision on retrieval (true agentic RAG)

```
Current: RAG always runs, Agent-Y always gets context injected
Problem: Agent-Y has no awareness of HOW relevant the retrieved context is
         Low-quality matches still shape Agent-Y's strategy

Agentic: pass similarity scores to Agent-Y — it decides how to weight context
         score > 0.85 → "exact match — reuse this approach directly"
         score 0.60-0.85 → "related — use as reference, not blueprint"
         score < 0.60 → "low signal — reason from scratch, ignore past fixes"
```

**Proposed fix:** include similarity_score in each RAG entry passed to Agent-Y
- Agent-Y system prompt updated: "entries with score < 0.60 are weak signal only"
- ~20 extra tokens per run — negligible cost
- Build at D0 when Agent-Y context is being restructured anyway

---

## Gap 4 — Multi-hop reasoning (future)

```
Current: single retrieval step — bug → memory → context
Future:  chain reasoning across memory entries
         "this bug is similar to X
          X was fixed by pattern Y
          pattern Y also applies here even though surface symptoms differ"

This requires Orchestrator (v3.0) — task chaining infrastructure
```

**Not buildable now. Lock for v3.0.**

---

## Upgrade Levels

```
Level 1 (current)  → TF-IDF keyword match → fixed top-5 always injected
Level 2 (next)     → semantic embeddings → matches meaning not words
Level 3 (next)     → dynamic k (threshold-based) → no bad RAG injected
Level 4 (D0)       → Agent-Y sees similarity scores → weights context correctly
Level 5 (v3.0)     → multi-hop chain reasoning across memory entries
```

---

## Proposed Build Plan

| Level | Step | Files | Cost |
|-------|------|-------|------|
| 2 + 3 | After E1 (gate: 101+ entries ✅) | phase2/memory/similarity.py | $0 local model |
| 4 | D0 — Agent-Y context restructure | agent_y/reasoner.py + context_builder.py | ~20 tokens/run |
| 5 | v3.0 Orchestrator | new architecture | Future |

---

## Open Questions for Gemini

1. Is sentence-transformers (all-MiniLM-L6-v2) the right embedding model for
   short error log snippets and bug signatures? Or is there a better local option?

2. Is 0.70 the right threshold for dynamic k, or should it be calibrated
   differently for error classification context (where bugs can be phrased many ways)?

3. For Gap 3 (agent-aware retrieval) — is passing raw similarity scores to Agent-Y
   the right approach, or should we use a different signal
   (e.g. a retrieval confidence label: "exact / related / weak")?

4. Is there a smarter query formulation strategy?
   Current query = bug_signature string only.
   Better query = bug_signature + error_category + keywords from log window?
   Would this meaningfully improve recall before even switching to embeddings?

5. At what memory.jsonl size does embedding similarity stop being better than
   TF-IDF for this specific use case (short structured bug signatures)?

---

## Claude's Recommendation (before Gemini review)

Build Level 2 + 3 immediately after E1:
- Embeddings fix the semantic equivalence gap — real impact on patch quality
- Dynamic k removes noise injection — cleaner context = better Agent-Y reasoning
- Both in one session, same file (similarity.py), zero new infrastructure

Level 4 at D0 — natural fit since Agent-Y context is being restructured there anyway.

Do NOT build Level 5 now — needs Orchestrator first.

**Decision pending Gemini review.**
