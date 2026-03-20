# Idea Validation Template
# Author: CH Y SAI SIDDHARDHA
# Method: Multi-model intelligence layering
# Stack: Gemini (ideas) → ChatGPT (constraints) → Perplexity (research) → Claude (execution)
# Rule: Idea must PASS all 4 gates before context.md is written
# Last updated: 2026-03-20

---

## THE METHOD

```
Your Interest/Problem
        ↓
GATE 1 — Gemini    : Idea Expansion      (diverge)
        ↓
GATE 2 — ChatGPT   : Constraint Check    (converge)
        ↓
GATE 3 — Perplexity: Reality Check       (ground truth)
        ↓
GATE 4 — Claude    : Execution Check     (ship or kill)
        ↓
PASS ALL 4 → write context.md + CLAUDE.md → build
FAIL ANY 1 → go back to that gate → fix or kill idea
```

---

## YOUR INTEREST STACK (what makes your ideas unique)

```
Present Tech    → what exists now that can be leveraged
Traditional Methods → proven approaches that still work
Mathematics     → where tech fails, math fills the gap

Sweet spot: problems where all 3 intersect
Example (Agent-X):
  Present Tech       = LLMs + GitHub Actions API
  Traditional Method = regex classification + unified diffs
  Mathematics        = confidence scoring + cosine similarity
```

Before any gate — ask yourself:
- Which of my 3 interests does this use?
- Does it use at least 2? (1 alone = too narrow)
- Where does tech fail here that math/tradition can fix?

---

## GATE 1 — GEMINI (Idea Expansion)

**Role:** Divergent thinking. No constraints yet. Pure possibility.

**Prompt to give Gemini:**
```
I have an interest in [present tech + traditional methods + math].
I want to solve this problem: [your problem in 1-2 sentences]

Generate 5 different approaches to solve this.
For each approach:
- What is the core mechanism?
- What makes it novel?
- Where does it combine tech + traditional + math?
- What would the input and output look like?

No constraints yet. Think big.
```

**What you capture from Gemini:**
```
[ ] Best idea selected: _______________
[ ] Core mechanism: _______________
[ ] What makes it novel: _______________
[ ] Input: _______________
[ ] Output: _______________
[ ] Which interests it uses: Tech / Traditional / Math (circle all)
```

**Gate 1 passes when:**
- At least 1 idea uses 2+ of your interests
- You can explain the mechanism in 1 sentence
- Input and output are clearly defined

---

## GATE 2 — CHATGPT (Constraint Check)

**Role:** Convergent thinking. Kill the fantasy. Find the walls.

**Prompt to give ChatGPT:**
```
I want to build: [best idea from Gate 1 — 3-4 sentences]

Give me:
1. Top 3 technical constraints (what will actually break this)
2. Top 3 practical constraints (time, cost, complexity)
3. Top 3 assumptions I'm making that could be wrong
4. What is the MVP that avoids all the above?
5. What has already been tried and failed? Why?
```

**What you capture from ChatGPT:**
```
Technical constraints:
[ ] 1. _______________
[ ] 2. _______________
[ ] 3. _______________

Practical constraints:
[ ] 1. _______________
[ ] 2. _______________
[ ] 3. _______________

Wrong assumptions I'm making:
[ ] 1. _______________
[ ] 2. _______________
[ ] 3. _______________

MVP definition: _______________
What's already failed: _______________
```

**Gate 2 passes when:**
- You have a concrete answer for every constraint
- MVP is specific (not "build a simple version")
- You know what's already failed and why yours is different

**Gate 2 kills the idea when:**
- A constraint has no solution
- MVP is still too complex to ship in 2-3 days
- What you're building already exists and does it better

---

## GATE 3 — PERPLEXITY (Reality Check)

**Role:** Ground truth. Citations. Evidence. What actually exists.

**Prompt to give Perplexity:**
```
Research these specific questions:
1. Does [core mechanism] already exist as a library or tool?
2. What papers or projects have attempted [problem]?
3. What is the current state-of-the-art for [problem]?
4. What APIs / datasets / tools exist that I can use?
5. What do practitioners say about [key assumption from Gate 2]?

Give me citations and links for each.
```

