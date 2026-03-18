from pydantic import BaseModel
from typing import List


class NestRequest(BaseModel):
    sheet_width: float
    sheet_height: float
    allowed_angles: List[float] = [0, 90]


class PlacedPartResponse(BaseModel):
    id: str
    x: float
    y: float
    angle: float
    polygon: List[List[float]]


class NestResponse(BaseModel):
    parts: List[PlacedPartResponse]