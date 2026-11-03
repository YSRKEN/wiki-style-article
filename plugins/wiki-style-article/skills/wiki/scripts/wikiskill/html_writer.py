"""読み取った記事を、ブラウザで開ける HTML 1 枚に書き出す。

見た目は日本語版 Wikipedia の現行の外装（Vector 2022）に寄せた「Wikipedia風」のページで、
雛形 ``assets/page-template.html``（CSS を中に持つ）の差し込み口に、記事の各部分を入れて作る。
外部の CSS・JS・フォント・画像は読まない。詳しくは ``docs/html.md``。

ページの並びは、冒頭の警告の枠、Infobox、導入部、節、脚注（注釈・出典の小節）、関連項目、
外部リンク、カテゴリ欄、フッタ。値のない部分は節も欄も作らない。目次は節の見出し（脚注以降の見出しも含む）から作る。

噂のある原稿は :func:`write_html_both` で、通常の記事と噂込みの記事を一枚に入れ、記事名の下の
ボタンで切り替えて読めるようにする（:mod:`wikiskill.html_switch`）。
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
from wikiskill.html_switch import (
    NORMAL,
    RUMOR,
    RUMOR_PREFIX,
    SWITCH_SCRIPT,
    SWITCH_STYLE,
    switch_html,
    variant_attrs,
)
from wikiskill.model import Article, InternalLink, NoticeKind, Section
from wikiskill.notices import article_notices
from wikiskill.types import ArticleType
from wikiskill.variants import has_rumor, normal_view, rumor_view

__all__ = [
    "DEFAULT_TEMPLATE_PATH",
    "HtmlError",
    "NestedFootnoteError",
    "UnknownFootnoteError",
    "load_template",
    "notice_box_html",
    "write_html",
    "write_html_both",
]

DEFAULT_TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "assets" / "page-template.html"
"""同梱の雛形（``plugins/wiki-style-article/skills/wiki/assets/page-template.html``）。"""

_WHOLE_LINE = re.compile(r"[ \t]*\{\{([A-Z_]+)\}\}[ \t]*")
_PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")
_NOP_TITLE = "この部品は見た目だけで、押しても動きません"
_CATEGORY_INDEX = f"{WIKI_BASE}Special:Categories"

NOTICE_TEXTS: dict[NoticeKind, str] = {
    "出典の明記": (
        "この記事には、出典が示されていない記述や、"
        "信頼性の確かめられていない出典に頼る記述があります。"
    ),
    "独自研究": "この記事には、出典で確かめられていない見方や推測が含まれています。",
    "観点": "この記事には、中立的な観点を欠くおそれのある噂や利用者の見方が含まれています。",
}
"""警告の枠の文面。本家の枠の文は写さず、自分で書いた。"""

NOTICE_HEADING = "この記事には次の問題があります。"
"""枠が二つ以上のときに、箇条の前に置く文。"""

_BODY_KEYS = (
    "NOTICES",
    "INFOBOX",
    "LEAD",
    "SECTIONS",
    "FOOTNOTES",
    "RELATED",
    "EXTERNAL_LINKS",
    "CATEGORIES",
)
"""記事の中身の差し込み口。雛形に並ぶ順。"""

_NO_VARIANTS: dict[str, str] = dict.fromkeys(
    (
        "VARIANT_STYLE",
        "VARIANT_SWITCH",
        "VARIANT_OPEN",
        "VARIANT_CLOSE",
        "RUMOR_VARIANT",
        "VARIANT_SCRIPT",
    ),
    "",
)
"""版が一つのときの、切り替えの差し込み口の値（どれも空なので行ごと消える）。"""

_VARIANT_END = "</div><!-- /variant -->"
"""版を包む要素の閉じ。"""


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
    mark_date: str | None = None,
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
    mark_date : str | None
        冒頭の警告の枠に添える日付（例 ``2026年11月``）。None なら日付を出さない。

    Returns
    -------
    str
        HTML 全文。改行で終わる。

    Raises
    ------
    HtmlError
        記事の ``type`` と ``article_type`` が食い違うとき。噂のある記事を渡したとき
        （:func:`write_html_both` を使う）。雛形に知らない差し込み口があるときも。
    UnknownFootnoteError
        本文の印が指す出典・注釈が設定欄にないとき。
    NestedFootnoteError
        注釈の本文に別の注釈への印があるとき。
    """
    _check_type(article, article_type)
    if has_rumor(article):
        raise HtmlError(
            "噂のある原稿は write_html_both で書き出す（通常の記事と噂込みの記事を一枚に入れる）"
        )
    page = _Page(article)
    body = page.body(article_type, mark_date)
    values = {
        "PAGE_TITLE": escape(article.settings.title),
        "TOC": page.toc(),
        **body,
        **_NO_VARIANTS,
        "UPDATED": escape(updated),
    }
    return _fill(load_template() if template is None else template, values)


