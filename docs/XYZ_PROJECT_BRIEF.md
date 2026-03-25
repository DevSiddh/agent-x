# XYZ PROJECT BRIEF — Universal LLM Template
# Author: CH Y SAI SIDDHARDHA
# Version: 2.0
# Last updated: 2026-03-25
#
# HOW TO USE:
# Step 1 → Copy this entire file
# Step 2 → Paste to ANY LLM (Claude, Gemini, ChatGPT, Perplexity)
# Step 3 → Add your idea at the bottom under "THE IDEA"
# Step 4 → LLM fills the OUTPUT BLOCK below
# Step 5 → Drop filled brief + any supporting files into /projects/new/:
#           your-project.yaml  ← this filled brief
#           *.md               ← research notes, LLM outputs, specs (Agent-Y reads these)
#           *.pdf              ← API docs (pdf_extractor.py handles)
#           *.csv / *.json     ← data samples (schema extracted automatically)
#           *.py / *.js        ← existing code to improve
# Step 6 → Agent-XYZ wakes up, reads everything, builds it

---

## INSTRUCTIONS FOR THE LLM (read before filling)

You are a staff-engineer-level project planner for an autonomous coding agent.
The agent is called Agent-XYZ. It has these hard constraints you MUST respect:

AGENT CONSTRAINTS (non-negotiable):
- Max 15 lines per file write (enforced by sanitiser)
- Max 3 files per task (enforced by Pydantic)
- Every task needs exactly 3 acceptance test cases: Happy Path + Edge Case + Error Case
- Test file is written FIRST before implementation (always)
- Language: Python 3.11 only (unless idea explicitly requires otherwise)
- No UI/frontend (agent has no visual judgment)
- Every module must be independently testable
- Pipeline must have a fallback if any external API fails

YOUR JOB:
Fill the OUTPUT BLOCK below completely and precisely for the given idea.
Do not add features the user didn't ask for.
Do not over-engineer. Minimum modules to make it work.
If a module needs >15 lines, split it into two smaller modules.
Every acceptance criteria case must have concrete input AND expected output values.
Not "valid input" — actual values like "RSI=28, price=45000".

QUALITY CHECK before submitting:
- [ ] Every task has exactly 3 acceptance cases with real values
- [ ] No task touches more than 3 files
- [ ] Module count is minimum needed (not maximum possible)
- [ ] All external APIs have a named fallback
- [ ] Done condition is measurable (number, not feeling)

---

## OUTPUT BLOCK (fill this completely)

### PROJECT SUMMARY
```
name:
one_liner:
trigger:          # cron / webhook / CLI / event
run_frequency:    # every N minutes / on-demand / continuous
language:         # Python 3.11
```

### DATA FLOW
```
inputs:
  - source:       # API name or file type
    format:       # JSON / CSV / text / webhook payload
    env_var:      # secret key name if needed
    free_or_paid: # free / paid / freemium

transformation_steps:
  - step: 1
    input:        # what comes in
    process:      # what you do to it
    output:       # what comes out
  - step: 2
    ...

output:
  format:         # JSON / Telegram message / DB row / file / PR
  destination:    # file path / API / Telegram / stdout
  example:        # one real example of final output
```

### CORE LOGIC
```
algorithm:        # Bayesian / Kelly / moving average / rule-based / etc.
formula:          # write it out if math is involved
signal_condition: # exactly when action fires
block_condition:  # exactly when action is blocked
```

### MODULES
```
# List minimum files needed. pipeline.py always last.
modules:
  - file: fetcher.py
    does: fetches raw data from source
  - file: processor.py
    does: transforms raw data
  - file: engine.py
    does: applies core logic, produces signal
  - file: executor.py
    does: acts on signal
  - file: pipeline.py
    does: wires all modules, runs on trigger
```

### TASKS FOR AGENT-XYZ
```
# Each task = one module. Test written first. Max 3 files. Max 15 lines each.

tasks:
  - task_id: T0
    action: scaffold
    description: Initialize project structure using cookiecutter template
    files_to_touch:
      - cookiecutter.json
    acceptance_criteria:
      target_function: scaffold
      cases:
        - inputs: ["fastapi-template", "my-project"]
          expected: "tests/ directory exists"
        - inputs: ["cli-template", "my-tool"]
          expected: "main.py exists"
        - inputs: ["invalid-template"]
          expected: "raises ValueError"

  - task_id: T1
    action: write_file
    description:
    files_to_touch:
      - tests/test_fetcher.py     # test FIRST
      - fetcher.py
    acceptance_criteria:
      target_function:
      cases:
        - inputs: []
          expected:               # HAPPY PATH — normal valid input
        - inputs: []
          expected:               # EDGE CASE — boundary or empty input
        - inputs: []
          expected:               # ERROR CASE — invalid input or API failure

  - task_id: T2
    action: write_file
    description:
    files_to_touch:
      - tests/test_processor.py
      - processor.py
    acceptance_criteria:
      target_function:
      cases:
        - inputs: []
          expected:
        - inputs: []
          expected:
        - inputs: []
          expected:

  # repeat for each module...
  # Use action: file_edit when modifying an existing file (search_block + replace_block)
  # Use action: write_file for new file creation only
```

### STACK
```
libraries:
  - name:         # exact pip install name
    used_for:

env_vars:
  - key:
    used_for:

storage:          # sqlite / json file / none
stores_what:
```

### HARD RULES
```
never:
  - Never act if confidence < ___
  - Never store ___
  - Never exceed ___ API calls per minute

always:
  - Always log every decision to ___
  - Always fallback to ___ if API fails

on_failure:
  max_retries: 3
  retry_changes: # what changes on retry (not same prompt twice)
  after_max_retries: # alert / skip / stop
```

### DONE CONDITION
```
v1_complete_when:   # exact measurable condition
minimum_shippable:  # least that counts as working
success_metric:     # number or observable output
out_of_scope_v1:
  - 1.
  - 2.
  - 3.
```

### SPIKE FIRST
```
# Prove core loop works before building all modules
spike_goal:         # what the spike proves
spike_input:        # exact test input
spike_output:       # what PASS looks like
spike_file:         # spike/run_spike_[name].py
```

---

## THE IDEA

[paste your project idea here — one paragraph is enough]
