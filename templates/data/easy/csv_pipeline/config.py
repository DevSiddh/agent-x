# Template source: pandas-pattern | Difficulty: easy | Niche: data
INPUT_PATH = "{{INPUT_CSV_PATH}}"
OUTPUT_PATH = "{{OUTPUT_CSV_PATH}}"
TRANSFORMS = ["{{TRANSFORM_1}}", "{{TRANSFORM_2}}"]  # e.g. drop_nulls, normalize_dates
SCHEMA = {
    "{{COLUMN_1}}": "{{TYPE_1}}",  # e.g. "age": "int"
    "{{COLUMN_2}}": "{{TYPE_2}}",
}
