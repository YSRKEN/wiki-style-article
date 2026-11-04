"""図のデータ（TOML）を読む共通の下請け。"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import cast

from wikiskill.figures.errors import FigureError


def read_toml(path: Path) -> dict[str, object]:
    """TOML のファイルを読み、表として返す。

    Parameters
    ----------
    path : Path
        読むファイル。

    Returns
    -------
    dict[str, object]
        読み取った表。

    Raises
    ------
    FigureError
        ファイルを読めない、または TOML として正しくないとき。
    """
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        raise FigureError(f"データを読めない: {path}（{error}）") from error
    try:
        return cast(dict[str, object], tomllib.loads(text))
    except tomllib.TOMLDecodeError as error:
        raise FigureError(f"データの TOML を読めない: {path.name}（{error}）") from error


def reject_unknown(table: dict[str, object], allowed: frozenset[str], where: str) -> None:
    """知らない項目があれば FigureError を投げる。

    Parameters
    ----------
    table : dict[str, object]
        調べる表。
    allowed : frozenset[str]
        使ってよい項目の名前。
    where : str
        誤りの文に出す場所の名前。
    """
    unknown = [key for key in table if key not in allowed]
    if unknown:
        names = "、".join(unknown)
        raise FigureError(f"{where} に知らない項目がある: {names}")


def string(table: dict[str, object], key: str, default: str, where: str) -> str:
    """表から文字列を取り出す。無ければ既定を返す。

    Parameters
    ----------
    table : dict[str, object]
        読む表。
    key : str
        項目の名前。
    default : str
        無いときの値。
    where : str
        誤りの文に出す場所の名前。

    Returns
    -------
    str
        取り出した文字列。
    """
    value = table.get(key, default)
    if not isinstance(value, str):
        raise FigureError(f"{where} の {key} は文字列で書く")
    return value


def boolean(table: dict[str, object], key: str, default: bool, where: str) -> bool:
    """表から真偽を取り出す。無ければ既定を返す。

    Parameters
    ----------
    table : dict[str, object]
        読む表。
    key : str
        項目の名前。
    default : bool
        無いときの値。
    where : str
        誤りの文に出す場所の名前。

    Returns
    -------
    bool
        取り出した真偽。
    """
    value = table.get(key, default)
    if not isinstance(value, bool):
        raise FigureError(f"{where} の {key} は true か false で書く")
    return value
