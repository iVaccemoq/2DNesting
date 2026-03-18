# visualization/plot.py
import matplotlib.pyplot as plt
from typing import List, Tuple

Point = Tuple[float, float]


def plot_layout(
    sheet_width: float,
    sheet_height: float,
    placed_parts,
    title: str | None = None,
):
    fig, ax = plt.subplots()

    # лист
    ax.set_xlim(0, sheet_width)
    ax.set_ylim(0, sheet_height)
    ax.set_aspect("equal")
    ax.add_patch(
        plt.Rectangle(
            (0, 0),
            sheet_width,
            sheet_height,
            fill=False,
            edgecolor="black",
            linewidth=2,
        )
    )

    # детали
    for p in placed_parts:
        xs = [x + p.x for x, y in p.polygon]
        ys = [y + p.y for x, y in p.polygon]
        xs.append(xs[0])
        ys.append(ys[0])

        ax.plot(xs, ys)
        ax.fill(xs, ys, alpha=0.4)
        ax.text(
            min(xs),
            min(ys),
            p.part_id,
            fontsize=8,
        )

    if title:
        ax.set_title(title)

    plt.show()
