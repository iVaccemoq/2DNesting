# nesting/placement.py

from dataclasses import dataclass
from typing import List, Tuple, Optional

import random
import copy

random.seed(0)

from geometry.polygon import rotate, translate, normalize, width_height
from geometry.nfp import compute_nfp
from shapely.geometry import Polygon as ShapelyPolygon


Point = Tuple[float, float]
Polygon = List[Point]


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


# =========================
# Geometry helper
# =========================

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


# =========================
# Main class
# =========================

class BottomLeftPlacer:

    def __init__(
        self,
        sheet_width: float,
        sheet_height: float,
        allowed_angles: List[float],
        multi_start: int = 10,
    ):
        self.sheet_width = sheet_width
        self.sheet_height = sheet_height
        self.allowed_angles = allowed_angles
        self.multi_start = multi_start

        self._nfp_cache = {}

    # =========================
    # Layout utilities
    # =========================
    
    def _compact(self, placed: PlacedPart, placed_parts):

        step = 0.5
        max_iter = 120
        iter_count = 0

        while iter_count < max_iter:

            moved = False

            # push down
            if self._can_place(
                placed.polygon,
                placed.x,
                placed.y - step,
                placed_parts,
                placed.part_id,
                placed.angle
            ):
                placed.y -= step
                placed.y = round(placed.y, 4)

                placed.shape = ShapelyPolygon(
                    [(vx + placed.x, vy + placed.y) for vx, vy in placed.polygon]
                )
                
                moved = True

            # push left
            if self._can_place(
                placed.polygon,
                placed.x - step,
                placed.y,
                placed_parts,
                placed.part_id,
                placed.angle
            ):
                placed.y -= step
                placed.y = round(placed.y, 4)

                placed.shape = ShapelyPolygon(
                    [(vx + placed.x, vy + placed.y) for vx, vy in placed.polygon]
                )

                moved = True

            if not moved:
                break

            iter_count += 1

        return placed
    def _current_bounds(self, placed_parts: List[PlacedPart]):
        if not placed_parts:
            return 0.0, 0.0

        max_x = 0.0
        max_y = 0.0

        for p in placed_parts:
            for vx, vy in p.polygon:
                px = vx + p.x
                py = vy + p.y

                if px > max_x:
                    max_x = px
                if py > max_y:
                    max_y = py

        return max_x, max_y
    
    def _contact_score(self, candidate: PlacedPart, placed_parts: List[PlacedPart]):

        moving = ShapelyPolygon(
            [(vx + candidate.x, vy + candidate.y) for vx, vy in candidate.polygon]
        )

        contact = 0.0

        for placed in placed_parts:

            static = ShapelyPolygon(
                [(vx + placed.x, vy + placed.y) for vx, vy in placed.polygon]
            )

            inter = moving.buffer(1e-6).intersection(static.buffer(1e-6))

            contact += inter.length

        return contact

    def _inside_layout(self, x, y, w, h, placed_parts):
        if not placed_parts:
            return False

        max_x, max_y = self._current_bounds(placed_parts)

        return (x + w <= max_x) and (y + h <= max_y)

    def _layout_score(self, placed_parts: List[PlacedPart]) -> float:
        max_x, max_y = self._current_bounds(placed_parts)
        edge_penalty = abs(self.sheet_width - max_x)
        occupied_area = max_x * max_y

        parts_area = sum(p.area for p in placed_parts)

        gap_penalty = occupied_area - parts_area
        if max_y == 0:
            aspect_penalty = 0
        else:
            aspect_ratio = max_x / max_y
            aspect_penalty = abs(aspect_ratio - 1.0)

        remaining_width = self.sheet_width - max_x
        remaining_height = self.sheet_height - max_y

        clean_rect_area = max(
            remaining_width * self.sheet_height,
            self.sheet_width * remaining_height
        )

        w1 = 1.0
        w2 = 800.0
        w3 = 3.0

        score = (
            occupied_area
            + 2000 * aspect_penalty
            + 5 * gap_penalty
            - 3 * clean_rect_area
            + 2 * edge_penalty
        )

        return score

    # =========================
    # MAIN
    # =========================

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
                best_layout = copy.deepcopy(placed_parts)

        if best_layout is None:
            raise RuntimeError("Failed to place parts")

        

        return best_layout

    # =========================
    # LOCAL IMPROVEMENT
    # =========================

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
                    area=part_to_move.area
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

    # =========================
    # SINGLE PART PLACEMENT
    # =========================

        # =========================
    # MULTI RELOCATION
    # =========================

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
                    area=part_to_insert.area
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

        # для bottom-left
        best_y = float("inf")
        best_x = float("inf")

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
            

            candidates = set()
            candidates.add((0.0, 0.0))
            for placed in placed_parts:

                cache_key = (placed.angle, angle, len(placed.polygon), len(rotated))

                if cache_key in self._nfp_cache:
                    nfp = self._nfp_cache[cache_key]
                else:
                    nfp = compute_nfp(placed.polygon, rotated)
                    self._nfp_cache[cache_key] = nfp

                nfp_global = translate(nfp, placed.x, placed.y)

                for x, y in nfp_global:
                    candidates.add((x, y))
            
            # вершины уже размещенных деталей
            for placed in placed_parts:
                for vx, vy in placed.polygon:
                    candidates.add((vx + placed.x, vy + placed.y))

            # кандидаты вдоль границы текущего layout
            max_x, max_y = self._current_bounds(placed_parts)

            candidates.add((max_x, 0))
            candidates.add((0, max_y))
            candidates.add((max_x, max_y))

            # центр layout (помогает заполнять карманы)
            candidates.add((max_x/2, max_y/2))

            ordered_candidates = sorted(candidates, key=lambda p: (p[1], p[0]))

            for x, y in ordered_candidates:

                if not self._can_place(rotated, x, y, placed_parts, part.id, angle):
                    continue

                shape = ShapelyPolygon([(vx + x, vy + y) for vx, vy in rotated])
                candidate = PlacedPart(part.id, rotated, x, y, angle, part.area, shape)

                candidate = self._compact(candidate, placed_parts)

                # обновляем shape после compact
                candidate.shape = ShapelyPolygon(
                    [(vx + candidate.x, vy + candidate.y) for vx, vy in candidate.polygon]
                )

                # проверяем снова после сдвига
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

    # =========================
    # COLLISION CHECK
    # =========================

    def _can_place(
        self,
        polygon: Polygon,
        x: float,
        y: float,
        placed_parts: List[PlacedPart],
        part_id: str,
        angle: float,
    ) -> bool:

        moving = ShapelyPolygon([(vx + x, vy + y) for vx, vy in polygon]).buffer(0)
        moving_shrink = moving.buffer(-1e-6)

        # проверка границ листа
        minx, miny, maxx, maxy = moving.bounds

        if minx < 0 or miny < 0:
            return False

        if maxx > self.sheet_width or maxy > self.sheet_height:
            return False

        for placed in placed_parts:

            static = placed.shape

            # если shape ещё не создан (первая деталь)
            if static is None:
                static = ShapelyPolygon(
                    [(vx + placed.x, vy + placed.y) for vx, vy in placed.polygon]
                )
                placed.shape = static

            if moving_shrink.intersects(static.buffer(-1e-6)):
                return False

        return True