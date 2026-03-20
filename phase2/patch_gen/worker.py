"""
phase2/patch_gen/worker.py
DeepSeek patch generator with retry logic.
- DEEPSEEK_API_KEY read lazily (P4 pattern)
- Retry prompt includes rejection_reason + line_count (P11)
- Max 3 retries, each with a different prompt
"""

import os
import sys
from pathlib import Path

import structlog
from pydantic import BaseModel, ConfigDict

try:
    from phase2.classifier.regex_pass import ClassifierResult
    from phase2.patch_gen.sanitiser import SanitiserResult, validate_patch
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from phase2.classifier.regex_pass import ClassifierResult
    from phase2.patch_gen.sanitiser import SanitiserResult, validate_patch

log = structlog.get_logger()

MAX_RETRIES = 3
MODEL = "deepseek-chat"
BASE_URL = "https://api.deepseek.com"

SYSTEM_PROMPT = (
    "You are a CI/CD repair bot. "
    "Return ONLY a unified diff. No explanation. No markdown. "
    "No code fences. Start with --- and nothing else before it."
)


class WorkerResult(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    diff: str
    raw_response: str
    attempt: int
    model_used: str
    sanitiser_result: SanitiserResult


def _get_api_key() -> str:
    """Lazy DEEPSEEK_API_KEY getter — never at module level (P4 pattern)."""
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        raise EnvironmentError("DEEPSEEK_API_KEY is not set")
    return key


def _build_initial_prompt(
    error_lines: list[str],
    classifier_result: ClassifierResult,
    context: str,
) -> str:
    error_text = "\n".join(error_lines)
    return (
        f"CI/CD failure log:\n{error_text}\n\n"
        f"Failure category: {classifier_result.category}\n"
        f"Affected file: {classifier_result.affected_file}\n\n"
        f"File content:\n{context}\n\n"
        f"Fix this. Return unified diff targeting {classifier_result.affected_file} only."
    )


def _build_retry_prompt(
    error_lines: list[str],
    classifier_result: ClassifierResult,
    context: str,
    rejection_reason: str,
    line_count: int,
    attempt: int,
) -> str:
    """Retry prompt MUST differ from initial — includes rejection context (P11)."""
    error_text = "\n".join(error_lines)
    return (
        f"Your previous patch was REJECTED.\n"
        f"Reason: {rejection_reason}\n"
        f"Lines generated: {line_count} (maximum allowed: {MAX_RETRIES * 5})\n\n"
        f"Attempt {attempt} of {MAX_RETRIES}. Use a simpler, more targeted fix.\n\n"
        f"CI/CD failure log:\n{error_text}\n\n"
        f"Affected file: {classifier_result.affected_file}\n"
        f"File content:\n{context}\n\n"
        f"Return ONLY the unified diff. Start with ---. No markdown. No explanation."
    )


def generate_patch(
    error_lines: list[str],
    classifier_result: ClassifierResult,
    context: str,
    retries: int = 0,
) -> WorkerResult:
    """
    Call DeepSeek to generate a patch, validate it, retry on rejection.

    Args:
        error_lines:       Cleaned log lines from LogParser.
        classifier_result: ClassifierResult from regex classifier.
        context:           Affected file content (from ContextBuilder).
        retries:           How many retries already used (pipeline passes this).

    Returns:
        WorkerResult with final diff, raw response, attempt count, model used.

    Raises:
        EnvironmentError: If DEEPSEEK_API_KEY not set.
        RuntimeError:     If all retries exhausted without valid patch.
    """
    from openai import OpenAI

    api_key = _get_api_key()
    client = OpenAI(api_key=api_key, base_url=BASE_URL)

    last_result: SanitiserResult | None = None
    raw_response = ""

    for attempt in range(1, MAX_RETRIES + 1):
        if attempt == 1:
            user_prompt = _build_initial_prompt(error_lines, classifier_result, context)
        else:
            assert last_result is not None
            user_prompt = _build_retry_prompt(
                error_lines, classifier_result, context,
                rejection_reason=last_result.rejection_reason,
                line_count=last_result.line_count,
                attempt=attempt,
            )

        log.info("worker.calling_llm", attempt=attempt, model=MODEL)

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0,
        )

        raw_response = response.choices[0].message.content or ""
        log.info("worker.raw_response", attempt=attempt, length=len(raw_response))

        last_result = validate_patch(raw_response)

        if last_result.passed:
            log.info("worker.patch_accepted", attempt=attempt, lines=last_result.line_count)
            return WorkerResult(
                diff=last_result.diff,
                raw_response=raw_response,
                attempt=attempt,
                model_used=MODEL,
                sanitiser_result=last_result,
            )

        log.warning(
            "worker.patch_rejected",
            attempt=attempt,
            reason=last_result.rejection_reason,
            line_count=last_result.line_count,
        )

    raise RuntimeError(
        f"All {MAX_RETRIES} attempts exhausted. "
        f"Last rejection: {last_result.rejection_reason if last_result else 'unknown'}"
    )


if __name__ == "__main__":
    from unittest.mock import MagicMock, patch

    # Mock a valid LLM response
    mock_diff = (
        "--- a/requirements.txt\n"
        "+++ b/requirements.txt\n"
        "@@ -1,2 +1,3 @@\n"
        " requests==2.31.0\n"
        "+setuptools\n"
        " python-dotenv==1.0.0"
    )

    mock_choice = MagicMock()
    mock_choice.message.content = mock_diff
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    dummy_classifier = ClassifierResult(
        category="DependencyError",
        confidence=0.99,
        matched_pattern="ModuleNotFoundError",
        keyword="pkg_resources",
        affected_file="requirements.txt",
        bug_signature="smoke/test:DependencyError:pkg_resources:requirements.txt",
    )

    os.environ["DEEPSEEK_API_KEY"] = "smoke-key"

    with patch("openai.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        result = generate_patch(
            error_lines=["ModuleNotFoundError: No module named 'pkg_resources'"],
            classifier_result=dummy_classifier,
            context="requests==2.31.0\npython-dotenv==1.0.0\n",
        )

    assert result.diff.startswith("---"), f"diff should start with ---: {result.diff!r}"
    assert result.attempt == 1
    assert result.model_used == MODEL
    assert result.sanitiser_result.passed is True
    print(f"PASS  generate_patch: attempt={result.attempt} lines={result.sanitiser_result.line_count}")
    print("worker.py smoke test PASSED")
