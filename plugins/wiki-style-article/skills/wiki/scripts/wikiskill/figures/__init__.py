"""地図・議席図・グラフの SVG を作る。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Final

from wikiskill.figures.bars import render_bars
from wikiskill.figures.errors import FigureError
from wikiskill.figures.line import render_line
from wikiskill.figures.maps import render_map
from wikiskill.figures.pie import render_pie
from wikiskill.figures.pyramid import render_pyramid
from wikiskill.figures.seats import render_seats

RENDERERS: Final[dict[str, Callable[[Path], str]]] = {
    "seats": render_seats,
    "bars": render_bars,
    "line": render_line,
    "pie": render_pie,
    "pyramid": render_pyramid,
}

LABELS: Final[dict[str, str]] = {
    "seats": "議席図",
    "bars": "棒グラフ",
    "line": "折れ線グラフ",
    "pie": "円グラフ",
    "pyramid": "人口ピラミッド",
}

KINDS: Final = ("map", *RENDERERS)


def render_figure(kind: str, data_path: Path, *, shape: str | None = None) -> str:
    """図の種類に合わせて SVG を作る。

    Parameters
    ----------
    kind : str
        図の種類（``map``・``seats``・``bars``・``line``・``pie``・``pyramid``）。
    data_path : Path
        図のデータ（TOML）の道。
    shape : str | None
        地図の形。地図以外では使えない。

    Returns
    -------
    str
        SVG の文字列。

    Raises
    ------
    FigureError
        種類が知らないもの、またはデータが正しくないとき。
    """
    if kind == "map":
        return render_map(data_path, shape=shape)
    renderer = RENDERERS.get(kind)
    if renderer is None:
        raise FigureError(f"知らない図の種類: {kind}")
    if shape is not None:
        raise FigureError(f"{LABELS[kind]}に形（shape）は使えない")
    return renderer(data_path)
