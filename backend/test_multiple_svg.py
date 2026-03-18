import os

from svg.parser import parse_svg
from nesting.placement import BottomLeftPlacer
from visualization.plot import plot_layout


folder = "svg_parts"

all_parts = []

for file in os.listdir(folder):

    if file.endswith(".svg"):

        parts = parse_svg(os.path.join(folder, file))

        all_parts.extend(parts)


print("Total parts:", len(all_parts))


placer = BottomLeftPlacer(
    sheet_width=1000,
    sheet_height=1000,
    allowed_angles=[0, 90]
)

layout = placer.place(all_parts)

plot_layout(1000, 1000, layout, title="Multi-SVG nesting")