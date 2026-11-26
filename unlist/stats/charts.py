# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The Unlist contributors
"""A two-series line chart drawn as SVG text. No library, no script, no inline style.

Colours, dashes and text sizes come from the classes in ``static/stats/stats.css``. The two
series differ in more than colour: dashed against solid line, and circle against square marker.
"""

from datetime import date
from xml.sax.saxutils import escape, quoteattr

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

WIDTH, HEIGHT = 640, 280
LEFT, RIGHT, TOP, BOTTOM = 44, 24, 28, 72
MARKER = 5
MAX_LABELLED_POINTS = 12


def month_label(month: date) -> str:
    return f"{MONTHS[month.month - 1]} {month.year}"


def _nice_top(largest: int) -> int:
    """The top of the y axis: the largest value rounded up to 4, 5, 10, 20, 50, ... (at least 4)."""
    if largest <= 4:
        return 4
    step = 1
    while step * 10 < largest:
        step *= 10
    for factor in (1, 2, 5, 10):
        if factor * step >= largest:
            return factor * step
    return 10 * step


def _text(x, y, content, css, anchor="middle"):
    return f'<text class="{css}" x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}">{escape(str(content))}</text>'


def line_chart(points, *, uid: str, title: str, description: str, names=("Holding data", "Removed")) -> str:
    """``points`` is a list of ``(month, holding, removed)``; returns an ``<svg>`` element as text."""
    plot_width, plot_height = WIDTH - LEFT - RIGHT, HEIGHT - TOP - BOTTOM
    top = _nice_top(max([value for _month, *values in points for value in values] or [0]))

    def x_at(index):
        if len(points) == 1:
            return LEFT + plot_width / 2
        return LEFT + plot_width * index / (len(points) - 1)

    def y_at(value):
        return TOP + plot_height * (1 - value / top)

    parts = [
        f'<svg class="stats-chart" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'role="img" aria-labelledby={quoteattr(uid + "-title")} aria-describedby={quoteattr(uid + "-desc")}>',
        f"<title id={quoteattr(uid + '-title')}>{escape(title)}</title>",
        f"<desc id={quoteattr(uid + '-desc')}>{escape(description)}</desc>",
    ]
    for tick in sorted({0, top // 2, top}):
        y = y_at(tick)
        parts.append(f'<line class="chart-grid" x1="{LEFT}" y1="{y:.1f}" x2="{WIDTH - RIGHT}" y2="{y:.1f}"/>')
        parts.append(_text(LEFT - 8, y + 4, tick, "chart-text", "end"))

    every = 1 if len(points) <= MAX_LABELLED_POINTS else -(-len(points) // MAX_LABELLED_POINTS)
    for index, (month, *_values) in enumerate(points):
        if index % every == 0 or index == len(points) - 1:
            parts.append(_text(x_at(index), HEIGHT - BOTTOM + 18, month_label(month), "chart-text"))

    for series, css in enumerate(("chart-holding", "chart-removed"), start=1):
        coordinates = [(x_at(index), y_at(point[series])) for index, point in enumerate(points)]
        if len(coordinates) > 1:
            joined = " ".join(f"{x:.1f},{y:.1f}" for x, y in coordinates)
            parts.append(f'<polyline class="chart-line {css}" points="{joined}"/>')
        for index, (x, y) in enumerate(coordinates):
            if css == "chart-holding":
                parts.append(f'<circle class="chart-mark {css}" cx="{x:.1f}" cy="{y:.1f}" r="{MARKER}"/>')
            else:
                parts.append(
                    f'<rect class="chart-mark {css}" x="{x - MARKER:.1f}" y="{y - MARKER:.1f}" '
                    f'width="{2 * MARKER}" height="{2 * MARKER}"/>'
                )
            if len(points) <= MAX_LABELLED_POINTS or index == len(points) - 1:
                offset = -10 if css == "chart-holding" else 18
                parts.append(_text(x, y + offset, points[index][series], "chart-value"))

    # Legend, as text under the axis.
    legend_y = HEIGHT - 14
    for css, name, x in (("chart-holding", names[0], LEFT), ("chart-removed", names[1], LEFT + 190)):
        parts.append(f'<line class="chart-line {css}" x1="{x}" y1="{legend_y - 4}" x2="{x + 28}" y2="{legend_y - 4}"/>')
        parts.append(_text(x + 36, legend_y, name, "chart-text", "start"))
    parts.append("</svg>")
    return "".join(parts)
