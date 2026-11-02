"""文中の記法（太字・脚注の印・注釈の印・内部リンク・点と範囲の印・噂の範囲）を部品に分ける。

使える記法は次の七つだけで、それ以外の文字はそのまま本文になる。

- ``'''…'''``: 太字
- ``[^キー]``: 出典への脚注の印
- ``[^n:キー]``: 注釈への印
- ``[[記事名]]``・``[[記事名|表示]]``: 内部リンク
- ``[!要出典]``・``[!信頼性要検証]``: 点の印（太字の中にも置ける）
- ``[!要出典範囲|範囲の文]``・``[!独自研究範囲|範囲の文]``: 範囲の印。範囲の文には文字・
  内部リンク・脚注の印・注釈の印を書ける。範囲の終わりは ``[`` と ``]`` の入れ子を数えて決める
- ``[!噂|範囲の文]``: 噂の範囲。範囲の文には文字・内部リンク・太字・脚注の印・注釈の印・
  点の印・範囲の印を書ける（噂の範囲の入れ子は書けない）。終わりの決め方は範囲の印と同じ

印が指すキーが設定欄にあるかはここでは見ない。記法として壊れているものだけをエラーにする。
"""

from __future__ import annotations

import re
from collections.abc import Callable

from wikiskill.errors import MarkupError
from wikiskill.model import (
    FIX_MARK_KINDS,
    FIX_RANGE_KINDS,
    Bold,
    FixMark,
    FixRange,
    FixRangeKind,
    Inline,
    InternalLink,
    NoteMark,
    RefMark,
    RumorRange,
    Text,
)

LineOf = Callable[[int], int]
"""文字列の中の位置（0 始まり）から、原稿全体での行番号を返す関数。"""

KEY_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
"""出典・注釈のキーとして使える文字列。"""

_NOTE_PREFIX = "n:"
_BOLD = "'''"
_FIX = "[!"
_RUMOR = "噂"

