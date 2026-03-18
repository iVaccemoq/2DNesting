# geometry/offset.py
from typing import List, Tuple
import pyclipper

Point = Tuple[float, float]
Polygon = List[Point]

# pyclipper работает с int → масштабируем
SCALE = 1000


def _scale_up(polygon: Polygon) -> List[Tuple[int, int]]:
    return [(int(x * SCALE), int(y * SCALE)) for x, y in polygon]


def _scale_down(polygon: List[Tuple[int, int]]) -> Polygon:
    return [(x / SCALE, y / SCALE) for x, y in polygon]


def offset_polygon(polygon: Polygon, distance: float) -> Polygon:
    """
    Offset polygon outward by distance.
    Positive distance → expand
    Negative distance → shrink
    """
    pc = pyclipper.PyclipperOffset()
    pc.AddPath(_scale_up(polygon), pyclipper.JT_MITER, pyclipper.ET_CLOSEDPOLYGON)

    result = pc.Execute(distance * SCALE)

    if not result:
        raise ValueError("Offset resulted in empty polygon")

    # берём самый большой контур (на случай сложных фигур)
    largest = max(result, key=lambda p: abs(pyclipper.Area(p)))

    return _scale_down(largest)

