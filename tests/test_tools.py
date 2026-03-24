"""
tests/test_tools.py — Tests for phase2/tools/* (D0)

Covers:
  - ast_mapper: signatures only, max_tokens cap
  - blast_radius: 3 tiers, max 8 files, empty fallback
  - web_reader: noise stripping, token cap, bad URL
  - github_search: no token, empty query, stars filter, snippet limit
  - pdf_extractor: missing file, non-PDF, structured output
  - security_gate: secret detection, clean patch, missing tool
  - regression D0: extract_failing_test, verify_pre_patch, shadow_type_check
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure repo root is on path
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))


# ---------------------------------------------------------------------------
# ast_mapper
# ---------------------------------------------------------------------------

class TestAstMapper:
    def test_returns_only_signatures(self, tmp_path: Path) -> None:
        """map_repo must return class/function signatures, NOT function bodies."""
        src = tmp_path / "mymod.py"
        src.write_text(
            "class Foo:\n"
            "    def bar(self, x: int) -> str:\n"
            "        return str(x)\n"
            "\n"
            "def top_level(a: str) -> None:\n"
            "    print(a)\n"
        )
        # Create minimal git structure
        (tmp_path / "__init__.py").write_text("")
        from phase2.tools.ast_mapper import map_repo

        result = map_repo(tmp_path, max_tokens=2000)
        assert "class Foo" in result
        assert "def bar" in result
        assert "return str(x)" not in result, "function body must NOT appear in output"
        assert "print(a)" not in result, "function body must NOT appear in output"

    def test_respects_max_tokens_cap(self, tmp_path: Path) -> None:
        """map_repo must stop adding files once output exceeds max_tokens."""
        # Create many Python files to exceed token budget
        for i in range(30):
            f = tmp_path / f"mod_{i:02d}.py"
            f.write_text(
                f"class BigClass{i}:\n"
                + "\n".join(f"    def method_{j}(self): pass" for j in range(20))
            )
        from phase2.tools.ast_mapper import map_repo

        result = map_repo(tmp_path, max_tokens=200)
        # Result must be under 200 * 4 * 1.1 chars (some overhead for truncation message)
        assert len(result) < 200 * 4 * 2, "output greatly exceeded max_tokens cap"

    def test_excludes_test_files(self, tmp_path: Path) -> None:
        """map_repo must exclude test files from the skeleton."""
        (tmp_path / "src.py").write_text("def real_func(x: int) -> int:\n    return x\n")
        (tmp_path / "test_src.py").write_text("def test_real_func(): assert True\n")
        from phase2.tools.ast_mapper import map_repo

        result = map_repo(tmp_path, max_tokens=2000)
        assert "real_func" in result
        assert "test_real_func" not in result

    def test_empty_repo_returns_empty(self, tmp_path: Path) -> None:
        """map_repo on a directory with no .py files must return empty string."""
        (tmp_path / "README.md").write_text("# test")
        from phase2.tools.ast_mapper import map_repo

        result = map_repo(tmp_path)
        assert result == ""

    def test_nonexistent_path_returns_empty(self) -> None:
        from phase2.tools.ast_mapper import map_repo

        result = map_repo(Path("/nonexistent/path"))
        assert result == ""


# ---------------------------------------------------------------------------
# blast_radius
# ---------------------------------------------------------------------------

class TestBlastRadius:
    def test_tier1_always_affected_file(self, tmp_path: Path) -> None:
        """First element must always be the affected_file."""
        affected = tmp_path / "main.py"
        affected.write_text("x = 1\n")
        from phase2.tools.blast_radius import get_blast_radius

        result = get_blast_radius(tmp_path, affected)
        assert result[0] == affected

    def test_tier2_includes_imports(self, tmp_path: Path) -> None:
        """Files imported by affected_file must appear in result (tier 2)."""
        dep = tmp_path / "dep.py"
        dep.write_text("def helper(): pass\n")
        affected = tmp_path / "main.py"
        affected.write_text("from dep import helper\n")
        from phase2.tools.blast_radius import get_blast_radius

        result = get_blast_radius(tmp_path, affected)
        assert dep in result

    def test_tier3_includes_importers(self, tmp_path: Path) -> None:
        """Files that import affected_file must appear in result (tier 3)."""
        affected = tmp_path / "store.py"
        affected.write_text("class Store: pass\n")
        consumer = tmp_path / "pipeline.py"
        consumer.write_text("from store import Store\n")
        from phase2.tools.blast_radius import get_blast_radius

        result = get_blast_radius(tmp_path, affected)
        assert consumer in result

    def test_max_8_files(self, tmp_path: Path) -> None:
        """get_blast_radius must never return more than 8 files."""
        affected = tmp_path / "hub.py"
        imports = []
        for i in range(15):
            f = tmp_path / f"mod_{i}.py"
            f.write_text(f"from hub import x\n")
            imports.append(f"import mod_{i}")
        affected.write_text("\n".join(imports))
        from phase2.tools.blast_radius import get_blast_radius, _MAX_FILES

        result = get_blast_radius(tmp_path, affected)
        assert len(result) <= _MAX_FILES

    def test_returns_affected_only_when_no_imports(self, tmp_path: Path) -> None:
        """If affected_file has no imports and nothing imports it, return [affected]."""
        affected = tmp_path / "isolated.py"
        affected.write_text("x = 42\n")
        from phase2.tools.blast_radius import get_blast_radius

        result = get_blast_radius(tmp_path, affected)
        assert result == [affected]

    def test_nonexistent_affected_file_returns_empty(self, tmp_path: Path) -> None:
        from phase2.tools.blast_radius import get_blast_radius

        result = get_blast_radius(tmp_path, tmp_path / "ghost.py")
        assert result == []


# ---------------------------------------------------------------------------
# web_reader
# ---------------------------------------------------------------------------

class TestWebReader:
    def test_invalid_url_returns_empty(self) -> None:
        from phase2.tools.web_reader import fetch_docs

        assert fetch_docs("not-a-url") == ""
        assert fetch_docs("") == ""
        assert fetch_docs("ftp://old-protocol.com") == ""

    def test_fetch_error_returns_empty(self) -> None:
        """Network failure must return empty string, never raise."""
        from phase2.tools.web_reader import fetch_docs

        with patch("httpx.get", side_effect=Exception("network error")):
            result = fetch_docs("https://example.com")
        assert result == ""

    def test_token_cap_respected(self) -> None:
        """Response must be truncated to max_tokens."""
        from phase2.tools.web_reader import fetch_docs

        # Create a very long fake HTML response
        long_html = "<html><body>" + "A" * 50000 + "</body></html>"
        mock_resp = MagicMock()
        mock_resp.text = long_html
        mock_resp.raise_for_status.return_value = None

        with patch("httpx.get", return_value=mock_resp):
            result = fetch_docs("https://example.com", max_tokens=100)
        # 100 tokens * 4 chars + some margin
        assert len(result) <= 100 * 4 + 100

    def test_noise_stripped(self) -> None:
        """Navigation, footer, scripts must be stripped."""
        from phase2.tools.web_reader import _strip_noise

        html = (
            "<html><body>"
            "<nav>Navigation menu</nav>"
            "<main><p>Actual content here.</p></main>"
            "<footer>Footer text</footer>"
            "<script>alert('ad')</script>"
            "</body></html>"
        )
        result = _strip_noise(html)
        assert "Actual content here" in result
        assert "Navigation menu" not in result
        assert "Footer text" not in result
        assert "alert" not in result


# ---------------------------------------------------------------------------
# github_search
# ---------------------------------------------------------------------------

class TestGithubSearch:
    def test_empty_query_returns_empty(self) -> None:
        from phase2.tools.github_search import search_code

        assert search_code("") == []
        assert search_code("   ") == []

    def test_no_token_returns_empty(self) -> None:
        from phase2.tools.github_search import search_code

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GITHUB_TOKEN", None)
            result = search_code("test query")
        assert result == []

    def test_api_error_returns_empty(self) -> None:
        """Any API error must return empty list, never raise."""
        from phase2.tools.github_search import search_code

        with patch.dict(os.environ, {"GITHUB_TOKEN": "fake_token"}):
            with patch("requests.get", side_effect=Exception("connection error")):
                result = search_code("test query")
        assert result == []

    def test_max_snippets_limit(self) -> None:
        """search_code must return at most _MAX_SNIPPETS results."""
        from phase2.tools.github_search import search_code, _MAX_SNIPPETS

        # Mock GitHub API returning many items with high stars
        mock_items = [
            {
                "repository": {"full_name": f"owner/repo{i}", "stargazers_count": 1000},
                "path": f"file{i}.py",
                "html_url": f"https://github.com/owner/repo{i}/blob/main/file{i}.py",
            }
            for i in range(10)
        ]
        mock_search_resp = MagicMock()
        mock_search_resp.status_code = 200
        mock_search_resp.json.return_value = {"items": mock_items}
        mock_search_resp.raise_for_status.return_value = None

        # Raw file response with relevant content
        mock_raw_resp = MagicMock()
        mock_raw_resp.status_code = 200
        mock_raw_resp.text = "import setuptools\nsetuptools.setup()\n"

        with patch.dict(os.environ, {"GITHUB_TOKEN": "fake_token"}):
            with patch("requests.get", side_effect=[mock_search_resp] + [mock_raw_resp] * 10):
                result = search_code("setuptools setup")

        assert len(result) <= _MAX_SNIPPETS

    def test_low_stars_filtered(self) -> None:
        """Repos with fewer than _MIN_STARS stars must be filtered out."""
        from phase2.tools.github_search import search_code, _MIN_STARS

        mock_items = [
            {
                "repository": {"full_name": "owner/tiny-repo", "stargazers_count": 3},
                "path": "file.py",
                "html_url": "https://github.com/owner/tiny-repo/blob/main/file.py",
            }
        ]
        mock_search_resp = MagicMock()
        mock_search_resp.status_code = 200
        mock_search_resp.json.return_value = {"items": mock_items}
        mock_search_resp.raise_for_status.return_value = None

        with patch.dict(os.environ, {"GITHUB_TOKEN": "fake_token"}):
            with patch("requests.get", return_value=mock_search_resp):
                result = search_code("test query")

        # No snippets — all filtered by star count
        assert result == []


# ---------------------------------------------------------------------------
# pdf_extractor
# ---------------------------------------------------------------------------

class TestPdfExtractor:
    def test_missing_file_returns_empty(self) -> None:
        from phase2.tools.pdf_extractor import summarize_docs

        result = summarize_docs(Path("/nonexistent/file.pdf"))
        assert result == ""

    def test_non_pdf_returns_empty(self, tmp_path: Path) -> None:
        from phase2.tools.pdf_extractor import summarize_docs

        txt_file = tmp_path / "doc.txt"
        txt_file.write_text("This is not a PDF")
        result = summarize_docs(txt_file)
        assert result == ""

    def test_structured_output_has_required_keys(self) -> None:
        """summarize_docs must return JSON with all 5 required keys."""
        from phase2.tools.pdf_extractor import summarize_docs

        fake_summary = {
            "what_it_does": "Test API for testing",
            "key_endpoints": ["/v1/test", "/v1/status"],
            "authentication": "API key in header",
            "rate_limits": "100 req/min",
            "key_params": ["api_key", "timeout"],
        }

        with patch("phase2.tools.pdf_extractor._extract_text", return_value="some PDF text"):
            with patch("phase2.tools.pdf_extractor._call_llm", return_value=fake_summary):
                # Create a fake PDF file
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                    f.write(b"%PDF-1.4 fake")
                    tmp_pdf = Path(f.name)
                try:
                    result = summarize_docs(tmp_pdf)
                    assert result != "", "must return non-empty result"
                    data = json.loads(result)
                    for key in ["what_it_does", "key_endpoints", "authentication",
                                "rate_limits", "key_params"]:
                        assert key in data, f"missing key: {key}"
                finally:
                    tmp_pdf.unlink(missing_ok=True)

    def test_never_returns_raw_dump(self) -> None:
        """summarize_docs must return structured JSON, not raw text dump."""
        from phase2.tools.pdf_extractor import summarize_docs

        # LLM returns incomplete structure → should return empty
        with patch("phase2.tools.pdf_extractor._extract_text", return_value="raw pdf text " * 100):
            with patch("phase2.tools.pdf_extractor._call_llm", return_value={"incomplete": "data"}):
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                    f.write(b"%PDF-1.4 fake")
                    tmp_pdf = Path(f.name)
                try:
                    result = summarize_docs(tmp_pdf)
                    # Either empty (incomplete structure) or valid JSON — never raw dump
                    if result:
                        data = json.loads(result)
                        assert "raw pdf text" not in result
                finally:
                    tmp_pdf.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# security_gate
# ---------------------------------------------------------------------------

class TestSecurityGate:
    def test_clean_patch_passes(self) -> None:
        from phase2.executor.security_gate import scan_patch

        clean = """--- a/requirements.txt
