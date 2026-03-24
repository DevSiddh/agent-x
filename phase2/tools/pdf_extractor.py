"""
phase2/tools/pdf_extractor.py — NotebookLM-style PDF summarizer for Agent-Y.

Extracts raw text from a PDF (via pdfplumber) then uses deepseek-chat to
produce a structured summary: what_it_does, key_endpoints, authentication,
rate_limits, key_params.

Never returns raw PDF dump — always structured output.
Only trigger when task contains "API" or "SDK" or user uploads PDF.

Usage:
    from phase2.tools.pdf_extractor import summarize_docs
    summary = summarize_docs(Path("openai_api.pdf"))
"""

import json
import os
import sys
from pathlib import Path

import structlog

log = structlog.get_logger()

_MAX_PDF_CHARS = 200 * 1024  # 200KB
_SUMMARY_SYSTEM_PROMPT = """\
You are a technical documentation summarizer. Extract structured information from the text below.
Return ONLY valid JSON with exactly these keys:
{
  "what_it_does": "1-2 sentence description of what this API/SDK does",
  "key_endpoints": ["endpoint1", "endpoint2"],
  "authentication": "how authentication works (API key, OAuth, etc.)",
  "rate_limits": "rate limit details, or 'not specified' if absent",
  "key_params": ["important_param_1", "important_param_2"]
}
Start with { and nothing else before it."""


def _extract_text(path: Path) -> str:
    """
    Extract raw text from a PDF file using pdfplumber.
    Returns empty string if pdfplumber not installed or file unreadable.
    Never raises.
    """
    try:
        import pdfplumber
    except ImportError:
        log.warning("pdf_extractor.pdfplumber_not_installed")
        return ""

    try:
        text_parts: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
                if sum(len(t) for t in text_parts) > _MAX_PDF_CHARS:
                    break

        full_text = "\n".join(text_parts)
        if len(full_text) > _MAX_PDF_CHARS:
            full_text = full_text[:_MAX_PDF_CHARS]

        log.info("pdf_extractor.extracted", path=str(path), chars=len(full_text))
        return full_text
    except Exception as exc:
        log.warning("pdf_extractor.extract_error", path=str(path), error=str(exc))
        return ""


def _call_llm(raw_text: str) -> dict:
    """
    Call deepseek-chat to summarize raw PDF text into structured output.
    Returns dict with the 5 structured keys. Never raises.
    """
    def _get_api_key() -> str:
        return os.environ.get("DEEPSEEK_API_KEY", "")

    api_key = _get_api_key()
    if not api_key:
        log.warning("pdf_extractor.no_api_key")
        return {}

    # Cap text to fit in context window
    text_cap = raw_text[:8000]

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
        )
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": _SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": f"Document text:\n\n{text_cap}"},
            ],
            max_tokens=800,
            temperature=0.0,
        )
        raw = response.choices[0].message.content or ""
        # Strip markdown fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.splitlines()[1:])
            if raw.endswith("```"):
                raw = raw[: raw.rfind("```")]

        return json.loads(raw)
    except Exception as exc:
        log.warning("pdf_extractor.llm_error", error=str(exc))
        return {}


def summarize_docs(path: Path) -> str:
    """
    Summarize a PDF document into structured output for Agent-Y.

    Args:
        path: Path to the PDF file.

    Returns:
        JSON string with structured summary (what_it_does, key_endpoints,
        authentication, rate_limits, key_params).
        Returns empty string on any failure. Never raises. Never returns raw PDF dump.
    """
    path = Path(path)
    if not path.exists():
        log.warning("pdf_extractor.file_missing", path=str(path))
        return ""

    if path.suffix.lower() != ".pdf":
        log.warning("pdf_extractor.not_pdf", path=str(path))
        return ""

    raw_text = _extract_text(path)
    if not raw_text.strip():
        log.warning("pdf_extractor.empty_text", path=str(path))
        return ""

    structured = _call_llm(raw_text)
    if not structured:
        return ""

    # Validate structure
    required_keys = {"what_it_does", "key_endpoints", "authentication", "rate_limits", "key_params"}
    if not required_keys.issubset(structured.keys()):
        log.warning("pdf_extractor.incomplete_structure", keys=list(structured.keys()))
        return ""

    result = json.dumps(structured, indent=2)
    log.info("pdf_extractor.done", path=str(path), chars=len(result))
    return result


if __name__ == "__main__":
    import tempfile

    # Test: non-existent file
    empty = summarize_docs(Path("/nonexistent/file.pdf"))
    assert empty == "", "missing file must return empty string"
    print("PASS  missing file → empty string")

    # Test: non-PDF file
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"not a pdf")
        tmp_txt = f.name
    not_pdf = summarize_docs(Path(tmp_txt))
    assert not_pdf == "", "non-PDF must return empty string"
    Path(tmp_txt).unlink(missing_ok=True)
    print("PASS  non-PDF → empty string")

    # Test: requires pdfplumber + DEEPSEEK_API_KEY to fully test
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("SKIP  summarize_docs: DEEPSEEK_API_KEY not set")
    else:
        print("SKIP  summarize_docs: no test PDF available in smoke test")

    print("pdf_extractor.py smoke test PASSED")
