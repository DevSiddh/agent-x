# DependencyError Level 1 — Simple missing import
# Classifier: DependencyError | ModuleNotFoundError | affected_file: main.py
# Fix: add pandas to requirements.txt (1 line)

import pandas

data = pandas.DataFrame({"value": [1, 2, 3]})
print(data)
