"""本文（見出し・段落・箇条書き）を導入部と節の木に組み立てる。

本文の書き方は次のとおり。

- ``## ``・``### ``・``#### `` で始まる行が見出し（h2〜h4）。``# `` は使えない
- 見出しの末尾の ``[!噂]`` は、その節と子の節を噂として扱う印。見出しの文字からは取り除く
- 空行で段落を区切る。段落の中の改行は空白なしでつなぐ
- 行頭の ``- `` で始まる行の連なりが箇条書き（入れ子なし）。字下げした行は前の項目の続き
- 行に単独で置いた ``![キャプション](画像の道)`` は画像。道は原稿からの相対だけ
- 最初の見出しより前の段落・箇条書きは導入部
"""

from __future__ import annotations

import re
from bisect import bisect_right
from collections.abc import Sequence

from wikiskill.errors import MarkupError
from wikiskill.inline import parse_inline
from wikiskill.model import Block, BulletList, Figure, Inline, Paragraph, Section

_HEADING = re.compile(r"(#+)(?:[ \t]+(.*))?")
_BULLET = re.compile(r"- (.*)")
_NESTED_BULLET = re.compile(r"[ \t]+- ")
_IMAGE = re.compile(r"!\[(?P<caption>[^\]]*)\]\((?P<source>[^)]*)\)")
_IMAGE_START = "!["
_URL = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
_ABSOLUTE = re.compile(r"^(?:[/\\]|[A-Za-z]:)")

_INDENT = " 	"
"""行頭・行末から取り除く空白。全角空白は取り除かず、字下げの誤りとして検査（FULLWIDTH-SPACE）に回す。"""

_RUMOR_MARK = "[!噂]"
"""見出しの末尾に付けて、節ごと噂にする印。"""

_MIN_HEADING_LEVEL = 2
_MAX_HEADING_LEVEL = 4


def parse_body(
    lines: Sequence[str],
    first_line: int,
) -> tuple[tuple[Block, ...], tuple[Section, ...]]:
    """本文の行を、導入部と節の木に組み立てる。

    Parameters
    ----------
    lines : Sequence[str]
        本文の行（改行コードは含めない）。
    first_line : int
        ``lines`` の先頭が原稿ファイルの何行目か（エラーの行番号に使う）。

    Returns
    -------
    tuple[tuple[Block, ...], tuple[Section, ...]]
        導入部のまとまりの並びと、``## `` の節（一段目）の並び。

    Raises
    ------
    MarkupError
        使えない見出し、飛んだ見出しの階層、入れ子の箇条書き、壊れた文中の記法、
        見出しの途中の ``[!噂]`` があるとき。
    """
    return _BodyBuilder().build(lines, first_line)


class _Lines:
    """一つの段落、または箇条書きの一項目。行ごとの文字と行番号を持つ。"""

    def __init__(self, text: str, number: int) -> None:
        self._texts = [text]
        self._numbers = [number]

    @property
    def first_line(self) -> int:
        """先頭の行の原稿ファイル全体での行番号。"""
        return self._numbers[0]

    def add(self, text: str, number: int) -> None:
        """続きの行を足す。"""
        self._texts.append(text)
        self._numbers.append(number)

    def to_inline(self) -> tuple[Inline, ...]:
        """行を空白なしでつないで、文中の記法を部品に分ける。"""
        starts: list[int] = []
        total = 0
        for text in self._texts:
            starts.append(total)
            total += len(text)

        def line_of(offset: int) -> int:
            return self._numbers[bisect_right(starts, offset) - 1]

        return parse_inline("".join(self._texts), line_of)


class _SectionBuilder:
    """組み立て中の節。"""

    def __init__(self, level: int, title: str, line: int, *, rumor: bool) -> None:
        self.level = level
        self.title = title
        self.line = line
        self.rumor = rumor
        self.blocks: list[Block] = []
        self.children: list[_SectionBuilder] = []

    def build(self) -> Section:
        """子の節も含めて、変更できない節にする。"""
        return Section(
            self.level,
            self.title,
            tuple(self.blocks),
            tuple(child.build() for child in self.children),
            line=self.line,
            rumor=self.rumor,
        )


