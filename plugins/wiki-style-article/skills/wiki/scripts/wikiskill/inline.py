"""文中の記法（太字・脚注の印・注釈の印・内部リンク）を部品に分ける。

使える記法は次の四つだけで、それ以外の文字はそのまま本文になる。

- ``'''…'''``: 太字
- ``[^キー]``: 出典への脚注の印
- ``[^n:キー]``: 注釈への印
- ``[[記事名]]``・``[[記事名|表示]]``: 内部リンク

印が指すキーが設定欄にあるかはここでは見ない。記法として壊れているものだけをエラーにする。
"""

from __future__ import annotations

import re
from collections.abc import Callable

from wikiskill.errors import MarkupError
from wikiskill.model import Bold, Inline, InternalLink, NoteMark, RefMark, Text

LineOf = Callable[[int], int]
"""文字列の中の位置（0 始まり）から、原稿全体での行番号を返す関数。"""

KEY_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
"""出典・注釈のキーとして使える文字列。"""

_NOTE_PREFIX = "n:"
_BOLD = "'''"

_BoldChild = Text | RefMark | NoteMark | InternalLink


def parse_inline(text: str, line: int | LineOf = 1) -> tuple[Inline, ...]:
    """文中の記法を部品の並びに分ける。

    Parameters
    ----------
    text : str
        記法を含む文字列。改行は含めない（段落の中の改行はあらかじめつなぐ）。
    line : int | Callable[[int], int]
        エラーに載せる行番号。整数なら常にその行、関数なら ``text`` の中の位置から行を引く。

    Returns
    -------
    tuple[Inline, ...]
        部品の並び。隣り合う文字は一つの :class:`~wikiskill.model.Text` にまとめる。

    Raises
    ------
    MarkupError
        閉じていない ``[[``・``[^``・``'''``、空の記法、使えないキーがあるとき。
    """
    line_of: LineOf = line if callable(line) else (lambda _offset: line)
    return _Parser(text, line_of).parse()


class _Parser:
    """文字列を左から読み、記法ごとに部品へ分ける。"""

    def __init__(self, text: str, line_of: LineOf) -> None:
        self._text = text
        self._line_of = line_of
        self._pos = 0

    def parse(self) -> tuple[Inline, ...]:
        """全体を読んで部品の並びを返す。"""
        return self._parse_run(bold_start=None)

    def _error(self, message: str, offset: int) -> MarkupError:
        return MarkupError(message, self._line_of(offset))

    def _parse_run(self, bold_start: int | None) -> tuple[Inline, ...]:
        """太字の外（``bold_start`` が None）か中を、閉じる位置まで読む。"""
        text = self._text
        parts: list[Inline] = []
        buffer: list[str] = []

        def flush() -> None:
            if buffer:
                parts.append(Text("".join(buffer)))
                buffer.clear()

        while self._pos < len(text):
            if text.startswith(_BOLD, self._pos):
                flush()
                if bold_start is not None:
                    self._pos += len(_BOLD)
                    return tuple(parts)
                parts.append(self._parse_bold())
            elif text.startswith("[[", self._pos):
                flush()
                parts.append(self._parse_link())
            elif text.startswith("[^", self._pos):
                flush()
                parts.append(self._parse_mark())
            else:
                buffer.append(text[self._pos])
                self._pos += 1
        flush()
        if bold_start is not None:
            raise self._error("太字の ''' が閉じていない", bold_start)
        return tuple(parts)

    def _parse_bold(self) -> Bold:
        start = self._pos
        self._pos += len(_BOLD)
        children = self._parse_run(bold_start=start)
        if not children:
            raise self._error("太字の中身が空", start)
        # 太字の中では太字を開かないので、子は太字以外に限られる。
        return Bold(tuple(child for child in children if isinstance(child, _BoldChild)))

    def _parse_link(self) -> InternalLink:
        start = self._pos
        end = self._text.find("]]", start + 2)
        if end == -1:
            raise self._error("内部リンクの [[ が ]] で閉じていない", start)
        inner = self._text[start + 2 : end]
        if "[[" in inner:
            raise self._error("内部リンクを入れ子にはできない", start)
        self._pos = end + 2

        target, separator, label = inner.partition("|")
        target = target.strip()
        if not target:
            raise self._error("内部リンクの記事名が空", start)
        if not separator:
            return InternalLink(target, None)
        label = label.strip()
        if not label:
            raise self._error("内部リンクの表示が空（表示を付けないなら | ごと省く）", start)
        if "|" in label:
            raise self._error("内部リンクの | は一つまで", start)
        return InternalLink(target, label)

    def _parse_mark(self) -> RefMark | NoteMark:
        start = self._pos
        end = self._text.find("]", start + 2)
        if end == -1:
            raise self._error("脚注の印の [^ が ] で閉じていない", start)
        inner = self._text[start + 2 : end]
        self._pos = end + 1

        is_note = inner.startswith(_NOTE_PREFIX)
        key = inner[len(_NOTE_PREFIX) :] if is_note else inner
        if not key:
            raise self._error("脚注の印のキーが空", start)
        if not KEY_PATTERN.fullmatch(key):
            raise self._error(
                f"キー {key!r} は使えない（英数字・ハイフン・下線だけ）",
                start,
            )
        return NoteMark(key) if is_note else RefMark(key)
