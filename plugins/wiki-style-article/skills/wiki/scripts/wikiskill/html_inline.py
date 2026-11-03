"""文中の部品（太字・内部リンク・脚注の印・点と範囲の印）を HTML にする。脚注の番号もここで付ける。

脚注の番号は本文に現れる順（導入部、節の順）に、出典と注釈で別々に付ける。注釈の中の出典は、
その注釈を最初に使った場所で数える。同じ出典・注釈を再利用したときは同じ番号を使う。

脚注の印は ``<sup id="cite_ref-N-K"><a href="#cite_note-N">[N]</a></sup>``（注釈は
``cite_ref-note-N-K``・``cite_note-note-N``・``[注 N]``）。``K`` は同じ印の何回目か。
一枚に二つの版を入れるときは、噂込みの版の id の前に接頭辞（``rumor-``）を付ける。

点の印は ``<sup class="fix-mark">[要出典]</sup>``、範囲の印は
``<span class="fix-range">範囲の文</span><sup class="fix-mark">[要出典]</sup>``
（独自研究範囲の印の文字は本家と同じ ``[独自研究?]``）。
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from wikiskill.html_escape import escape, wiki_href
from wikiskill.images import ImageError, data_uri
from wikiskill.model import (
    FIX_RANGE_LABELS,
    Article,
    Block,
    Bold,
    BulletList,
    Figure,
    FixMark,
    FixRange,
    Inline,
    InternalLink,
    NoteMark,
    Original,
    Paragraph,
    RefMark,
    RumorRange,
    Section,
    Text,
)

NOTE_LABEL = "注"
"""注釈の印に付ける文字（``[注 1]``）。"""


class HtmlError(ValueError):
    """HTML へ書き出せない記事を渡したときの基底の例外。"""


class UnknownFootnoteError(HtmlError):
    """本文の印が指す出典・注釈が、設定欄の ``[refs]``・``[notes]`` にない。"""


class NestedFootnoteError(HtmlError):
    """注釈の本文の中に別の注釈への印がある（注釈は入れ子にできない）。"""


# --- 番号づけ ---------------------------------------------------------------------


@dataclass(frozen=True)
class Numbering:
    """脚注の番号。キーから 1 始まりの番号を引く。

    Attributes
    ----------
    refs : dict[str, int]
        使われた出典の番号。番号の昇順（＝本文に現れる順）に並ぶ。
    notes : dict[str, int]
        使われた注釈の番号。
    """

    refs: dict[str, int]
    notes: dict[str, int]


def number_footnotes(article: Article) -> Numbering:
    """本文を先頭から読み、使われた出典・注釈に現れる順の番号を付ける。

    Parameters
    ----------
    article : Article
        読み取った記事。

    Returns
    -------
    Numbering
        出典と注釈の番号。使われないものは入らない。

    Raises
    ------
    UnknownFootnoteError
        印が指す出典・注釈が設定欄にないとき。
    NestedFootnoteError
        注釈の本文に別の注釈への印があるとき。
    """
    settings = article.settings
    ref_keys = {r.key for r in settings.references}
    notes = {n.key: n for n in settings.notes}
    refs: dict[str, int] = {}
    note_numbers: dict[str, int] = {}

    def visit(items: Iterable[Inline], in_note: str | None) -> None:
        for item in items:
            if isinstance(item, Bold | FixRange | RumorRange):
                visit(item.children, in_note)
            elif isinstance(item, RefMark):
                if item.key not in ref_keys:
                    raise UnknownFootnoteError(f"出典 {item.key!r} が設定欄の [refs] にない")
                refs.setdefault(item.key, len(refs) + 1)
            elif isinstance(item, NoteMark):
                if in_note is not None:
                    raise NestedFootnoteError(
                        f"注釈 {in_note!r} の本文に別の注釈への印 [^n:{item.key}] がある"
                        "（注釈は入れ子にできない）"
                    )
                note = notes.get(item.key)
                if note is None:
                    raise UnknownFootnoteError(f"注釈 {item.key!r} が設定欄の [notes] にない")
                if item.key not in note_numbers:
                    note_numbers[item.key] = len(note_numbers) + 1
                    visit(note.text, item.key)

    def visit_blocks(blocks: Sequence[Block]) -> None:
        for block in blocks:
            if isinstance(block, Paragraph):
                visit(block.content, None)
            elif isinstance(block, BulletList):
                for item in block.items:
                    visit(item, None)

    def visit_section(section: Section) -> None:
        visit_blocks(section.blocks)
        for child in section.children:
            visit_section(child)

    visit_blocks(article.lead)
    for section in article.sections:
        visit_section(section)
    return Numbering(refs, note_numbers)


# --- 書き出し ---------------------------------------------------------------------


def ref_item_id(number: int, prefix: str = "") -> str:
    """出典の脚注欄の項目の id。``prefix`` は版ごとの接頭辞（通常は空）。"""
    return f"{prefix}cite_note-{number}"


def note_item_id(number: int, prefix: str = "") -> str:
    """注釈の脚注欄の項目の id。"""
    return f"{prefix}cite_note-note-{number}"


def ref_mark_id(number: int, nth: int, prefix: str = "") -> str:
    """出典の印の id（``nth`` は同じ出典の何回目の印か。1 始まり）。"""
    return f"{prefix}cite_ref-{number}-{nth}"


def note_mark_id(number: int, nth: int, prefix: str = "") -> str:
    """注釈の印の id。"""
    return f"{prefix}cite_ref-note-{number}-{nth}"


def internal_link(link: InternalLink) -> str:
    """内部リンクを、本家の記事へのリンクにする。"""
    href, title = wiki_href(link.target), escape(link.target)
    return f'<a href="{href}" title="{title}">{escape(link.display)}</a>'


def fix_mark(label: str) -> str:
    """点の印、または範囲の印の後ろに付ける上付きの文字。"""
    return f'<sup class="fix-mark">[{escape(label)}]</sup>'


class InlineWriter:
    """文中の部品を HTML にする。脚注の印は、書いた回数を数えながら番号つきのリンクにする。

    Parameters
    ----------
    numbering : Numbering | None
        脚注の番号。None なら印を脚注にせず、書かれたままの文字（``[^キー]``）で出す
        （Infobox の値のように、脚注を持たない場所用）。
    prefix : str
        脚注の印とリンク先の id に付ける接頭辞。一枚に二つの版を入れるときの噂込みの版で使う。
    """

    def __init__(self, numbering: Numbering | None = None, *, prefix: str = "") -> None:
        self._numbering = numbering
        self._prefix = prefix
        self.ref_uses: Counter[str] = Counter()
        self.note_uses: Counter[str] = Counter()

    def inline(self, items: Sequence[Inline]) -> str:
        """文中の部品の並びを HTML にする。"""
        return "".join(self._one(item) for item in items)

    def _one(self, item: Inline) -> str:
        if isinstance(item, Text):
            return escape(item.text)
        if isinstance(item, Bold):
            return f"<b>{self.inline(item.children)}</b>"
        if isinstance(item, InternalLink):
            return internal_link(item)
        if isinstance(item, FixMark):
            return fix_mark(item.kind)
        if isinstance(item, FixRange):
            inner = self.inline(item.children)
            return f'<span class="fix-range">{inner}</span>{fix_mark(FIX_RANGE_LABELS[item.kind])}'
        if isinstance(item, Original):
            return f'<span lang="{escape(item.lang)}">{escape(item.text)}</span>'
        if isinstance(item, RumorRange):
            # 書き出す前に二つの版へ分けるので、ふつうは来ない。来たら中身だけを書く。
            return self.inline(item.children)
        if isinstance(item, RefMark):
            return self._ref(item.key)
        return self._note(item.key)

    def _ref(self, key: str) -> str:
        if self._numbering is None:
            return escape(f"[^{key}]")
        number = self._numbering.refs[key]
        self.ref_uses[key] += 1
        mark = ref_mark_id(number, self.ref_uses[key], self._prefix)
        return (
            f'<sup id="{mark}" class="reference">'
            f'<a href="#{ref_item_id(number, self._prefix)}">[{number}]</a></sup>'
        )

    def _note(self, key: str) -> str:
        if self._numbering is None:
            return escape(f"[^n:{key}]")
        number = self._numbering.notes[key]
        self.note_uses[key] += 1
        mark = note_mark_id(number, self.note_uses[key], self._prefix)
        return (
            f'<sup id="{mark}" class="reference">'
            f'<a href="#{note_item_id(number, self._prefix)}">[{NOTE_LABEL} {number}]</a></sup>'
        )


def letters(count: int) -> list[str]:
    """戻りリンクに使う ``a``・``b``・…・``z``・``aa``・… を ``count`` 個返す。"""
    out: list[str] = []
    for index in range(count):
        n = index + 1
        label = ""
        while n:
            n, rest = divmod(n - 1, 26)
            label = chr(ord("a") + rest) + label
        out.append(label)
    return out


def figure_html(figure: Figure, base_dir: Path | None) -> str:
    """画像を、本文に埋め込む figure の HTML にする。画像の中身は data: の URI として入れる。"""
    try:
        uri = data_uri(figure.source, base_dir)
    except ImageError as error:
        raise HtmlError(f"{figure.line} 行目の画像を埋め込めない: {error}") from error
    caption = escape(figure.caption)
    return (
        '<figure class="thumb">'
        f'<img src="{uri}" alt="{caption}">'
        f"<figcaption>{caption}</figcaption></figure>"
    )


def blocks_html(
    writer: InlineWriter,
    blocks: Sequence[Block],
    *,
    base_dir: Path | None = None,
) -> list[str]:
    """段落・箇条書き・画像を、まとまりごとの HTML にする。

    Parameters
    ----------
    writer : InlineWriter
        文中の部品を書く人。
    blocks : Sequence[Block]
        まとまりの並び。
    base_dir : Path | None
        原稿の置き場。画像の道を解くのに使う。

    Returns
    -------
    list[str]
        まとまりごとの HTML。

    Raises
    ------
    HtmlError
        画像を埋め込めないとき。
    """
    out: list[str] = []
    for block in blocks:
        if isinstance(block, Paragraph):
            out.append(f"<p>{writer.inline(block.content)}</p>")
        elif isinstance(block, Figure):
            out.append(figure_html(block, base_dir))
        else:
            items = "\n".join(f"<li>{writer.inline(item)}</li>" for item in block.items)
            out.append(f"<ul>\n{items}\n</ul>")
    return out
