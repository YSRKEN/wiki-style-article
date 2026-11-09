"""人口ピラミッド（男女別の年齢構成）の図を描く。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from wikiskill.figures.data import read_toml, reject_unknown, string
from wikiskill.figures.errors import FigureError
from wikiskill.figures.svg import escape, format_value, hex_color, number, text_width

MARGIN: float = 20.0
HEADING_HEIGHT: float = 24.0
HEADING_FONT: float = 15.0
ROW_HEIGHT: float = 20.0
ROW_GAP: float = 6.0
BAR_MAX: float = 200.0
CENTER_PADDING: float = 16.0
LABEL_FONT: float = 15.0
VALUE_FONT: float = 13.0
VALUE_GAP: float = 6.0
DIGITS_MAX: int = 2
DEFAULT_MALE_LABEL: str = "男性"
DEFAULT_FEMALE_LABEL: str = "女性"
DEFAULT_MALE_COLOR: str = "#2c5aa0"
DEFAULT_FEMALE_COLOR: str = "#c0392b"


@dataclass(frozen=True, slots=True)
class Band:
    """人口ピラミッドの 1 段（年齢の区切り）。"""

    label: str
    male: float
    female: float


@dataclass(frozen=True, slots=True)
class PyramidData:
    """人口ピラミッドのデータ（TOML）を読んだ結果。"""

    title: str
    unit: str
    digits: int
    male_label: str
    female_label: str
    male_color: str
    female_color: str
    bands: tuple[Band, ...]


def render_pyramid(data_path: Path) -> str:
    """人口ピラミッドのデータを読み、男女の棒を左右に並べた SVG を返す。

    Parameters
    ----------
    data_path : Path
        人口ピラミッドのデータ（TOML）の道。

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
    count = len(data.bands)
    center_width = max(text_width(band.label, LABEL_FONT) for band in data.bands) + CENTER_PADDING
    male_texts = [format_value(band.male, data.digits, data.unit) for band in data.bands]
    female_texts = [format_value(band.female, data.digits, data.unit) for band in data.bands]
    male_text_width = max(text_width(text, VALUE_FONT) for text in male_texts)
    female_text_width = max(text_width(text, VALUE_FONT) for text in female_texts)
    width = MARGIN + male_text_width + BAR_MAX + center_width + BAR_MAX + female_text_width + MARGIN
    height = MARGIN + HEADING_HEIGHT + count * ROW_HEIGHT + (count - 1) * ROW_GAP + MARGIN
    male_zone_left = MARGIN + male_text_width
    center_left = male_zone_left + BAR_MAX
    center_right = center_left + center_width
    # 左右で同じ縮尺を使い、男女を通じた最大値が BAR_MAX になるようにする。
    # 片側ずつ 200 に伸ばすと、左右の長さをそのまま比べられなくなるため。
    maximum = max([band.male for band in data.bands] + [band.female for band in data.bands])
    scale = BAR_MAX / maximum if maximum > 0.0 else 0.0
    parts: list[str] = []
    heading_y = MARGIN + HEADING_FONT
    if data.male_label:
        parts.append(
            _text(
                male_zone_left + BAR_MAX / 2.0,
                heading_y,
                data.male_label,
                anchor="middle",
                size=HEADING_FONT,
                weight="bold",
            )
        )
    if data.female_label:
        parts.append(
            _text(
                center_right + BAR_MAX / 2.0,
                heading_y,
                data.female_label,
                anchor="middle",
                size=HEADING_FONT,
                weight="bold",
            )
        )
    for index, band in enumerate(data.bands):
        top = MARGIN + HEADING_HEIGHT + index * (ROW_HEIGHT + ROW_GAP)
        male_length = band.male * scale
        female_length = band.female * scale
        if band.male > 0.0:
            parts.append(
                f'<rect x="{number(center_left - male_length)}" y="{number(top)}" '
                f'width="{number(male_length)}" height="{number(ROW_HEIGHT)}" '
                f'fill="{data.male_color}"/>'
            )
        parts.append(
            _text(
                center_left - male_length - VALUE_GAP,
                top + VALUE_FONT + 1.0,
                male_texts[index],
                anchor="end",
                size=VALUE_FONT,
            )
        )
        if band.female > 0.0:
            parts.append(
                f'<rect x="{number(center_right)}" y="{number(top)}" '
                f'width="{number(female_length)}" height="{number(ROW_HEIGHT)}" '
                f'fill="{data.female_color}"/>'
            )
        parts.append(
            _text(
                center_right + female_length + VALUE_GAP,
                top + VALUE_FONT + 1.0,
                female_texts[index],
                anchor="start",
                size=VALUE_FONT,
            )
        )
        parts.append(
            _text(
                center_left + center_width / 2.0,
                top + LABEL_FONT,
                band.label,
                anchor="middle",
                size=LABEL_FONT,
            )
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


def _text(
    x: float,
    y: float,
    text: str,
    *,
    anchor: str,
    size: float,
    weight: str = "",
) -> str:
    """文字を 1 つ置く。"""
    weight_attribute = f' font-weight="{weight}"' if weight else ""
    return (
        f'<text x="{number(x)}" y="{number(y)}" text-anchor="{anchor}" '
        f'font-family="sans-serif" font-size="{number(size)}"{weight_attribute} '
        f'fill="#222222">{escape(text)}</text>'
    )


def _value(table: dict[str, object], key: str, label: str, where: str) -> float:
    """段の値を検査し、0 以上の有限の数として返す。"""
    value = table.get(key)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0.0
    ):
        raise FigureError(
            f"{where} の band の {label} の {key} は 0 以上の有限の数で書く: {value!r}"
        )
    return float(value)