class _BodyBuilder:
    """本文を一行ずつ読み、導入部と節の木を組み立てる。"""

    def __init__(self) -> None:
        self._lead: list[Block] = []
        self._roots: list[_SectionBuilder] = []
        self._stack: list[_SectionBuilder] = []
        self._paragraph: _Lines | None = None
        self._bullets: list[_Lines] = []

    def build(
        self,
        lines: Sequence[str],
        first_line: int,
    ) -> tuple[tuple[Block, ...], tuple[Section, ...]]:
        """全行を読んで結果を返す。"""
        for number, raw in enumerate(lines, start=first_line):
            self._read_line(raw.rstrip(_INDENT), number)
        self._flush()
        return tuple(self._lead), tuple(root.build() for root in self._roots)

    def _read_line(self, line: str, number: int) -> None:
        if not line.strip():
            self._flush()
            return

        heading = _HEADING.fullmatch(line) if line.startswith("#") else None
        if heading is not None:
            self._start_section(len(heading.group(1)), (heading.group(2) or "").strip(), number)
            return

        if line.startswith(_IMAGE_START):
            image = _IMAGE.fullmatch(line)
            if image is None:
                raise MarkupError(
                    "画像は行に単独で置く（![キャプション](画像の道) の形で書く）", number
                )
            self._flush()
            self._container().append(self._figure(image, number))
            return

        if _IMAGE_START in line:
            raise MarkupError(
                "画像は行に単独で置く（![キャプション](画像の道) の形で書く）", number
            )

        if _NESTED_BULLET.match(line):
            raise MarkupError("箇条書きの入れ子は使えない（- は行頭から書く）", number)

        bullet = _BULLET.fullmatch(line)
        if bullet is not None:
            self._flush_paragraph()
            self._bullets.append(_Lines(bullet.group(1).strip(_INDENT), number))
        elif self._bullets:
            if line[0] not in " \t":
                raise MarkupError(
                    "箇条書きの直後に空行なしで段落は続けられない（空行を入れる）", number
                )
            self._bullets[-1].add(line.strip(_INDENT), number)
        elif self._paragraph is None:
            self._paragraph = _Lines(line.strip(_INDENT), number)
        else:
            self._paragraph.add(line.strip(_INDENT), number)

    def _figure(self, image: re.Match[str], number: int) -> Figure:
        """画像の行を Figure にする。"""
        caption = image.group("caption").strip(_INDENT)
        source = image.group("source").strip(_INDENT)
        if not source:
            raise MarkupError("画像の道が空（![キャプション](画像の道) の形で書く）", number)
        if _URL.match(source) or _ABSOLUTE.match(source):
            raise MarkupError("画像は原稿からの相対の道で指す（URL や絶対の道は使えない）", number)
        return Figure(caption=caption, source=source, line=number)

    def _start_section(self, level: int, title: str, number: int) -> None:
        if not _MIN_HEADING_LEVEL <= level <= _MAX_HEADING_LEVEL:
            raise MarkupError(
                f"見出しに使えるのは ## から #### まで（{'#' * level} は使えない）",
                number,
            )
        rumor = title.endswith(_RUMOR_MARK)
        if rumor:
            title = title.removesuffix(_RUMOR_MARK).rstrip(_INDENT)
        if not title:
            raise MarkupError("見出しの文字が空", number)
        if "[!噂" in title:
            raise MarkupError(
                "見出しの [!噂] は末尾にだけ付けられる（## 騒動 [!噂] の形で書く）", number
            )

        self._flush()
        while self._stack and self._stack[-1].level >= level:
            self._stack.pop()
        expected = self._stack[-1].level + 1 if self._stack else _MIN_HEADING_LEVEL
        if level != expected:
            raise MarkupError(
                f"見出しの階層が飛んでいる（{'#' * level} の前に {'#' * expected} の見出しが要る）",
                number,
            )

        section = _SectionBuilder(level, title, number, rumor=rumor)
        (self._stack[-1].children if self._stack else self._roots).append(section)
        self._stack.append(section)

    def _flush(self) -> None:
        """書きかけの段落・箇条書きを、いまの節（なければ導入部）に確定する。"""
        self._flush_paragraph()
        self._flush_bullets()

    def _container(self) -> list[Block]:
        return self._stack[-1].blocks if self._stack else self._lead

    def _flush_paragraph(self) -> None:
        if self._paragraph is not None:
            self._container().append(
                Paragraph(self._paragraph.to_inline(), line=self._paragraph.first_line)
            )
            self._paragraph = None

    def _flush_bullets(self) -> None:
        if self._bullets:
            items = tuple(item.to_inline() for item in self._bullets)
            item_lines = tuple(item.first_line for item in self._bullets)
            self._container().append(BulletList(items, line=item_lines[0], item_lines=item_lines))
            self._bullets = []
