"""折れ線グラフを描く。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

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

LEFT: Final[float] = 72.0
RIGHT: Final[float] = 20.0
TOP: Final[float] = 20.0
BOTTOM: Final[float] = 20.0
PLOT_WIDTH: Final[float] = 560.0
PLOT_HEIGHT: Final[float] = 300.0
PLOT_BOTTOM: Final[float] = TOP + PLOT_HEIGHT
X_LABEL_OFFSET: Final[float] = 20.0
X_LABEL_SPACE: Final[float] = 24.0
X_LABEL_PADDING: Final[float] = 8.0
LEGEND_GAP: Final[float] = 12.0
FONT_SIZE: Final[float] = 14.0
TICK_GAP: Final[float] = 8.0
TICK_LEFT_PAD: Final[float] = 4.0
TICK_OFFSET: Final[float] = 5.0
TICK_COUNT: Final[int] = 5
DOT_LIMIT: Final[int] = 24
DOT_RADIUS: Final[float] = 3.5
LINE_WIDTH: Final[float] = 2.5
GRID_COLOR: Final[str] = "#dddddd"
AXIS_COLOR: Final[str] = "#999999"
TEXT_COLOR: Final[str] = "#222222"

TOP_KEYS: Final[frozenset[str]] = frozenset(
    {"title", "unit", "digits", "y_min", "y_max", "labels", "series"}
)
SERIES_KEYS: Final[frozenset[str]] = frozenset({"name", "color", "values"})


@dataclass(frozen=True, slots=True)
class Series:
    """折れ線グラフの 1 本の線。"""

    name: str
    color: str
    values: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class LineData:
    """折れ線グラフのデータ（TOML）を読んだ結果。"""

    title: str
    unit: str
    digits: int
    labels: tuple[str, ...]
    y_min: float | None
    y_max: float | None
    series: tuple[Series, ...]


def render_line(data_path: Path) -> str:
    """折れ線グラフのデータを読み、SVG の文字列を返す。

    Parameters
    ----------
    data_path : Path
        折れ線グラフのデータ（TOML）のファイルの場所。

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
    lower, upper = _range(data)
    ticks = _ticks(lower, upper)
    left = _left_margin(ticks, data.digits, data.unit)
    width = left + PLOT_WIDTH + RIGHT
    items = [(item.name, item.color) for item in data.series]
    legend_markup, legend_height = legend(items, PLOT_WIDTH)
    legend_top = PLOT_BOTTOM + X_LABEL_SPACE + LEGEND_GAP
    height = legend_top + legend_height + BOTTOM
    count = len(data.labels)
    parts: list[str] = []
    # 目盛りの線を先に引き、折れ線と軸をその上に重ねる。
    for tick in ticks:
        y = _y(tick, lower, upper)
        parts.append(
            f'<line x1="{number(left)}" y1="{number(y)}" x2="{number(left + PLOT_WIDTH)}" '
            f'y2="{number(y)}" stroke="{GRID_COLOR}" stroke-width="1"/>'
        )
    parts.append(
        f'<line x1="{number(left)}" y1="{number(TOP)}" x2="{number(left)}" '
        f'y2="{number(PLOT_BOTTOM)}" stroke="{AXIS_COLOR}" stroke-width="1"/>'
    )
    parts.append(
        f'<line x1="{number(left)}" y1="{number(PLOT_BOTTOM)}" '
        f'x2="{number(left + PLOT_WIDTH)}" y2="{number(PLOT_BOTTOM)}" '
        f'stroke="{AXIS_COLOR}" stroke-width="1"/>'
    )
    for item in data.series:
        points = [
            (_x(index, count, left), _y(value, lower, upper))
            for index, value in enumerate(item.values)
        ]
        path = " ".join(
            f"{'M' if index == 0 else 'L'} {number(x)} {number(y)}"
            for index, (x, y) in enumerate(points)
        )
        parts.append(
            f'<path d="{path}" fill="none" stroke="{item.color}" '
            f'stroke-width="{number(LINE_WIDTH)}" stroke-linejoin="round"/>'
        )
        if count <= DOT_LIMIT:
            for x, y in points:
                parts.append(
                    f'<circle cx="{number(x)}" cy="{number(y)}" '
                    f'r="{number(DOT_RADIUS)}" fill="{item.color}"/>'
                )
    for tick in ticks:
        y = _y(tick, lower, upper)
        text = escape(format_value(tick, data.digits, data.unit))
        parts.append(
            f'<text x="{number(left - TICK_GAP)}" y="{number(y + TICK_OFFSET)}" '
            f'text-anchor="end" font-family="sans-serif" font-size="{number(FONT_SIZE)}" '
            f'fill="{TEXT_COLOR}">{text}</text>'
        )
    for index in _label_indices(data.labels):
        parts.append(
            f'<text x="{number(_x(index, count, left))}" '
            f'y="{number(PLOT_BOTTOM + X_LABEL_OFFSET)}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="{number(FONT_SIZE)}" '
            f'fill="{TEXT_COLOR}">{escape(data.labels[index])}</text>'
        )
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
        f'<g transform="translate({number(left)},{number(legend_top)})">{legend_markup}</g>'
    )
    output.append("</svg>")
    return "".join(output)


def _left_margin(ticks: list[float], digits: int, unit: str) -> float:
    """目盛りのラベルがはみ出さないように、左の余白を決める。"""
    widest = max(text_width(format_value(tick, digits, unit), FONT_SIZE) for tick in ticks)
    return max(LEFT, widest + TICK_GAP + TICK_LEFT_PAD)


