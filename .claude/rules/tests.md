---
paths:
  - "tests/**/*.py"
---

# Test Rules — Agent-X

Loads automatically when Claude touches any file in tests/.

## Coverage
- Every test class must cover: happy path + at least one failure path
- If a module can fail (missing file, bad input, external call) → test that failure

## Mocking
- Mock only external calls: subprocess, HTTP requests, DeepSeek API
- Never mock core logic — if you mock it, you're not testing it
- Use `unittest.mock.patch.object` — never monkeypatch internal functions

## File I/O in Tests
- Always use `tmp_path` pytest fixture for any file read/write
- Never hardcode absolute paths in tests
- Never write to the real `memory/memory.jsonl` in tests

## Naming
- Test function names must describe the behavior: `test_validate_patch_rejects_missing_plus_header`
- Not: `test_1`, `test_case`, `test_it_works`

## Fixtures
- Use `fixtures/syn_001..005/` for real git apply tests
- Each fixture is a real git repo — treat it as read-only, rollback after use

## Assertions
- Assert specific values, not just truthiness
- Wrong: `assert result` → Right: `assert result.decision == "accepted"`

## Never
- Never use `time.sleep()` in tests
- Never skip a test with `pytest.skip()` without a comment explaining why
- Never move to next file if any test in the suite is failing
