"""地図や議席図の SVG を作る。"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from wikiskill.figures.errors import FigureError
from wikiskill.figures.maps import render_map
from wikiskill.figures.seats import render_seats

KINDS: Final = ("map", "seats")


def render_figure(kind: str, data_path: Path, *, shape: str | None = None) -> str:
    """図の種類に合わせて SVG を作る。

    Parameters
    ----------
    kind : str
        図の種類（map か seats）。
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
    if kind == "seats":
        if shape is not None:
            raise FigureError("議席図に形（shape）は使えない")
        return render_seats(data_path)
    raise FigureError(f"知らない図の種類: {kind}")
