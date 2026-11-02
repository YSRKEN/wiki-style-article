"""読み取った記事を、ブラウザで開ける HTML 1 枚に書き出す。

見た目は日本語版 Wikipedia の現行の外装（Vector 2022）に寄せた「Wikipedia風」のページで、
雛形 ``assets/page-template.html``（CSS を中に持つ）の差し込み口に、記事の各部分を入れて作る。
外部の CSS・JS・フォント・画像は読まない。詳しくは ``docs/html.md``。

ページの並びは、Infobox、導入部、節、脚注（注釈・出典の小節）、関連項目、外部リンク、
カテゴリ欄、フッタ。値のない部分は節も欄も作らない。目次は節の見出し（脚注以降の見出しも含む）から作る。
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from wikiskill.html_cite import cite_html
from wikiskill.html_escape import WIKI_BASE, escape, external_href
from wikiskill.html_infobox import build_infobox_html
from wikiskill.html_inline import (
    HtmlError,
    InlineWriter,
    NestedFootnoteError,
    Numbering,
    UnknownFootnoteError,
    blocks_html,
    internal_link,
    letters,
    note_item_id,
    note_mark_id,
    number_footnotes,
    ref_item_id,
    ref_mark_id,
)
from wikiskill.model import Article, InternalLink, Section
from wikiskill.types import ArticleType

__all__ = [
    "DEFAULT_TEMPLATE_PATH",
    "HtmlError",
    "NestedFootnoteError",
    "UnknownFootnoteError",
    "load_template",
    "write_html",
]

DEFAULT_TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "assets" / "page-template.html"
"""同梱の雛形（``plugins/wiki-style-article/skills/wiki/assets/page-template.html``）。"""

_WHOLE_LINE = re.compile(r"[ \t]*\{\{([A-Z_]+)\}\}[ \t]*")
_PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")
_NOP_TITLE = "この部品は見た目だけで、押しても動きません"
_CATEGORY_INDEX = f"{WIKI_BASE}Special:Categories"


def load_template(path: str | Path | None = None) -> str:
    """HTML の雛形を読む。

    Parameters
    ----------
    path : str | Path | None
        雛形のファイル。省略すると同梱の雛形（:data:`DEFAULT_TEMPLATE_PATH`）。

    Returns
    -------
    str
        雛形の全文（UTF-8）。
    """
    return Path(path or DEFAULT_TEMPLATE_PATH).read_text(encoding="utf-8")


def write_html(
    article: Article,
    article_type: ArticleType,
    updated: str,
    *,
    template: str | None = None,
) -> str:
    """記事を HTML 1 枚に書き出す。

    現在時刻は関数の中で取らない。最終更新の日時は呼ぶ側が文字列で渡す。

    Parameters
    ----------
    article : Article
        :func:`wikiskill.read_article` で読み取った記事。
    article_type : ArticleType
        記事の類型の定義。``article.settings.type_id`` と同じ ``id`` のもの。
    updated : str
        フッタに出す最終更新の日時（例 ``2026年11月2日 (月) 12:00 (JST)``）。
        逃がしてそのまま入れる。
    template : str | None
        雛形の全文。省略すると同梱の雛形を読む。

    Returns
    -------
    str
        HTML 全文。改行で終わる。

    Raises
    ------
    HtmlError
        記事の ``type`` と ``article_type`` が食い違うとき。
        雛形に知らない差し込み口があるときも。
    UnknownFootnoteError
        本文の印が指す出典・注釈が設定欄にないとき。
    NestedFootnoteError
        注釈の本文に別の注釈への印があるとき。
    """
    settings = article.settings
    if article_type.id != settings.type_id:
        raise HtmlError(
            f"原稿の type は {settings.type_id!r} だが、渡された類型は {article_type.id!r}"
        )
    page = _Page(article)
    lead = page.lead()
    sections = page.sections()
    footnotes = page.footnotes()
    related = page.related()
    external_links = page.external_links()
    values = {
        "PAGE_TITLE": escape(settings.title),
        "TOC": page.toc(),
        "INFOBOX": build_infobox_html(settings, article_type),
        "LEAD": lead,
        "SECTIONS": sections,
        "FOOTNOTES": footnotes,
        "RELATED": related,
        "EXTERNAL_LINKS": external_links,
        "CATEGORIES": page.categories(),
        "UPDATED": escape(updated),
    }
    return _fill(load_template() if template is None else template, values)


# --- 雛形への差し込み -------------------------------------------------------------


def _fill(template: str, values: Mapping[str, str]) -> str:
    """雛形の差し込み口を値で置き換える。

    差し込み口だけの行は、値が空ならその行ごと消す。値の中の ``{{…}}`` は置き換えない
    （一度の走査で置き換えるので、値が差し込み口に見えても再び置き換わらない）。
    """

    def lookup(name: str) -> str:
        if name not in values:
            raise HtmlError(f"雛形に知らない差し込み口 {{{{{name}}}}} がある")
        return values[name]

    lines: list[str] = []
    for line in template.split("\n"):
        whole = _WHOLE_LINE.fullmatch(line)
        if whole:
            value = lookup(whole[1])
            if value:
                lines.append(value)
        else:
            lines.append(_PLACEHOLDER.sub(lambda m: lookup(m[1]), line))
    return "\n".join(lines)


# --- ページの各部分 ---------------------------------------------------------------


@dataclass(frozen=True)
class _Heading:
    """目次に載せる見出し一つ。"""

    level: int
    id: str
    number: str
    title: str


@dataclass
class _Node:
    heading: _Heading
    children: list[_Node] = field(default_factory=lambda: [])


class _Page:
    """記事の各部分を、書き出す順に HTML にする。見出しと脚注の使用回数を覚える。"""

    def __init__(self, article: Article) -> None:
        self._article = article
        self._numbering: Numbering = number_footnotes(article)
        self._writer = InlineWriter(self._numbering)
        self._headings: list[_Heading] = []
        self._counters: list[int] = []

    # -- 見出しと目次

    def _heading(self, level: int, title: str) -> str:
        """見出しの HTML を作り、目次用に覚える。id は節の番号から作る（``section-2-1``）。"""
        depth = level - 1
        if len(self._counters) >= depth:
            del self._counters[depth:]
            self._counters[depth - 1] += 1
        else:
            self._counters.extend([1] * (depth - len(self._counters)))
        number = ".".join(str(n) for n in self._counters)
        heading = _Heading(level, "section-" + number.replace(".", "-"), number, title)
        self._headings.append(heading)
        return (
            f'<div class="mw-heading mw-heading{level}"><h{level} id="{heading.id}">'
            f"{escape(title)}</h{level}>"
            '<span class="mw-editsection">'
            f'<span class="nop" title="{_NOP_TITLE}">編集</span></span>'
            "</div>"
        )

    def toc(self) -> str:
        """目次の項目（``<li>`` の並び）。節がなければ空文字列。"""
        root = _Node(_Heading(1, "", "", ""))
        stack = [root]
        for heading in self._headings:
            while stack[-1].heading.level >= heading.level:
                stack.pop()
            node = _Node(heading)
            stack[-1].children.append(node)
            stack.append(node)
        return _toc_items(root.children)

    # -- 本文

    def lead(self) -> str:
        """導入部（見出しなし）。"""
        return "\n".join(blocks_html(self._writer, self._article.lead))

    def sections(self) -> str:
        """原稿の節を、見出しと本文の順に。"""
        out: list[str] = []
        for section in self._article.sections:
            out += self._section(section)
        return "\n".join(out)

    def _section(self, section: Section) -> list[str]:
        out = [self._heading(section.level, section.title)]
        out += blocks_html(self._writer, section.blocks)
        for child in section.children:
            out += self._section(child)
        return out

    # -- 脚注

    def footnotes(self) -> str:
        """「脚注」の節。注釈があれば「注釈」、出典があれば「出典」の小節を作る。"""
        numbering = self._numbering
        if not numbering.notes and not numbering.refs:
            return ""
        parts = [self._heading(2, "脚注")]
        if numbering.notes:
            parts += [self._heading(3, "注釈"), self._note_list()]
        if numbering.refs:
            parts += [self._heading(3, "出典"), self._ref_list()]
        return "\n".join(parts)

    def _note_list(self) -> str:
        notes = {n.key: n for n in self._article.settings.notes}
        items: list[str] = []
        for key, number in self._numbering.notes.items():
            # 注釈の中の出典の印は、この一覧の中に置かれる。先に本文を書いて使用回数を数える。
            text = self._writer.inline(notes[key].text)
            back = _backlink(note_mark_id, number, self._writer.note_uses[key])
            items.append(
                f'<li id="{note_item_id(number)}">{back} '
                f'<span class="reference-text">{text}</span></li>'
            )
        return _reflist(items)

    def _ref_list(self) -> str:
        refs = {r.key: r for r in self._article.settings.references}
        items: list[str] = []
        for key, number in self._numbering.refs.items():
            back = _backlink(ref_mark_id, number, self._writer.ref_uses[key])
            items.append(
                f'<li id="{ref_item_id(number)}">{back} '
                f'<span class="reference-text">{cite_html(refs[key])}</span></li>'
            )
        return _reflist(items)

    # -- 末尾

    def related(self) -> str:
        """「関連項目」の節。"""
        names = self._article.settings.related
        if not names:
            return ""
        items = [f"<li>{internal_link(InternalLink(name, None))}</li>" for name in names]
        return "\n".join([self._heading(2, "関連項目"), _ul(items)])

    def external_links(self) -> str:
        """「外部リンク」の節。"""
        links = self._article.settings.external_links
        if not links:
            return ""
        items: list[str] = []
        for link in links:
            href = external_href(link.url)
            title = escape(link.title)
            if href is None:
                items.append(f"<li>{title}</li>")
            else:
                items.append(
                    f'<li><a class="external" rel="nofollow" href="{href}">{title}</a></li>'
                )
        return "\n".join([self._heading(2, "外部リンク"), _ul(items)])

    def categories(self) -> str:
        """カテゴリ欄。"""
        names = self._article.settings.categories
        if not names:
            return ""
        items = [
            f"<li>{internal_link(InternalLink(f'Category:{name}', name))}</li>" for name in names
        ]
        body = "\n".join(items)
        label = f'<a href="{_CATEGORY_INDEX}">カテゴリ</a>'
        return f'<div class="catlinks">{label}: <ul>\n{body}\n</ul></div>'


def _toc_items(nodes: list[_Node]) -> str:
    items: list[str] = []
    for node in nodes:
        h = node.heading
        link = (
            f'<a href="#{h.id}"><span class="tocnumber">{h.number}</span>'
            f'<span class="toctext">{escape(h.title)}</span></a>'
        )
        if node.children:
            children = _toc_items(node.children)
            items.append(f'<li data-id="{h.id}">{link}\n<ul>\n{children}\n</ul></li>')
        else:
            items.append(f'<li data-id="{h.id}">{link}</li>')
    return "\n".join(items)


def _backlink(mark_id: Callable[[int, int], str], number: int, count: int) -> str:
    """脚注欄の項目の戻りリンク。一回なら「↑」、複数なら「↑ a b …」。"""
    if count <= 1:
        return f'<span class="mw-cite-backlink"><a href="#{mark_id(number, 1)}">↑</a></span>'
    links = "".join(
        f'<a href="#{mark_id(number, nth)}">{label}</a>'
        for nth, label in enumerate(letters(count), start=1)
    )
    return f'<span class="mw-cite-backlink">↑ {links}</span>'


def _reflist(items: list[str]) -> str:
    body = "\n".join(items)
    return f'<div class="reflist">\n<ol class="references">\n{body}\n</ol>\n</div>'


def _ul(items: list[str]) -> str:
    return "<ul>\n" + "\n".join(items) + "\n</ul>"
