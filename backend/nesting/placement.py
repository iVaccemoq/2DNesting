# nesting/placement.py

from dataclasses import dataclass
from typing import List, Tuple, Optional

import random
import copy

random.seed(0)

from geometry.polygon import rotate, translate, normalize, width_height
from geometry.nfp import compute_nfp
from shapely.geometry import Polygon as ShapelyPolygon, Point as ShapelyPoint


Point = Tuple[float, float]
Polygon = List[Point]


_CONCAVE_RATIO = 1.2


def _poly_hash(polygon: Polygon) -> int:

    return hash(tuple(polygon))


@dataclass
class Part:
    id: str
    polygon: Polygon
    area: float


@dataclass
class PlacedPart:
    part_id: str
    polygon: Polygon
    x: float
    y: float
    angle: float
    area: float
    shape: Optional[ShapelyPolygon] = None
    shape_shrunk: Optional[ShapelyPolygon] = None    
    shape_expanded: Optional[ShapelyPolygon] = None  

    def rebuild_shape(self):
        
        pts = [(vx + self.x, vy + self.y) for vx, vy in self.polygon]
        self.shape = ShapelyPolygon(pts)
        self.shape_shrunk = self.shape.buffer(-1e-6)
        self.shape_expanded = self.shape.buffer(1e-6)


def point_in_polygon(point: Point, polygon: Polygon) -> bool:
    x, y = point
    inside = False
    n = len(polygon)

    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]

        if (y1 > y) != (y2 > y):
            xinters = (y - y1) * (x2 - x1) / (y2 - y1 + 1e-12) + x1
            if x < xinters:
                inside = not inside

    return inside

