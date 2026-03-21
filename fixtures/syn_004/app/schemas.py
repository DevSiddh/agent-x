from pydantic import BaseModel, ConfigDict
from typing import Optional


class User(BaseModel):
    id: int
    name: str


class Item(BaseModel):
    model_id: str
