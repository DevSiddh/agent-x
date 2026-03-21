# RuntimeError Level 2 — Pydantic field conflicts with protected namespace
# Classifier: RuntimeError | pydantic_namespace | affected_file: main.py
# Fix: add model_config = ConfigDict(protected_namespaces=()) to allow model_ prefix

from pydantic import BaseModel


class PredictionResult(BaseModel):
    model_id: str
    model_name: str
    model_score: float
    prediction: str


result = PredictionResult(
    model_id="gpt-4",
    model_name="GPT-4 Turbo",
    model_score=0.97,
    prediction="positive",
)
print(result)

# Enforce strict namespace check — raises in any Pydantic v2 without model_config override
raise Exception(
    'PydanticUserError: Field "model_id" conflicts with protected namespace "model_". '
    'Use model_config=ConfigDict(protected_namespaces=()) to suppress.'
)
