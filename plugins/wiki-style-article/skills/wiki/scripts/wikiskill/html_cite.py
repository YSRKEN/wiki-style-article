"""出典（:class:`~wikiskill.model.Reference`）を脚注欄の一行の HTML にする。

書き方は、ウィキテキストの素の記法（``docs/wikitext.md`` の「出典の地の文」）と同じ。
「著者「題名」媒体、発行者、日付、ページ、ISBN、閲覧日。備考」の形で、``url`` があれば題名を
リンクにする。題は web・news が「」、book が『』。news の媒体名は題の直後に『』で書く。
日付は ``2020-09-01`` を ``2020年9月1日`` のように日本語の形に直す。
"""

from __future__ import annotations

from wikiskill.html_escape import escape, external_href
from wikiskill.model import Reference, RefKind
from wikiskill.wikitext_cite import japanese_date

_TITLE_BRACKETS: dict[RefKind, tuple[str, str]] = {
    "web": ("「", "」"),
    "book": ("『", "』"),
    "news": ("「", "」"),
}
_PAGE_UNIT: dict[RefKind, str] = {"web": "頁", "book": "頁", "news": "面"}


def cite_html(ref: Reference) -> str:
    """出典を、脚注欄に入れる書誌の HTML にする。

    Parameters
    ----------
    ref : Reference
        出典。空の項目は書かない。``note`` は文末に添える。

    Returns
    -------
    str
        逃がし済みの HTML（``<span class="reference-text">`` の中身）。
    """
    opening, closing = _TITLE_BRACKETS[ref.kind]
    head = _text(ref.author) + opening + _title(ref) + closing
    work = _text(ref.work)
    tail: list[str] = []
    if work and ref.kind == "news":
        head += f"『{work}』"
    elif work:
        tail.append(work)
    tail.append(_text(ref.publisher))
    tail.append(_date(ref.date))
    if ref.pages:
        tail.append(_text(ref.pages) + _PAGE_UNIT[ref.kind])
    if ref.isbn:
        tail.append(f"ISBN {_text(ref.isbn)}")
    if ref.access_date:
        tail.append(_date(ref.access_date) + "閲覧")
    return head + "、".join(t for t in tail if t) + "。" + _text(ref.note)


def _title(ref: Reference) -> str:
    href = external_href(ref.url) if ref.url else None
    if href is None:
        return escape(ref.title)
    return f'<a class="external" rel="nofollow" href="{href}">{escape(ref.title)}</a>'


def _text(value: str | None) -> str:
    return escape(value) if value else ""


def _date(value: str | None) -> str:
    return escape(japanese_date(value)) if value else ""
