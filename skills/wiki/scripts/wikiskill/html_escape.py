"""HTML へ書き出すときの文字の逃がし方と、リンク先の作り方。

原稿の文字は記法を含まない（記法は読み取りで部品に分けてある）ので、HTML の記法として読まれる
文字をすべて逃がす。``{`` と ``}`` も数値参照にして、雛形の差し込み口 ``{{名前}}`` と
本文の文字が取り違えられないようにする。
"""

from __future__ import annotations

from urllib.parse import quote

WIKI_BASE = "https://ja.wikipedia.org/wiki/"
"""内部リンクの張り先。本家には問い合わせず、アドレスを組み立てるだけに使う。"""

_ESCAPES = (
    ("&", "&amp;"),
    ("<", "&lt;"),
    (">", "&gt;"),
    ('"', "&quot;"),
    ("{", "&#123;"),
    ("}", "&#125;"),
)
_URL_SAFE = "!#$%&'()*+,/:;=?@[]~"


def escape(text: str) -> str:
    """地の文と属性値の文字を、HTML の記法に読まれない形に直す。

    Parameters
    ----------
    text : str
        原稿の文字。

    Returns
    -------
    str
        ``& < > "`` と ``{ }`` を文字参照に直した文字列。属性値（二重引用符で囲む）にも使える。
    """
    for char, entity in _ESCAPES:
        text = text.replace(char, entity)
    return text


def external_href(url: str) -> str | None:
    """外部リンクのアドレスを、属性値に入れられる形にする。

    ``http://`` と ``https://`` 以外（``javascript:`` など）はリンクにしないので None を返す。
    空白や非 ASCII の文字は ``%`` 表記に直し、すでにある ``%`` 表記は保つ。

    Parameters
    ----------
    url : str
        原稿のアドレス。

    Returns
    -------
    str | None
        逃がし済みのアドレス。リンクにできないなら None。
    """
    stripped = url.strip()
    if not stripped.lower().startswith(("http://", "https://")):
        return None
    return escape(quote(stripped, safe=_URL_SAFE + "%-._"))


def wiki_href(target: str) -> str:
    """内部リンクの記事名から、本家の記事へのアドレスを作る（属性値に入れられる形）。

    スペースは下線にし、日本語などは ``%`` 表記に直す。``#`` 以降は節の指定として分ける。

    Parameters
    ----------
    target : str
        記事名。``記事名#節`` の形でもよい。

    Returns
    -------
    str
        ``https://ja.wikipedia.org/wiki/…`` の形のアドレス。
    """
    page, hash_mark, fragment = target.partition("#")
    href = WIKI_BASE + quote(page.strip().replace(" ", "_"), safe="_/():")
    if hash_mark and fragment.strip():
        href += "#" + quote(fragment.strip().replace(" ", "_"), safe="_")
    return escape(href)
