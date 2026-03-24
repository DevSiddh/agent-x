"""
agent_y/reasoner.py
Reasoning layer for Agent-X. Slots between ContextBuilder and DeepSeekWorker.
Decides HOW to fix before DeepSeekWorker generates the patch.
Does NOT generate code or patches — reasoning and strategy only.
"""

import json
from typing import Literal

import structlog
from openai import OpenAI
from pydantic import BaseModel, Field, field_validator

from phase2.classifier.regex_pass import ClassifierResult

log = structlog.get_logger()

MAX_RETRIES = 2

# ---------------------------------------------------------------------------
# Category → keyword mapping for strategy validation (P1)
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "DependencyError": ["dependency", "package", "install", "requirements", "setuptools", "module"],
    "EnvironmentError": ["env", "build", "config", "environment", "variable", "flag", "isolation", "pycache", "cache", "process"],
    "ConfigError": ["import", "config", "missing", "module", "table", "migration", "schema", "yaml"],
    "RuntimeError": ["schema", "type", "model", "namespace", "conflict", "field", "pydantic"],
    "NetworkError": ["connection", "retry", "timeout", "network", "port", "socket"],
    "BuildError": ["docker", "build", "image", "isolation"],
}

_SYSTEM_PROMPT = """You are a reasoning engine for a CI/CD self-healing system.
Your job is to analyze a build failure and decide the best fix strategy.

Return ONLY valid JSON. No markdown. No fences. No explanation outside the JSON.
Start your response with { and end with }.

Required JSON schema (all fields mandatory):
{
  "action": "repair" | "observe" | "escalate",
  "reasoning": "why this strategy was selected (1-2 sentences)",
  "strategy": "concrete fix approach — specific to the error, not generic",
  "confidence": 0.0 to 1.0,
  "files_to_change": ["list", "of", "file", "paths"] (max 3 files),
  "diagnosis": "one sentence: what is broken and why (plain English, no jargon)"
}

Rules:
- action must be exactly one of: repair, observe, escalate
- strategy must be specific to the error type — not generic advice
- files_to_change must only include files mentioned in the error context (max 3)
- confidence is your internal estimate — float between 0.0 and 1.0
- diagnosis must be plain English, max 200 chars, no code snippets
- Do NOT generate code or patches — reasoning and strategy only"""


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ReasonerOutput(BaseModel):
    action: Literal["repair", "observe", "escalate"]
    reasoning: str
    strategy: str
    confidence: float = Field(ge=0.0, le=1.0)
    files_to_change: list[str]
    diagnosis: str = ""  # 1 sentence: what is broken and why (plain English)

    @field_validator("files_to_change")
    @classmethod
    def cap_files(cls, v: list[str]) -> list[str]:
        if len(v) > 3:
            raise ValueError(f"files_to_change has {len(v)} items — max is 3")
        return v

    @field_validator("strategy")
    @classmethod
    def strategy_non_empty(cls, v: str) -> str:
        if not v or len(v.strip()) < 5:
            raise ValueError("strategy must be a non-empty, meaningful string")
        return v

    @field_validator("diagnosis")
    @classmethod
    def diagnosis_max_length(cls, v: str) -> str:
        if len(v) > 200:
            return v[:200]
        return v


