"""
spike/run_spike.py — throwaway core-loop validator.
Proves DeepSeek → patch → git apply → pytest works before building 8 modules.
Run: python spike/run_spike.py
Requires: DEEPSEEK_API_KEY in .env
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
JSONL_PATH = REPO_ROOT / "phase1" / "dataset" / "synthetic.jsonl"
FIXTURE_PATH = REPO_ROOT / "fixtures" / "syn_001"


def load_case(case_id: str) -> dict:
    with open(JSONL_PATH) as f:
        for line in f:
            if line.strip():
                case = json.loads(line)
                if case["id"] == case_id:
                    return case
    raise ValueError(f"{case_id} not found in synthetic.jsonl")


def strip_markdown_fences(text: str) -> str:
    text = re.sub(r"^```[a-z]*\n", "", text, flags=re.MULTILINE)
    text = re.sub(r"^```$", "", text, flags=re.MULTILINE)
    for i, line in enumerate(text.splitlines()):
        if line.startswith("---"):
            return "\n".join(text.splitlines()[i:])
    return text


def count_diff_lines(diff: str) -> int:
    return sum(
        1 for line in diff.splitlines()
        if (line.startswith("+") or line.startswith("-"))
        and not line.startswith("+++")
        and not line.startswith("---")
    )


def ensure_git_repo(path: Path) -> None:
    """Init fixture as git repo if not already (conftest.py does this for pytest)."""
    if (path / ".git").exists():
        return
    git = ["git", "-C", str(path)]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "config", "user.email", "challayagneshsaisiddhardha@gmail.com"], check=True)
    subprocess.run([*git, "config", "user.name", "CH Y SAI SIDDHARDHA"], check=True)
    subprocess.run([*git, "config", "core.autocrlf", "false"], check=True)
    subprocess.run([*git, "config", "core.eol", "lf"], check=True)
    (path / ".gitattributes").write_text("* text eol=lf\n")
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "init buggy state"], check=True)


def main() -> None:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("FAIL: DEEPSEEK_API_KEY not set in .env")
        sys.exit(1)

    case = load_case("syn_001")
    error_log = "\n".join(case["error_log"])
    print(f"[spike] case: {case['id']} — {case['description']}")
    print(f"[spike] error_log:\n{error_log}\n")

    # 1 — Read affected file content from fixture
    affected_file = case["bug_signature"].split(":")[-1]  # e.g. requirements.txt
    file_path = FIXTURE_PATH / affected_file
    file_content = file_path.read_text() if file_path.exists() else ""
    print(f"[spike] affected file: {affected_file}\n{file_content}")

    # 2 — Call DeepSeek
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    print("[spike] calling DeepSeek...")
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": (
                    "Return ONLY a unified diff. No explanation. No markdown. "
                    "No code fences. Start with --- and nothing else before it."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"CI/CD failure log:\n{error_log}\n\n"
                    f"Affected file ({affected_file}):\n{file_content}\n"
                    f"Fix this. Return unified diff only targeting {affected_file}."
                ),
            },
        ],
        temperature=0,
    )
    raw = response.choices[0].message.content or ""
    print(f"[spike] raw LLM response:\n{raw}\n")

    # 2 — Strip fences
    diff = strip_markdown_fences(raw)
    line_count = count_diff_lines(diff)
    print(f"[spike] cleaned diff ({line_count} changed lines):\n{diff}\n")

    # 3 — git apply
    ensure_git_repo(FIXTURE_PATH)
    # Reset to clean state first (idempotent runs)
    subprocess.run(["git", "-C", str(FIXTURE_PATH), "checkout", "--", "."], capture_output=True)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False, newline="\n") as tf:
        tf.write(diff + "\n")
        tmp_path = tf.name

    try:
        apply = subprocess.run(
            ["git", "apply", tmp_path],
            cwd=FIXTURE_PATH, capture_output=True, text=True
        )
    finally:
        os.unlink(tmp_path)

    if apply.returncode != 0:
        print(f"FAIL at git apply:\n{apply.stderr.strip()}")
        sys.exit(1)
    print("[spike] git apply: OK")

    # 4 — pytest on fixture
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--tb=short", "-q"],
        cwd=FIXTURE_PATH, capture_output=True, text=True
    )
    print(f"[spike] pytest output:\n{result.stdout}{result.stderr}")

    if result.returncode == 0:
        print("=" * 50)
        print("SPIKE PASS — DeepSeek loop works end-to-end.")
        print("=" * 50)
    else:
        print("=" * 50)
        print("SPIKE FAIL — patch applied but tests failed.")
        print("=" * 50)
        sys.exit(1)


if __name__ == "__main__":
    main()
