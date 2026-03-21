# EnvironmentError Level 2 — Circular import
# Classifier: EnvironmentError | stale_pycache (circular import pattern)
# Fix: break the circular dependency

from module_b import get_b_value


def get_a_value() -> str:
    return "value_a"


def combined() -> str:
    return get_a_value() + get_b_value()