def _x(index: int, count: int, left: float) -> float:
    return left + PLOT_WIDTH * index / max(1, count - 1)


def _y(value: float, lower: float, upper: float) -> float:
    span = upper - lower
    position = TOP + PLOT_HEIGHT * (upper - value) / span
    # 範囲の外の値は枠の中に留める。
    return min(PLOT_BOTTOM, max(TOP, position))


def _ticks(lower: float, upper: float) -> list[float]:
    step = (upper - lower) / (TICK_COUNT - 1)
    values = [lower + step * index for index in range(TICK_COUNT - 1)]
    values.append(upper)
    return values


def _label_indices(labels: tuple[str, ...]) -> list[int]:
    if len(labels) <= 1:
        return [0]
    spacing = PLOT_WIDTH / (len(labels) - 1)
    widest = max(text_width(label, FONT_SIZE) for label in labels) + X_LABEL_PADDING
    every = 1
    while spacing * every < widest and every < len(labels):
        every += 1
    return list(range(0, len(labels), every))


def _ceil_nice(value: float) -> float:
    if value <= 0.0:
        return 0.0
    exponent = math.floor(math.log10(value))
    base = 10.0**exponent
    fraction = value / base
    for limit in (1.0, 2.0, 5.0):
        if fraction <= limit * (1.0 + 1e-9):
            return limit * base
    return 10.0 * base


def _floor_nice(value: float) -> float:
    if value >= 0.0:
        return 0.0
    return -_ceil_nice(-value)


def _range(data: LineData) -> tuple[float, float]:
    values = [value for item in data.series for value in item.values]
    lowest = min(values)
    highest = max(values)
    lower = data.y_min if data.y_min is not None else min(0.0, _floor_nice(lowest))
    upper = data.y_max if data.y_max is not None else _ceil_nice(highest)
    if upper <= lower:
        upper = lower + 1.0
    return lower, upper


def _optional_number(table: dict[str, object], key: str, where: str) -> float | None:
    value = table.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FigureError(f"{where} の {key} は数で書く: {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise FigureError(f"{where} の {key} は有限の数で書く: {value!r}")
    return result


def _digits(table: dict[str, object], where: str) -> int:
    value = table.get("digits", 0)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 2:
        raise FigureError(f"{where} の digits は 0 から 2 の整数で書く: {value!r}")
    return value


def _labels(table: dict[str, object], where: str) -> tuple[str, ...]:
    value = table.get("labels")
    if not isinstance(value, list):
        raise FigureError(f"{where} の labels は文字列の並びで書く")
    items = cast(list[object], value)
    if len(items) < 2:
        raise FigureError(f"{where} の labels は 2 件以上書く")
    labels: list[str] = []
    for item in items:
        if not isinstance(item, str):
            raise FigureError(f"{where} の labels は文字列で書く")
        if not item.strip():
            raise FigureError(f"{where} の labels に空の項目がある")
        labels.append(item)
    return tuple(labels)


def _values(table: dict[str, object], name: str, count: int, where: str) -> tuple[float, ...]:
    value = table.get("values")
    if not isinstance(value, list):
        raise FigureError(f"{where} の series の values は数の並びで書く: {name}")
    items = cast(list[object], value)
    if len(items) != count:
        raise FigureError(f"{where} の series の values の数が labels と違う: {name}")
    values: list[float] = []
    for item in items:
        if (
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not math.isfinite(float(item))
        ):
            raise FigureError(f"{where} の series の values は数で書く: {name}")
        values.append(float(item))
    return tuple(values)


def _series(table: dict[str, object], count: int, where: str) -> tuple[Series, ...]:
    value = table.get("series", [])
    if not isinstance(value, list):
        raise FigureError(f"{where} の series は表の並びで書く")
    items = cast(list[object], value)
    if not items:
        raise FigureError(f"{where} の series が空")
    series: list[Series] = []
    names: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise FigureError(f"{where} の series の要素は表で書く")
        entry = cast(dict[str, object], item)
        reject_unknown(entry, SERIES_KEYS, where)
        name = string(entry, "name", "", where)
        if not name.strip():
            raise FigureError(f"{where} の series の name が空")
        if name in names:
            raise FigureError(f"{where} の series の name が重複している: {name}")
        names.add(name)
        color = (
            hex_color(entry.get("color"), where=f"{where} の series の {name} の color")
            if "color" in entry
            else palette_color(index)
        )
        series.append(Series(name=name, color=color, values=_values(entry, name, count, where)))
    return tuple(series)


def _load_data(path: Path) -> LineData:
    raw = read_toml(path)
    where = "折れ線グラフのデータ"
    reject_unknown(raw, TOP_KEYS, where)
    title = string(raw, "title", "", where)
    unit = string(raw, "unit", "", where)
    digits = _digits(raw, where)
    y_min = _optional_number(raw, "y_min", where)
    y_max = _optional_number(raw, "y_max", where)
    labels = _labels(raw, where)
    series = _series(raw, len(labels), where)
    if y_min is not None and y_max is not None and y_min >= y_max:
        raise FigureError(f"{where} の y_min は y_max より小さく書く")
    return LineData(
        title=title,
        unit=unit,
        digits=digits,
        labels=labels,
        y_min=y_min,
        y_max=y_max,
        series=series,
    )