def _digits(raw: dict[str, object], where: str) -> int:
    """小数の桁数を検査して返す。"""
    value = raw.get("digits", 0)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= DIGITS_MAX:
        raise FigureError(f"{where} の digits は 0 から {DIGITS_MAX} の整数で書く: {value!r}")
    return value


def _load_data(path: Path) -> PyramidData:
    raw = read_toml(path)
    where = "人口ピラミッドのデータ"
    reject_unknown(
        raw,
        frozenset(
            {
                "title",
                "unit",
                "digits",
                "male_label",
                "female_label",
                "male_color",
                "female_color",
                "band",
            }
        ),
        where,
    )
    title = string(raw, "title", "", where)
    unit = string(raw, "unit", "", where)
    male_label = string(raw, "male_label", DEFAULT_MALE_LABEL, where)
    female_label = string(raw, "female_label", DEFAULT_FEMALE_LABEL, where)
    male_color = hex_color(
        raw.get("male_color", DEFAULT_MALE_COLOR), where=f"{where} の male_color"
    )
    female_color = hex_color(
        raw.get("female_color", DEFAULT_FEMALE_COLOR), where=f"{where} の female_color"
    )
    digits = _digits(raw, where)
    value = raw.get("band")
    if not isinstance(value, list) or not value:
        raise FigureError(f"{where} の band は 1 つ以上の表の並びで書く")
    bands: list[Band] = []
    labels: set[str] = set()
    for item in cast(list[object], value):
        if not isinstance(item, dict):
            raise FigureError(f"{where} の band の要素は表で書く")
        table = cast(dict[str, object], item)
        reject_unknown(table, frozenset({"label", "male", "female"}), where)
        label = string(table, "label", "", where)
        if not label.strip():
            raise FigureError(f"{where} の band の label が空")
        if label in labels:
            raise FigureError(f"{where} の band の label が重複している: {label}")
        labels.add(label)
        male = _value(table, "male", label, where)
        female = _value(table, "female", label, where)
        bands.append(Band(label=label, male=male, female=female))
    return PyramidData(
        title=title,
        unit=unit,
        digits=digits,
        male_label=male_label,
        female_label=female_label,
        male_color=male_color,
        female_color=female_color,
        bands=tuple(bands),
    )
