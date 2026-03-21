# RuntimeError Level 3 — TypeError in nested function calls
# Classifier: RuntimeError | type_error | affected_file: main.py
# Fix: add None guard in parse_age() or default in create_user() (3-4 lines)

def parse_age(value: str) -> int:
    return int(value)  # TypeError if value is None


def create_user(name: str, age_str: str) -> dict:
    return {"name": name, "age": parse_age(age_str)}


def process_users(data: list[dict]) -> list[dict]:
    return [create_user(d["name"], d.get("age")) for d in data]  # age may be None


if __name__ == "__main__":
    users = [
        {"name": "Alice", "age": "25"},
        {"name": "Bob", "age": "30"},
        {"name": "Charlie"},            # missing age → None → TypeError
    ]
    result = process_users(users)
    print(result)
