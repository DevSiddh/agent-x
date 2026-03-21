# Agent-X | AUDIT Prompt
# Say "audit" to trigger this. Run before every new phase boundary.

When to use:
- Before starting a new phase (v2.0, v2.1 etc.)
- After a major change to pipeline, memory, or executor
- When something feels broken but tests still pass
- When memory.jsonl starts accumulating and you want a health check

---

```
You are auditing Agent-X — an autonomous CI/CD self-healing system built by a solo developer.

Before saying anything, read these files in order:
1. docs/progress.md         → what is built and what passed
2. CLAUDE.md                → hard rules and key decisions
3. context.md               → architecture and pipeline flow
4. docs/problems_and_solutions.md → known bugs and their status
5. phase2/pipeline.py       → the full orchestration logic
6. phase2/patch_gen/worker.py     → DeepSeek prompt + retry logic
7. phase2/patch_gen/sanitiser.py  → diff validation rules
8. phase2/executor/runner.py      → git apply + rollback
9. phase2/executor/regression.py  → before/after pytest comparison
10. phase2/memory/store.py        → append-only JSONL store
11. phase2/context_builder.py     → RAG context assembly
12. memory/memory.jsonl           → actual run history (real data)

DO NOT audit from memory. Read the actual files.

---

WHAT TO AUDIT (in this order):

1. PIPELINE INTEGRITY
   - Does the stage order in pipeline.py match CLAUDE.md exactly?
     Observer → LogParser → RegexClassifier → PreSafetyGate
     → ContextBuilder → DeepSeekWorker → PostSafetyValidation
     → Sanitiser → Executor → RegressionCheck → DecisionEngine → MemoryStore
   - Is the try/finally guarantee for memory write still in place? (Hard Rule 4)
   - Can any exception path skip the memory write?
   - Does rollback() get called on every failure path?

2. DEEPSEEK PROMPT QUALITY
   - Does the system prompt show an exact --- a/ +++ b/ format example?
   - Does the initial prompt specify the exact affected_file path?
   - Does the retry prompt include: rejection_reason + format reminder + affected_file?
   - Is DEEPSEEK_API_KEY read lazily (inside function, never at module level)?

3. SANITISER RULES
   - Does validate_patch() reject: missing +++ line, wrong file path, > 15 lines?
   - Does it check the affected_file path matches the --- a/<path> header?
   - Does strip_markdown_fences() correctly find the first --- line?

4. GIT APPLY SAFETY
   - Does runner.py use: --ignore-whitespace --recount flags?
   - Does rollback() use git checkout -- . (not git reset --hard)?
   - Are temp diff files written with newline="\n" (LF, not CRLF)?

5. MEMORY STORE HEALTH
   - Check memory/memory.jsonl: are all entries valid JSON?
   - Are all required fields present in every entry?
   - Is bug_signature always in format repo:ErrorType:keyword:file?
   - Any entries where decision="abstained" unexpectedly?
   - Are rejected entries building up for the same bug_signature (dedup issue)?

6. REGRESSION CHECK LOGIC
   - Is check_regression() comparing new_failures > before_failures (not total)?
   - Does run_tests() handle fixture with no tests gracefully?
   - Is the JSON report cleaned up after each run?

7. CONTEXT BUILDER (RAG)
   - Does build_context() return 3 sections: error summary, file content, past fixes?
   - Are past fixes capped at 3 entries?
   - Does it handle missing file gracefully (no crash)?
   - Is the token budget respected (error lines capped at 20)?

8. TEST QUALITY CHECK
   For each test file, ask:
   - Are tests verifying real behavior or just that code runs?
   - Are there tests for failure paths (not just happy path)?
   - Any test that would pass even if the module was broken?

9. KNOWN P-BUGS STATUS
   Check docs/problems_and_solutions.md. For each bug marked PENDING:
   - Is it actually still open or was it silently fixed?
   - Does any fixed bug have a regression risk now?

10. COST CHECK
    - How many DeepSeek API calls per pipeline run? (should be 1-3 max per case)
    - Is get_similar() doing a full file scan every call? (JSONL scan — acceptable for < 1000 entries)
    - Any unnecessary reads or writes in the hot path?

---

OUTPUT FORMAT:

### System Health: [GREEN / YELLOW / RED]
One line summary of overall state.

### Critical Issues (fix before next step)
For each: Problem → Why it happens → Impact → Minimal fix

### High Priority Issues
Same format. Fix soon but not blocking.

### Medium / Low Issues
Note but don't act on yet.

### Confirmed Working Correctly
List what you verified is solid. Be specific.

### Suggested Next Action
One thing only. The highest leverage move right now.

---

RULES FOR THIS AUDIT:
- Read the actual code. Do not guess.
- If something looks correct, say so explicitly — don't hedge.
- If you find a real bug, give the minimal fix only (no rewrites).
- Do not suggest anything that requires more than 20 lines of new code.
- Do not suggest features. Audit only what exists.
- Solo developer constraint: every finding must be fixable in one session.
```
