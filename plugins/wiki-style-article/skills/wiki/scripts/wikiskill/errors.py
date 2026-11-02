"""原稿の読み取りで起きる例外。

どの例外も、原稿ファイルの何行目が原因かを ``line`` に持つ。
行番号は 1 始まりで、冒頭の ``+++`` の行が 1 行目。
"""

from __future__ import annotations


class SourceError(Exception):
    """原稿を読み取れなかったときの基底の例外。

    Parameters
    ----------
    message : str
        原因の説明。行番号は含めない。
    line : int
        原因の行（原稿ファイル全体での 1 始まりの行番号）。

    Attributes
    ----------
    message : str
        原因の説明。行番号は含めない。
    line : int
        原因の行。
    """

    def __init__(self, message: str, line: int) -> None:
        super().__init__(f"{line} 行目: {message}")
        self.message = message
        self.line = line


class FrontMatterError(SourceError):
    """設定欄を囲む ``+++`` の行がない、閉じていないなど、設定欄の枠が壊れている。"""


class SettingsError(SourceError):
    """設定欄の TOML が読めない、必須の項目がない、型や値が合わない。"""


class MarkupError(SourceError):
    """本文や文中の記法が壊れている（閉じていない ``[[``、使えない見出しなど）。"""
