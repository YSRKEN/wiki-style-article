"""図を描けないときの誤り。"""

from __future__ import annotations


class FigureError(Exception):
    """図のデータや形が正しくないので描けない。"""
