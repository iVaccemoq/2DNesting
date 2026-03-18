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
    sheet_width=700,
    sheet_height=700,
    allowed_angles=[0, 90]
)

layout = placer.place(all_parts)

plot_layout(700, 700, layout, title="Multi-SVG nesting")