"""書き出した HTML を機械で検査する。

見るのは次の項目（規則の ID は ``docs/html.md``）。

- 雛形の差し込み口 ``{{名前}}`` が残っていないこと（``HTML-PLACEHOLDER``）
- タグの開き閉じが合うこと（``HTML-TAG``）
- ``id`` が重ならず（``HTML-ID-DUPLICATE``）、``#…`` のリンク先に対応する ``id`` があること
  （目次などは ``HTML-ANCHOR-MISSING``、脚注は ``HTML-FOOTNOTE-MISSING``）
- 脚注番号が、リンクにならずプレーンな文字のまま残っていないこと（``HTML-FOOTNOTE-PLAIN``。
  ``lang`` 属性つきの ``<span>`` ＝外国語の原文の中の ``[24]`` のような文字は見ない）
- 脚注の過不足（参照されない脚注は ``HTML-FOOTNOTE-UNREFERENCED``）と、番号とリンク先・並びの
  食い違い（``HTML-FOOTNOTE-NUMBER``）
- 外部の CSS・JS・フォント・画像を読まないこと（``HTML-EXTERNAL-RESOURCE``）

脚注の id は ``cite_note-N``・``cite_note-note-N`` で、前に英小文字とハイフンの接頭辞
（噂込みの版の ``rumor-``）が付いたものも脚注とみなす。二つの版を入れた HTML では、版ごとの
脚注欄（``ol.references``）の中で番号の並びを見る。

注意: このファイル名は標準ライブラリの ``html`` と紛らわしいが、中で読む ``html.parser`` は
標準ライブラリのもの。``wikiskill/`` の中を ``sys.path`` の先頭に置いて実行しないこと。
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import unquote

_VOID = frozenset(
    [
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    ],
)
_PLACEHOLDER = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")
_PLAIN_NUMBER = re.compile(r"\[\s*(?:注\s*)?\d+\s*\]")
_ITEM_ID = re.compile(r"(?:[a-z]+-)?cite_note-(note-)?(\d+)")
_FOOTNOTE_ID = re.compile(r"(?:[a-z]+-)?cite_note-")
"""脚注の項目の id の始まり。接頭辞（``rumor-``）の付いたものも含む。"""
_LINK_TEXT = re.compile(r"\[\s*(?:(注)\s*)?(\d+)\s*\]")
_CSS_EXTERNAL = re.compile(r"@import|url\(\s*[\"']?\s*(?:https?:)?//", re.IGNORECASE)
_RESOURCE_ATTRS: dict[str, tuple[str, ...]] = {
    "img": ("src", "srcset"),
    "iframe": ("src",),
    "embed": ("src",),
    "source": ("src", "srcset"),
    "video": ("src", "poster"),
    "audio": ("src",),
    "track": ("src",),
    "object": ("data",),
    "input": ("src",),
}


@dataclass(frozen=True)
class HtmlFinding:
    """検査で見つけた一件。

    Attributes
    ----------
    rule : str
        規則の ID（``HTML-TAG`` など）。
    message : str
        何がどう誤っているかの文面。
    """

    rule: str
    message: str

    def __str__(self) -> str:
        """``HTML-TAG: …`` の形の一行。"""
        return f"{self.rule}: {self.message}"


def check_html(html: str) -> tuple[HtmlFinding, ...]:
    """HTML 全文を検査して、見つかったものを返す。

    Parameters
    ----------
    html : str
        :func:`wikiskill.html_writer.write_html` が書き出した HTML。

    Returns
    -------
    tuple[HtmlFinding, ...]
        見つかったもの。規則ごとにまとめ、同じ規則の中では文書に現れる順。何もなければ空。
    """
    scanner = _Scanner()
    scanner.feed(html)
    scanner.close()
    found = [*_placeholders(html), *scanner.tag_findings]
    found += _ids(scanner)
    found += _footnotes(scanner)
    found += scanner.resource_findings
    return tuple(found)


# --- 走査 -------------------------------------------------------------------------


class _Scanner(HTMLParser):
    """HTML を一度読み、タグの対応・id・リンク・文字・外部の資源を集める。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tag_findings: list[HtmlFinding] = []
        self.resource_findings: list[HtmlFinding] = []
        self.ids: list[str] = []
        self.hash_links: list[tuple[str, str]] = []  # (リンク先の id、リンクの文字)
        self.plain_text: list[str] = []  # リンクの外の文字
        self.reference_lists: list[list[str]] = []  # ol.references ごとの li の id
        self._stack: list[tuple[str, int]] = []
        self._lang_spans: list[int] = []  # lang 属性つきの span の深さ（原文の中にいる間だけ入る）
        self._opening_lang = False
        self._anchor: tuple[str, list[str]] | None = None
        self._raw: str | None = None  # script・style の中にいる間だけ入る
        self._raw_text: list[str] = []
        self._references: list[str] | None = None

    # -- 開始・終了

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """開始タグ。空要素以外は対応を見るために積む。"""
        self._open(tag, attrs)
        if tag not in _VOID:
            self._stack.append((tag, self.getpos()[0]))
            if self._opening_lang:
                self._lang_spans.append(len(self._stack))
        if tag in ("script", "style"):
            self._raw, self._raw_text = tag, []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """``<br />`` のような自己終了タグ。積まない。"""
        self._open(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        """終了タグ。積んだ開始タグと突き合わせる。"""
        line = self.getpos()[0]
        if tag == self._raw:
            self._finish_raw(tag)
        if tag == "a" and self._anchor is not None:
            self.hash_links.append((self._anchor[0], "".join(self._anchor[1])))
            self._anchor = None
        if tag == "ol" and self._references is not None:
            self.reference_lists.append(self._references)
            self._references = None
        if tag in _VOID:
            self._tag(f"空要素に終了タグ </{tag}> がある（{line} 行目）")
            return
        tags = [t for t, _ in self._stack]
        if tag not in tags:
            self._tag(f"開始タグのない終了タグ </{tag}> がある（{line} 行目）")
            return
        while self._stack[-1][0] != tag:
            open_tag, open_line = self._stack.pop()
            self._tag(f"<{open_tag}>（{open_line} 行目）が閉じられないまま </{tag}> に達した")
        if self._lang_spans and self._lang_spans[-1] == len(self._stack):
            self._lang_spans.pop()
        self._stack.pop()

    def handle_data(self, data: str) -> None:
        """文字。script・style の中は別に溜め、リンクの外の文字は脚注番号の検査に回す。"""
        if self._raw is not None:
            self._raw_text.append(data)
            return
        if self._anchor is not None:
            self._anchor[1].append(data)
        elif not self._lang_spans:
            # 外国語の原文（lang つきの span）の中の ``[24]`` は引用元の番号で、脚注番号ではない。
            self.plain_text.append(data)

    def close(self) -> None:
        """読み終え、閉じられていないタグを報告する。"""
        super().close()
        for tag, line in self._stack:
            self._tag(f"<{tag}>（{line} 行目）が閉じられていない")
        self._stack.clear()

    # -- 属性

    def _open(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        self._opening_lang = tag == "span" and "lang" in values
        if "id" in values:
            self.ids.append(values["id"])
            if _is_footnote(values["id"]) and self._references is not None:
                self._references.append(values["id"])
        href = values.get("href", "")
        if tag == "a" and href.startswith("#") and len(href) > 1:
            self._anchor = (unquote(href[1:]), [])
        elif tag == "a":
            self._anchor = ("", [])
        if tag == "ol" and "references" in values.get("class", "").split():
            self._references = []
        self._check_resources(tag, values)

    def _check_resources(self, tag: str, values: dict[str, str]) -> None:
        if tag == "link":
            self._resource(f"<link href={values.get('href', '')!r}>")
        if tag == "script" and values.get("src"):
            self._resource(f"<script src={values['src']!r}>")
        for attr in _RESOURCE_ATTRS.get(tag, ()):
            value = values.get(attr, "").strip().lower()
            if value.startswith(("http:", "https:", "//")):
                self._resource(f"<{tag} {attr}={values[attr]!r}>")
        if _CSS_EXTERNAL.search(values.get("style", "")):
            self._resource(f"<{tag}> の style 属性")

    def _finish_raw(self, tag: str) -> None:
        text = "".join(self._raw_text)
        if tag == "style" and _CSS_EXTERNAL.search(text):
            self._resource("<style> の中の @import か url(外部のアドレス)")
        self._raw = None
        self._raw_text = []

    def _tag(self, message: str) -> None:
        self.tag_findings.append(HtmlFinding("HTML-TAG", message))

    def _resource(self, what: str) -> None:
        self.resource_findings.append(
            HtmlFinding("HTML-EXTERNAL-RESOURCE", f"外部の資源を読む部品がある: {what}")
        )


# --- 規則ごとの検査 ---------------------------------------------------------------


def _placeholders(html: str) -> list[HtmlFinding]:
    counts: dict[str, int] = {}
    for match in _PLACEHOLDER.finditer(html):
        counts[match[0]] = counts.get(match[0], 0) + 1
    return [
        HtmlFinding("HTML-PLACEHOLDER", f"差し込み口 {name} が残っている（{count} 箇所）")
        for name, count in counts.items()
    ]


def _ids(scanner: _Scanner) -> list[HtmlFinding]:
    found = [
        HtmlFinding("HTML-ID-DUPLICATE", f"id {value!r} が重なっている")
        for value, count in Counter(scanner.ids).items()
        if count > 1
    ]
    known = set(scanner.ids)
    # 脚注への参照（cite_note-）は HTML-FOOTNOTE-MISSING で報告する。
    targets = dict.fromkeys(t for t, _ in scanner.hash_links if t and not _is_footnote(t))
    found += [
        HtmlFinding("HTML-ANCHOR-MISSING", f"リンク先 #{target} に対応する id がない")
        for target in targets
        if target not in known
    ]
    return found


def _footnotes(scanner: _Scanner) -> list[HtmlFinding]:
    known = set(scanner.ids)
    found: list[HtmlFinding] = []

    reported: set[str] = set()
    for target, _ in scanner.hash_links:
        if _is_footnote(target) and target not in known and target not in reported:
            reported.add(target)
            found.append(
                HtmlFinding("HTML-FOOTNOTE-MISSING", f"存在しない脚注 #{target} への参照がある")
            )

    referenced = {target for target, _ in scanner.hash_links}
    found += [
        HtmlFinding("HTML-FOOTNOTE-UNREFERENCED", f"脚注 #{value} がどこからも参照されていない")
        for value in scanner.ids
        if _is_footnote(value) and value not in referenced
    ]

    for text in scanner.plain_text:
        found += [
            HtmlFinding(
                "HTML-FOOTNOTE-PLAIN",
                f"脚注番号 {match[0]} がリンクにならず文字のまま残っている",
            )
            for match in _PLAIN_NUMBER.finditer(text)
        ]

    found += _number_mismatches(scanner)
    return found


def _is_footnote(value: str) -> bool:
    """脚注の項目の id（またはそれへのリンク先）か。"""
    return _FOOTNOTE_ID.match(value) is not None


def _number_mismatches(scanner: _Scanner) -> list[HtmlFinding]:
    found: list[HtmlFinding] = []
    checked: set[tuple[str, str]] = set()
    for target, text in scanner.hash_links:
        item = _ITEM_ID.fullmatch(target)
        if item is None or (target, text) in checked:
            continue
        checked.add((target, text))
        shown = _LINK_TEXT.fullmatch(text.strip())
        expected = (item[1] is not None, item[2])
        if shown is None or (shown[1] is not None, shown[2]) != expected:
            label = f"[注 {item[2]}]" if item[1] else f"[{item[2]}]"
            found.append(
                HtmlFinding(
                    "HTML-FOOTNOTE-NUMBER",
                    f"脚注への参照の表示 {text.strip()!r} がリンク先 #{target} の番号"
                    f"（{label}）と合わない",
                )
            )
    for items in scanner.reference_lists:
        for position, value in enumerate(items, start=1):
            item = _ITEM_ID.fullmatch(value)
            if item is not None and int(item[2]) != position:
                found.append(
                    HtmlFinding(
                        "HTML-FOOTNOTE-NUMBER",
                        f"脚注の一覧の{position}番目の項目の id が #{value} で、番号が合わない",
                    )
                )
    return found