def write_html_both(
    article: Article,
    article_type: ArticleType,
    updated: str,
    *,
    template: str | None = None,
    mark_date: str | None = None,
) -> str:
    """噂のある記事を、通常の記事と噂込みの記事の二つの版を入れた HTML 1 枚に書き出す。

    記事名のすぐ下に二つのボタン（通常の記事・噂込みの記事）を置き、押すと本文（冒頭の枠・
    Infobox・導入部・節・脚注・関連項目・外部リンク・カテゴリ）と目次（左の列と浮き窓）が、
    その版のものに切り替わる。開いたときと、スクリプトが動かないときは通常の記事が見える。

    版は :func:`wikiskill.variants.normal_view`・:func:`wikiskill.variants.rumor_view` で作る。
    脚注の番号は版ごとに振り、噂込みの版の id には接頭辞 ``rumor-`` を付けて重ならないようにする。

    Parameters
    ----------
    article : Article
        :func:`wikiskill.read_article` で読み取った記事。噂の部品を含んでよい。
    article_type : ArticleType
        記事の類型の定義。
    updated : str
        フッタに出す最終更新の日時。
    template : str | None
        雛形の全文。省略すると同梱の雛形を読む。
    mark_date : str | None
        冒頭の警告の枠に添える日付。None なら日付を出さない。

    Returns
    -------
    str
        HTML 全文。改行で終わる。

    Raises
    ------
    HtmlError
        記事の ``type`` と ``article_type`` が食い違うとき。雛形に知らない差し込み口があるときも。
    UnknownFootnoteError
        本文の印が指す出典・注釈が設定欄にないとき。
    NestedFootnoteError
        注釈の本文に別の注釈への印があるとき。
    """
    _check_type(article, article_type)
    normal = _Page(normal_view(article))
    rumor = _Page(rumor_view(article), prefix=RUMOR_PREFIX)
    normal_body = normal.body(article_type, mark_date)
    rumor_body = rumor.body(article_type, mark_date)
    toc = "\n".join(part for part in (normal.toc(NORMAL), rumor.toc(RUMOR)) if part)
    rumor_html = "\n".join(
        [
            f'<div class="variant"{variant_attrs(RUMOR)}>',
            *(value for value in rumor_body.values() if value),
            _VARIANT_END,
        ]
    )
    values = {
        "PAGE_TITLE": escape(article.settings.title),
        "TOC": toc,
        **normal_body,
        "VARIANT_STYLE": SWITCH_STYLE,
        "VARIANT_SWITCH": switch_html(),
        "VARIANT_OPEN": f'<div class="variant"{variant_attrs(NORMAL)}>',
        "VARIANT_CLOSE": _VARIANT_END,
        "RUMOR_VARIANT": rumor_html,
        "VARIANT_SCRIPT": SWITCH_SCRIPT,
        "UPDATED": escape(updated),
    }
    return _fill(load_template() if template is None else template, values)


def _check_type(article: Article, article_type: ArticleType) -> None:
    type_id = article.settings.type_id
    if article_type.id != type_id:
        raise HtmlError(f"原稿の type は {type_id!r} だが、渡された類型は {article_type.id!r}")


