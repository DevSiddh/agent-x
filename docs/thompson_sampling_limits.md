# Thompson Sampling — Failure Modes + Fixes
# Last updated: 2026-03-25
# Context: Agent-XYZ uses TS for error category routing + skill vault scoring

---

## Why TS is the right choice (not full RL)
TS is Bayesian bandit RL — correct for Agent-XYZ because:
- Reward is immediate (pytest pass/fail, not delayed)
- Arms are independent (one skill doesn't affect another)
- Binary reward fits Beta(α,β) perfectly
- Works well in low-data regimes (no need for 1000s of samples)

Full RL (PPO/DQN) only needed when actions have long-term consequences
across multiple steps. Not our case.

---

## Failure Mode 1: Non-stationarity
**Problem:** A previously-winning strategy breaks (new Python version, API change).
TS keeps injecting it because accumulated α wins resist β catch-up.

**Fix:** Exponential decay on old wins
```python
decay_factor = 0.95  # apply on each save/load cycle
alpha = 1 + (raw_alpha - 1) * decay_factor
beta  = 1 + (raw_beta  - 1) * decay_factor
```
**Gate:** Add when any arm shows >20 wins (phase2/strategy/thompson.py)

---

## Failure Mode 2: No cross-arm learning
**Problem:** 100+ arms. TS treats "FastAPI DependencyError" and "Django
DependencyError" as fully independent. 30 wins on one gives zero signal
to the other.

**Fix:** Hierarchical priors — group arms by category tag, share
alpha/beta initialisation across similar arms at creation time.

**Gate:** Add when skill vault exceeds 100 entries (phase2/skills/vault.py)

---

## Failure Mode 3: Binary reward loses signal
**Problem:** "Passed on 3rd retry" counts same as "passed first try".
TS can't express quality of win. Best-of-N makes this worse without fix.

**Fix:** Continuous reward (wire to variations_tried field in Task)
```python
def reward_from_variations(variations_tried: int, passed: bool) -> tuple[float, float]:
    if not passed:
        return 0.0, 1.0   # beta += 1
    rewards = {1: 1.0, 2: 0.6, 3: 0.3}
    r = rewards.get(variations_tried, 0.2)
    return r, 0.0          # alpha += r (fractional update)
```
**Gate:** Add at Y-C1 (variations_tried already tracked in Task schema)

---

## Failure Mode 4: Cold start at enterprise scale
**Problem:** New org joins, all arms start at Beta(1,1). TS explores
randomly too long before finding winning patterns. Bad UX for paying customers.

**Fix:** Warm start from global vault (discounted prior)
```python
new_org_alpha = 1 + (global_alpha - 1) * 0.3
new_org_beta  = 1 + (global_beta  - 1) * 0.3
```
**Gate:** Add when multi-org is implemented (enterprise audit post-Y-C1)

---

## Scale thresholds

| Scale | Arms | TS ok? | Action |
|-------|------|--------|--------|
| Current | 5–50 | Perfect | Nothing |
| Growing single org | 50–200 | Yes | Add decay (Failure Mode 1) |
| Multi-org enterprise | 200–1000 | Partial | Hierarchical priors + warm start |
| Massive scale | 1000+ | No | Upgrade to LinUCB or NeuralUCB |

---

## Files to modify when each fix is needed
| Fix | File |
|-----|------|
| Decay | phase2/strategy/thompson.py → save() method |
| Continuous reward | phase2/skills/vault.py → update() method |
| Hierarchical priors | phase2/skills/vault.py → add_skill() method |
| Warm start | phase2/skills/vault.py → SkillVault.__init__() |
