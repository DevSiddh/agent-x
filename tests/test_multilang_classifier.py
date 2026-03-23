"""
tests/test_multilang_classifier.py — Step C3b
Tests for JS/Node, PHP, Java, SQL classifier patterns.
Also verifies Python patterns still work (regression).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase2.classifier.regex_pass import classify


# ---------------------------------------------------------------------------
# JS / Node patterns
# ---------------------------------------------------------------------------

class TestJSClassifier:

    def test_cannot_find_module_is_dependency_error(self) -> None:
        lines = ["Error: Cannot find module 'express'", "    at Function.Module._resolveFilename"]
        r = classify(lines, repo="test/repo")
        assert r.category == "DependencyError"
        assert r.confidence >= 0.80

    def test_reference_error_is_runtime_error(self) -> None:
        lines = ["ReferenceError: myVar is not defined", "    at Object.<anonymous> (app.js:10:5)"]
        r = classify(lines, repo="test/repo")
        assert r.category == "RuntimeError"
        assert r.confidence >= 0.80

    def test_syntax_error_unexpected_token(self) -> None:
        lines = ["SyntaxError: Unexpected token '}'", "    at wrapSafe (internal/modules/cjs/loader.js:915:16)"]
        r = classify(lines, repo="test/repo")
        assert r.category == "SyntaxError"
        assert r.confidence >= 0.85

    def test_type_error_not_a_function(self) -> None:
        lines = ["TypeError: myFunc is not a function", "    at Object.<anonymous> (index.js:5:1)"]
        r = classify(lines, repo="test/repo")
        assert r.category == "RuntimeError"
        assert r.confidence >= 0.80

    def test_econnrefused_is_environment_error(self) -> None:
        lines = ["Error: connect ECONNREFUSED 127.0.0.1:5432", "    at TCPConnectWrap.afterConnect"]
        r = classify(lines, repo="test/repo")
        assert r.category == "EnvironmentError"
        assert r.confidence >= 0.80


# ---------------------------------------------------------------------------
# PHP patterns
# ---------------------------------------------------------------------------

class TestPHPClassifier:

    def test_fatal_class_not_found_is_dependency_error(self) -> None:
        lines = ["PHP Fatal error: Class 'Monolog\\Logger' not found in /app/src/App.php on line 12"]
        r = classify(lines, repo="test/repo")
        assert r.category == "DependencyError"
        assert r.confidence >= 0.80

    def test_parse_error_is_syntax_error(self) -> None:
        lines = ["PHP Parse error: syntax error, unexpected '}' in /app/src/Controller.php on line 45"]
        r = classify(lines, repo="test/repo")
        assert r.category == "SyntaxError"
        assert r.confidence >= 0.85

    def test_warning_wrong_param_is_runtime_error(self) -> None:
        lines = ["PHP Warning:  strpos() expects parameter 1 to be string, array given in app.php on line 7"]
        r = classify(lines, repo="test/repo")
        assert r.category == "RuntimeError"
        assert r.confidence >= 0.70


# ---------------------------------------------------------------------------
# Java patterns
# ---------------------------------------------------------------------------

class TestJavaClassifier:

    def test_class_not_found_exception_is_dependency_error(self) -> None:
        lines = [
            "Exception in thread \"main\" java.lang.ClassNotFoundException: com.example.Driver",
            "    at java.net.URLClassLoader.findClass(URLClassLoader.java:382)",
        ]
        r = classify(lines, repo="test/repo")
        assert r.category == "DependencyError"
        assert r.confidence >= 0.80

    def test_null_pointer_exception_is_runtime_error(self) -> None:
        lines = [
            "Exception in thread \"main\" java.lang.NullPointerException",
            "    at com.example.Main.run(Main.java:42)",
        ]
        r = classify(lines, repo="test/repo")
        assert r.category == "RuntimeError"
        assert r.confidence >= 0.80

    def test_runtime_error_confidence_above_threshold(self) -> None:
        lines = ["java.lang.NullPointerException: Cannot invoke method size() on null object"]
        r = classify(lines, repo="test/repo")
        assert r.confidence >= 0.80


# ---------------------------------------------------------------------------
# SQL patterns
# ---------------------------------------------------------------------------

class TestSQLClassifier:

    def test_table_not_exist_is_config_error(self) -> None:
        lines = ["ERROR 1146 (42S02): Table 'mydb.users' doesn't exist"]
        r = classify(lines, repo="test/repo")
        assert r.category == "ConfigError"
        assert r.confidence >= 0.80

    def test_column_not_found_is_config_error(self) -> None:
        lines = ["ERROR 1054 (42S22): Unknown column 'email' not found in 'field list'"]
        r = classify(lines, repo="test/repo")
        assert r.category == "ConfigError"
        assert r.confidence >= 0.80

    def test_access_denied_is_environment_error(self) -> None:
        lines = ["ERROR 1045 (28000): Access denied for user 'root'@'localhost'"]
        r = classify(lines, repo="test/repo")
        assert r.category == "EnvironmentError"
        assert r.confidence >= 0.80


# ---------------------------------------------------------------------------
# Python regression — existing patterns must still work
# ---------------------------------------------------------------------------

class TestPythonRegression:

    def test_module_not_found_still_classified(self) -> None:
        lines = ["ModuleNotFoundError: No module named 'setuptools'"]
        r = classify(lines, repo="test/repo")
        assert r.category == "DependencyError"
        assert r.confidence >= 0.85

    def test_no_such_table_still_classified(self) -> None:
        lines = ["sqlalchemy.exc.OperationalError: no such table: users"]
        r = classify(lines, repo="test/repo")
        assert r.category == "ConfigError"

    def test_assertion_error_still_classified(self) -> None:
        lines = ["AssertionError: expected 200 got 500"]
        r = classify(lines, repo="test/repo")
        assert r.category == "RuntimeError"
        assert r.confidence >= 0.85
