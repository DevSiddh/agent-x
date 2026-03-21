# Agent-X Test Cases — 18 Controlled CI Failures

## How to use
1. Copy `ci.yml` → `.github/workflows/ci.yml` in your test repo (one time)
2. For each test: copy all files from the case folder to your test repo root
3. Push to main → CI fails → webhook fires → Agent-X processes

## Test Case Reference

| Case    | Folder   | Category        | Level | Error                              | Expected Decision |
|---------|----------|-----------------|-------|------------------------------------|-------------------|
| dep_l1  | dep_l1/  | DependencyError | 1     | pandas not installed               | accepted          |
| dep_l2  | dep_l2/  | DependencyError | 2     | numpy + scipy not installed        | accepted          |
| dep_l3  | dep_l3/  | DependencyError | 3     | cryptography chain via utils.py    | accepted          |
| env_l1  | env_l1/  | EnvironmentError| 1     | API_KEY env var not set            | accepted          |
| env_l2  | env_l2/  | EnvironmentError| 2     | circular import module_a ↔ b       | accepted/abstained|
| env_l3  | env_l3/  | EnvironmentError| 3     | 3 missing env vars in config class | accepted/abstained|
| cfg_l1  | cfg_l1/  | ConfigError     | 1     | KeyError: 'database'               | accepted          |
| cfg_l2  | cfg_l2/  | ConfigError     | 2     | no such table: users               | accepted          |
| cfg_l3  | cfg_l3/  | ConfigError     | 3     | malformed YAML (unclosed bracket)  | accepted          |
| run_l1  | run_l1/  | RuntimeError    | 1     | AssertionError: discount > 100     | accepted          |
| run_l2  | run_l2/  | RuntimeError    | 2     | Pydantic model_ namespace conflict | accepted          |
| run_l3  | run_l3/  | RuntimeError    | 3     | TypeError: int(None) in chain      | accepted          |
| bld_l1  | bld_l1/  | BuildError      | 1     | docker build failed: bad tag       | accepted/abstained|
| bld_l2  | bld_l2/  | BuildError      | 2     | build isolation: setup.py broken   | accepted/abstained|
| bld_l3  | bld_l3/  | BuildError      | 3     | failed to build image: bad base    | accepted/abstained|
| mix_l1  | mix_l1/  | DependencyError | 1     | redis missing + config key missing | accepted          |
| mix_l2  | mix_l2/  | DependencyError | 2     | sqlalchemy missing + no table      | accepted          |
| mix_l3  | mix_l3/  | RuntimeError    | 3     | pydantic + env + no table (hard)   | structural/abstain|

## Fastest path to unlock gates

### C2 gate (same signature ≥ 3 times)
Push dep_l1 three times in a row → same bug_signature every time.

### v2.2 gate (20+ accepted total)
Mix dep_l1, dep_l2, cfg_l1, cfg_l2, run_l1, run_l2 — all reliably accepted.
Avoid bld_* and mix_l3 until gates are unlocked — those may abstain.

## Copy command (Windows)
```
# Copy dep_l1 case to test repo root
xcopy /Y "test_repo_cases\cases\dep_l1\*" "path\to\your\test-repo\"
```
