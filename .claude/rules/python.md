---
paths:
  - "**/*.py"
---

# Python Rules — Agent-X

Loads automatically when Claude touches any .py file.

## Type Hints
- Every function must have type hints on all parameters and return value
- No exceptions — not even for __main__ blocks

## Logging
- structlog only — never `import logging`
- Every module gets `log = structlog.get_logger()` at module level
- Log events use dot notation: `log.info("module.event", key=value)`

## Data Models
- Pydantic v2 for all structured data — never plain dicts for API boundaries
- Use `model_copy(update={...})` not direct mutation

## Environment Variables
- `os.environ.get("KEY")` inside functions only — never at module level
- If missing and critical: raise `EnvironmentError("KEY not set")`

## Paths
- `pathlib.Path` everywhere — never string concatenation for paths
- Always use `cwd=` param in subprocess calls

## Exceptions
- Specific exceptions only — never bare `except:`
- Use `except Exception as exc:` only in finally-block patterns (P8)
- Log the exception before swallowing it

## Smoke Test
- Every module must have `if __name__ == "__main__":` block
- Smoke test must actually exercise the main function

## Tests
- Run `python -m pytest tests/ --tb=short -q` after every file written
- Tests must pass before moving to next file — no exceptions
