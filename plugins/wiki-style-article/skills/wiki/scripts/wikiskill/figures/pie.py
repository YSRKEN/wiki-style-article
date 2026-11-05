"""円グラフを描く。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from wikiskill.figures.data import read_toml, reject_unknown, string
from wikiskill.figures.errors import FigureError
from wikiskill.figures.svg import (
    escape,
    format_value,
    hex_color,
    legend,
    number,
    palette_color,
    text_width,
)

RADIUS: float = 96.0
MARGIN: float = 20.0
LEGEND_FONT_SIZE: float = 14.0
INSIDE_FONT_SIZE: float = 14.0
INSIDE_RATIO: float = 0.62
MIN_INSIDE_SHARE: float = 6.0
LEGEND_ITEM_WIDTH: float = 78.0
WHERE: str = "円グラフのデータ"

TOP_KEYS: frozenset[str] = frozenset({"title", "unit", "digits", "slice"})
SLICE_KEYS: frozenset[str] = frozenset({"label", "value", "color"})


@dataclass(frozen=True, slots=True)
class Slice:
    """円グラフの 1 つの切片。

    Attributes
    ----------
    label : str
        凡例に出す名前。
    value : float
        0 より大きい値。割合はこの値の合計から計算する。
    color : str
        扇形の色。
    """

    label: str
    value: float
    color: str


@dataclass(frozen=True, slots=True)
class PieData:
    """円グラフのデータ（TOML）を読み取った結果。"""

    title: str
    unit: str
    digits: int
    slices: tuple[Slice, ...]


def render_pie(data_path: Path) -> str:
    """円グラフのデータを読み、扇形と凡例を並べた SVG を返す。

    Parameters
    ----------
    data_path : Path
        データの TOML の道。

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
    total = sum(item.value for item in data.slices)
    shares = [item.value / total * 100.0 for item in data.slices]
    texts = [
        _legend_text(item, share, data.digits, data.unit)
        for item, share in zip(data.slices, shares, strict=True)
    ]
    items = [(text, item.color) for text, item in zip(texts, data.slices, strict=True)]
    needs = max(text_width(text, LEGEND_FONT_SIZE) for text in texts) + LEGEND_ITEM_WIDTH
    width = max(RADIUS * 2.0 + MARGIN * 2.0, needs)
    center_x = width / 2.0
    center_y = RADIUS + MARGIN
    parts: list[str] = []
    if len(data.slices) == 1:
        only = data.slices[0]
        parts.append(
            f'<circle cx="{number(center_x)}" cy="{number(center_y)}" '
            f'r="{number(RADIUS)}" fill="{only.color}"/>'
        )
        parts.append(_inside_label(center_x, center_y, -90.0, shares[0]))
    else:
        start = -90.0
        for item, share in zip(data.slices, shares, strict=True):
            span = share / 100.0 * 360.0
            parts.append(_sector(center_x, center_y, start, start + span, item.color))
            if share >= MIN_INSIDE_SHARE:
                parts.append(_inside_label(center_x, center_y, start + span / 2.0, share))
            start += span
    chart_height = center_y + RADIUS + MARGIN
    legend_markup, legend_height = legend(items, width, font_size=LEGEND_FONT_SIZE)
    height = chart_height + legend_height
    return _document(data.title, width, height, parts, legend_markup, chart_height)


def _document(
    title: str,
    width: float,
    height: float,
    parts: list[str],
    legend_markup: str,
    chart_height: float,
) -> str:
    attributes = [
        'xmlns="http://www.w3.org/2000/svg"',
        f'width="{number(width)}"',
        f'height="{number(height)}"',
        f'viewBox="0 0 {number(width)} {number(height)}"',
        'role="img"',
    ]
    if title:
        attributes.append(f'aria-label="{escape(title)}"')
    output = [f"<svg {' '.join(attributes)}>"]
    if title:
        output.append(f"<title>{escape(title)}</title>")
    output.extend(parts)
    output.append(f'<g transform="translate(0,{number(chart_height)})">{legend_markup}</g>')
    output.append("</svg>")
    return "".join(output)


def _sector(cx: float, cy: float, start: float, end: float, color: str) -> str:
    x1, y1 = _point(cx, cy, start)
    x2, y2 = _point(cx, cy, end)
    large = 1 if end - start > 180.0 else 0
    return (
        f'<path d="M {number(cx)} {number(cy)} L {number(x1)} {number(y1)} '
        f'A {number(RADIUS)} {number(RADIUS)} 0 {large} 1 {number(x2)} {number(y2)} Z" '
        f'fill="{color}"/>'
    )


def _point(cx: float, cy: float, degrees: float) -> tuple[float, float]:
    radians = math.radians(degrees)
    return (cx + RADIUS * math.cos(radians), cy + RADIUS * math.sin(radians))


def _inside_label(cx: float, cy: float, degrees: float, share: float) -> str:
    radians = math.radians(degrees)
    distance = RADIUS * INSIDE_RATIO
    x = cx + distance * math.cos(radians)
    y = cy + distance * math.sin(radians)
    return (
        f'<text x="{number(x)}" y="{number(y + 5.0)}" text-anchor="middle" '
        f'font-family="sans-serif" font-size="{number(INSIDE_FONT_SIZE)}" '
        f'fill="#ffffff">{format_value(share, 1, "%")}</text>'
    )


def _legend_text(item: Slice, share: float, digits: int, unit: str) -> str:
    percent = format_value(share, 1, "%")
    if not unit:
        return f"{item.label}（{percent}）"
    return f"{item.label}（{format_value(item.value, digits, unit)}・{percent}）"


def _load_data(path: Path) -> PieData:
    raw = read_toml(path)
    reject_unknown(raw, TOP_KEYS, WHERE)
    title = string(raw, "title", "", WHERE)
    unit = string(raw, "unit", "", WHERE)
    digits = _digits(raw.get("digits"))
    rows = raw.get("slice")
    if not isinstance(rows, list) or not rows:
        raise FigureError(f"{WHERE} の slice が空")
    slices: list[Slice] = []
    seen: set[str] = set()
    for index, row in enumerate(cast(list[object], rows)):
        if not isinstance(row, dict):
            raise FigureError(f"{WHERE} の slice は表で書く")
        table = cast(dict[str, object], row)
        reject_unknown(table, SLICE_KEYS, WHERE)
        label = string(table, "label", "", WHERE)
        if not label:
            raise FigureError(f"{WHERE} の slice の label が空")
        if label in seen:
            raise FigureError(f"{WHERE} の slice の label が重複している: {label}")
        seen.add(label)
        slices.append(
            Slice(
                label=label,
                value=_value(table.get("value"), label),
                color=_color(table.get("color"), index, label),
            )
        )
    return PieData(title=title, unit=unit, digits=digits, slices=tuple(slices))


def _digits(raw: object) -> int:
    if raw is None:
        return 0
    if isinstance(raw, bool) or not isinstance(raw, int) or not 0 <= raw <= 2:
        raise FigureError(f"{WHERE} の digits は 0 から 2 の整数で書く")
    return raw


def _value(raw: object, label: str) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise FigureError(f"{WHERE} の slice の value は数で書く: {label}")
    value = float(raw)
    if not math.isfinite(value) or value <= 0.0:
        raise FigureError(f"{WHERE} の slice の value は 0 より大きい数で書く: {label}")
    return value


def _color(raw: object, index: int, label: str) -> str:
    if raw is None:
        return palette_color(index)
    if not isinstance(raw, str):
        raise FigureError(f"{WHERE} の slice の color は文字列で書く: {label}")
    return hex_color(raw, where=f"{WHERE} の slice の color")