+++ b/requirements.txt
@@ -1 +1,2 @@
 setuptools>=60.0
+requests>=2.28.0
"""
        result = scan_patch(clean, requirements_modified=False)
        assert result.passed is True
        assert result.reason == ""

    def test_empty_patch_passes(self) -> None:
        from phase2.executor.security_gate import scan_patch

        result = scan_patch("")
        assert result.passed is True

    def test_missing_detect_secrets_never_blocks(self) -> None:
        """If detect-secrets is not installed, patch must still pass."""
        from phase2.executor.security_gate import scan_patch

        with patch("subprocess.run", side_effect=FileNotFoundError("detect_secrets not found")):
            result = scan_patch("--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n+x = 1\n")
        assert result.passed is True

    def test_secret_in_patch_rejected(self) -> None:
        """Patch with detected secret must be rejected."""
        from phase2.executor.security_gate import scan_patch

        # Mock detect-secrets returning a secret finding
        secret_output = json.dumps({
            "results": {
                "patch.diff": [{"type": "AWS Access Key", "line_number": 1}]
            }
        })
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = secret_output

        with patch("subprocess.run", return_value=mock_result):
            result = scan_patch("--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n+AWS_KEY = 'FAKE'\n")

        assert result.passed is False
        assert result.reason != ""

    def test_cve_in_requirements_rejected(self, tmp_path: Path) -> None:
        """requirements_modified=True with CVE found must be rejected."""
        from phase2.executor.security_gate import scan_patch

        # Mock detect-secrets passes, then pip-audit finds CVE
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests==2.4.0\n")

        clean_secrets = MagicMock()
        clean_secrets.returncode = 0
        clean_secrets.stdout = json.dumps({"results": {}})

        cve_result = MagicMock()
        cve_result.returncode = 1
        cve_result.stdout = json.dumps({
            "dependencies": [{
                "name": "requests",
                "version": "2.4.0",
                "vulns": [{"id": "CVE-2023-1234", "description": "test"}],
            }]
        })
        cve_result.stderr = ""

        # First subprocess call = detect-secrets, second = pip-audit
        with patch("subprocess.run", side_effect=[clean_secrets, cve_result]):
            with patch("os.getcwd", return_value=str(tmp_path)):
                result = scan_patch("+requests==2.4.0\n", requirements_modified=True)

        assert result.passed is False
        assert "CVE" in result.reason


# ---------------------------------------------------------------------------
# regression D0 (new functions)
# ---------------------------------------------------------------------------

class TestRegressionD0:
    def test_extract_failing_test_found(self) -> None:
        from phase2.executor.regression import extract_failing_test

        lines = [
            "FAILED tests/test_auth.py::test_login - AssertionError: False is not True",
            "1 failed in 0.5s",
        ]
        result = extract_failing_test(lines)
        assert result == "tests/test_auth.py::test_login"

    def test_extract_failing_test_not_found(self) -> None:
        from phase2.executor.regression import extract_failing_test

        lines = ["Error: some other error", "Traceback follows"]
        result = extract_failing_test(lines)
        assert result is None

    def test_verify_pre_patch_returns_true_when_test_fails(self, tmp_path: Path) -> None:
        """verify_pre_patch must return True when test exit code != 0."""
        from phase2.executor.regression import verify_pre_patch

        mock_result = MagicMock()
        mock_result.returncode = 1  # test failed — expected

        with patch("subprocess.run", return_value=mock_result):
            result = verify_pre_patch(tmp_path, "tests/test_foo.py::test_bar")
        assert result is True

    def test_verify_pre_patch_returns_false_when_test_passes(self, tmp_path: Path) -> None:
        """verify_pre_patch must return False (placebo) when test exit code == 0."""
        from phase2.executor.regression import verify_pre_patch

        mock_result = MagicMock()
        mock_result.returncode = 0  # test passes — placebo!

        with patch("subprocess.run", return_value=mock_result):
            result = verify_pre_patch(tmp_path, "tests/test_foo.py::test_bar")
        assert result is False

    def test_shadow_type_check_passes_clean_file(self, tmp_path: Path) -> None:
        from phase2.executor.regression import shadow_type_check

        py_file = tmp_path / "clean.py"
        py_file.write_text("def add(x: int, y: int) -> int:\n    return x + y\n")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            error = shadow_type_check(py_file)
        assert error == ""

    def test_shadow_type_check_catches_violation(self, tmp_path: Path) -> None:
        from phase2.executor.regression import shadow_type_check

        py_file = tmp_path / "bad.py"
        py_file.write_text("def add(x: int, y: int) -> int:\n    return 'wrong type'\n")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "bad.py:2: error: Incompatible return value type"

        with patch("subprocess.run", return_value=mock_result):
            error = shadow_type_check(py_file)
        assert error != ""
        assert "Incompatible" in error

    def test_mypy_missing_skips_gracefully(self, tmp_path: Path) -> None:
        """If mypy is not installed, shadow_type_check must return empty string."""
        from phase2.executor.regression import shadow_type_check

        py_file = tmp_path / "any.py"
        py_file.write_text("x = 1\n")

        with patch("subprocess.run", side_effect=FileNotFoundError("mypy not found")):
            error = shadow_type_check(py_file)
        assert error == ""

    def test_shadow_type_check_skips_non_python(self, tmp_path: Path) -> None:
        """shadow_type_check must return empty string for non-.py files."""
        from phase2.executor.regression import shadow_type_check

        js_file = tmp_path / "app.js"
        js_file.write_text("console.log('hello')\n")
        assert shadow_type_check(js_file) == ""