**What you capture from Perplexity:**
```
Already exists (tools/libraries):
[ ] _______________  link: _______________
[ ] _______________  link: _______________

Prior attempts:
[ ] _______________  what failed: _______________

APIs/tools I can use:
[ ] _______________  cost: _______________
[ ] _______________  cost: _______________

Key assumption validated/invalidated:
[ ] Assumption: _______________ → TRUE / FALSE
    Evidence: _______________
```

**Gate 3 passes when:**
- Core mechanism doesn't already exist as a polished product
- You found at least 1 usable API/tool
- Your key assumption is validated by evidence

**Gate 3 kills the idea when:**
- It already exists and is better than what you'd build
- No tools/APIs exist and you'd have to build everything from scratch
- Key assumption is invalidated by evidence

---

## GATE 4 — CLAUDE SONNET (Execution Check)

**Role:** Deep reasoning + practical architecture + ship or kill decision.

**Prompt to give Claude:**
```
I want to build: [idea]

Here is my validation so far:
- Gate 1 (Gemini): [mechanism, input, output]
- Gate 2 (ChatGPT): [constraints, MVP, what failed before]
- Gate 3 (Perplexity): [tools available, assumption status]

Now tell me:
1. Is this buildable in 2-3 days as a v1?
2. What is the strict pipeline (stage1 → stage2 → ... → output)?
3. What are the top 3 technical risks that could kill this?
4. Does math/traditional methods help where tech fails here? How?
5. What is the EXACT done condition for v1?
6. What is the spike (50-line proof) that validates the core loop?

Then: SHIP or KILL recommendation with reasoning.
```

**What Claude produces:**
```
Buildable in 2-3 days: YES / NO
Pipeline: _______________
Top 3 risks: _______________
Math/tradition advantage: _______________
Done condition: _______________
Spike: _______________
Recommendation: SHIP / KILL
Reasoning: _______________
```

**Gate 4 passes when:**
- Buildable in 2-3 days: YES
- Done condition is specific and measurable
- Spike is defined (you can prove it in 50 lines)
- Recommendation: SHIP

**Gate 4 kills the idea when:**
- Not buildable in 2-3 days as v1
- Done condition is vague
- Top risks have no solutions
- Recommendation: KILL

---

## FINAL SCORECARD

Fill this after all 4 gates:

```
Idea: _______________
Date: _______________

GATE 1 — Gemini    : PASS / FAIL
GATE 2 — ChatGPT   : PASS / FAIL
GATE 3 — Perplexity: PASS / FAIL
GATE 4 — Claude    : PASS / FAIL

Interests used     : Tech / Traditional / Math (circle all used)
MVP defined        : _______________
Done condition     : _______________
Spike defined      : _______________
Tools needed       : _______________
APIs needed        : _______________
Estimated days     : _______________

FINAL DECISION: BUILD / KILL / PARK FOR LATER

If BUILD → run scaffold command → create context.md → step 0
If KILL  → document why (saves future you from revisiting)
If PARK  → save to ideas_graveyard.md with reason
```

---

## IDEAS GRAVEYARD (park killed ideas here, not in trash)

Killed ideas are future ideas waiting for better tools.

```
| Idea | Killed at Gate | Reason | Revisit when |
|------|---------------|--------|--------------|
|      |               |        |              |
```

---

## HOW THIS CONNECTS TO YOUR BUILD SYSTEM

```
Idea passes all 4 gates
        ↓
Give Gate 4 output to Claude:
"Use this as context. Run scaffold."
        ↓
Claude generates:
  - context.md        (from pipeline + done condition)
  - CLAUDE.md         (from constraints + risks)
  - problems_and_solutions.md (from top 3 risks)
  - session_prompts.md (from pipeline stages)
        ↓
Say "step 0" → building starts
        ↓
2-3 days later → shipped
```

---

## THE FULL STACK SUMMARY

```
You (curiosity + interests)
        ↓
Gemini   → what could this be?      (diverge)
ChatGPT  → what stops this?         (converge)
Perplexity → what already exists?   (ground truth)
Claude   → can we ship it?          (execute)
        ↓
4 gates passed → context.md written → scaffold → step N → ship
        ↓
Autoresearch → skills self-improve → gets better every run
```

That is your complete method. Documented. Repeatable. Scalable.
