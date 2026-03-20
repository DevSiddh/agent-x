---
name: always_run_tests
description: Always run tests after building/modifying code
type: feedback
---

After writing or modifying any code, always run the relevant tests immediately without waiting to be asked.

**Why:** User explicitly said "yes always run" when asked about running tests after a build.

**How to apply:** After every file write/edit, run pytest (or smoke test) for the affected module before responding as done.
