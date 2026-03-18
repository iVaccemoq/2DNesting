# test_layout.py
import math

from nesting.placement import BottomLeftPlacer, Part
from visualization.plot import plot_layout


# =========================
# Shape generators
# =========================

def rect(w, h):
    return [(0, 0), (w, 0), (w, h), (0, h)]


def triangle():
    return [(0, 0), (80, 0), (40, 90)]


def hexagon(r=40):
    return [
        (
            r + r * math.cos(2 * math.pi * i / 6),
            r + r * math.sin(2 * math.pi * i / 6),
        )
        for i in range(6)
    ]


def circle(radius=30, segments=32):
    return [
        (
            radius + radius * math.cos(2 * math.pi * i / segments),
            radius + radius * math.sin(2 * math.pi * i / segments),
        )
        for i in range(segments)
    ]


# =========================
# VISUAL TESTS
# =========================

def test_basic():
    parts = [
        Part("Square", rect(100, 100), 10000),
        Part("Triangle", triangle(), 3600),
        Part("Bar", rect(150, 20), 3000),
    ]

    placer = BottomLeftPlacer(500, 300, [0, 90])
    placed = placer.place(parts)

    plot_layout(500, 300, placed, title="Basic shapes")


def test_hexagons():
    parts = [
        Part(f"Hex_{i}", hexagon(), 4000)
        for i in range(16)
    ]

    placer = BottomLeftPlacer(400, 300, [0])
    placed = placer.place(parts)

    plot_layout(400, 300, placed, title="Hexagon packing")


def test_needles():
    parts = [
        Part(f"Needle_{i}", rect(200, 6), 1200)
        for i in range(6)
    ]

    placer = BottomLeftPlacer(600, 200, [0, 90])
    placed = placer.place(parts)

    plot_layout(600, 200, placed, title="Needles")


def test_c_with_small():
    big_c = Part(
        "Big_C",
        [
            (0, 0), (200, 0), (200, 200), (0, 200),
            (0, 160), (160, 160), (160, 40), (0, 40),
        ],
        200 * 200 - 120 * 120,
    )

    small = [
        Part(f"Small_{i}", rect(20, 10), 200)
        for i in range(20)
    ]

    parts = [big_c] + small

    placer = BottomLeftPlacer(600, 400, [0])
    placed = placer.place(parts)

    plot_layout(600, 400, placed, title="Concave C + small parts")


def test_mixed_hard():
    parts = [
        Part("L", [(0,0),(160,0),(160,40),(40,40),(40,160),(0,160)], 160*160 - 120*120),
        Part("Circle", circle(35), math.pi * 35 * 35),
        Part("Triangle", triangle(), 3600),
        Part("Bar1", rect(180, 10), 1800),
        Part("Bar2", rect(180, 10), 1800),
        Part("SmallA", rect(25, 20), 500),
        Part("SmallB", rect(25, 20), 500),
    ]

    placer = BottomLeftPlacer(700, 400, [0, 90])
    placed = placer.place(parts)

    plot_layout(700, 400, placed, title="Mixed hard case")


# =========================
# MAIN
# =========================

if __name__ == "__main__":
    # ВыбирайZ, что смотреть 👇

    test_basic()
    test_hexagons()
    test_needles()
    test_c_with_small()
    test_mixed_hard()