def notice_box_html(kinds: tuple[NoticeKind, ...], mark_date: str | None) -> str:
    """冒頭の警告の枠を HTML にする。

    Parameters
    ----------
    kinds : tuple[NoticeKind, ...]
        貼る枠（:func:`wikiskill.notices.article_notices` の結果）。
    mark_date : str | None
        各文に添える日付。None なら添えない。

    Returns
    -------
    str
        枠が一つならその文、二つ以上なら見出しの文と各文の箇条を入れた一つの枠。
        枠が無ければ空文字列。
    """
    if not kinds:
        return ""
    suffix = "" if mark_date is None else f"（{escape(mark_date)}）"
    texts = [f"{NOTICE_TEXTS[kind]}{suffix}" for kind in kinds]
    if len(texts) == 1:
        body = texts[0]
    else:
        items = "\n".join(f"<li>{text}</li>" for text in texts)
        body = f"{NOTICE_HEADING}\n<ul>\n{items}\n</ul>"
    return f'<div class="ambox" role="note"><div class="ambox-text">{body}</div></div>'


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
    """記事の各部分を、書き出す順に HTML にする。見出しと脚注の使用回数を覚える。

    ``prefix`` は見出し・脚注の id に付ける接頭辞（一枚に二つの版を入れるときの噂込みの版）。
    """

    def __init__(self, article: Article, *, prefix: str = "") -> None:
        self._article = article
        self._prefix = prefix
        self._numbering: Numbering = number_footnotes(article)
        self._writer = InlineWriter(self._numbering, prefix=prefix)
        self._headings: list[_Heading] = []
        self._counters: list[int] = []

    def body(self, article_type: ArticleType, mark_date: str | None) -> dict[str, str]:
        """記事の中身の差し込み口の値（雛形に並ぶ順）。目次より先に呼ぶ（見出しを覚える）。"""
        article = self._article
        # 見出しの番号は書く順に振るので、本文・脚注・末尾の節の順に作る。
        lead = self.lead()
        sections = self.sections()
        footnotes = self.footnotes()
        related = self.related()
        external_links = self.external_links()
        values = {
            "NOTICES": notice_box_html(article_notices(article), mark_date),
            "INFOBOX": build_infobox_html(article.settings, article_type),
            "LEAD": lead,
            "SECTIONS": sections,
            "FOOTNOTES": footnotes,
            "RELATED": related,
            "EXTERNAL_LINKS": external_links,
            "CATEGORIES": self.categories(),
        }
        return {key: values[key] for key in _BODY_KEYS}

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
        heading_id = f"{self._prefix}section-" + number.replace(".", "-")
        heading = _Heading(level, heading_id, number, title)
        self._headings.append(heading)
        return (
            f'<div class="mw-heading mw-heading{level}"><h{level} id="{heading.id}">'
            f"{escape(title)}</h{level}>"
            '<span class="mw-editsection">'
            f'<span class="nop" title="{_NOP_TITLE}">編集</span></span>'
            "</div>"
        )

    def toc(self, variant: str | None = None) -> str:
        """目次の項目（``<li>`` の並び）。節がなければ空文字列。

        ``variant`` を渡すと、一段目の項目に版の印（``data-variant``。通常の版のほかは ``hidden``）
        を付ける。子の項目は親の項目ごと隠れるので印を付けない。
        """
        root = _Node(_Heading(1, "", "", ""))
        stack = [root]
        for heading in self._headings:
            while stack[-1].heading.level >= heading.level:
                stack.pop()
            node = _Node(heading)
            stack[-1].children.append(node)
            stack.append(node)
        return _toc_items(root.children, "" if variant is None else variant_attrs(variant))

    # -- 本文

    def lead(self) -> str:
        """導入部（見出しなし）。"""
        return "\n".join(
            blocks_html(self._writer, self._article.lead, base_dir=self._article.base_dir)
        )

    def sections(self) -> str:
        """原稿の節を、見出しと本文の順に。"""
        out: list[str] = []
        for section in self._article.sections:
            out += self._section(section)
        return "\n".join(out)

    def _section(self, section: Section) -> list[str]:
        out = [self._heading(section.level, section.title)]
        out += blocks_html(self._writer, section.blocks, base_dir=self._article.base_dir)
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
            back = _backlink(note_mark_id, number, self._writer.note_uses[key], self._prefix)
            items.append(
                f'<li id="{note_item_id(number, self._prefix)}">{back} '
                f'<span class="reference-text">{text}</span></li>'
            )
        return _reflist(items)

    def _ref_list(self) -> str:
        refs = {r.key: r for r in self._article.settings.references}
        items: list[str] = []
        for key, number in self._numbering.refs.items():
            back = _backlink(ref_mark_id, number, self._writer.ref_uses[key], self._prefix)
            items.append(
                f'<li id="{ref_item_id(number, self._prefix)}">{back} '
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


def _toc_items(nodes: list[_Node], attrs: str = "") -> str:
    """目次の項目。``attrs`` はこの段の項目に付ける属性（子の段には付けない）。"""
    items: list[str] = []
    for node in nodes:
        h = node.heading
        link = (
            f'<a href="#{h.id}"><span class="tocnumber">{h.number}</span>'
            f'<span class="toctext">{escape(h.title)}</span></a>'
        )
        if node.children:
            children = _toc_items(node.children)
            items.append(f'<li data-id="{h.id}"{attrs}>{link}\n<ul>\n{children}\n</ul></li>')
        else:
            items.append(f'<li data-id="{h.id}"{attrs}>{link}</li>')
    return "\n".join(items)


def _backlink(mark_id: Callable[[int, int, str], str], number: int, count: int, prefix: str) -> str:
    """脚注欄の項目の戻りリンク。一回なら「↑」、複数なら「↑ a b …」。"""
    if count <= 1:
        href = mark_id(number, 1, prefix)
        return f'<span class="mw-cite-backlink"><a href="#{href}">↑</a></span>'
    links = "".join(
        f'<a href="#{mark_id(number, nth, prefix)}">{label}</a>'
        for nth, label in enumerate(letters(count), start=1)
    )
    return f'<span class="mw-cite-backlink">↑ {links}</span>'


def _reflist(items: list[str]) -> str:
    body = "\n".join(items)
    return f'<div class="reflist">\n<ol class="references">\n{body}\n</ol>\n</div>'


def _ul(items: list[str]) -> str:
    return "<ul>\n" + "\n".join(items) + "\n</ul>"
