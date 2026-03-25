# Autoresearch Skill — Auto-Improves Any Prompt on Autopilot
# Based on: Karpathy autoresearch method (via @itsolelehmann)
# Adapted for: Agent-X v1 by CH Y SAI SIDDHARDHA
# Date: 2026-03-20
#
# HOW TO USE:
# Say "run autoresearch on [skill name]" — agent does the rest
# Or run directly: python skills/autoresearch/runner.py --skill worker

---

## THE METHOD (understand this first)

```
skill prompt (your recipe)
       ↓
run on test input
       ↓
score output against checklist (yes/no only)
       ↓
make ONE small prompt change
       ↓
score again
  better? → KEEP change
  worse?  → REVERT change
       ↓
repeat until score ≥ 95% three times in a row
       ↓
save improved prompt + changelog
```

Key rules:
- ONE change per round (isolates what works)
- 3-6 checklist items only (more = gaming the checklist)
- Yes/No questions only (no 1-10 scales — too vague)
- Original skill always preserved (improved saved separately)
- Changelog saved — future models pick up where this one left off

---

## REPORT FORMAT (use this structure for every autoresearch output)

When presenting findings — after baseline, after each improvement, and at completion —
structure the response exactly like this:

```
1. Reality Check   — what the current score actually is (number, not opinion)
2. Key Insight     — the ONE thing causing the lowest score (specific, not generic)
3. Decision        — keep change / revert change / try different approach
4. Minimal Steps   — exactly what to change next (one targeted edit, not a rewrite)
```

Rules:
- No motivational commentary
- No "great progress" filler
- If score drops → say it directly → revert → state next attempt
- If score plateaus 3 rounds → say it → switch approach

---

## CHECKLISTS FOR AGENT-X SKILLS

### Checklist: DeepSeek Patch Generator (worker.py prompt)
These are your yes/no scoring questions:

1. Does the output start with `---` (raw unified diff, no fences)? yes/no
2. Is the diff under 15 lines of actual changes (+/- lines)? yes/no
3. Does `git apply` succeed on the fixture repo? yes/no
4. Does `pytest` pass after applying the patch? yes/no
5. Does the patch target only the affected file (no scope creep)? yes/no

Pass threshold: 4/5 (80%) → target: 5/5 (100%)
Starting baseline: measure this before first loop

---

### Checklist: Regex Classifier (regex_pass.py)
1. Does it return the correct failure_category for the input? yes/no
2. Is confidence ≥ 0.85 for clear-cut errors (syn_001..005)? yes/no
3. Is confidence < 0.85 for ambiguous/mixed logs? yes/no
4. Does bug_signature follow repo:Type:keyword:file format? yes/no
5. Does it complete in < 100ms? yes/no

Pass threshold: 5/5 (100%)

---

### Checklist: Sanitiser (sanitiser.py strip logic)
1. Does strip_markdown_fences() remove all ``` fences? yes/no
2. Does output start exactly with `---`? yes/no
3. Are non-diff lines (explanations) completely removed? yes/no
4. Is a clean diff preserved without modification? yes/no

Pass threshold: 4/4 (100%)

---

### Checklist: Memory Store (store.py)
1. Does dedup correctly block same repo+signature? yes/no
2. Does append() never raise even with broken path? yes/no
3. Does get_similar() return entries from same category? yes/no
4. Is schema 100% valid JSON per context.md spec? yes/no

Pass threshold: 4/4 (100%)

---

## HOW TO RUN

### Step 1 — Pick a skill
```
"run autoresearch on worker"         → improves DeepSeek prompt
"run autoresearch on classifier"     → improves regex patterns
"run autoresearch on sanitiser"      → improves strip logic
```

### Step 2 — Agent asks you 3 things
1. Which skill to optimize
2. Test inputs (e.g. error logs from synthetic.jsonl)
3. Confirm checklist (or customise it)

### Step 3 — Agent runs the loop
- Measures baseline score
- Makes ONE change
- Tests again
- Keeps or reverts
- Repeats until 95%+ hit 3 times in a row

### Step 4 — Walk away
Come back to:
- Improved skill saved as `[skill]_improved.py`
- Results log: `skills/autoresearch/logs/[skill]_results.jsonl`
- Changelog: `skills/autoresearch/logs/[skill]_changelog.md`
- Original untouched

---

## THE LOOP PROMPT (what Claude runs each iteration)

```
You are improving a skill prompt using the autoresearch method.

Current skill prompt:
{current_prompt}

Test input:
{test_input}

Current output:
{current_output}

Checklist score: {score}/5

Checklist results:
{checklist_results}

Your job:
1. Identify the LOWEST scoring checklist item
2. Make ONE small, targeted change to the prompt that directly addresses it
3. Do NOT change multiple things at once
4. Return ONLY the updated prompt — nothing else

