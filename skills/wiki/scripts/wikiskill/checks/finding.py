"""検査の結果を表すデータ型。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Level(StrEnum):
    """検査の結果の重さ。

    ``ERROR`` は直すまで原稿を渡さない誤り、``WARNING`` は AI が読み直して判断する注意。
    """

    ERROR = "error"
    WARNING = "warning"

    @property
    def label(self) -> str:
        """利用者に見せる呼び名（エラー／警告）。"""
        return "エラー" if self is Level.ERROR else "警告"


@dataclass(frozen=True)
class Finding:
    """検査で見つけた一件。

    Attributes
    ----------
    level : Level
        エラーか警告か。
    rule : str
        規則の ID（``REF-UNDEFINED`` など。一覧は ``docs/checks.md``）。
    message : str
        何がどう誤っているかの文面。直し方を含む。
    line : int
        原稿ファイル全体での行番号（1 始まり）。段落の中の指摘は段落の先頭の行を指す。
    """

    level: Level
    rule: str
    message: str
    line: int

    def __str__(self) -> str:
        """``12 行目 [エラー] REF-UNDEFINED: …`` の形の一行。"""
        return f"{self.line} 行目 [{self.level.label}] {self.rule}: {self.message}"
