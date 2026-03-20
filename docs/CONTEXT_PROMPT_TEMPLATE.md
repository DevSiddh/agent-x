# Context + Prompt Generation Template
# Author: CH Y SAI SIDDHARDHA
# Purpose: Replaces deep-think model for generating context.md, CLAUDE.md, prompts
# Method: Answer these questions → paste answers to Claude → get perfect context
# Rule: If you cannot answer a question → you are not ready to build yet
# Last updated: 2026-03-20

---

## HOW TO USE

Step 1 → Fill every section below (skip nothing)
Step 2 → Paste the filled template to Claude with this message:
         "Generate context.md, CLAUDE.md and session prompts from this."
Step 3 → Claude produces everything. No deep-think model needed.

The questions ARE the deep thinking.
Answering them forces the clarity a deep-think model would extract anyway.

---

## SECTION 1 — THE PROBLEM

```
Problem in one sentence (no jargon):
→

Who has this problem? (be specific, not "developers"):
→

How do they solve it today? (manual process, existing tool, workaround):
→

What is painful about that current solution?:
→

What would the world look like if this problem was perfectly solved?:
→
```

---

## SECTION 2 — THE SOLUTION

```
Your solution in one sentence:
→

What is the INPUT? (exact format — file, API call, text, event):
→

What is the OUTPUT? (exact format — file, JSON, action, result):
→

What happens in between? (list each transformation step):
→ Step 1:
→ Step 2:
→ Step 3:
→ Step 4:
→ Step 5:

What makes your solution different from current approach?:
→

Which of your interests does it use? (circle):
  Present Tech / Traditional Methods / Mathematics
→ How specifically:
```

---

## SECTION 3 — THE DONE CONDITION

```
v1 is complete when (be exact, no vague words):
→

How will you measure success? (number, test result, observable output):
→

What is the minimum that counts as shipped?:
→

What is explicitly OUT OF SCOPE for v1?:
→ 1.
→ 2.
→ 3.
```

---

## SECTION 4 — THE PIPELINE

```
Draw your pipeline as a linear flow:
→ [Input] → [Stage 1] → [Stage 2] → [Stage 3] → [Output]

For each stage fill this:

Stage 1 name:
  Input:
  Output:
  Fails when:
  Hard rule:

Stage 2 name:
  Input:
  Output:
  Fails when:
  Hard rule:

Stage 3 name:
  Input:
  Output:
  Fails when:
  Hard rule:

(add more stages as needed)
```

---

## SECTION 5 — THE RISKS (fill before coding)

```
What external tool/API/CLI does this depend on?:
→ 1.                    Does it actually exist? YES/NO
→ 2.                    Does it actually exist? YES/NO
→ 3.                    Does it actually exist? YES/NO

What happens if the LLM returns garbage output?:
→ How you handle it:

What is the single biggest assumption you are making?:
→ Assumption:
→ How you will validate it:

What will break first when this runs in production?:
→

What has already been tried and failed (by you or others)?:
→ Why yours is different:
```

---

## SECTION 6 — THE SPIKE

```
What is the core loop of your system? (simplest version):
→ [Input] → [one key step] → [output]

Write the spike in plain English (50 lines max, throwaway):
→ 1. Load test input from:
→ 2. Call [API/function]:
→ 3. Check if output is:
→ 4. Print PASS or FAIL

What does PASS look like exactly?:
→

What does FAIL tell you?:
→
```

---

## SECTION 7 — ENVIRONMENT + STACK

```
Language + version:
→ Python 3.11 / Node / other:

External APIs needed:
→ 1. Name:          Key env var:          Free/Paid:
→ 2. Name:          Key env var:          Free/Paid:
→ 3. Name:          Key env var:          Free/Paid:

Key libraries:
→

All env variables (name only, no values):
→ 1.
→ 2.
→ 3.

Port (if server):
→

Database/storage (if any):
→
```

---

## SECTION 8 — HARD RULES

```
What must NEVER happen in this system? (safety rules):
→ 1.
→ 2.
→ 3.

What must ALWAYS happen regardless of outcome?:
→ 1.
→ 2.

What is the retry strategy when something fails?:
→ Max retries:
→ What changes on retry:
→ What happens after max retries:
```

---

## SECTION 9 — UPGRADE QUEUE

```
What is locked until v1 ships? (do not build these now):
→ v1.1:
→ v1.2:
→ v2.0:

What are you most tempted to over-engineer right now?:
→ Why you won't:
```

---

## SECTION 10 — AUTORESEARCH CHECKLIST (pre-fill now)

```
For each key skill/prompt in your system, define the yes/no checklist:

Skill 1 name:
→ Check 1 (yes/no):
→ Check 2 (yes/no):
→ Check 3 (yes/no):
→ Pass threshold: ___/___

Skill 2 name:
→ Check 1 (yes/no):
→ Check 2 (yes/no):
→ Check 3 (yes/no):
→ Pass threshold: ___/___
```

---

## PASTE THIS TO CLAUDE WHEN DONE

```
I filled the CONTEXT_PROMPT_TEMPLATE.md for my new project.
Here it is: [paste filled template]

Generate these files from it:
1. context.md          (max 80 lines, index only)
2. CLAUDE.md           (session protocol + hard rules + build status)
3. docs/problems_and_solutions.md  (extract all risks as P1..PN)
4. docs/roadmap.md     (build order from pipeline stages)
5. docs/session_prompts.md  (one prompt per stage as step 0..N)
6. docs/progress.md    (all steps PENDING to start)

Then run: scaffold
```

---

## WHAT THIS REPLACES

```
Before:
  You → Perplexity deep think → heavy analysis → context.md
  You → ChatGPT constraints → CLAUDE.md
  You → Claude prompts → session_prompts.md
  3 models, 3 sessions, 30-60 minutes

After:
  You → fill this template (15-20 min)
  You → paste to Claude
  Claude → generates all 6 files in one shot
  1 model, 1 session, 20 minutes total
```

The template forces the same depth of thinking.
The questions ARE the deep-think model.
Claude executes on your answers.

No Perplexity needed. No ChatGPT needed. Just you + this template + Claude.
