"""脚注の印と出典・注釈の一覧の対応、出典の中身の検査。

どれも誤検出の余地が小さい（印と定義の突き合わせ、書式、ホスト名）ので、原則エラーにする。
例外は出典の題や発行元がウィキペディアを名乗るだけの場合で、実在の書名に含まれうるため警告にする。
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date
from urllib.parse import urlsplit

from wikiskill.checks.finding import Finding, Level
from wikiskill.checks.walk import flatten, iter_inline_groups
from wikiskill.model import Article, NoteMark, Reference, RefMark

WIKIPEDIA_HOSTS: tuple[str, ...] = (
    "wikipedia.org",
    "wikiwand.com",
    "wapedia.mobi",
    "wiki5.ru",
    "wpanda.net",
    "findwiki.info",
    "jibiki.info",
    "wikipedia.7val.com",
)
"""出典にしてはいけないホスト（とそのサブドメイン）。

ウィキペディア本体（他言語版・モバイル版を含む ``wikipedia.org``）と、
「Wikipedia:ウィキペディアを情報源とするサイト」が転載サイトとして挙げるもののうち、
転載が主であるもの。Weblio はウィキペディアの写しを他の辞書と同じ
``www.weblio.jp/content/`` に並べており、ホスト名では見分けられないため含めない。
"""

_WIKIPEDIA_NAME = re.compile(r"wikipedia|wikiwand|ウィキペディア|フリー百科事典", re.IGNORECASE)
_DATE_FULL = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_DATE_MONTH = re.compile(r"(\d{4})-(0[1-9]|1[0-2])")
_DATE_YEAR = re.compile(r"\d{4}")


def check_references(article: Article) -> Iterator[Finding]:
    """脚注の印と一覧の対応、出典・外部リンクの中身を検査する。"""
    yield from _check_marks(article)
    for reference in article.settings.references:
        yield from _check_reference(reference)
    for link in article.settings.external_links:
        if not is_http_url(link.url):
            yield Finding(
                Level.ERROR,
                "LINK-URL",
                f"外部リンクの url {link.url!r} が http:// か https:// で始まる"
                "アドレスになっていない",
                link.line,
            )


def _check_marks(article: Article) -> Iterator[Finding]:
    ref_keys = {reference.key for reference in article.settings.references}
    note_keys = {note.key for note in article.settings.notes}
    used_refs: set[str] = set()
    used_notes: set[str] = set()

    for parts, line in iter_inline_groups(article):
        for part in flatten(parts):
            if isinstance(part, RefMark):
                used_refs.add(part.key)
                if part.key not in ref_keys:
                    yield Finding(
                        Level.ERROR,
                        "REF-UNDEFINED",
                        f"脚注の印 [^{part.key}] に対応する [refs.{part.key}] が設定欄にない",
                        line,
                    )
            elif isinstance(part, NoteMark):
                used_notes.add(part.key)
                if part.key not in note_keys:
                    yield Finding(
                        Level.ERROR,
                        "NOTE-UNDEFINED",
                        f"注釈の印 [^n:{part.key}] に対応する [notes.{part.key}] が設定欄にない",
                        line,
                    )

    for reference in article.settings.references:
        if reference.key not in used_refs:
            yield Finding(
                Level.ERROR,
                "REF-UNUSED",
                f"出典 [refs.{reference.key}] が本文でも注釈でも使われていない"
                f"（[^{reference.key}] を付けるか、定義を消す）",
                reference.line,
            )
    for note in article.settings.notes:
        if note.key not in used_notes:
            yield Finding(
                Level.ERROR,
                "NOTE-UNUSED",
                f"注釈 [notes.{note.key}] が本文で使われていない"
                f"（[^n:{note.key}] を付けるか、定義を消す）",
                note.line,
            )


def _check_reference(reference: Reference) -> Iterator[Finding]:
    key = reference.key
    wikipedia_url = False
    if reference.url is not None:
        if not is_http_url(reference.url):
            yield Finding(
                Level.ERROR,
                "REF-URL",
                f"[refs.{key}] の url {reference.url!r} が http:// か https:// で始まる"
                "アドレスになっていない",
                reference.line_of("url"),
            )
        elif is_wikipedia_url(reference.url):
            wikipedia_url = True
            yield Finding(
                Level.ERROR,
                "REF-WIKIPEDIA",
                f"[refs.{key}] がウィキペディア（他言語版・転載サイトを含む）を出典にしている: "
                f"{reference.url}（循環した出典になる。元になった一次の資料に当たる）",
                reference.line_of("url"),
            )

    if not wikipedia_url:
        for name in ("title", "publisher", "work"):
            value: str | None = getattr(reference, name)
            if value is not None and _WIKIPEDIA_NAME.search(value):
                yield Finding(
                    Level.WARNING,
                    "REF-WIKIPEDIA-NAME",
                    f"[refs.{key}] の {name} {value!r} がウィキペディアを名乗っている。"
                    "ウィキペディア自身や転載を出典にしていないか確かめる",
                    reference.line_of(name),
                )
                break

    if reference.date is not None and not is_partial_date(reference.date):
        yield Finding(
            Level.ERROR,
            "REF-DATE",
            f"[refs.{key}] の date {reference.date!r} は YYYY-MM-DD・YYYY-MM・YYYY の"
            "どれかの形（0 詰めの半角）で、実在する日付にする",
            reference.line_of("date"),
        )
    if reference.access_date is not None and not is_full_date(reference.access_date):
        yield Finding(
            Level.ERROR,
            "REF-ACCESS-DATE",
            f"[refs.{key}] の access_date {reference.access_date!r} は YYYY-MM-DD の形"
            "（0 詰めの半角で、実在する日付）にする",
            reference.line_of("access_date"),
        )


def is_http_url(url: str) -> bool:
    """``http://`` か ``https://`` で始まり、ホスト名があり、空白を含まない。"""
    if re.search(r"\s", url):
        return False
    try:
        parts = urlsplit(url)
        return parts.scheme in ("http", "https") and bool(parts.hostname)
    except ValueError:
        return False


def is_wikipedia_url(url: str) -> bool:
    """ホスト名が :data:`WIKIPEDIA_HOSTS` のいずれか（のサブドメイン）に当たる。"""
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return False
    if not host:
        return False
    return any(host == known or host.endswith("." + known) for known in WIKIPEDIA_HOSTS)


def is_full_date(text: str) -> bool:
    """``YYYY-MM-DD`` の形で、実在する日付。"""
    found = _DATE_FULL.fullmatch(text)
    if found is None:
        return False
    try:
        date(int(found[1]), int(found[2]), int(found[3]))
    except ValueError:
        return False
    return True


def is_partial_date(text: str) -> bool:
    """``YYYY-MM-DD``・``YYYY-MM``・``YYYY`` のどれかの形で、実在する日付。"""
    return bool(_DATE_YEAR.fullmatch(text) or _DATE_MONTH.fullmatch(text) or is_full_date(text))
