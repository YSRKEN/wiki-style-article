"""出典（:class:`~wikiskill.model.Reference`）を ``<ref>`` の中身の文字列にする。

- 本家の形: 日本語版の ``{{Cite web}}``・``{{Cite book}}``・``{{Cite news}}``。
  和書として第 1 引数に ``和書`` を置く
- 素の記法: テンプレートを使わず、書誌を地の文で書く。「著者「[URL 題名]」媒体、日付、閲覧日。」の形

どちらも ``<ref>`` の外側は呼び出す側が付ける。
"""

from __future__ import annotations

import re

from wikiskill.model import Reference, RefKind
from wikiskill.wikitext_escape import escape_text, external_link

_TEMPLATE_NAME: dict[RefKind, str] = {"web": "Cite web", "book": "Cite book", "news": "Cite news"}
_WORK_PARAM: dict[RefKind, str] = {"web": "website", "book": "series", "news": "newspaper"}
_TITLE_BRACKETS: dict[RefKind, tuple[str, str]] = {
    "web": ("「", "」"),
    "book": ("『", "』"),
    "news": ("「", "」"),
}
_PAGE_UNIT: dict[RefKind, str] = {"web": "頁", "book": "頁", "news": "面"}
_PAGE_LIST = re.compile(r"[-‐–—,、]")
_DATE_YMD = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_DATE_YM = re.compile(r"(\d{4})-(\d{1,2})")
_DATE_Y = re.compile(r"\d{4}")


def cite_template(ref: Reference) -> str:
    """出典を日本語版の Cite 系テンプレートで書く（本家の形）。

    Parameters
    ----------
    ref : Reference
        出典。空の項目は書かない。``note`` はテンプレートの直後に添える。

    Returns
    -------
    str
        ``{{Cite web |和書 |url=… |title=…}}`` の形の文字列。``<ref>`` の中に入れる。
    """
    pages_param = "pages" if ref.pages and _PAGE_LIST.search(ref.pages) else "page"
    params = (
        ("url", ref.url),
        ("title", ref.title),
        ("author", ref.author),
        (_WORK_PARAM[ref.kind], ref.work),
        ("publisher", ref.publisher),
        ("date", ref.date),
        (pages_param, ref.pages),
        ("isbn", ref.isbn),
        ("access-date", ref.access_date),
    )
    args = "".join(f" |{name}={escape_text(value, pipes=True)}" for name, value in params if value)
    note = escape_text(ref.note, pipes=True) if ref.note else ""
    return f"{{{{{_TEMPLATE_NAME[ref.kind]} |和書{args}}}}}{note}"


def cite_plain(ref: Reference) -> str:
    """出典を地の文で書く（素の記法）。

    形は「著者「[URL 題名]」媒体、発行者、日付、ページ、ISBN、閲覧日。」。書籍の題は『』、
    ウェブと新聞の題は「」で囲み、URL があれば題をリンクにする。新聞の媒体名は題の直後に『』で書く。
    日付は ``2020-09-01`` を ``2020年9月1日`` のように日本語の形に直す（直せない書き方はそのまま）。

    Parameters
    ----------
    ref : Reference
        出典。空の項目は書かない。``note`` は文末に添える。

    Returns
    -------
    str
        ``<ref>`` の中に入れる地の文。
    """
    opening, closing = _TITLE_BRACKETS[ref.kind]
    title = escape_text(ref.title, pipes=True).replace("]", "&#93;")
    shown = external_link(ref.url, ref.title) if ref.url else title
    head = _plain(ref.author) + opening + shown + closing
    work = _plain(ref.work)
    tail: list[str] = []
    if work and ref.kind == "news":
        head += f"『{work}』"
    elif work:
        tail.append(work)
    tail.append(_plain(ref.publisher))
    tail.append(japanese_date(_plain(ref.date)))
    if ref.pages:
        tail.append(_plain(ref.pages) + _PAGE_UNIT[ref.kind])
    if ref.isbn:
        tail.append(f"ISBN {_plain(ref.isbn)}")
    if ref.access_date:
        tail.append(japanese_date(_plain(ref.access_date)) + "閲覧")
    note = _plain(ref.note)
    return head + "、".join(t for t in tail if t) + "。" + note


def japanese_date(value: str) -> str:
    """``2020-09-01``・``2020-09``・``2020`` を日本語の日付に直す。ほかの書き方はそのまま返す。

    Parameters
    ----------
    value : str
        日付の文字列。

    Returns
    -------
    str
        ``2020年9月1日``・``2020年9月``・``2020年`` の形。直せなければ ``value`` のまま。
    """
    if m := _DATE_YMD.fullmatch(value):
        return f"{int(m[1])}年{int(m[2])}月{int(m[3])}日"
    if m := _DATE_YM.fullmatch(value):
        return f"{int(m[1])}年{int(m[2])}月"
    if _DATE_Y.fullmatch(value):
        return f"{int(value)}年"
    return value


def _plain(value: str | None) -> str:
    return escape_text(value, pipes=True) if value else ""
