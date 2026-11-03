"""読み取った記事を MediaWiki のウィキテキストに書き出す。

書き方は二つあり、``style`` で選ぶ（詳しくは ``docs/wikitext.md``）。

``"wikipedia"``（既定。本家の形）
    日本語版 Wikipedia の原稿と同じテンプレートを使う。出典は ``{{Cite web}}``・``{{Cite book}}``・
    ``{{Cite news}}``、脚注の一覧は ``{{Reflist}}``、Infobox は類型ごとのテンプレート。
``"plain"``（素の記法）
    素の MediaWiki と Cite 拡張だけで描ける。出典は ``<ref>`` の中に地の文で書き、Infobox は
    ``{| class="infobox"`` の表、脚注の一覧は ``<references />``。テンプレートは使わない。

ページの並びは、冒頭の警告の枠、Infobox、導入部、節、脚注（注釈・出典の小節）、関連項目、
外部リンク、``{{DEFAULTSORT:}}``、カテゴリ。値のない部分は節も行も書かない。

印と警告の枠は、本家の形では ``{{要出典|date=…}}``・``{{要出典範囲|1=範囲の文|date=…}}``・
``{{出典の明記|date=…}}``・``{{複数の問題|出典の明記=…|…}}`` のテンプレート、素の記法では
``[要出典]`` のような文字と、斜体の一行にする。
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from wikiskill.images import file_name
from wikiskill.model import (
    FIX_RANGE_LABELS,
    Article,
    Block,
    Bold,
    Figure,
    FixMark,
    FixRange,
    Inline,
    InternalLink,
    NoticeKind,
    Original,
    Paragraph,
    RefMark,
    RumorRange,
    Section,
    Settings,
    Text,
)
from wikiskill.notices import article_notices
from wikiskill.types import ArticleType
from wikiskill.variants import has_rumor
from wikiskill.wikitext_cite import cite_plain, cite_template
from wikiskill.wikitext_escape import escape_text, external_link, guard_line_start
from wikiskill.wikitext_infobox import build_infobox, unknown_labels

WikitextStyle = Literal["wikipedia", "plain"]
"""書き出しの書き方。``wikipedia`` は本家の形、``plain`` は素の記法。"""

WIKITEXT_STYLES: tuple[WikitextStyle, ...] = ("wikipedia", "plain")
"""``style`` に指定できる値。"""

_NOTE_GROUP = "注釈"


# --- 例外 -------------------------------------------------------------------------


class WikitextError(ValueError):
    """ウィキテキストへ書き出せない記事を渡したときの基底の例外。"""


class UnknownReferenceError(WikitextError):
    """本文の印が指す出典・注釈が、設定欄の ``[refs]``・``[notes]`` にない。"""


class NestedNoteError(WikitextError):
    """注釈の本文の中に別の注釈への印がある（注釈は入れ子にできない）。"""


# --- 公開関数 ---------------------------------------------------------------------


def write_wikitext(
    article: Article,
    article_type: ArticleType,
    *,
    style: WikitextStyle = "wikipedia",
    mark_date: str | None = None,
) -> str:
    """記事をウィキテキストに書き出す。

    Parameters
    ----------
    article : Article
        :func:`wikiskill.read_article` で読み取った記事。
    article_type : ArticleType
        記事の類型の定義。``article.settings.type_id`` と同じ ``id`` のもの。
    style : WikitextStyle
        書き方。``"wikipedia"`` は本家の形（既定）、``"plain"`` は素の記法。
    mark_date : str | None
        印と冒頭の警告の枠に添える日付（例 ``2026年11月``）。None なら日付を付けない。

    Returns
    -------
    str
        ウィキテキスト。空でなければ改行で終わる。

    Raises
    ------
    WikitextError
        記事の ``type`` と ``article_type`` が食い違うとき。噂のある記事を渡したとき
        （:func:`wikiskill.variants.normal_view`・:func:`wikiskill.variants.rumor_view` で
        二つの版に分けてから渡す）。
    UnknownReferenceError
        本文の印が指す出典・注釈が設定欄にないとき。
    NestedNoteError
        注釈の本文に別の注釈への印があるとき。
    """
    settings = article.settings
    if article_type.id != settings.type_id:
        raise WikitextError(
            f"原稿の type は {settings.type_id!r} だが、渡された類型は {article_type.id!r}"
        )
    if has_rumor(article):
        raise WikitextError(
            "噂のある原稿は wikiskill.variants の normal_view・rumor_view で"
            "二つの版に分けてから書き出す"
        )
    plain = style == "plain"
    # 同じ出典・注釈を二回以上使うかは、通して書かないと分からない。
    # 一度目で数え、二度目で名前を付ける。
    first = _write_body(article, plain, frozenset(), frozenset(), mark_date)
    body = _write_body(
        article,
        plain,
        frozenset(k for k, n in first.ref_uses.items() if n > 1),
        frozenset(k for k, n in first.note_uses.items() if n > 1),
        mark_date,
    )

    infobox = build_infobox(settings, article_type, plain=plain)
    notices = _notice_block(article_notices(article), plain, mark_date)
    head = "\n".join(part for part in (notices, infobox.top, infobox.lead) if part)
    chunks = [
        "\n\n".join(body.chunks),
        _footnote_section(body, plain),
        _related_section(settings),
        _external_links_section(settings),
        _category_block(settings),
    ]
    text = "\n\n".join(chunk for chunk in chunks if chunk)
    text = f"{head}\n{text}" if head and text else head or text
    return text + "\n" if text else ""


def unknown_infobox_labels(article: Article, article_type: ArticleType) -> tuple[str, ...]:
    """原稿の ``[infobox]`` のうち、類型の定義にない項目名を返す。

    本家の形では、これらの項目は Infobox に書けないので HTML コメントで残す。
    値が空の項目は数えない。

    Parameters
    ----------
    article : Article
        読み取った記事。
    article_type : ArticleType
        記事の類型の定義。

    Returns
    -------
    tuple[str, ...]
        定義にない項目名。原稿に書いた順。Infobox を持たない類型では、書かれた項目名すべて。
    """
    return unknown_labels(article.settings, article_type)


# --- 本文 -------------------------------------------------------------------------


@dataclass(frozen=True)
class _Body:
    """本文を書き出した結果。"""

    chunks: list[str]
    ref_uses: Counter[str]
    note_uses: Counter[str]


def _write_body(
    article: Article,
    plain: bool,
    reused_refs: frozenset[str],
    reused_notes: frozenset[str],
    mark_date: str | None,
) -> _Body:
    """導入部と節を、文書の出現順に書き出す。出典と注釈は最初に使われた場所で定義する。"""
    writer = _BodyWriter(article.settings, plain, reused_refs, reused_notes, mark_date)
    chunks = writer.blocks(article.lead)
    for section in article.sections:
        chunks += writer.section(section)
    return _Body(chunks, writer.ref_uses, writer.note_uses)


class _BodyWriter:
    """本文の部品をウィキテキストにする。出典と注釈を何度使ったかも数える。"""

    def __init__(
        self,
        settings: Settings,
        plain: bool,
        reused_refs: frozenset[str],
        reused_notes: frozenset[str],
        mark_date: str | None,
    ) -> None:
        self._mark_date = mark_date
        self._refs = {r.key: r for r in settings.references}
        self._notes = {n.key: n for n in settings.notes}
        self._plain = plain
        self._reused_refs = reused_refs
        self._reused_notes = reused_notes
        self._defined_refs: set[str] = set()
        self._defined_notes: set[str] = set()
        self._note_key: str | None = None  # 注釈の本文を書いている間だけ入る
        self._nested = False  # {{Efn}}・{{#tag:}} の引数の中を書いている間だけ真
        self.ref_uses: Counter[str] = Counter()
        self.note_uses: Counter[str] = Counter()

    # -- まとまり

    def blocks(self, blocks: Sequence[Block]) -> list[str]:
        """段落と箇条書きを、空行で区切る単位の文字列にする。"""
        return [self._block(b) for b in blocks]

    def section(self, section: Section) -> list[str]:
        """節を、見出しとその下の本文・子の節の順に書く。見出しは最初のまとまりと同じ単位にする。"""
        marks = "=" * section.level
        heading = f"{marks} {escape_text(section.title)} {marks}"
        blocks = self.blocks(section.blocks)
        out = [f"{heading}\n{blocks[0]}"] if blocks else [heading]
        out += blocks[1:]
        for child in section.children:
            out += self.section(child)
        return out

    def _block(self, block: Block) -> str:
        if isinstance(block, Paragraph):
            return guard_line_start(self.inline(block.content))
        if isinstance(block, Figure):
            return self._figure(block)
        return "\n".join("* " + guard_line_start(self.inline(item)) for item in block.items)

    def _figure(self, figure: Figure) -> str:
        """画像を、本家のファイルの記法にする。画像そのものは本家に上げるので、名前だけを書く。"""
        caption = escape_text(figure.caption, pipes=True)
        return f"[[ファイル:{file_name(figure.source)}|thumb|{caption}]]"

    # -- 文中の部品

    def inline(self, items: Sequence[Inline]) -> str:
        """文中の部品の並びをウィキテキストにする。"""
        return "".join(self._inline_one(item) for item in items)

    def _inline_one(self, item: Inline) -> str:
        if isinstance(item, Text):
            return escape_text(item.text, pipes=self._nested)
        if isinstance(item, Bold):
            return f"'''{self.inline(item.children)}'''"
        if isinstance(item, InternalLink):
            if item.label is None:
                return f"[[{item.target}]]"
            return f"[[{item.target}|{escape_text(item.label, pipes=self._nested)}]]"
        if isinstance(item, FixMark):
            if self._plain:
                return f"[{item.kind}]"
            return f"{{{{{item.kind}{self._date_arg()}}}}}"
        if isinstance(item, FixRange):
            return self._range(item)
        if isinstance(item, Original):
            return self._original(item)
        if isinstance(item, RumorRange):
            # 書き出す前に二つの版へ分けるので、ふつうは来ない。来たら中身だけを書く。
            return self.inline(item.children)
        if isinstance(item, RefMark):
            return self._ref(item.key)
        return self._note(item.key)

    def _original(self, item: Original) -> str:
        """外国語の原文。本家の形は ``{{lang|タグ|文}}``、素の記法では文字だけ。"""
        if self._plain:
            return escape_text(item.text, pipes=self._nested)
        body = escape_text(item.text, pipes=True)
        # 等号があると名前つきの引数に読まれるので、番号を付けて守る。
        argument = f"2={body}" if "=" in body else body
        return f"{{{{lang|{item.lang}|{argument}}}}}"

    def _date_arg(self) -> str:
        return "" if self._mark_date is None else f"|date={self._mark_date}"

    def _range(self, item: FixRange) -> str:
        if self._plain:
            return f"{self.inline(item.children)}[{FIX_RANGE_LABELS[item.kind]}]"
        # テンプレートの引数の中なので、範囲の文の縦棒を逃がす。等号は 1= を付けて守る。
        outer, self._nested = self._nested, True
        try:
            body = self.inline(item.children)
        finally:
            self._nested = outer
        return f"{{{{{item.kind}|1={body}{self._date_arg()}}}}}"

    def _ref(self, key: str) -> str:
        ref = self._refs.get(key)
        if ref is None:
            raise UnknownReferenceError(f"出典 {key!r} が設定欄の [refs] にない")
        self.ref_uses[key] += 1
        name = _quoted_name(key)
        named = key in self._reused_refs
        # 素の記法の注釈の中は {{#tag:ref}} で入れ子にする（<ref> は入れ子にできないため）。
        if self._plain and self._nested:
            if key in self._defined_refs:
                return f"{{{{#tag:ref||name={name}}}}}"
            self._defined_refs.add(key)
            suffix = f"|name={name}" if named else ""
            return f"{{{{#tag:ref|{cite_plain(ref)}{suffix}}}}}"
        if key in self._defined_refs:
            return f"<ref name={name} />"
        self._defined_refs.add(key)
        body = cite_plain(ref) if self._plain else cite_template(ref)
        attr = f" name={name}" if named else ""
        return f"<ref{attr}>{body}</ref>"

    def _note(self, key: str) -> str:
        if self._note_key is not None:
            raise NestedNoteError(
                f"注釈 {self._note_key!r} の本文に別の注釈への印 [^n:{key}] がある"
                "（注釈は入れ子にできない）"
            )
        note = self._notes.get(key)
        if note is None:
            raise UnknownReferenceError(f"注釈 {key!r} が設定欄の [notes] にない")
        self.note_uses[key] += 1
        name = _quoted_name(key)
        if key in self._defined_notes:
            return f'<ref group="{_NOTE_GROUP}" name={name} />'
        self._defined_notes.add(key)
        named = key in self._reused_notes
        nested = _has_ref_mark(note.text)
        self._note_key, self._nested = key, nested
        try:
            body = self.inline(note.text)
        finally:
            self._note_key, self._nested = None, False
        if not nested:
            attr = f" name={name}" if named else ""
            return f'<ref group="{_NOTE_GROUP}"{attr}>{body}</ref>'
        # 注釈の中に出典があるときは、入れ子にできるテンプレート・関数で包む。
        if self._plain:
            suffix = f"|name={name}" if named else ""
            return f'{{{{#tag:ref|{body}|group="{_NOTE_GROUP}"{suffix}}}}}'
        suffix = f"|name={_ref_name(key)}" if named else ""
        return f"{{{{Efn|1={body}{suffix}}}}}"


def _has_ref_mark(items: Sequence[Inline]) -> bool:
    """文中の部品の並びに、出典への印があるか（太字と範囲の印の中も見る）。"""
    return any(
        isinstance(i, RefMark)
        or (isinstance(i, Bold | FixRange | RumorRange) and _has_ref_mark(i.children))
        for i in items
    )


def _ref_name(key: str) -> str:
    """``<ref name>`` に使う名前。数字だけの名前は使えないので、コロンを前に付ける。"""
    return f":{key}" if key.isdigit() else key


def _quoted_name(key: str) -> str:
    return f'"{_ref_name(key)}"'


# --- 冒頭の警告の枠 ---------------------------------------------------------------


def _notice_block(kinds: tuple[NoticeKind, ...], plain: bool, mark_date: str | None) -> str:
    """冒頭の警告の枠。枠が無ければ空文字列。

    本家の形では、一つなら ``{{出典の明記|date=…}}``、二つ以上なら
    ``{{複数の問題|出典の明記=…|独自研究=…}}``。日付が無いときは、二つ以上でも単独の
    テンプレートを行ごとに並べる（複数の問題は、値の空な引数の項目を出さないため）。
    素の記法では斜体の一行にする。
    """
    if not kinds:
        return ""
    if plain:
        date = "" if mark_date is None else f"（{mark_date}）"
        return f"''この記事には次の問題があります: {'、'.join(kinds)}{date}''"
    if mark_date is None:
        return "\n".join(f"{{{{{kind}}}}}" for kind in kinds)
    if len(kinds) == 1:
        return f"{{{{{kinds[0]}|date={mark_date}}}}}"
    args = "".join(f"|{kind}={mark_date}" for kind in kinds)
    return f"{{{{複数の問題{args}}}}}"


# --- 末尾 -------------------------------------------------------------------------


def _footnote_section(body: _Body, plain: bool) -> str:
    """「脚注」節。注釈があれば「注釈」、出典があれば「出典」の小節を作る。どちらもなければ書かない。"""
    if plain:
        note_list = f'<references group="{_NOTE_GROUP}" />'
    else:
        note_list = f'{{{{Reflist|group="{_NOTE_GROUP}"}}}}'
    ref_list = "<references />" if plain else "{{Reflist}}"
    lines = ["== 脚注 =="]
    if body.note_uses:
        lines += [f"=== {_NOTE_GROUP} ===", note_list]
    if body.ref_uses:
        lines += ["=== 出典 ===", ref_list]
    return "\n".join(lines) if len(lines) > 1 else ""


def _related_section(settings: Settings) -> str:
    if not settings.related:
        return ""
    return "\n".join(["== 関連項目 ==", *(f"* [[{name}]]" for name in settings.related)])


def _external_links_section(settings: Settings) -> str:
    if not settings.external_links:
        return ""
    links = (f"* {external_link(link.url, link.title)}" for link in settings.external_links)
    return "\n".join(["== 外部リンク ==", *links])


def _category_block(settings: Settings) -> str:
    lines: list[str] = []
    if settings.defaultsort:
        lines.append(f"{{{{DEFAULTSORT:{settings.defaultsort}}}}}")
    lines += [f"[[Category:{name}]]" for name in settings.categories]
    return "\n".join(lines)
