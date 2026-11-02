"""記事の木をたどって、検査に使う部品を取り出す。"""

from __future__ import annotations

from collections.abc import Iterator

from wikiskill.model import (
    Article,
    Block,
    Bold,
    FixRange,
    Inline,
    InternalLink,
    Paragraph,
    RumorRange,
    Section,
)


def iter_sections(article: Article) -> Iterator[Section]:
    """節を、親・子の順（原稿に現れる順）にすべてたどる。"""

    def walk(sections: tuple[Section, ...]) -> Iterator[Section]:
        for section in sections:
            yield section
            yield from walk(section.children)

    yield from walk(article.sections)


def _inline_groups(blocks: tuple[Block, ...]) -> Iterator[tuple[tuple[Inline, ...], int]]:
    for block in blocks:
        if isinstance(block, Paragraph):
            yield block.content, block.line
        else:
            lines = block.item_lines or (block.line,) * len(block.items)
            yield from zip(block.items, lines, strict=True)


def iter_inline_groups(article: Article) -> Iterator[tuple[tuple[Inline, ...], int]]:
    """文中の部品の並びを、その先頭の行番号とともに、原稿に現れる順にたどる。

    導入部・節（見出しの直後のまとまり）・注釈の本文を含む。
    Infobox の値と見出しは文字列なので含まない。
    """
    yield from _inline_groups(article.lead)
    for section in iter_sections(article):
        yield from _inline_groups(section.blocks)
    for note in article.settings.notes:
        yield note.text, note.line


def flatten(parts: tuple[Inline, ...]) -> Iterator[Inline]:
    """太字・範囲の印・噂の範囲の中身を展開して、文中の部品を一列にたどる（それら自身も返す）。"""
    for part in parts:
        yield part
        if isinstance(part, Bold | FixRange | RumorRange):
            yield from flatten(part.children)


def iter_links(article: Article) -> Iterator[tuple[InternalLink, int]]:
    """内部リンクを、その行番号とともにたどる。"""
    for parts, line in iter_inline_groups(article):
        for part in flatten(parts):
            if isinstance(part, InternalLink):
                yield part, line
