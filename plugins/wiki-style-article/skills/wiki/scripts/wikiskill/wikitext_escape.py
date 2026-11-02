"""ウィキテキストへ書き出すときの文字の逃がし方。

原稿の文字は記法を含まない（記法は読み取りで部品に分けてある）ので、そのまま書くと
ウィキテキストの記法として読まれてしまう文字だけを、見た目の変わらない形に直す。
"""

from __future__ import annotations

import re

_EXTERNAL_SCHEME = re.compile(r"\[(?=(?:https?|ftp|ftps|sftp|mailto|news|irc|ircs|git|ssh|//))")
_LINE_START = ("*", "#", ":", ";", "=", " ", "----")
_URL_REPLACEMENTS = {
    " ": "%20",
    "[": "%5B",
    "]": "%5D",
    "|": "%7C",
    '"': "%22",
    "<": "%3C",
    ">": "%3E",
}


def escape_text(text: str, *, pipes: bool = False) -> str:
    """地の文の文字を、ウィキテキストの記法に読まれない形に直す。

    直すのは ``<``（タグ）・``{`` と ``}``（テンプレート）・URL の前の ``[``（外部リンク）。
    ``pipes`` を真にすると ``|`` も直す。テンプレートや ``{{#tag:}}`` の引数の中に書く文字列用。

    Parameters
    ----------
    text : str
        原稿の文字。
    pipes : bool
        ``|`` も ``&#124;`` に直すか。

    Returns
    -------
    str
        直した文字列。
    """
    out = text.replace("<", "&lt;").replace("{", "&#123;").replace("}", "&#125;")
    out = _EXTERNAL_SCHEME.sub("&#91;", out)
    if pipes:
        out = out.replace("|", "&#124;")
    return out


def guard_line_start(line: str) -> str:
    """行頭に置くと箇条書き・見出し・整形済みなどに読まれる文字で始まる行を、読まれないようにする。

    Parameters
    ----------
    line : str
        段落の一行、または箇条書きの一項目の中身。

    Returns
    -------
    str
        行頭が危ない文字なら ``<nowiki/>`` を前に付けた文字列。そうでなければそのまま。
    """
    return "<nowiki/>" + line if line.startswith(_LINE_START) else line


def escape_template_value(value: str) -> str:
    """テンプレートの引数や表のセルに書く値の、リンクとテンプレートの外にある ``|`` を直す。

    値はウィキテキストなので、``[[甲|乙]]`` や ``{{x|y}}`` の縦棒は
    引数の区切りではなく、そのまま残す。

    Parameters
    ----------
    value : str
        原稿の Infobox の値。

    Returns
    -------
    str
        外側の ``|`` を ``&#124;`` に直した文字列。
    """
    out: list[str] = []
    depth = 0
    i = 0
    while i < len(value):
        pair = value[i : i + 2]
        if pair in ("[[", "{{"):
            depth += 1
            out.append(pair)
            i += 2
        elif pair in ("]]", "}}") and depth > 0:
            depth -= 1
            out.append(pair)
            i += 2
        else:
            out.append("&#124;" if value[i] == "|" and depth == 0 else value[i])
            i += 1
    return "".join(out)


def external_link(url: str, label: str) -> str:
    """外部リンク ``[URL 表示]`` を書く。URL と表示の区切りは半角スペース。

    Parameters
    ----------
    url : str
        リンク先。空白や括弧などは ``%`` 表記に直す。
    label : str
        表示する文字。``]`` と ``|`` は直す。

    Returns
    -------
    str
        ``[URL 表示]`` の形の文字列。
    """
    safe_url = "".join(_URL_REPLACEMENTS.get(ch, ch) for ch in url)
    safe_label = escape_text(label, pipes=True).replace("]", "&#93;")
    return f"[{safe_url} {safe_label}]"
