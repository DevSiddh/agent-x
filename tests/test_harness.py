"""
tests/test_harness.py — Unit tests for harness.py.

All DeepSeek / apply_patch calls are mocked.
Tests use tmp_path to avoid touching real memory.jsonl or case dirs.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import phase2.memory.store as mem_store
import harness as h


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolate_memory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Redirect memory writes to a temp file."""
    monkeypatch.setattr(mem_store, "_memory_path", lambda: tmp_path / "memory.jsonl")


@pytest.fixture()
def fake_case(tmp_path: Path) -> Path:
    """Create a minimal fake case directory with a failing main.py."""
    case_dir = tmp_path / "fake_case"
    case_dir.mkdir()
    # Broken main.py — raises AssertionError
    (case_dir / "main.py").write_text(
        "assert False, 'discount 150 must be between 0 and 100'\n",
        encoding="utf-8",
    )
    return case_dir


# ---------------------------------------------------------------------------
# _run_main
# ---------------------------------------------------------------------------

class TestRunMain:
    def test_failing_script_returns_exit_1(self, tmp_path: Path) -> None:
        script = tmp_path / "main.py"
        script.write_text("raise AssertionError('discount 150 > 100')\n", encoding="utf-8")
        lines, code = h._run_main(tmp_path)
        assert code != 0
        assert any("AssertionError" in l for l in lines)

    def test_passing_script_returns_exit_0(self, tmp_path: Path) -> None:
        script = tmp_path / "main.py"
        script.write_text("print('ok')\n", encoding="utf-8")
        lines, code = h._run_main(tmp_path)
        assert code == 0

    def test_output_lines_non_empty(self, tmp_path: Path) -> None:
        script = tmp_path / "main.py"
        script.write_text("import sys; sys.stderr.write('error here\\n')\nimport sys; sys.exit(1)\n", encoding="utf-8")
        lines, code = h._run_main(tmp_path)
        assert code == 1
        assert any("error here" in l for l in lines)


# ---------------------------------------------------------------------------
# run_case — skip paths
# ---------------------------------------------------------------------------

