"""噂を含む原稿を、通常の記事と噂込みの記事の二つの版に分ける。

噂は、文の中の噂の範囲 ``[!噂|…]`` と、見出しの末尾に ``[!噂]`` を付けた節（子の節を含む）で書く。

- 通常の版（:func:`normal_view`）: 噂の範囲・噂だけのまとまり・噂の節を取り除く
- 噂込みの版（:func:`rumor_view`）: 噂の範囲を中身にほどき、噂の節の印を外す

どちらの版も噂の部品を持たない、ふつうの記事になる。今の検査（``check_article``）と書き出し
（``write_html``・``write_wikitext``）にそのまま渡せる。関数はすべて純粋で、渡した記事を変えない。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import replace

from wikiskill.model import (
    Article,
    Block,
    Bold,
    BulletList,
    Figure,
    FixRange,
    Inline,
    NoteMark,
    NoticeKind,
    Paragraph,
    RefMark,
    RumorRange,
    Section,
    Text,
)

__all__ = ["has_rumor", "normal_view", "rumor_view"]

_POV: NoticeKind = "観点"
"""噂込みの版に貼り、通常の版から外す警告の枠。"""

_InlineMap = Callable[[tuple[Inline, ...]], tuple[Inline, ...]]


def has_rumor(article: Article) -> bool:
    """原稿に噂の範囲か噂の節が一つでもあるか。

    Parameters
    ----------
    article : Article
        読み取った記事。導入部・節・注釈の本文の噂の範囲と、節の ``rumor`` を見る。

    Returns
    -------
    bool
        噂が一つでもあれば真。
    """
    if any(section.rumor for section in _iter_sections(article.sections)):
        return True
    groups = [*_body_groups(article), *(note.text for note in article.settings.notes)]
    return any(isinstance(part, RumorRange) for parts in groups for part in _flatten(parts))


def normal_view(article: Article) -> Article:
    """通常の記事の版を作る。

    噂の範囲を取り除き（範囲の前後の文字は残す）、噂だけのまとまり（段落・箇条の項目）と噂の節
    （子の節を含む）を取り除く。取り除いた結果どこからも使われなくなった出典・注釈は設定欄から外す
    （元の原稿でも使われていなかったものは、検査で知らせるために残す）。``notices`` から ``観点``
    を外す。

    Parameters
    ----------
    article : Article
        読み取った記事。

    Returns
    -------
    Article
        噂の部品を持たない記事。
    """
    settings = article.settings
    stripped = Article(
        settings=replace(
            settings,
            notes=tuple(replace(note, text=_strip(note.text)) for note in settings.notes),
            notices=tuple(kind for kind in settings.notices if kind != _POV),
        ),
        lead=_blocks(article.lead, _strip),
        sections=_normal_sections(article.sections),
        base_dir=article.base_dir,
    )
    used_refs, used_notes = _used_footnotes(article)
    kept_refs, kept_notes = _used_footnotes(stripped)
    dropped_refs = used_refs - kept_refs
    dropped_notes = used_notes - kept_notes
    return replace(
        stripped,
        settings=replace(
            stripped.settings,
            references=tuple(r for r in stripped.settings.references if r.key not in dropped_refs),
            notes=tuple(n for n in stripped.settings.notes if n.key not in dropped_notes),
        ),
    )


def rumor_view(article: Article) -> Article:
    """噂込みの記事の版を作る。

    噂の範囲をその中身にほどき、噂の節の印を外す。噂が一つでもあれば ``notices`` に ``観点`` を
    足す（すでにあれば重ねない）。出典と注釈はそのまま残す。

    Parameters
    ----------
    article : Article
        読み取った記事。

    Returns
    -------
    Article
        噂の部品を持たない記事。噂が無ければ元と等しい記事。
    """
    settings = article.settings
    notices = settings.notices
    if has_rumor(article) and _POV not in notices:
        notices = (*notices, _POV)
    return Article(
        settings=replace(
            settings,
            notes=tuple(replace(note, text=_unwrap(note.text)) for note in settings.notes),
            notices=notices,
        ),
        lead=_blocks(article.lead, _unwrap),
        sections=_rumor_sections(article.sections),
        base_dir=article.base_dir,
    )


# --- 文中の部品 ---------------------------------------------------------------------


def _strip(parts: tuple[Inline, ...]) -> tuple[Inline, ...]:
    """噂の範囲を取り除く。"""
    return _merge_texts(part for part in parts if not isinstance(part, RumorRange))


def _unwrap(parts: tuple[Inline, ...]) -> tuple[Inline, ...]:
    """噂の範囲を、その中身の部品に置き換える。"""

    def expand() -> Iterator[Inline]:
        for part in parts:
            if isinstance(part, RumorRange):
                yield from part.children
            else:
                yield part

    return _merge_texts(expand())


def _merge_texts(parts: Iterable[Inline]) -> tuple[Inline, ...]:
    """隣り合う文字を一つにまとめる（読み取りの結果と同じ形にする）。"""
    out: list[Inline] = []
    for part in parts:
        if isinstance(part, Text) and out and isinstance(out[-1], Text):
            out[-1] = Text(out[-1].text + part.text)
        else:
            out.append(part)
    return tuple(out)


def _is_blank(parts: tuple[Inline, ...]) -> bool:
    """部品が無いか、空白だけの文字しか無いか。"""
    return all(isinstance(part, Text) and not part.text.strip() for part in parts)


# --- まとまりと節 -------------------------------------------------------------------


def _blocks(blocks: tuple[Block, ...], change: _InlineMap) -> tuple[Block, ...]:
    """まとまりの文中の部品を ``change`` で変える。中身が空になった段落・箇条の項目は除く。"""
    out: list[Block] = []
    for block in blocks:
        if isinstance(block, Paragraph):
            content = change(block.content)
            if not _is_blank(content):
                out.append(replace(block, content=content))
            continue
        if isinstance(block, Figure):
            out.append(block)
            continue
        lines = block.item_lines or (block.line,) * len(block.items)
        kept = [
            (content, line)
            for content, line in (
                (change(item), line) for item, line in zip(block.items, lines, strict=True)
            )
            if not _is_blank(content)
        ]
        if kept:
            out.append(
                BulletList(
                    tuple(content for content, _ in kept),
                    line=kept[0][1],
                    item_lines=tuple(line for _, line in kept),
                )
            )
    return tuple(out)


def _normal_sections(sections: tuple[Section, ...]) -> tuple[Section, ...]:
    return tuple(
        replace(
            section,
            blocks=_blocks(section.blocks, _strip),
            children=_normal_sections(section.children),
        )
        for section in sections
        if not section.rumor
    )


def _rumor_sections(sections: tuple[Section, ...]) -> tuple[Section, ...]:
    return tuple(
        replace(
            section,
            blocks=_blocks(section.blocks, _unwrap),
            children=_rumor_sections(section.children),
            rumor=False,
        )
        for section in sections
    )


# --- 使われている出典と注釈 -----------------------------------------------------------


def _used_footnotes(article: Article) -> tuple[set[str], set[str]]:
    """本文から使われている出典と注釈のキー。使われている注釈の本文の中の出典も数える。"""
    note_texts = {note.key: note.text for note in article.settings.notes}
    refs: set[str] = set()
    notes: set[str] = set()

    def visit(parts: tuple[Inline, ...]) -> None:
        for part in _flatten(parts):
            if isinstance(part, RefMark):
                refs.add(part.key)
            elif isinstance(part, NoteMark) and part.key not in notes:
                notes.add(part.key)
                visit(note_texts.get(part.key, ()))

    for parts in _body_groups(article):
        visit(parts)
    return refs, notes


# --- 木のたどり方 -------------------------------------------------------------------
# checks.walk と同じたどり方だが、checks から使えるように checks には頼らない。


def _iter_sections(sections: tuple[Section, ...]) -> Iterator[Section]:
    for section in sections:
        yield section
        yield from _iter_sections(section.children)


def _block_groups(blocks: tuple[Block, ...]) -> Iterator[tuple[Inline, ...]]:
    for block in blocks:
        if isinstance(block, Paragraph):
            yield block.content
        elif isinstance(block, BulletList):
            yield from block.items


def _body_groups(article: Article) -> Iterator[tuple[Inline, ...]]:
    """導入部と節の、文中の部品の並び（注釈の本文は含めない）。"""
    yield from _block_groups(article.lead)
    for section in _iter_sections(article.sections):
        yield from _block_groups(section.blocks)


def _flatten(parts: tuple[Inline, ...]) -> Iterator[Inline]:
    """太字・範囲の印・噂の範囲の中まで、部品を一列にたどる。"""
    for part in parts:
        yield part
        if isinstance(part, Bold | FixRange | RumorRange):
            yield from _flatten(part.children)
