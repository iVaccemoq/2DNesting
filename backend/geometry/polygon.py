# geometry/polygon.py
from typing import List, Tuple
import math

Point = Tuple[float, float]
Polygon = List[Point]


# -------------------------
# Basic transforms
# -------------------------

def translate(polygon: Polygon, dx: float, dy: float) -> Polygon:
    """
    Move polygon by (dx, dy).
    """
    return [(x + dx, y + dy) for x, y in polygon]


def rotate(polygon: Polygon, angle_deg: float, origin: Point = (0.0, 0.0)) -> Polygon:
    """
    Rotate polygon around origin by angle in degrees.
    """
    angle_rad = math.radians(angle_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    ox, oy = origin
    rotated: Polygon = []

    for x, y in polygon:
        tx = x - ox
        ty = y - oy

        rx = tx * cos_a - ty * sin_a
        ry = tx * sin_a + ty * cos_a

        rotated.append((rx + ox, ry + oy))

    return rotated


# -------------------------
# Bounding box
# -------------------------

def bounding_box(polygon: Polygon) -> Tuple[float, float, float, float]:
    """
    Returns (min_x, min_y, max_x, max_y)
    """
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]

    return min(xs), min(ys), max(xs), max(ys)


def width_height(polygon: Polygon) -> Tuple[float, float]:
    """
    Returns width and height of polygon bounding box.
    """
    min_x, min_y, max_x, max_y = bounding_box(polygon)
    return max_x - min_x, max_y - min_y


# -------------------------
# Utility
# -------------------------

def normalize(polygon: Polygon) -> Polygon:
    """
    Move polygon so that its bounding box starts at (0, 0).
    """
    min_x, min_y, _, _ = bounding_box(polygon)
    return translate(polygon, -min_x, -min_y)