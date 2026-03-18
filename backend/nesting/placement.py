from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict

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
    shape_shrink: Optional[ShapelyPolygon] = None
    width: float = 0.0
    height: float = 0.0
    max_x: float = 0.0
    max_y: float = 0.0


class BottomLeftPlacer:

    def __init__(
        self,
        sheet_width: float,
        sheet_height: float,
        allowed_angles: List[float],
        multi_start: int = 10,
        candidate_limit: int = 250,
        local_search_passes: int = 2,
    ):
        self.sheet_width = sheet_width
        self.sheet_height = sheet_height
        self.allowed_angles = allowed_angles
        self.multi_start = multi_start
        self.candidate_limit = candidate_limit
        self.local_search_passes = local_search_passes

        self._nfp_cache = {}
        self._rotation_cache: Dict[Tuple[int, float], Tuple[Polygon, float, float]] = {}

    def _build_shape(self, polygon: Polygon, x: float, y: float) -> ShapelyPolygon:
        return ShapelyPolygon([(vx + x, vy + y) for vx, vy in polygon]).buffer(0)

    def _finalize_part(self, placed: PlacedPart) -> PlacedPart:
        placed.width, placed.height = width_height(placed.polygon)
        placed.max_x = placed.x + placed.width
        placed.max_y = placed.y + placed.height

        if placed.shape is None:
            placed.shape = self._build_shape(placed.polygon, placed.x, placed.y)
        if placed.shape_shrink is None:
            placed.shape_shrink = placed.shape.buffer(-1e-6)
        return placed

    def _current_bounds(self, placed_parts: List[PlacedPart]):
        if not placed_parts:
            return 0.0, 0.0
        return (
            max(p.max_x for p in placed_parts),
            max(p.max_y for p in placed_parts),
        )

    def _layout_score(self, placed_parts: List[PlacedPart]) -> float:
        max_x, max_y = self._current_bounds(placed_parts)
        edge_penalty = abs(self.sheet_width - max_x)
        occupied_area = max_x * max_y
        parts_area = sum(p.area for p in placed_parts)
        gap_penalty = occupied_area - parts_area
        aspect_penalty = 0 if max_y == 0 else abs((max_x / max_y) - 1.0)
        remaining_width = self.sheet_width - max_x
        remaining_height = self.sheet_height - max_y
        clean_rect_area = max(
            remaining_width * self.sheet_height,
            self.sheet_width * remaining_height,
        )
        return (
            occupied_area
            + 2000 * aspect_penalty
            + 5 * gap_penalty
            - 3 * clean_rect_area
            + 2 * edge_penalty
        )

    def _contact_score(self, candidate: PlacedPart, placed_parts: List[PlacedPart]):
        moving = candidate.shape or self._build_shape(candidate.polygon, candidate.x, candidate.y)
        contact = 0.0
        moving_buffer = moving.buffer(1e-6)
        for placed in placed_parts:
            static = placed.shape
            if static is None:
                self._finalize_part(placed)
                static = placed.shape
            inter = moving_buffer.intersection(static.buffer(1e-6))
            contact += inter.length
        return contact

    def _compact(self, placed: PlacedPart, placed_parts):
        step = 0.5
        max_iter = 40
        iter_count = 0
        while iter_count < max_iter:
            moved = False
            if self._can_place(placed.polygon, placed.x, placed.y - step, placed_parts):
                placed.y = round(placed.y - step, 4)
                placed.shape = None
                placed.shape_shrink = None
                self._finalize_part(placed)
                moved = True

            if self._can_place(placed.polygon, placed.x - step, placed.y, placed_parts):
                placed.x = round(placed.x - step, 4)
                placed.shape = None
                placed.shape_shrink = None
                self._finalize_part(placed)
                moved = True

            if not moved:
                break
            iter_count += 1
        return placed

    def _effective_multi_start(self, parts_count: int) -> int:
        if parts_count >= 8:
            return min(self.multi_start, 4)
        if parts_count >= 5:
            return min(self.multi_start, 6)
        return self.multi_start

    def _part_shape_signature(self, part: Part):
        w, h = width_height(part.polygon)
        return (part.area, max(w, h), min(w, h), len(part.polygon))

    def _generate_orderings(self, parts: List[Part], attempts: int) -> List[List[Part]]:
        if not parts:
            return []

        def bbox_area(part: Part):
            w, h = width_height(part.polygon)
            return w * h

        strategies = [
            sorted(parts, key=lambda p: p.area, reverse=True),
            sorted(parts, key=lambda p: bbox_area(p), reverse=True),
            sorted(parts, key=lambda p: self._part_shape_signature(p), reverse=True),
            sorted(parts, key=lambda p: (width_height(p.polygon)[0], p.area), reverse=True),
        ]

        while len(strategies) < attempts:
            if len(strategies) == 4:
                seed = strategies[0][:]
            else:
                seed = copy.deepcopy(random.choice(strategies[: min(3, len(strategies))]))
            self._mutate_order(seed)
            strategies.append(seed)

        return strategies[:attempts]

    def _mutate_order(self, ordered: List[Part]) -> None:
        if len(ordered) < 2:
            return
        swaps = max(1, min(4, len(ordered) // 3))
        for _ in range(swaps):
            i, j = sorted(random.sample(range(len(ordered)), 2))
            if random.random() < 0.5:
                ordered[i], ordered[j] = ordered[j], ordered[i]
            else:
                chunk = ordered[i:j + 1]
                random.shuffle(chunk)
                ordered[i:j + 1] = chunk

    def place(self, parts: List[Part]) -> List[PlacedPart]:
        best_layout = None
        best_score = float("inf")
        attempts = self._effective_multi_start(len(parts))

        for ordered in self._generate_orderings(parts, attempts):
            placed_parts = []
            for part in ordered:
                placed = self._place_single_part(part, placed_parts)
                if not placed:
                    break
                placed_parts.append(placed)

            if len(placed_parts) != len(parts):
                continue

            improved = self._improve_layout(placed_parts)
            score = self._layout_score(improved)
            if score < best_score:
                best_score = score
                best_layout = copy.deepcopy(improved)

        if best_layout is None:
            raise RuntimeError("Failed to place parts")
        return best_layout

    def _rotated_part(self, part: Part, angle: float):
        cache_key = (id(part), angle)
        cached = self._rotation_cache.get(cache_key)
        if cached is not None:
            return cached
        rotated = normalize(rotate(part.polygon, angle))
        w, h = width_height(rotated)
        self._rotation_cache[cache_key] = (rotated, w, h)
        return rotated, w, h

    def _candidate_seed_positions(self, rotated: Polygon, w: float, h: float, placed_parts: List[PlacedPart]):
        candidates = {(0.0, 0.0)}
        max_x, max_y = self._current_bounds(placed_parts)
        candidates.update(
            {
                (max_x, 0.0),
                (0.0, max_y),
                (max_x, max_y),
                (max(0.0, max_x - w), 0.0),
                (0.0, max(0.0, max_y - h)),
                (max_x / 2, 0.0),
                (0.0, max_y / 2),
            }
        )

        for placed in placed_parts:
            cache_key = (placed.angle, tuple(placed.polygon), tuple(rotated))
            nfp = self._nfp_cache.get(cache_key)
            if nfp is None:
                nfp = compute_nfp(placed.polygon, rotated)
                self._nfp_cache[cache_key] = nfp

            for x, y in translate(nfp, placed.x, placed.y):
                if x < -1e-6 or y < -1e-6:
                    continue
                if x + w > self.sheet_width + 1e-6 or y + h > self.sheet_height + 1e-6:
                    continue
                candidates.add((round(x, 4), round(y, 4)))

            candidates.update(
                {
                    (round(placed.max_x, 4), round(placed.y, 4)),
                    (round(placed.x, 4), round(placed.max_y, 4)),
                    (round(max(0.0, placed.max_x - w), 4), round(placed.y, 4)),
                    (round(placed.x, 4), round(max(0.0, placed.max_y - h), 4)),
                }
            )

        return sorted(candidates, key=lambda p: (p[1], p[0]))[: self.candidate_limit]

    def _candidate_score(self, candidate: PlacedPart, placed_parts: List[PlacedPart]) -> float:
        temp_layout = placed_parts + [candidate]
        score = self._layout_score(temp_layout)
        contact = self._contact_score(candidate, placed_parts)

        max_x, max_y = self._current_bounds(temp_layout)
        gravity = candidate.y * 4 + candidate.x * 2
        width_pressure = max_x * 12 + max_y * 4
        aligned_edges = 0.0
        for placed in placed_parts:
            if abs(candidate.x - placed.max_x) < 1e-3 or abs(candidate.max_x - placed.x) < 1e-3:
                aligned_edges += 1
            if abs(candidate.y - placed.max_y) < 1e-3 or abs(candidate.max_y - placed.y) < 1e-3:
                aligned_edges += 1

        return score + gravity + width_pressure - contact * 700 - aligned_edges * 150

    def _place_single_part(
        self,
        part: Part,
        placed_parts: List[PlacedPart],
    ) -> Optional[PlacedPart]:
        best_candidate = None
        best_score = float("inf")

        for angle in self.allowed_angles:
            rotated, w, h = self._rotated_part(part, angle)
            if w > self.sheet_width or h > self.sheet_height:
                continue

            if not placed_parts:
                candidate = self._finalize_part(
                    PlacedPart(part.id, rotated, 0.0, 0.0, angle, part.area, width=w, height=h)
                )
                score = self._candidate_score(candidate, [])
                if score < best_score:
                    best_score = score
                    best_candidate = candidate
                continue

            for x, y in self._candidate_seed_positions(rotated, w, h, placed_parts):
                if not self._can_place(rotated, x, y, placed_parts):
                    continue

                candidate = self._finalize_part(
                    PlacedPart(part.id, rotated, x, y, angle, part.area, width=w, height=h)
                )
                candidate = self._compact(candidate, placed_parts)
                if not self._can_place(candidate.polygon, candidate.x, candidate.y, placed_parts):
                    continue

                combined = self._candidate_score(candidate, placed_parts)
                if combined < best_score:
                    best_score = combined
                    best_candidate = candidate

        return best_candidate

    def _improve_layout(self, layout: List[PlacedPart]) -> List[PlacedPart]:
        best_layout = copy.deepcopy(layout)
        best_score = self._layout_score(best_layout)

        for _ in range(self.local_search_passes):
            improved = False
            reinsert_order = sorted(
                range(len(best_layout)),
                key=lambda i: (best_layout[i].max_x + best_layout[i].max_y, best_layout[i].area),
                reverse=True,
            )

            for idx in reinsert_order:
                part_to_move = best_layout[idx]
                remaining = [copy.deepcopy(p) for i, p in enumerate(best_layout) if i != idx]
                candidate_part = Part(part_to_move.part_id, part_to_move.polygon, part_to_move.area)
                new_position = self._place_single_part(candidate_part, remaining)
                if not new_position:
                    continue

                new_layout = remaining + [new_position]
                new_score = self._layout_score(new_layout)
                if new_score + 1e-6 < best_score:
                    best_layout = new_layout
                    best_score = new_score
                    improved = True
                    break

            if not improved:
                break

        return best_layout

    def _can_place(
        self,
        polygon: Polygon,
        x: float,
        y: float,
        placed_parts: List[PlacedPart],
    ) -> bool:
        moving = self._build_shape(polygon, x, y)
        minx, miny, maxx, maxy = moving.bounds
        if minx < 0 or miny < 0 or maxx > self.sheet_width or maxy > self.sheet_height:
            return False

        moving_shrink = moving.buffer(-1e-6)
        for placed in placed_parts:
            if placed.shape_shrink is None:
                self._finalize_part(placed)
            if moving_shrink.intersects(placed.shape_shrink):
                return False
        return True
