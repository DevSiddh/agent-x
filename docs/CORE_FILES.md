# Minimum Required Files by Project Type

---

## TYPE 1 — Personal Script
Will be deleted in a week. Solo use. No LLM.

```
script.py
.env
requirements.txt
```

---

## TYPE 2 — Real Project (No LLM)
Multiple modules. Used by others. Runs in prod.

```
CLAUDE.md
context.md
tests/
Makefile
.github/workflows/ci.yml
```

---

## TYPE 3 — Agent / LLM Pipeline
LLM in the loop. Autonomous decisions. Data accumulates.

```
CLAUDE.md
context.md
docs/session_prompts.md
docs/progress.md
docs/problems_and_solutions.md
docs/roadmap.md
memory/memory.jsonl
```

Rule: For TYPE 3, these 7 files are mandatory. No shortcuts.
If any are missing at session start → create them before writing code.
