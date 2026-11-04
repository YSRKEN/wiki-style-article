"""議席の半円図を描く。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from wikiskill.figures.data import read_toml, reject_unknown, string
from wikiskill.figures.errors import FigureError
from wikiskill.figures.svg import escape, hex_color, legend, number

SPACING: float = 12.0
DOT: float = 4.6
PADDING: float = DOT + 6.0
TOTAL_HEIGHT: float = 26.0
FONT_SIZE: float = 16.0


@dataclass(frozen=True, slots=True)
class Party:
    """議席図に出す政党。"""

    name: str
    seats: int
    color: str


@dataclass(frozen=True, slots=True)
class SeatsData:
    """議席図のデータ（TOML）を読んだ結果。"""

    title: str
    parties: tuple[Party, ...]


def render_seats(data_path: Path) -> str:
    """議席図のデータを読み、半円に議席を並べた SVG を返す。

    Parameters
    ----------
    data_path : Path
        議席図のデータ（TOML）の道。

    Returns
    -------
    str
        SVG の文字列。

    Raises
    ------
    FigureError
        データが正しくないとき。
    """
    data = _load_data(data_path)
    total = sum(party.seats for party in data.parties)
    rows = _row_count(total)
    counts = _allocate(total, rows)
    outer = rows * SPACING
    center_x = outer + PADDING
    center_y = outer + PADDING
    chart_height = center_y + DOT + 4.0
    width = center_x * 2.0
    colors = [party.color for party in data.parties for _ in range(party.seats)]
    # 議席は弧に沿って左から右へ並べる。政党の並び順がそのまま左右の並びになる。
    seats: list[tuple[float, float]] = []
    for row, count in enumerate(counts):
        if count == 0:
            continue
        radius = SPACING * (row + 1)
        for position in range(count):
            angle = math.pi - (position + 0.5) * math.pi / count
            seats.append((angle, radius))
    seats.sort(key=lambda seat: (-seat[0], seat[1]))
    parts: list[str] = []
    for (angle, radius), color in zip(seats, colors, strict=True):
        x = center_x + radius * math.cos(angle)
        y = center_y - radius * math.sin(angle)
        parts.append(
            f'<circle cx="{number(x)}" cy="{number(y)}" r="{number(DOT)}" fill="{color}"/>'
        )
    items = [
        (f"{party.name}（{party.seats}）", party.color) for party in data.parties if party.seats
    ]
    legend_markup, legend_height = legend(items, width)
    height = chart_height + TOTAL_HEIGHT + legend_height
    attributes = [
        'xmlns="http://www.w3.org/2000/svg"',
        f'width="{number(width)}"',
        f'height="{number(height)}"',
        f'viewBox="0 0 {number(width)} {number(height)}"',
        'role="img"',
    ]
    if data.title:
        attributes.append(f'aria-label="{escape(data.title)}"')
    output = [f"<svg {' '.join(attributes)}>"]
    if data.title:
        output.append(f"<title>{escape(data.title)}</title>")
    output.extend(parts)
    output.append(
        f'<text x="{number(center_x)}" y="{number(chart_height + 18.0)}" '
        f'text-anchor="middle" font-family="sans-serif" font-size="{number(FONT_SIZE)}" '
        f'fill="#222222">合計 {total} 議席</text>'
    )
    if legend_markup:
        output.append(
            f'<g transform="translate(0,{number(chart_height + TOTAL_HEIGHT)})">{legend_markup}</g>'
        )
    output.append("</svg>")
    return "".join(output)


def _row_count(total: int) -> int:
    return max(1, math.ceil((-1.0 + math.sqrt(1.0 + 8.0 * total / math.pi)) / 2.0))


def _allocate(total: int, rows: int) -> list[int]:
    weights = [row + 1 for row in range(rows)]
    weight_sum = sum(weights)
    counts: list[int] = []
    fractions: list[tuple[float, int]] = []
    for row, weight in enumerate(weights):
        exact = total * weight / weight_sum
        base = int(math.floor(exact))
        counts.append(base)
        fractions.append((exact - base, row))
    remaining = total - sum(counts)
    fractions.sort(key=lambda item: (-item[0], item[1]))
    for _, row in fractions[:remaining]:
        counts[row] += 1
    return counts


def _load_data(path: Path) -> SeatsData:
    raw = read_toml(path)
    where = "議席図のデータ"
    reject_unknown(raw, frozenset({"title", "party"}), where)
    title = string(raw, "title", "", where)
    value = raw.get("party")
    if not isinstance(value, list) or not value:
        raise FigureError(f"{where} の party は 1 つ以上の表の並びで書く")
    parties: list[Party] = []
    names: set[str] = set()
    for item in cast(list[object], value):
        if not isinstance(item, dict):
            raise FigureError(f"{where} の party の要素は表で書く")
        table = cast(dict[str, object], item)
        reject_unknown(table, frozenset({"name", "seats", "color"}), where)
        name = string(table, "name", "", where)
        if not name.strip():
            raise FigureError(f"{where} の party の name が空")
        if name in names:
            raise FigureError(f"{where} の party の name が重複している: {name}")
        names.add(name)
        seats = table.get("seats")
        if isinstance(seats, bool) or not isinstance(seats, int) or seats < 0:
            raise FigureError(f"{where} の party の seats は 0 以上の整数で書く: {name}")
        color = hex_color(table.get("color"), where=f"{where} の party の {name} の color")
        parties.append(Party(name=name, seats=seats, color=color))
    if sum(party.seats for party in parties) == 0:
        raise FigureError(f"{where} の議席の合計が 0")
    return SeatsData(title=title, parties=tuple(parties))
