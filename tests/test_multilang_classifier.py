"""
tests/test_multilang_classifier.py
Tests for multi-language classifier patterns (C3b).
Covers JS/PHP/Java/SQL error classification + Python regression.
"""

from phase2.classifier.regex_pass import classify, classify_with_fallback, ClassifierResult


# ---------------------------------------------------------------------------
# JS / Node.js patterns
# ---------------------------------------------------------------------------

def test_js_cannot_find_module_classified_as_dependency_error() -> None:
    """Cannot find module → DependencyError."""
    lines = ["Error: Cannot find module 'express'", "    at Function.Module._resolveFilename"]
    result = classify(lines, repo="owner/repo")
    assert result.category == "DependencyError"
    assert result.confidence >= 0.85
    assert result.ecosystem == "Node"


def test_js_reference_error_classified_as_runtime_error() -> None:
    """ReferenceError: x is not defined → RuntimeError."""
    lines = ["ReferenceError: myVar is not defined", "    at Object.<anonymous> (app.js:5:1)"]
    result = classify(lines, repo="owner/repo")
    assert result.category == "RuntimeError"
    assert result.confidence >= 0.85


def test_js_type_not_a_function_classified_as_runtime_error() -> None:
    """TypeError: foo is not a function → RuntimeError."""
    lines = ["TypeError: foo is not a function", "    at Object.<anonymous> (index.js:10:3)"]
    result = classify(lines, repo="owner/repo")
    assert result.category == "RuntimeError"
    assert result.confidence >= 0.85


def test_js_syntax_error_classified_as_syntax_error() -> None:
    """SyntaxError: Unexpected token → SyntaxError."""
    lines = ["SyntaxError: Unexpected token '}'", "    at wrapSafe (internal/modules/cjs/loader.js)"]
    result = classify(lines, repo="owner/repo")
    assert result.category == "SyntaxError"
    assert result.confidence >= 0.85


def test_js_econnrefused_classified_as_environment_error() -> None:
    """ECONNREFUSED → EnvironmentError."""
    lines = ["Error: connect ECONNREFUSED 127.0.0.1:5432"]
    result = classify(lines, repo="owner/repo")
    assert result.category == "EnvironmentError"
    assert result.confidence >= 0.85


# ---------------------------------------------------------------------------
# PHP patterns
# ---------------------------------------------------------------------------

def test_php_class_not_found_classified_as_dependency_error() -> None:
    """Fatal error: Class X not found → DependencyError."""
    lines = ["Fatal error: Class 'App\\Http\\Controllers\\AuthController' not found in /var/www/index.php on line 15"]
    result = classify(lines, repo="owner/repo")
    assert result.category == "DependencyError"
    assert result.confidence >= 0.85


def test_php_parse_error_classified_as_syntax_error() -> None:
    """Parse error: syntax error → SyntaxError."""
    lines = ["Parse error: syntax error, unexpected '}' in /var/www/app.php on line 42"]
    result = classify(lines, repo="owner/repo")
    assert result.category == "SyntaxError"
    assert result.confidence >= 0.85


def test_php_wrong_param_classified_as_runtime_error() -> None:
    """Warning: X expects parameter → RuntimeError."""
    lines = ["Warning: array_push() expects parameter 1 to be array, null given in app.php on line 7"]
    result = classify(lines, repo="owner/repo")
    assert result.category == "RuntimeError"
    assert result.confidence >= 0.70


# ---------------------------------------------------------------------------
# Java patterns
# ---------------------------------------------------------------------------

def test_java_class_not_found_classified_as_dependency_error() -> None:
    """ClassNotFoundException → DependencyError."""
    lines = ["java.lang.ClassNotFoundException: com.example.MissingClass", "    at java.net.URLClassLoader.findClass(URLClassLoader.java:382)"]
    result = classify(lines, repo="owner/repo")
    assert result.category == "DependencyError"
    assert result.confidence >= 0.85


def test_java_null_pointer_classified_as_runtime_error() -> None:
    """NullPointerException → RuntimeError."""
    lines = ["java.lang.NullPointerException", "    at com.example.App.main(App.java:15)"]
    result = classify(lines, repo="owner/repo")
    assert result.category == "RuntimeError"
    assert result.confidence >= 0.85


def test_java_stack_trace_file_extracted() -> None:
    """Java stack trace → affected_file extracted from (File.java:N) format."""
    lines = [
        "java.lang.NullPointerException",
        "    at com.example.App.processData(DataProcessor.java:42)",
    ]
    result = classify(lines, repo="owner/repo")
    assert result.category == "RuntimeError"
    assert "DataProcessor.java" in result.affected_file


# ---------------------------------------------------------------------------
# SQL patterns
# ---------------------------------------------------------------------------

def test_sql_table_missing_classified_as_config_error() -> None:
    """Table X doesn't exist → ConfigError."""
    lines = ["ERROR 1146 (42S02): Table 'mydb.users' doesn't exist"]
    result = classify(lines, repo="owner/repo")
    assert result.category == "ConfigError"
    assert result.confidence >= 0.85


def test_sql_column_not_found_classified_as_config_error() -> None:
    """Column X not found → ConfigError."""
    lines = ["ERROR 1054 (42S22): Unknown column 'email_address' in 'field list'"]
    result = classify(lines, repo="owner/repo")
    assert result.category == "ConfigError"
    assert result.confidence >= 0.85


def test_sql_access_denied_classified_as_environment_error() -> None:
    """Access denied for user → EnvironmentError."""
    lines = ["ERROR 1045 (28000): Access denied for user 'app'@'localhost' (using password: YES)"]
    result = classify(lines, repo="owner/repo")
    assert result.category == "EnvironmentError"
    assert result.confidence >= 0.85


# ---------------------------------------------------------------------------
# Python regression — existing patterns must still work
# ---------------------------------------------------------------------------

def test_python_module_not_found_still_works() -> None:
    """Python DependencyError regression — must not be broken by new patterns."""
    lines = ["ModuleNotFoundError: No module named 'setuptools'"]
    result = classify(lines, repo="owner/repo")
    assert result.category == "DependencyError"
    assert result.confidence >= 0.85
    assert result.ecosystem == "Python"


def test_python_runtime_error_still_works() -> None:
    """Python RuntimeError regression."""
    lines = [
        'File "app/schemas.py", line 12, in SomeModel',
        "PydanticUserError: Field 'model_id' conflicts with protected namespace",
    ]
    result = classify(lines, repo="owner/repo")
    assert result.category == "RuntimeError"
    assert result.ecosystem == "Python"


# ---------------------------------------------------------------------------
# Ecosystem field
# ---------------------------------------------------------------------------

def test_ecosystem_defaults_to_python_when_unknown_extension() -> None:
    """Unknown file extension defaults to Python ecosystem."""
    lines = ["ModuleNotFoundError: No module named 'foo'"]
    result = classify(lines, repo="owner/repo")
    assert result.ecosystem == "Python"


def test_ecosystem_node_for_js_affected_file() -> None:
    """Node ecosystem returned when affected_file is a .js path."""
    lines = ["Error: Cannot find module 'express'", "    at Object.<anonymous> (/app/server.js:1:1)"]
    result = classify(lines, repo="owner/repo")
    assert result.ecosystem == "Node"
