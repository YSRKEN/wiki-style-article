"""SVG を組み立てる共通の下請け。"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Final

from wikiskill.figures.errors import FigureError

HEX_PATTERN: Final[re.Pattern[str]] = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
TEXT_LEFT: Final = 20.0
TEXT_RIGHT: Final = 20.0


def escape(text: str) -> str:
    """XML の本文や属性に置ける形へ変換する。

    Parameters
    ----------
    text : str
        変換する文字列。

    Returns
    -------
    str
        実体参照に直した文字列。
    """
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def hex_color(value: object, *, where: str) -> str:
    """色の指定を検査し、小文字の #rrggbb にして返す。

    Parameters
    ----------
    value : object
        検査する値。
    where : str
        誤りの文に出す場所の名前。

    Returns
    -------
    str
        小文字にした色。

    Raises
    ------
    FigureError
        #rgb か #rrggbb の形でないとき。
    """
    if not isinstance(value, str) or HEX_PATTERN.fullmatch(value) is None:
        raise FigureError(f"{where} の色は #rgb か #rrggbb の形で書く: {value!r}")
    return value.lower()


def number(value: float) -> str:
    """SVG に書く数の文字列を作る（小数は 2 桁まで）。

    Parameters
    ----------
    value : float
        書く数。

    Returns
    -------
    str
        余分な 0 を落とした文字列。
    """
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


PALETTE: Final[tuple[str, ...]] = (
    "#2c5aa0",
    "#c0392b",
    "#2e8b57",
    "#b9770e",
    "#6c3483",
    "#117a65",
    "#7f8c8d",
    "#a04000",
)


def palette_color(index: int) -> str:
    """色を指定しなかったときに使う色を、並び順から選ぶ。

    Parameters
    ----------
    index : int
        データの並び順（0 から）。

    Returns
    -------
    str
        選んだ色。
    """
    return PALETTE[index % len(PALETTE)]


def format_value(value: float, digits: int, unit: str = "") -> str:
    """グラフに書く値の文字列を作る。

    Parameters
    ----------
    value : float
        書く値。
    digits : int
        小数の桁数（0 から 2）。
    unit : str
        値の後ろに付ける単位（「万票」など）。

    Returns
    -------
    str
        3 桁区切りにした値と単位。
    """
    return f"{value:,.{digits}f}{unit}"


def text_width(text: str, font_size: float) -> float:
    """凡例の幅を見積もる（日本語は 1 文字を font_size 幅とみなす）。

    Parameters
    ----------
    text : str
        見積もる文字列。
    font_size : float
        文字の大きさ。

    Returns
    -------
    float
        見積もった幅。
    """
    return sum(font_size if ord(char) > 0x2E7F else font_size * 0.55 for char in text)


def legend(
    items: Sequence[tuple[str, str]], width: float, *, font_size: float = 14.0
) -> tuple[str, float]:
    """色の見本と名前を並べた凡例を作る。

    Parameters
    ----------
    items : Sequence[tuple[str, str]]
        （名前, 色）の並び。
    width : float
        図の幅。入りきらないときは折り返す。
    font_size : float
        文字の大きさ。

    Returns
    -------
    tuple[str, float]
        凡例の SVG と、その高さ。
    """
    if not items:
        return "", 0.0
    row_height = font_size + 8.0
    x = TEXT_LEFT
    y = font_size + 6.0
    parts: list[str] = []
    for label, color in items:
        side = font_size - 2.0
        item_width = side + 8.0 + text_width(label, font_size) + 18.0
        if x > TEXT_LEFT and x + item_width > width - TEXT_RIGHT:
            x = TEXT_LEFT
            y += row_height
        parts.append(
            f'<rect x="{number(x)}" y="{number(y - side + 2.0)}" width="{number(side)}" '
            f'height="{number(side)}" rx="2" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{number(x + side + 8.0)}" y="{number(y)}" font-family="sans-serif" '
            f'font-size="{number(font_size)}" fill="#222222">{escape(label)}</text>'
        )
        x += item_width
    height = y + 10.0
    return "".join(parts), height