class TestRunCaseSkips:
    def test_exit_0_case_is_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Case that passes locally → skipped, no classify called."""
        monkeypatch.setattr(h, "CASES_ROOT", tmp_path)
        case_dir = tmp_path / "dep_l1"
        case_dir.mkdir()
        (case_dir / "main.py").write_text("print('ok')\n", encoding="utf-8")

        result = h.run_case("dep_l1", no_llm=True)
        assert result["decision"] == "skipped"
        assert result["category"] is None

    def test_low_confidence_returns_observer(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Confidence below gate → observer mode, no LLM called."""
        monkeypatch.setattr(h, "CASES_ROOT", tmp_path)
        case_dir = tmp_path / "run_l1"
        case_dir.mkdir()
        (case_dir / "main.py").write_text(
            "raise Exception('some ambiguous error')\n", encoding="utf-8"
        )

        mock_clf = MagicMock()
        mock_clf.category = "RuntimeError"
        mock_clf.confidence = 0.40
        mock_clf.bug_signature = "test_repo_cases/run_l1:RuntimeError:unknown:main.py"
        mock_clf.affected_file = "main.py"
        mock_clf.matched_pattern = "exception"
        mock_clf.keyword = "unknown"

        mock_gate = MagicMock()
        mock_gate.passed = False
        mock_gate.mode = "observer"
        mock_gate.reason = "confidence too low"

        monkeypatch.setattr(h, "classify", lambda lines, repo: mock_clf)
        monkeypatch.setattr(h, "gate_check", lambda clf: mock_gate)

        result = h.run_case("run_l1", no_llm=True)
        assert result["decision"] == "observer"
        assert result["confidence"] == 0.40

    def test_no_llm_flag_stops_before_deepseek(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--no-llm → classify_only, generate_patch never called."""
        monkeypatch.setattr(h, "CASES_ROOT", tmp_path)
        case_dir = tmp_path / "run_l1"
        case_dir.mkdir()
        (case_dir / "main.py").write_text(
            "assert False, 'discount 150 must be between 0 and 100'\n",
            encoding="utf-8",
        )

        mock_clf = MagicMock()
        mock_clf.category = "RuntimeError"
        mock_clf.confidence = 0.99
        mock_clf.bug_signature = "test_repo_cases/run_l1:RuntimeError:assertion_error:main.py"
        mock_clf.affected_file = "main.py"
        mock_clf.keyword = "assertion_error"

        mock_gate = MagicMock()
        mock_gate.passed = True
        mock_gate.mode = "repair"

        generate_called: list[int] = []
        monkeypatch.setattr(h, "classify", lambda lines, repo: mock_clf)
        monkeypatch.setattr(h, "gate_check", lambda clf: mock_gate)
        monkeypatch.setattr(h, "generate_patch", lambda **kw: generate_called.append(1))

        result = h.run_case("run_l1", no_llm=True)
        assert result["decision"] == "classify_only"
        assert len(generate_called) == 0


# ---------------------------------------------------------------------------
# run_case — full pipeline (LLM mocked)
# ---------------------------------------------------------------------------

class TestRunCaseFullPipeline:
    def _setup_case(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        monkeypatch.setattr(h, "CASES_ROOT", tmp_path)
        case_dir = tmp_path / "run_l1"
        case_dir.mkdir()
        # Script that fails first run, passes after fix is applied
        (case_dir / "main.py").write_text(
            "assert False, 'discount 150 must be between 0 and 100'\n",
            encoding="utf-8",
        )
        return case_dir

    def _mock_pipeline(self, monkeypatch: pytest.MonkeyPatch, apply_success: bool = True, verify_exit: int = 0) -> None:
        mock_clf = MagicMock()
        mock_clf.category = "RuntimeError"
        mock_clf.confidence = 0.99
        mock_clf.bug_signature = "test_repo_cases/run_l1:RuntimeError:assertion_error:main.py"
        mock_clf.affected_file = "main.py"
        mock_clf.keyword = "assertion_error"
        mock_clf.matched_pattern = "AssertionError"

        mock_gate = MagicMock()
        mock_gate.passed = True
        mock_gate.mode = "repair"

        mock_sanitiser = MagicMock()
        mock_sanitiser.passed = True
        mock_sanitiser.line_count = 3

        mock_worker = MagicMock()
        mock_worker.diff = "--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@\n-assert False\n+pass\n"
        mock_worker.sanitiser_result = mock_sanitiser
        mock_worker.model_used = "deepseek-chat"
        mock_worker.attempt = 1

        mock_apply = MagicMock()
        mock_apply.success = apply_success
        mock_apply.error = "" if apply_success else "patch failed"

        monkeypatch.setattr(h, "classify", lambda lines, repo: mock_clf)
        monkeypatch.setattr(h, "gate_check", lambda clf: mock_gate)
        monkeypatch.setattr(h, "build_context", lambda clf, path, error_lines=None: "mock context")
        monkeypatch.setattr(h, "generate_patch", lambda **kw: mock_worker)
        monkeypatch.setattr(h, "apply_patch", lambda diff, path: mock_apply)
        monkeypatch.setattr(h, "rollback", lambda path: None)
        monkeypatch.setattr(h, "_ensure_git_repo", lambda path: None)

        # Second _run_main call (verify) returns exit code via side_effect
        original_run_main = h._run_main
        call_count = [0]

        def mock_run_main(path: Path) -> tuple[list[str], int]:
            call_count[0] += 1
            if call_count[0] == 1:
                return ["AssertionError: discount 150 > 100"], 1  # first run — broken
            return [], verify_exit  # second run — after patch

        monkeypatch.setattr(h, "_run_main", mock_run_main)

    def test_accepted_when_verify_passes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._setup_case(tmp_path, monkeypatch)
        self._mock_pipeline(monkeypatch, apply_success=True, verify_exit=0)

        result = h.run_case("run_l1")
        assert result["decision"] == "accepted"
        assert result["verify_pass"] is True

    def test_rejected_when_verify_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._setup_case(tmp_path, monkeypatch)
        self._mock_pipeline(monkeypatch, apply_success=True, verify_exit=1)

        result = h.run_case("run_l1")
        assert result["decision"] == "rejected"
        assert result["verify_pass"] is False

    def test_rejected_when_apply_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._setup_case(tmp_path, monkeypatch)
        self._mock_pipeline(monkeypatch, apply_success=False)

        result = h.run_case("run_l1")
        assert result["decision"] == "rejected"
        assert result["verify_pass"] is None

    def test_memory_written_on_accepted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import json
        self._setup_case(tmp_path, monkeypatch)
        self._mock_pipeline(monkeypatch, apply_success=True, verify_exit=0)

        h.run_case("run_l1")

        memory_file = tmp_path / "memory.jsonl"
        assert memory_file.exists()
        entries = [json.loads(l) for l in memory_file.read_text().splitlines() if l.strip()]
        assert len(entries) == 1
        assert entries[0]["source"] == "harness"
        assert entries[0]["decision"] == "accepted"

    def test_memory_written_on_exception(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import json
        self._setup_case(tmp_path, monkeypatch)

        mock_clf = MagicMock()
        mock_clf.category = "RuntimeError"
        mock_clf.confidence = 0.99
        mock_clf.bug_signature = "test_repo_cases/run_l1:RuntimeError:x:main.py"
        mock_clf.affected_file = "main.py"
        mock_clf.keyword = "x"
        mock_clf.matched_pattern = "AssertionError"

        mock_gate = MagicMock()
        mock_gate.passed = True
        mock_gate.mode = "repair"

        monkeypatch.setattr(h, "classify", lambda lines, repo: mock_clf)
        monkeypatch.setattr(h, "gate_check", lambda clf: mock_gate)
        monkeypatch.setattr(h, "build_context", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("network error")))
        monkeypatch.setattr(h, "rollback", lambda path: None)
        monkeypatch.setattr(h, "_ensure_git_repo", lambda path: None)

        call_count = [0]
        def mock_run(path: Path) -> tuple[list[str], int]:
            call_count[0] += 1
            return ["AssertionError: bad input"], 1
        monkeypatch.setattr(h, "_run_main", mock_run)

        result = h.run_case("run_l1")
        assert result["decision"] == "error"

        memory_file = tmp_path / "memory.jsonl"
        assert memory_file.exists()  # always written
