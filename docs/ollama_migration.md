# Agent-Y | Ollama Migration Guide
# Use this when: sensitive code in pipeline OR monthly DeepSeek bill > $30
# Last updated: 2026-03-20

---

## When to migrate (both must be true)
- [ ] Trigger fired: real prod repos with proprietary code, OR bill > $30/month
- [ ] Step A4 is DONE (agent_y/prompt_loader.py exists, REASONER_MODEL switch works)

If Step A4 is not done yet → say "step A4" first, then return here.

---

## PHASE 1 — Install Ollama (one time)

### Option A — Local machine (Windows)
```
1. Download: https://ollama.com/download
2. Install → Ollama runs as background service on port 11434
3. Verify: curl http://localhost:11434  → should return "Ollama is running"
```

### Option B — VPS (GitHub Student Pack / DigitalOcean)
```
1. Spin up droplet: Ubuntu 22.04, minimum 16GB RAM (for 7B model)
   GPU droplet if available — otherwise CPU works, just slower (~15s per call)
2. SSH in and run:
   curl -fsSL https://ollama.com/install.sh | sh
3. Start service:
   ollama serve &
4. Open port 11434 in firewall if calling from outside VPS
5. Set OLLAMA_HOST in .env:
   OLLAMA_HOST=http://<your-vps-ip>:11434
```

---

## PHASE 2 — Pull the model

```bash
# On whichever machine runs Ollama:
ollama pull qwen2.5:7b

# Verify it works:
ollama run qwen2.5:7b "Return JSON: {\"test\": true}"
# Should print JSON — if it does, model is ready
```

Why Qwen2.5-7B:
- 7B parameters → fits in 8GB RAM (quantized)
- Strong instruction following → respects JSON-only constraint
- Apache 2.0 license → commercial use allowed
- Upgrade path: qwen2.5:14b or qwen2.5:72b if quality insufficient

---

## PHASE 3 — Switch Agent-Y (one line)

Open `.env` and change:
```
# Before (DeepSeek API):
REASONER_MODEL=deepseek-reasoner

# After (local Ollama):
REASONER_MODEL=ollama/qwen2.5:7b
```

That's it. No code changes. `agent_y/reasoner.py` reads REASONER_MODEL lazily
and routes to Ollama's OpenAI-compatible endpoint automatically.

---

## PHASE 4 — Verify

```bash
# Run single case — check logs for reasoner.ok
python phase2/pipeline.py syn_001

# Expected log line:
# {"event": "reasoner.ok", "strategy": "...", "confidence": 0.x, ...}

# If you see reasoner.fallback instead → see troubleshooting below

# Run full suite — confirm 5/5 still accepted
python phase2/pipeline.py

# Run tests — confirm no regressions
python -m pytest tests/ --tb=short -q
```

---

## PHASE 5 — Confirm DeepSeek fallback still works

```bash
# Switch back temporarily to verify no regression:
REASONER_MODEL=deepseek-reasoner python phase2/pipeline.py syn_001

# Switch back to Ollama:
REASONER_MODEL=ollama/qwen2.5:7b
```

Both must work. The switch is reversible at any time.

---

## Troubleshooting

### "reasoner.fallback" logged instead of "reasoner.ok"
Means Qwen returned invalid JSON or strategy mismatch.
```bash
# Test Qwen directly:
ollama run qwen2.5:7b "Return ONLY valid JSON with key 'action': repair, 'strategy': install missing package"
# If it wraps in markdown → _extract_json() strips it, should be fine
# If it adds prose → prompt needs strengthening in load_system_prompt()
```

### Connection refused on port 11434
```bash
# Check Ollama is running:
ollama list
# If not running:
ollama serve
```

### Model too slow (>30s per call)
- CPU inference on 7B: 10–30s per call — acceptable for personal use
- If unacceptable: upgrade to GPU droplet, or switch to qwen2.5:3b (faster, less quality)
- Or stay on deepseek-reasoner — it's faster and costs <$1/month

### Quality worse than DeepSeek
Expected — 7B local model vs DeepSeek-Reasoner is not equal quality.
Options:
1. Upgrade to qwen2.5:14b (needs 16GB RAM)
2. Strengthen system prompt via autoresearch loop (run autoresearch on reasoner skill)
3. Accept quality tradeoff for privacy benefit

---

## Cost comparison post-migration

| Item | Before | After |
|------|--------|-------|
| Agent-Y Reasoner | ~$1/month (DeepSeek) | $0 API cost |
| VPS (if needed) | $0 | $6–20/month (CPU droplet) |
| Agent-X PatchGen | ~$2–5/month (DeepSeek) | unchanged |
| Net change | — | +$5–19/month VPS, -$1 API |

Note: local machine Ollama = zero additional cost if machine is already running.
VPS only worth it if machine is off most of the time.

---

## Rollback (instant)

If anything goes wrong — one line in .env:
```
REASONER_MODEL=deepseek-reasoner
```

Back to DeepSeek in 1 second. No code changes, no redeployment.
