# geometry/nfp.py
from typing import List, Tuple
import pyclipper

Point = Tuple[float, float]
Polygon = List[Point]

SCALE = 100000  # тот же масштаб, что и в offset


def _scale_up(polygon: Polygon) -> List[Tuple[int, int]]:
    return [(int(x * SCALE), int(y * SCALE)) for x, y in polygon]


def _scale_down(polygon: List[Tuple[int, int]]) -> Polygon:
    return [(x / SCALE, y / SCALE) for x, y in polygon]


def reflect_polygon(polygon: Polygon) -> Polygon:
    """
    Reflect polygon around origin (x, y) -> (-x, -y)
    """
    return [(-x, -y) for x, y in polygon]


def compute_nfp(static_poly: Polygon, moving_poly: Polygon) -> Polygon:

    # 1. отражаем движущуюся деталь
    reflected = reflect_polygon(moving_poly)

    # 2. масштабируем
    subj = _scale_up(static_poly)
    clip = _scale_up(reflected)

    # 3. Minkowski sum
    solutions = pyclipper.MinkowskiSum(subj, clip, True)

    if not solutions:
        raise ValueError("Failed to compute NFP")

    # 4. объединяем все части
    pc = pyclipper.Pyclipper()
    pc.AddPaths(solutions, pyclipper.PT_SUBJECT, True)

    union = pc.Execute(
        pyclipper.CT_UNION,
        pyclipper.PFT_NONZERO,
        pyclipper.PFT_NONZERO
    )

    if not union:
        raise ValueError("Failed to union NFP")

    # 5. берём внешний контур
    largest = max(union, key=lambda p: abs(pyclipper.Area(p)))

    return _scale_down(largest)