class ReasonerError(Exception):
    """Raised when Reasoner exhausts retries or cannot produce valid output."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_json(raw: str) -> dict:
    """Strip markdown fences and parse the first JSON object found."""
    cleaned = raw.strip()
    for fence in ("```json", "```JSON", "```"):
        if cleaned.startswith(fence):
            cleaned = cleaned[len(fence):]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    start = cleaned.find("{")
    if start == -1:
        raise json.JSONDecodeError("No JSON object found", cleaned, 0)
    return json.loads(cleaned[start:])


def validate_strategy(strategy: str, category: str) -> bool:
    """
    Check that strategy is semantically related to the classified error category.
    Prevents valid JSON with wrong strategy from passing silently (P1).
    """
    keywords = _CATEGORY_KEYWORDS.get(category, [])
    return any(kw in strategy.lower() for kw in keywords)


def _filter_files(
    files: list[str], context: str, affected_file: str
) -> list[str]:
    """
    Keep only files mentioned in the context or matching the affected file.
    Hard cap at 3 to prevent wide hallucinated edits (P4).
    """
    allowed = [f for f in files if f in context or f == affected_file]
    if not allowed and files:
        # Fallback: keep affected_file if no overlap found
        allowed = [affected_file]
    return allowed[:3]


def _build_user_prompt(
    context: str, category: str, attempt: int, error_msg: str = ""
) -> str:
    if attempt == 0:
        return (
            f"{context}\n\n"
            f"What is the best fix strategy for this {category}? "
            f"Return ONLY the JSON object — no explanation outside it."
        )
    return (
        f"{context}\n\n"
        f"Previous attempt FAILED. Reason: {error_msg}\n\n"
        f"Required keys: action, reasoning, strategy, confidence, files_to_change\n"
        f"action must be one of: repair, observe, escalate\n"
        f"Return ONLY the JSON object starting with {{. No markdown. No fences."
    )


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------


def reason(context: str, classification: ClassifierResult) -> ReasonerOutput:
    """
    Reason about the best fix strategy for the classified error.

    Args:
        context:        Enriched context string from build_context().
        classification: ClassifierResult from regex classifier.

    Returns:
        ReasonerOutput with action, reasoning, strategy, confidence, files_to_change.

    Raises:
        ReasonerError: after MAX_RETRIES exhausted or strategy validation fails.
    """
    import os

    def _get_api_key() -> str:
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not key:
            raise EnvironmentError("DEEPSEEK_API_KEY not set")
        return key

    client = OpenAI(api_key=_get_api_key(), base_url="https://api.deepseek.com")

    category = classification.category
    affected_file = classification.affected_file
    last_error = ""

    for attempt in range(MAX_RETRIES + 1):
        user_prompt = _build_user_prompt(context, category, attempt, last_error)

        try:
            response = client.chat.completions.create(
                model="deepseek-reasoner",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=300,
            )
            raw = response.choices[0].message.content or ""

            parsed = _extract_json(raw)

            # Validate all required keys present
            required = {"action", "reasoning", "strategy", "confidence", "files_to_change", "diagnosis"}
            missing = required - set(parsed.keys())
            if missing:
                raise KeyError(f"Missing keys: {missing}")

            # Validate strategy relates to error category (P1)
            strategy = parsed["strategy"]
            if not validate_strategy(strategy, category):
                raise ValueError(
                    f"strategy '{strategy[:60]}...' does not match category '{category}'"
                )

            # Filter files to only context-relevant ones, cap at 3 (P4)
            files = _filter_files(
                parsed.get("files_to_change", []), context, affected_file
            )

            output = ReasonerOutput(
                action=parsed["action"],
                reasoning=parsed["reasoning"],
                strategy=strategy,
                confidence=float(parsed["confidence"]),
                files_to_change=files,
                diagnosis=str(parsed.get("diagnosis", "")),
            )

            # confidence logged as metadata only — never used in decisions (P3)
            log.info(
                "reasoner.ok",
                category=category,
                action=output.action,
                strategy=output.strategy[:80],
                confidence=output.confidence,
                files=output.files_to_change,
                attempt=attempt,
            )
            return output

        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            last_error = str(exc)
            log.warning(
                "reasoner.retry",
                attempt=attempt,
                max_retries=MAX_RETRIES,
                error=last_error,
                category=category,
            )

    raise ReasonerError(
        f"Reasoner exhausted {MAX_RETRIES} retries for category={category}. "
        f"Last error: {last_error}"
    )


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    from unittest.mock import MagicMock

    mock_response_content = json.dumps({
        "action": "repair",
        "reasoning": "Setuptools is missing from requirements, causing pkg_resources import to fail.",
        "strategy": "Add setuptools to requirements.txt to resolve the missing dependency.",
        "confidence": 0.9,
        "files_to_change": ["requirements.txt"],
    })

    mock_choice = MagicMock()
    mock_choice.message.content = mock_response_content
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    cls_result = ClassifierResult(
        category="DependencyError",
        confidence=0.99,
        matched_pattern=r"ModuleNotFoundError",
        keyword="pkg_resources",
        affected_file="requirements.txt",
        bug_signature="smoke/test:DependencyError:pkg_resources:requirements.txt",
    )

    context = (
        "Error Category: DependencyError\n"
        "Affected File: requirements.txt\n"
        "Error Log:\nModuleNotFoundError: No module named 'pkg_resources'"
    )

    # Inject mock by temporarily replacing the module-level OpenAI symbol
    os.environ["DEEPSEEK_API_KEY"] = "test-key"
    _real_OpenAI = globals()["OpenAI"]
    globals()["OpenAI"] = lambda **_kw: mock_client
    try:
        output = reason(context, cls_result)
    finally:
        globals()["OpenAI"] = _real_OpenAI

    print("=== Reasoner Smoke Test ===")
    print(f"action:          {output.action}")
    print(f"strategy:        {output.strategy}")
    print(f"confidence:      {output.confidence}  (metadata only — not used in decisions)")
    print(f"files_to_change: {output.files_to_change}")
    print("PASSED")
