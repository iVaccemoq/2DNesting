import copy
import matplotlib.pyplot as plt

from svg.parser import parse_svg
from nesting.placement import BottomLeftPlacer


# загружаем один hexagon
parts = parse_svg("hexagon.svg")

if len(parts) == 0:
    raise RuntimeError("SVG parsing failed")

hexagon = parts[0]


# создаём 8 копий
all_parts = []

for i in range(8):
    p = copy.deepcopy(hexagon)
    p.id = f"hex_{i}"
    all_parts.append(p)

print("Total parts:", len(all_parts))


# запускаем nesting
placer = BottomLeftPlacer(
    sheet_width=500,
    sheet_height=400,
    allowed_angles=[0, 60, 120, 180, 240, 300, 360],
    multi_start=10
)

layout = placer.place(all_parts)


# визуализация
fig, ax = plt.subplots()

for placed in layout:

    xs = [p[0] + placed.x for p in placed.polygon]
    ys = [p[1] + placed.y for p in placed.polygon]

    xs.append(xs[0])
    ys.append(ys[0])

    ax.plot(xs, ys)

ax.set_xlim(0, 500)
ax.set_ylim(0, 400)
ax.set_aspect("equal")

plt.title("Hexagon Nesting Test")

plt.show()