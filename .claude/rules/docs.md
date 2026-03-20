---
paths:
  - "**/*.md"
---

# Docs Rules — Agent-X

Loads automatically when Claude touches any .md file.

## context.md
- 80 lines maximum — hard limit, never broken
- Index only — never add explanations or code directly
- If content needs more room → create docs/modules/<name>.md and point to it

## progress.md
- Two states only: PENDING or DONE
- No diary entries, no "tried X", no "thinking about Y"
- Always include: test result + date when marking DONE

## CLAUDE.md
- Only add a rule if Claude would make a mistake without it
- If a rule is enforced by a hook or test → delete it from CLAUDE.md (hook owns it)
- Keep under 200 lines — compliance drops after that

## session_prompts.md
- Every step must have: exact file names + exact function signatures + exact done condition
- If Claude can ask a clarifying question about the step → the prompt is not finished

## problems_and_solutions.md
- Never write a problem without its concrete solution
- Solution must include actual code, not just a description
- Status: PENDING → IN PROGRESS → DONE only

## General
- Never grow a file beyond its purpose
- Never duplicate content that already exists in another doc — reference it instead