Rules:
- One change per round
- If score drops → revert immediately
- If score stays same 3 rounds → try different approach
- Stop when score ≥ 95% three times in a row
```

---

## SCORING FUNCTION TEMPLATE

```python
def score_output(output: str, checklist: list[dict]) -> dict:
    """
    Score skill output against yes/no checklist.
    Returns: {score: float, results: list[dict], passed: int, total: int}
    """
    results = []
    passed = 0

    for item in checklist:
        # Each checklist item has: question, check_fn
        result = item["check_fn"](output)
        results.append({
            "question": item["question"],
            "passed": result,
            "weight": item.get("weight", 1)
        })
        if result:
            passed += item.get("weight", 1)

    total_weight = sum(i.get("weight", 1) for i in checklist)
    return {
        "score": passed / total_weight,
        "passed": passed,
        "total": total_weight,
        "results": results
    }
```

---

## CHECKLIST FUNCTIONS FOR AGENT-X (copy into runner.py)

```python
import re
import subprocess
from pathlib import Path

# ── Worker (DeepSeek patch generator) ────────────────────────────────────────
WORKER_CHECKLIST = [
    {
        "question": "Does output start with --- (raw unified diff)?",
        "check_fn": lambda out: out.strip().startswith("---"),
        "weight": 2,  # most critical
    },
    {
        "question": "Is patch under 15 lines of changes?",
        "check_fn": lambda out: sum(
            1 for l in out.splitlines()
            if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))
        ) <= 15,
        "weight": 1,
    },
    {
        "question": "Does git apply succeed on fixture?",
        "check_fn": lambda out: _try_git_apply(out),
        "weight": 2,  # critical
    },
    {
        "question": "Does pytest pass after patch?",
        "check_fn": lambda out: _try_pytest(out),
        "weight": 2,  # critical
    },
    {
        "question": "Patch targets only one file (no scope creep)?",
        "check_fn": lambda out: out.count("--- a/") == 1,
        "weight": 1,
    },
]

# ── Classifier ────────────────────────────────────────────────────────────────
def make_classifier_checklist(expected_category: str, expected_confidence_min: float = 0.85):
    return [
        {
            "question": f"Returns correct category: {expected_category}?",
            "check_fn": lambda out: expected_category in out,
            "weight": 2,
        },
        {
            "question": "Confidence >= 0.85 for clear error?",
            "check_fn": lambda out: _extract_confidence(out) >= expected_confidence_min,
            "weight": 2,
        },
        {
            "question": "bug_signature in repo:Type:keyword:file format?",
            "check_fn": lambda out: bool(re.search(r'\w+/\w+:\w+:\w+:\S+', out)),
            "weight": 1,
        },
    ]
```

---

## LOOP CONTROLLER (pseudocode — implement in runner.py)

```python
MAX_ROUNDS   = 50
WIN_STREAK   = 3   # consecutive rounds at 95%+ to stop
THRESHOLD    = 0.95

def autoresearch_loop(skill_prompt, test_inputs, checklist):
    best_prompt  = skill_prompt
    best_score   = 0.0
    win_streak   = 0
    changelog    = []

    for round_num in range(MAX_ROUNDS):
        # 1 — Run skill on all test inputs
        scores = []
        for test_input in test_inputs:
            output = run_skill(best_prompt, test_input)
            result = score_output(output, checklist)
            scores.append(result["score"])

        avg_score = sum(scores) / len(scores)

        # 2 — Check win condition
        if avg_score >= THRESHOLD:
            win_streak += 1
            if win_streak >= WIN_STREAK:
                print(f"Done! Score: {avg_score:.0%} — {WIN_STREAK} consecutive wins")
                break
        else:
            win_streak = 0

        # 3 — Ask LLM to make ONE targeted change
        new_prompt = llm_improve_prompt(best_prompt, scores, checklist)

        # 4 — Test new prompt
        new_scores = [
            score_output(run_skill(new_prompt, inp), checklist)["score"]
            for inp in test_inputs
        ]
        new_avg = sum(new_scores) / len(new_scores)

        # 5 — Keep or revert
        if new_avg > avg_score:
            changelog.append({
                "round": round_num,
                "change": "kept",
                "score_before": avg_score,
                "score_after": new_avg,
            })
            best_prompt = new_prompt
            best_score  = new_avg
        else:
            changelog.append({
                "round": round_num,
                "change": "reverted",
                "score_before": avg_score,
                "score_after": new_avg,
            })
            # best_prompt unchanged

    return best_prompt, best_score, changelog
```

---

## WHAT YOU GET AT THE END

```
skills/autoresearch/logs/
├── worker_improved.py          ← drop-in replacement for worker.py
├── worker_results.jsonl        ← score per round
├── worker_changelog.md         ← every change tried, kept/reverted, why
└── worker_original_backup.py   ← original untouched
```

---

## SWEET SPOTS (from the article)

- 3-6 checklist items (more = gaming)
- Weight critical items 2x (git apply, pytest pass)
- One change per round (isolation is everything)
- Run on ALL 5 synthetic cases as test inputs
- Stop at 95% × 3 consecutive rounds
- Save changelog — when Claude 4 / DeepSeek v4 ships, hand it the changelog
