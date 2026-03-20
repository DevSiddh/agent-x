"""
spike/run_spike_y.py — Agent-Y reasoning loop validator.
Proves DeepSeek can return structured JSON strategy (not code/patches) before building
agent_y/reasoner.py.
Tests 3 error categories: DependencyError, ConfigError, RuntimeError.
Run: python spike/run_spike_y.py
Requires: DEEPSEEK_API_KEY in .env
"""
import json
import sys
from pathlib import Path

import structlog
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

log = structlog.get_logger()

REPO_ROOT = Path(__file__).resolve().parent.parent
JSONL_PATH = REPO_ROOT / "phase1" / "dataset" / "synthetic.jsonl"

REQUIRED_KEYS = {"action", "reasoning", "strategy", "confidence", "files_to_change"}
VALID_ACTIONS = {"repair", "observe", "escalate"}

SYSTEM_PROMPT = """You are a reasoning engine for a CI/CD self-healing system.
Your job is to analyze a build failure and decide the best fix strategy.

Return ONLY valid JSON. No markdown. No fences. No explanation outside the JSON.
Start your response with { and end with }.

Required JSON schema (all fields mandatory):
{
  "action": "repair" | "observe" | "escalate",
  "reasoning": "why this strategy was selected (1-2 sentences)",
  "strategy": "concrete fix approach (specific to the error, not generic)",
  "confidence": 0.0 to 1.0,
  "files_to_change": ["list", "of", "file", "paths"] (max 3 files)
}

Rules:
- action must be exactly one of: repair, observe, escalate
- strategy must be specific to the error type shown — not generic advice
- files_to_change must only include files mentioned in the error context
- confidence is your internal estimate — float between 0.0 and 1.0
- Do NOT generate any code or patches — reasoning and strategy only"""


def load_cases(case_ids: list[str]) -> list[dict]:
    cases = []
    with open(JSONL_PATH) as f:
        for line in f:
            if line.strip():
                case = json.loads(line)
                if case["id"] in case_ids:
                    cases.append(case)
    return cases


def build_context(case: dict) -> str:
    error_lines = "\n".join(case["error_log"])
    return (
        f"Error Category: {case['failure_category']}\n"
        f"Affected File: {case['bug_signature'].split(':')[-1]}\n"
        f"Error Log:\n{error_lines}"
    )


def extract_json(raw: str) -> dict:
    """Strip markdown fences and extract JSON object from LLM response."""
    # Strip common fence patterns
    cleaned = raw.strip()
    for fence in ("```json", "```JSON", "```"):
        if cleaned.startswith(fence):
            cleaned = cleaned[len(fence):]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    # Find first { and parse from there
    start = cleaned.find("{")
    if start == -1:
        raise json.JSONDecodeError("No JSON object found in response", cleaned, 0)
    return json.loads(cleaned[start:])


def validate_output(parsed: dict, case_id: str) -> list[str]:
    """Return list of validation failures (empty = PASS)."""
    failures = []

    # Check all required keys present
    missing = REQUIRED_KEYS - set(parsed.keys())
    if missing:
        failures.append(f"Missing keys: {missing}")

    # Check action value
    action = parsed.get("action", "")
    if action not in VALID_ACTIONS:
        failures.append(f"Invalid action '{action}' — must be one of {VALID_ACTIONS}")

    # Check strategy is non-empty and non-generic
    strategy = parsed.get("strategy", "")
    if not strategy or len(strategy) < 10:
        failures.append(f"strategy too short or empty: '{strategy}'")

    # Check confidence is float in range
    confidence = parsed.get("confidence")
    if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
        failures.append(f"confidence must be float 0.0-1.0, got: {confidence!r}")

    # Check files_to_change is a list, capped at 3
    files = parsed.get("files_to_change", [])
    if not isinstance(files, list):
        failures.append(f"files_to_change must be a list, got: {type(files)}")
    elif len(files) > 3:
        failures.append(f"files_to_change has {len(files)} items — max is 3")

    return failures


def run_spike() -> None:
    target_cases = ["syn_001", "syn_003", "syn_004"]
    cases = load_cases(target_cases)

    if len(cases) != 3:
        print(f"FAIL — could not load all 3 cases, got {len(cases)}")
        sys.exit(1)

    def _get_api_key() -> str:
        import os
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not key:
            raise EnvironmentError("DEEPSEEK_API_KEY not set")
        return key

    client = OpenAI(api_key=_get_api_key(), base_url="https://api.deepseek.com")

    results: list[dict] = []

    for case in cases:
        case_id = case["id"]
        category = case["failure_category"]
        context = build_context(case)

        print(f"\n{'='*60}")
        print(f"Case: {case_id} | Category: {category}")
        print(f"{'='*60}")

        user_prompt = (
            f"{context}\n\n"
            f"What is the best fix strategy for this {category}? "
            f"Return ONLY the JSON object — no explanation outside it."
        )

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=300,
            )
            raw = response.choices[0].message.content or ""
            print(f"Raw response:\n{raw}\n")

            parsed = extract_json(raw)
            failures = validate_output(parsed, case_id)

            if failures:
                print(f"FAIL — {case_id}")
                for f in failures:
                    print(f"  ✗ {f}")
                results.append({"case": case_id, "passed": False, "failures": failures})
            else:
                print(f"PASS — {case_id}")
                print(f"  action:          {parsed['action']}")
                print(f"  strategy:        {parsed['strategy']}")
                print(f"  confidence:      {parsed['confidence']}")
                print(f"  files_to_change: {parsed['files_to_change']}")
                results.append({"case": case_id, "passed": True})

        except json.JSONDecodeError as exc:
            print(f"FAIL — {case_id} — JSON parse error: {exc}")
            results.append({"case": case_id, "passed": False, "failures": [str(exc)]})
        except EnvironmentError as exc:
            print(f"FAIL — {case_id} — env error: {exc}")
            sys.exit(1)

    # Final summary
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"\n{'='*60}")
    print(f"SPIKE RESULT: {passed}/{total} cases passed")
    if passed == total:
        print("SPIKE PASS — Agent-Y JSON reasoning loop validated.")
        print("Ready to build agent_y/reasoner.py (Step A1).")
    else:
        print("SPIKE FAIL — Fix prompt or JSON schema before building Step A1.")
        for r in results:
            if not r["passed"]:
                print(f"  {r['case']}: {r.get('failures', [])}")
        sys.exit(1)


if __name__ == "__main__":
    run_spike()
