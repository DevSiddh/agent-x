# Template source: python-telegram-bot + openai | Difficulty: medium | Niche: bots
import json
import os
from config import MAX_HISTORY, MEMORY_PATH

def load_history(user_id: int) -> list[dict]:
    path = MEMORY_PATH.replace("{{USER_ID}}", str(user_id))
    if not os.path.exists(path):
        return []
    with open(path) as f:
        lines = f.readlines()
    return [json.loads(l) for l in lines[-MAX_HISTORY:]]

def save_message(user_id: int, role: str, content: str):
    path = MEMORY_PATH.replace("{{USER_ID}}", str(user_id))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps({"role": role, "content": content}) + "\n")
