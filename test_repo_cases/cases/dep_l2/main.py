# DependencyError Level 2 — Import inside function, two missing packages
# Classifier: DependencyError | ModuleNotFoundError | affected_file: main.py
# Fix: add numpy and scipy to requirements.txt (2 lines)

def analyse(values: list) -> float:
    import numpy as np
    from scipy import stats
    arr = np.array(values)
    return float(stats.mean(arr))

if __name__ == "__main__":
    print(analyse([10, 20, 30, 40]))
