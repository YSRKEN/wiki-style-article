"""横棒グラフの SVG を描く。"""

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
    number,
    palette_color,
    text_width,
)

MARGIN: Final = 20.0
BAR_WIDTH: Final = 320.0
ROW_HEIGHT: Final = 24.0
ROW_GAP: Final = 8.0
FONT_SIZE: Final = 16.0
LABEL_PAD: Final = 16.0
VALUE_PAD: Final = 8.0
VALUE_GAP: Final = 6.0
BASELINE: Final = 5.5
TEXT_COLOR: Final = "#222222"
TOP_LEVEL_KEYS: Final[frozenset[str]] = frozenset(
    {"title", "unit", "digits", "color", "sort", "value_max", "bar"}
)
BAR_KEYS: Final[frozenset[str]] = frozenset({"label", "value", "color"})


@dataclass(frozen=True, slots=True)
class Bar:
    """横棒グラフに出す 1 本の棒。"""

    label: str
    value: float
    color: str


@dataclass(frozen=True, slots=True)
class BarsData:
    """棒グラフのデータ（TOML）を読んだ結果。"""

    title: str
    unit: str
    digits: int
    bars: tuple[Bar, ...]
    value_max: float


def render_bars(data_path: Path) -> str:
    """棒グラフのデータを読み、横棒を並べた SVG を返す。

    Parameters
    ----------
    data_path : Path
        棒グラフのデータ（TOML）のファイルのパス。

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
    values = [format_value(bar.value, data.digits, data.unit) for bar in data.bars]
    label_column = max(text_width(bar.label, FONT_SIZE) for bar in data.bars) + LABEL_PAD
    value_column = max(text_width(text, FONT_SIZE) for text in values) + VALUE_PAD
    width = MARGIN + label_column + BAR_WIDTH + value_column + MARGIN
    height = MARGIN * 2.0 + len(data.bars) * ROW_HEIGHT + (len(data.bars) - 1) * ROW_GAP
    bar_left = MARGIN + label_column
    parts: list[str] = []
    for row, (bar, text) in enumerate(zip(data.bars, values, strict=True)):
        center = MARGIN + row * (ROW_HEIGHT + ROW_GAP) + ROW_HEIGHT / 2.0
        baseline = center + BASELINE
        bar_width = bar.value / data.value_max * BAR_WIDTH if data.value_max > 0.0 else 0.0
        parts.append(
            f'<text x="{number(bar_left)}" y="{number(baseline)}" text-anchor="end" '
            f'font-family="sans-serif" font-size="{number(FONT_SIZE)}" '
            f'fill="{TEXT_COLOR}">{escape(bar.label)}</text>'
        )
        # 値が 0 の棒は塗るものが無いので、矩形を出さず値のラベルだけを置く。
        if bar_width > 0.0:
            parts.append(
                f'<rect x="{number(bar_left)}" y="{number(center - ROW_HEIGHT / 2.0)}" '
                f'width="{number(bar_width)}" height="{number(ROW_HEIGHT)}" '
                f'fill="{bar.color}"/>'
            )
        parts.append(
            f'<text x="{number(bar_left + bar_width + VALUE_GAP)}" y="{number(baseline)}" '
            f'text-anchor="start" font-family="sans-serif" '
            f'font-size="{number(FONT_SIZE)}" fill="{TEXT_COLOR}">{escape(text)}</text>'
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
    output.append("</svg>")
    return "".join(output)


def _order(bars: list[Bar], sort: str | None) -> list[Bar]:
    if sort == "value":
        return sorted(bars, key=lambda bar: -bar.value)
    if sort == "label":
        return sorted(bars, key=lambda bar: bar.label)
    return bars


def _load_data(path: Path) -> BarsData:
    raw = read_toml(path)
    where = "棒グラフのデータ"
    reject_unknown(raw, TOP_LEVEL_KEYS, where)
    title = string(raw, "title", "", where)
    unit = string(raw, "unit", "", where)
    digits = _digits(raw.get("digits", 0), where)
    top_color = _top_color(raw.get("color"), where)
    sort = _sort(raw.get("sort"), where)
    items = raw.get("bar")
    if not isinstance(items, list) or not items:
        raise FigureError(f"{where} の bar は 1 つ以上の表の並びで書く")
    bars: list[Bar] = []
    labels: set[str] = set()
    for index, item in enumerate(cast(list[object], items)):
        if not isinstance(item, dict):
            raise FigureError(f"{where} の bar の要素は表で書く")
        table = cast(dict[str, object], item)
        reject_unknown(table, BAR_KEYS, where)
        label = string(table, "label", "", where)
        if not label.strip():
            raise FigureError(f"{where} の bar の label が空")
        if label in labels:
            raise FigureError(f"{where} の bar の label が重複している: {label}")
        labels.add(label)
        value = _value(table.get("value"), label, where)
        color = _bar_color(table.get("color"), top_color, index, label, where)
        bars.append(Bar(label=label, value=value, color=color))
    largest = max(bar.value for bar in bars)
    value_max = _value_max(raw.get("value_max"), largest, where)
    ordered = tuple(_order(bars, sort))
    return BarsData(title=title, unit=unit, digits=digits, bars=ordered, value_max=value_max)


def _digits(raw: object, where: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int) or not 0 <= raw <= 2:
        raise FigureError(f"{where} の digits は 0 から 2 の整数で書く")
    return raw


def _sort(raw: object, where: str) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str) or raw not in {"value", "label"}:
        raise FigureError(f"{where} の sort は value か label で書く: {raw!r}")
    return raw


def _value(raw: object, label: str, where: str) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise FigureError(f"{where} の bar の value は数で書く: {label}")
    value = float(raw)
    if not math.isfinite(value) or value < 0.0:
        raise FigureError(f"{where} の bar の value は 0 以上の数で書く: {label}")
    return value


def _value_max(raw: object, largest: float, where: str) -> float:
    if raw is None:
        return largest
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise FigureError(f"{where} の value_max は数で書く")
    limit = float(raw)
    if not math.isfinite(limit) or limit < largest:
        raise FigureError(f"{where} の value_max は値の最大以上で書く")
    return limit


def _top_color(raw: object, where: str) -> str | None:
    if raw is None:
        return None
    return hex_color(raw, where=f"{where} の color")


def _bar_color(raw: object, default: str | None, index: int, label: str, where: str) -> str:
    if raw is not None:
        return hex_color(raw, where=f"{where} の bar の {label} の color")
    if default is not None:
        return default
    return palette_color(index)