class BottomLeftPlacer:

    def __init__(
        self,
        sheet_width: float,
        sheet_height: float,
        allowed_angles: List[float],
        multi_start: int = 10,
        direction: int = 0,
    ):
        """
        direction:
            1 — горизонтальный раскрой: детали укладываются вдоль ширины листа,
                свободный остаток образуется снизу (полоса по всей ширине).
            0 — вертикальный раскрой: детали укладываются вдоль высоты листа,
                свободный остаток образуется справа (полоса по всей высоте).
        """
        self.sheet_width = sheet_width
        self.sheet_height = sheet_height
        self.allowed_angles = allowed_angles
        self.multi_start = multi_start
        self.direction = direction

        self._nfp_cache = {}


    def _compact(self, placed: PlacedPart, placed_parts: List[PlacedPart]) -> PlacedPart:
        step = 1.0      
        max_iter = 60   

        iter_count = 0
        while iter_count < max_iter:
            moved = False

            if self._can_place(
                placed.polygon,
                placed.x,
                placed.y - step,
                placed_parts,
                placed.part_id,
                placed.angle,
            ):
                placed.y = round(placed.y - step, 4)
                placed.rebuild_shape()
                moved = True

            if self._can_place(
                placed.polygon,
                placed.x - step,
                placed.y,
                placed_parts,
                placed.part_id,
                placed.angle,
            ):
                placed.x = round(placed.x - step, 4)
                placed.rebuild_shape()
                moved = True

            if not moved:
                break

            iter_count += 1

        return placed

    def _current_bounds(self, placed_parts: List[PlacedPart]) -> Tuple[float, float]:
        if not placed_parts:
            return 0.0, 0.0

        max_x = 0.0
        max_y = 0.0

        for p in placed_parts:
            if p.shape is not None:
                _, _, bx, by = p.shape.bounds
            else:
                bx = max(vx + p.x for vx, vy in p.polygon)
                by = max(vy + p.y for vx, vy in p.polygon)
            if bx > max_x:
                max_x = bx
            if by > max_y:
                max_y = by

        return max_x, max_y

    def _contact_score(self, candidate: PlacedPart, placed_parts: List[PlacedPart]) -> float:
        if candidate.shape_expanded is None:
            candidate.rebuild_shape()

        moving_buf = candidate.shape_expanded
        contact = 0.0

        for placed in placed_parts:
            if placed.shape_expanded is None:
                placed.rebuild_shape()
            inter = moving_buf.intersection(placed.shape_expanded)
            contact += inter.length

        return contact

    def _inside_layout(self, x, y, w, h, placed_parts):
        if not placed_parts:
            return False
        max_x, max_y = self._current_bounds(placed_parts)
        return (x + w <= max_x) and (y + h <= max_y)

    def _layout_score(self, placed_parts: List[PlacedPart]) -> float:
        max_x, max_y = self._current_bounds(placed_parts)
        occupied_area = max_x * max_y

        parts_area = sum(p.area for p in placed_parts)
        gap_penalty = occupied_area - parts_area

        if self.direction == 1:
            # Горизонтальный раскрой:
            #   - тянем max_x к ширине листа (штраф за недозаполнение по X)
            #   - минимизируем max_y (свободная полоса — снизу, по всей ширине)
            edge_penalty = abs(self.sheet_width - max_x)
            clean_rect_area = self.sheet_width * max(0.0, self.sheet_height - max_y)
        else:
            # Вертикальный раскрой:
            #   - тянем max_y к высоте листа (штраф за недозаполнение по Y)
            #   - минимизируем max_x (свободная полоса — справа, по всей высоте)
            edge_penalty = abs(self.sheet_height - max_y)
            clean_rect_area = max(0.0, self.sheet_width - max_x) * self.sheet_height

        score = (
            occupied_area
            + 5 * gap_penalty
            - 3 * clean_rect_area
            + 2 * edge_penalty
        )

        return score


    def _get_interior_candidates(
        self,
        placed_parts: List[PlacedPart],
        moving_w: float,
        moving_h: float,
    ) -> List[Tuple[float, float]]:

        candidates = []

        for placed in placed_parts:
            if placed.shape is None:
                placed.rebuild_shape()

            shape = placed.shape
            if not shape.is_valid or shape.area < 1e-6:
                continue

            hull = shape.convex_hull
            if hull.area <= 0:
                continue

            ratio = hull.area / max(shape.area, 1e-9)
            if ratio < _CONCAVE_RATIO:
                continue

            pocket = hull.difference(shape)
            if pocket.is_empty or pocket.area < moving_w * moving_h * 0.25:
                continue

            minx, miny, maxx, maxy = pocket.bounds
            step = max(moving_w * 0.5, moving_h * 0.5, 1.0)

            x = minx
            while x <= maxx:
                y = miny
                while y <= maxy:
                    if pocket.contains(ShapelyPoint(x, y)):
                        candidates.append((x - moving_w / 2, y - moving_h / 2))
                        candidates.append((x, y))
                    y += step
                x += step

        return candidates

    def place(self, parts: List[Part]) -> List[PlacedPart]:
        best_layout = None
        best_score = float("inf")

        for attempt in range(self.multi_start):

            if attempt == 0:
                ordered = sorted(parts, key=lambda p: p.area, reverse=True)
            elif attempt == 1:
                ordered = sorted(parts, key=lambda p: p.area)
            else:
                ordered = parts[:]
                random.shuffle(ordered)

            placed_parts = []

            for part in ordered:
                placed = self._place_single_part(part, placed_parts)
                if not placed:
                    break
                placed_parts.append(placed)

            if len(placed_parts) != len(parts):
                continue

            score = self._layout_score(placed_parts)

            if score < best_score:
                best_score = score

                best_layout = [
                    PlacedPart(p.part_id, p.polygon, p.x, p.y, p.angle, p.area)
                    for p in placed_parts
                ]
                for p in best_layout:
                    p.rebuild_shape()

        if best_layout is None:
            raise RuntimeError("Failed to place parts")

        return best_layout

    def _local_improvement(self, layout: List[PlacedPart]) -> List[PlacedPart]:
        best_layout = layout
        best_score = self._layout_score(layout)
        improved = True
        while improved:
            improved = False
            for i in range(len(best_layout)):
                part_to_move = best_layout[i]
                remaining = best_layout[:i] + best_layout[i + 1:]
                part = Part(
                    id=part_to_move.part_id,
                    polygon=part_to_move.polygon,
                    area=part_to_move.area,
                )
                new_position = self._place_single_part(part, remaining)

                if not new_position:
                    continue
                new_layout = remaining + [new_position]
                new_score = self._layout_score(new_layout)
                if new_score < best_score:
                    best_layout = new_layout
                    best_score = new_score
                    improved = True
                    break

        return best_layout

    def _multi_relocation(self, layout: List[PlacedPart], iterations: int = 20) -> List[PlacedPart]:
        best_layout = layout
        best_score = self._layout_score(layout)
        for _ in range(iterations):
            if len(best_layout) < 3:
                break
            k = random.choice([2, 3])
            indices = random.sample(range(len(best_layout)), k)
            removed = [best_layout[i] for i in indices]
            remaining = [p for i, p in enumerate(best_layout) if i not in indices]

            random.shuffle(removed)
            new_layout = remaining.copy()
            success = True
            for part_to_insert in removed:
                part = Part(
                    id=part_to_insert.part_id,
                    polygon=part_to_insert.polygon,
                    area=part_to_insert.area,
                )
                new_position = self._place_single_part(part, new_layout)
                if not new_position:
                    success = False
                    break
                new_layout.append(new_position)
            if not success:
                continue
            new_score = self._layout_score(new_layout)
            if new_score < best_score:
                best_layout = new_layout
                best_score = new_score
        return best_layout

    def _place_single_part(
        self,
        part: Part,
        placed_parts: List[PlacedPart],
    ) -> Optional[PlacedPart]:

        best_candidate = None
        best_score = float("inf")

        for angle in self.allowed_angles:

            rotated = rotate(part.polygon, angle)
            rotated = normalize(rotated)
            w, h = width_height(rotated)

            if w > self.sheet_width or h > self.sheet_height:
                continue

            if not placed_parts:
                temp_layout = [
                    PlacedPart(part.id, rotated, 0.0, 0.0, angle, part.area)
                ]
                score = self._layout_score(temp_layout)

                if score < best_score:
                    best_score = score
                    best_candidate = temp_layout[0]

                continue

            candidates: set = set()
            candidates.add((0.0, 0.0))

            for placed in placed_parts:

                cache_key = (_poly_hash(placed.polygon), _poly_hash(rotated), placed.angle, angle)

                if cache_key in self._nfp_cache:
                    nfp = self._nfp_cache[cache_key]
                else:
                    nfp = compute_nfp(placed.polygon, rotated)
                    self._nfp_cache[cache_key] = nfp

                nfp_global = translate(nfp, placed.x, placed.y)

                for x, y in nfp_global:
                    candidates.add((x, y))

            for placed in placed_parts:
                for vx, vy in placed.polygon:
                    candidates.add((vx + placed.x, vy + placed.y))


            max_x, max_y = self._current_bounds(placed_parts)

            candidates.add((max_x, 0))
            candidates.add((0, max_y))
            candidates.add((max_x, max_y))
            candidates.add((max_x / 2, max_y / 2))

            for c in self._get_interior_candidates(placed_parts, w, h):
                candidates.add(c)

            ordered_candidates = sorted(candidates, key=lambda p: (p[1], p[0]))

            for x, y in ordered_candidates:

                if not self._can_place(rotated, x, y, placed_parts, part.id, angle):
                    continue

                candidate = PlacedPart(part.id, rotated, x, y, angle, part.area)
                candidate.rebuild_shape()

                candidate = self._compact(candidate, placed_parts)

                if not self._can_place(candidate.polygon, candidate.x, candidate.y, placed_parts, part.id, angle):
                    continue

                temp_layout = placed_parts + [candidate]
                score = self._layout_score(temp_layout)
                contact = self._contact_score(candidate, placed_parts)
                combined = score - contact * 500

                if combined < best_score:
                    best_score = combined
                    best_candidate = candidate

        return best_candidate

    def _can_place(
        self,
        polygon: Polygon,
        x: float,
        y: float,
        placed_parts: List[PlacedPart],
        part_id: str,
        angle: float,
    ) -> bool:


        min_x = x + min(vx for vx, vy in polygon)
        min_y = y + min(vy for vx, vy in polygon)
        max_x = x + max(vx for vx, vy in polygon)
        max_y = y + max(vy for vx, vy in polygon)

        if min_x < 0 or min_y < 0:
            return False

        if max_x > self.sheet_width or max_y > self.sheet_height:
            return False

        if not placed_parts:
            return True

        moving_shrink = ShapelyPolygon([(vx + x, vy + y) for vx, vy in polygon]).buffer(-1e-6)

        for placed in placed_parts:

            if placed.shape_shrunk is None:
                placed.rebuild_shape()

            if moving_shrink.intersects(placed.shape_shrunk):
                return False

        return True
