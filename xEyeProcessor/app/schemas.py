from pydantic import BaseModel, Field
from typing import List, Literal

class Box(BaseModel):
    # Normalizado [0..1] para menos payload
    x1: float; y1: float; x2: float; y2: float
    cls: int
    conf: float

class InferResponse(BaseModel):
    model: str
    img_w: int
    img_h: int
    time_ms: float
    boxes: List[Box] = Field(default_factory=list)
    names: dict[int, str]

class HealthResponse(BaseModel):
    status: Literal["ok"]
