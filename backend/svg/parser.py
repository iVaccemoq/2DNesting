# svg/parser.py

from dataclasses import dataclass
from typing import List, Tuple
import numpy as np
import xml.etree.ElementTree as ET
import math


from shapely.geometry import Polygon as ShapelyPolygon
from svgpathtools import parse_path, Line, CubicBezier, QuadraticBezier, Arc
from geometry.polygon import width_height

Point = Tuple[float, float]

@dataclass
class Part:
    id: str
    polygon: List[Point]
    holes: List[List[Point]]
    area: float


# =========================
# SIMPLIFY
# =========================

def simplify_polygon(points: List[Point], tolerance: float = 0.5) -> List[Point]:
    """
    Reduce number of vertices but keep polygon shape.
    """

    try:
        poly = ShapelyPolygon(points)

        if not poly.is_valid:
            return points

        simplified = poly.simplify(tolerance, preserve_topology=True)

        coords = list(simplified.exterior.coords)

        # shapely дублирует первую точку в конце
        if coords[0] == coords[-1]:
            coords.pop()

        return coords

    except:
        return points


# =========================
# PUBLIC API
# =========================

def parse_svg(file_path: str, tolerance: int = 40) -> List[Part]:

    tree = ET.parse(file_path)
    root = tree.getroot()

    polygons: List[List[Point]] = []

    # ---------- viewBox ----------
    scale_x = 1.0
    scale_y = 1.0

    viewbox = root.attrib.get("viewBox")

    if viewbox:
        vb = [float(v) for v in viewbox.split()]
        _, _, vw, vh = vb

        width = float(root.attrib.get("width", vw))
        height = float(root.attrib.get("height", vh))

        scale_x = width / vw
        scale_y = height / vh

    # ---------- parse elements ----------

    for elem in root.iter():

        tag = elem.tag.split("}")[-1]
        polygon = None

        if tag == "path":
            d = elem.attrib.get("d")
            if d:
                polygon = path_to_polygon(d, tolerance)

        elif tag == "rect":
            polygon = rect_to_polygon(elem)

        elif tag == "circle":
            polygon = circle_to_polygon(elem)

        elif tag == "ellipse":
            polygon = ellipse_to_polygon(elem)

        elif tag == "polygon":
            polygon = polygon_to_points(elem)

        elif tag == "polyline":
            polygon = polygon_to_points(elem)

        if polygon and len(polygon) >= 3:

            # viewBox scaling
            polygon = [(x * scale_x, y * scale_y) for x, y in polygon]

            polygon = normalize_polygon(polygon)

            # transform
            transform = elem.attrib.get("transform")

            if transform:
                tx, ty, scale, rot = parse_transform(transform)
                polygon = apply_transform(polygon, tx, ty, scale, rot)

            polygons.append(polygon)

    # ---------- convert to parts ----------

    parts: List[Part] = []

    for idx, polygon in enumerate(polygons):


        w, h = width_height(polygon)
        area = polygon_area(polygon)

        parts.append(
            Part(
                id=f"part_{idx}",
                polygon=polygon,
                holes=[],
                area=area
            )
        )

    return parts


# =========================
# PATH
# =========================

def path_to_polygon(d: str, tolerance: int) -> List[Point]:

    path = parse_path(d)

    polygon: List[Point] = []

    for segment in path:

        points = segment_to_points(segment, tolerance)

        if polygon:
            points = points[1:]

        polygon.extend(points)

    if len(polygon) > 2 and polygon[0] == polygon[-1]:
        polygon.pop()

    return polygon


def segment_to_points(segment, tolerance: int) -> List[Point]:

    if isinstance(segment, Line):
        return [
            (segment.start.real, segment.start.imag),
            (segment.end.real, segment.end.imag),
        ]

    if isinstance(segment, (CubicBezier, QuadraticBezier, Arc)):
        return bezier_to_poly(segment, tolerance)

    return []


def bezier_to_poly(segment, tolerance: int) -> List[Point]:

    ts = np.linspace(0, 1, tolerance)

    return [
        (segment.point(t).real, segment.point(t).imag)
        for t in ts
    ]


# =========================
# BASIC SHAPES
# =========================

def rect_to_polygon(elem):

    x = float(elem.attrib.get("x", 0))
    y = float(elem.attrib.get("y", 0))
    w = float(elem.attrib.get("width", 0))
    h = float(elem.attrib.get("height", 0))

    return [
        (x, y),
        (x + w, y),
        (x + w, y + h),
        (x, y + h)
    ]


def circle_to_polygon(elem, segments=90):

    cx = float(elem.attrib.get("cx", 0))
    cy = float(elem.attrib.get("cy", 0))
    r = float(elem.attrib.get("r", 0))

    return [
        (
            cx + r * np.cos(2 * np.pi * i / segments),
            cy + r * np.sin(2 * np.pi * i / segments),
        )
        for i in range(segments)
    ]


def ellipse_to_polygon(elem, segments=90):

    cx = float(elem.attrib.get("cx", 0))
    cy = float(elem.attrib.get("cy", 0))
    rx = float(elem.attrib.get("rx", 0))
    ry = float(elem.attrib.get("ry", 0))

    return [
        (
            cx + rx * np.cos(2 * np.pi * i / segments),
            cy + ry * np.sin(2 * np.pi * i / segments),
        )
        for i in range(segments)
    ]


def polygon_to_points(elem):

    points = elem.attrib.get("points", "")
    pts: List[Point] = []

    for p in points.split():
        x, y = p.split(",")
        pts.append((float(x), float(y)))

    return pts


# =========================
# TRANSFORM
# =========================

def parse_transform(transform: str):

    tx = 0
    ty = 0
    scale = 1
    rot = 0

    if "translate" in transform:
        vals = transform.split("translate(")[1].split(")")[0]
        nums = [float(v) for v in vals.replace(",", " ").split()]
        tx = nums[0]
        if len(nums) > 1:
            ty = nums[1]

    if "scale" in transform:
        vals = transform.split("scale(")[1].split(")")[0]
        scale = float(vals)

    if "rotate" in transform:
        vals = transform.split("rotate(")[1].split(")")[0]
        rot = float(vals)

    return tx, ty, scale, rot


def apply_transform(points, tx, ty, scale, rot):

    rad = math.radians(rot)

    cos_a = math.cos(rad)
    sin_a = math.sin(rad)

    result = []

    for x, y in points:

        x *= scale
        y *= scale

        xr = x * cos_a - y * sin_a
        yr = x * sin_a + y * cos_a

        result.append((xr + tx, yr + ty))

    return result


# =========================
# GEOMETRY
# =========================

def normalize_polygon(points: List[Point]) -> List[Point]:

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    min_x = min(xs)
    min_y = min(ys)

    return [(x - min_x, y - min_y) for x, y in points]


def polygon_area(points: List[Point]) -> float:

    area = 0
    n = len(points)

    for i in range(n):

        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]

        area += x1 * y2 - x2 * y1

    return abs(area) / 2