"""座標の書き表し方。

設定欄の ``[coord]`` を、本家の ``{{Coord}}`` に渡す十進の度、HTML に出す度分秒、
GeoHack へのリンクに組み替える。ウィキテキストと HTML の両方から使う。
"""

from __future__ import annotations

from urllib.parse import quote

from wikiskill.model import Coordinate

__all__ = ["decimal", "dms", "geohack_url", "text"]

_LATITUDE = ("北緯", "南緯")
_NORTH = "N"
_SOUTH = "S"
_LONGITUDE = ("東経", "西経")
_EAST = "E"
_WEST = "W"
_GEOHACK = "https://geohack.toolforge.org/geohack.php"


def decimal(value: float) -> str:
    """十進の度を、余計な 0 を付けない文字列にする（``35.681236``）。"""
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def dms(value: float, positive: str, negative: str) -> str:
    """十進の度を、度分秒の文字列にする（``北緯35度40分52秒``）。

    本家の ``{{Coord}}`` に合わせて、秒は整数で二桁に詰める（``東経139度46分02秒``）。
    """
    label = positive if value >= 0 else negative
    total = abs(value)
    degrees = int(total)
    rest = (total - degrees) * 60.0
    minutes = int(rest)
    seconds = round((rest - minutes) * 60.0)
    if seconds >= 60:
        seconds -= 60
        minutes += 1
    if minutes >= 60:
        minutes -= 60
        degrees += 1
    return f"{label}{degrees}度{minutes}分{seconds:02d}秒"


def text(coord: Coordinate) -> str:
    """座標を ``北緯35度40分52秒 東経139度46分02秒`` の形にする。"""
    return f"{dms(coord.lat, *_LATITUDE)} {dms(coord.lon, *_LONGITUDE)}"


def _oriented(value: float, positive: str, negative: str) -> tuple[str, str]:
    """十進の度を、絶対値と向きの記号に分ける（``-33.8688`` → ``("33.8688", "S")``）。"""
    rounded = round(value, 6)
    return decimal(abs(rounded)), (positive if rounded >= 0 else negative)


def geohack_url(coord: Coordinate, page: str | None = None) -> str:
    """座標の GeoHack へのリンク。``page`` は記事名（本家の ``pagename``）。

    本家と同じく、十進の度には向きの記号（``N``/``S``/``E``/``W``）を添える。
    """
    latitude = _oriented(coord.lat, _NORTH, _SOUTH)
    longitude = _oriented(coord.lon, _EAST, _WEST)
    params = "_".join([*latitude, *longitude])
    if coord.type:
        params += f"_type:{coord.type}"
    url = f"{_GEOHACK}?language=ja&params={params}"
    if page:
        url += f"&pagename={quote(page, safe='')}"
    return url
