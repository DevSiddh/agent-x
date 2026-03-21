# Circular import — module_b imports module_a which imports module_b
from module_a import get_a_value


def get_b_value() -> str:
    return get_a_value() + "_b"
