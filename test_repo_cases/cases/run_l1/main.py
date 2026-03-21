# RuntimeError Level 1 — AssertionError on invalid input
# Classifier: RuntimeError | assertion_error | affected_file: main.py
# Fix: add input validation before assert (2-3 lines)

def calculate_discount(price: float, discount_pct: float) -> float:
    assert 0 <= discount_pct <= 100, f"discount {discount_pct} must be between 0 and 100"
    return price * (1 - discount_pct / 100)

if __name__ == "__main__":
    print(calculate_discount(100.0, 150.0))  # invalid — 150% discount