_BoldChild = Text | RefMark | NoteMark | InternalLink | FixMark
_RangeChild = Text | RefMark | NoteMark | InternalLink
_RumorChild = Text | RefMark | NoteMark | InternalLink | FixMark | FixRange | Bold


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
        閉じていない ``[[``・``[^``・``'''``・``[!``、空の記法、使えないキーがあるとき。
        知らない印の名前、``|`` の付け方の誤った印、空の範囲の文、範囲の文の中の太字と印、
        太字の中の範囲の印も。噂の範囲の入れ子、太字や範囲の印の中の噂の範囲、空の噂の範囲も。
    """
    line_of: LineOf = line if callable(line) else (lambda _offset: line)
    return _Parser(text, line_of).parse()


class _Parser:
    """文字列を左から読み、記法ごとに部品へ分ける。

    ``in_range`` が真なら範囲の印の範囲の文を読む。範囲の文の中では太字と印を開かない。
    ``in_rumor`` が真なら噂の範囲の文を読む。噂の範囲の文の中では噂の範囲を開かない。
    """

    def __init__(
        self, text: str, line_of: LineOf, *, in_range: bool = False, in_rumor: bool = False
    ) -> None:
        self._text = text
        self._line_of = line_of
        self._in_range = in_range
        self._in_rumor = in_rumor
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
                if self._in_range:
                    raise self._error("範囲の印の範囲の文に太字は書けない", self._pos)
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
            elif text.startswith(_FIX, self._pos):
                flush()
                if self._in_range:
                    raise self._error(
                        "印は入れ子にできない（範囲の文の中に印は書けない）", self._pos
                    )
                parts.append(self._parse_fix(in_bold=bold_start is not None))
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
        # 太字の中では太字と範囲の印を開かないので、子はそれ以外に限られる。
        return Bold(tuple(child for child in children if isinstance(child, _BoldChild)))

    def _parse_fix(self, *, in_bold: bool) -> FixMark | FixRange | RumorRange:
        """点の印 ``[!名前]``・範囲の印 ``[!名前|範囲の文]``・噂の範囲 ``[!噂|…]`` を読む。"""
        text = self._text
        start = self._pos
        name_end = start + len(_FIX)
        while name_end < len(text) and text[name_end] not in "]|":
            name_end += 1
        if name_end == len(text):
            raise self._error("印の [! が ] で閉じていない", start)
        name = text[start + len(_FIX) : name_end]
        has_range = text[name_end] == "|"

        for kind in FIX_MARK_KINDS:
            if name == kind:
                if has_range:
                    raise self._error(
                        f"点の印 [!{kind}] に | は付けない"
                        "（範囲を示すなら要出典範囲・独自研究範囲の印を使う）",
                        start,
                    )
                self._pos = name_end + 1
                return FixMark(kind)
        for kind in FIX_RANGE_KINDS:
            if name == kind:
                if not has_range:
                    raise self._error(
                        f"範囲の印に | が無い（[!{kind}|範囲の文] の形で書く）", start
                    )
                if in_bold:
                    raise self._error("太字の中に範囲の印は書けない", start)
                return self._parse_range(kind, start, name_end + 1)
        if name == _RUMOR:
            if not has_range:
                raise self._error(
                    "噂の範囲に | が無い（[!噂|範囲の文] の形で書く。"
                    "節ごと噂にするなら見出しの末尾に [!噂] を付ける）",
                    start,
                )
            if in_bold:
                raise self._error(
                    "太字の中に噂の範囲は書けない（太字を噂の範囲の中に入れる）", start
                )
            if self._in_rumor:
                raise self._error("噂の範囲は入れ子にできない", start)
            return self._parse_rumor(start, name_end + 1)
        names = "、".join((*FIX_MARK_KINDS, *FIX_RANGE_KINDS, _RUMOR))
        raise self._error(f"未知の印 [!{name}] は使えない（使える印: {names}）", start)

    def _parse_range(self, kind: FixRangeKind, start: int, body_start: int) -> FixRange:
        """範囲の文を、``[`` と ``]`` の入れ子を数えて閉じる ``]`` まで読む。"""
        end = self._range_end(start, body_start, "範囲の印")
        body = self._text[body_start:end]
        if not body.strip():
            raise self._error(f"範囲の印 [!{kind}|…] の範囲の文が空", start)
        line_of = self._line_of
        children = _Parser(body, lambda offset: line_of(body_start + offset), in_range=True).parse()
        self._pos = end + 1
        # 範囲の文の中では太字と印を開かないので、子はそれ以外に限られる。
        return FixRange(kind, tuple(child for child in children if isinstance(child, _RangeChild)))

    def _parse_rumor(self, start: int, body_start: int) -> RumorRange:
        """噂の範囲の文を、範囲の印と同じく入れ子を数えて閉じる ``]`` まで読む。"""
        end = self._range_end(start, body_start, "噂の範囲")
        body = self._text[body_start:end]
        if not body.strip():
            raise self._error("噂の範囲 [!噂|…] の範囲の文が空", start)
        line_of = self._line_of
        children = _Parser(body, lambda offset: line_of(body_start + offset), in_rumor=True).parse()
        self._pos = end + 1
        # 噂の範囲の文の中では噂の範囲を開かないので、子はそれ以外に限られる。
        return RumorRange(tuple(child for child in children if isinstance(child, _RumorChild)))

    def _range_end(self, start: int, body_start: int, what: str) -> int:
        """範囲の文を閉じる ``]`` の位置を、``[`` と ``]`` の入れ子を数えて探す。"""
        text = self._text
        depth = 1
        end = body_start
        while end < len(text):
            if text[end] == "[":
                depth += 1
            elif text[end] == "]":
                depth -= 1
                if depth == 0:
                    break
            end += 1
        if depth != 0:
            raise self._error(f"{what}の [! が ] で閉じていない", start)
        return end

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
