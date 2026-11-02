"""原稿の ``[infobox]`` を、右寄せの Infobox の表（HTML）にする。

- 行の並びは類型の定義の順。項目名は日本語のまま表の見出しセルに出す
- 定義にない項目は、定義の項目の後ろに原稿に書いた順で並べる（捨てない）
- Infobox を持たない類型では出さない。値のある項目が一つもなければ出さない
- 定義の ``title_field`` の項目は行にせず、表の見出し（caption）にする。原稿に書かれていなければ
  記事名が見出しになる（ウィキテキストの書き出しが記事名で埋めるのと同じ）
- 値の空白だけの項目は「書かれていない」ものとして扱う

値はウィキテキストの記法で書かれうる（``[[リンク]]``・``<br />``）ので、内部リンク・太字・改行だけを
HTML にし、ほかは文字のまま出す。記法が壊れている値も文字のまま出す。
"""

from __future__ import annotations

import re

from wikiskill.errors import MarkupError
from wikiskill.html_escape import escape
from wikiskill.html_inline import InlineWriter
from wikiskill.inline import parse_inline
from wikiskill.model import InfoboxField, Settings
from wikiskill.types import ArticleType

_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)


def build_infobox_html(settings: Settings, article_type: ArticleType) -> str:
    """Infobox の表を書き出す。

    Parameters
    ----------
    settings : Settings
        原稿の設定欄。
    article_type : ArticleType
        記事の類型。

    Returns
    -------
    str
        ``<table class="infobox">``。出さないときは空文字列。
    """
    if not article_type.has_infobox:
        return ""
    written = {f.name: f for f in settings.infobox if f.value.strip()}
    if not written:
        return ""

    title_labels = [p.title_field for p in article_type.infobox if p.title_field]
    caption = next(
        (_value(written[label].value) for label in title_labels if label in written),
        escape(settings.title),
    )
    defined = [f.label for f in article_type.fields]
    order = [name for name in defined if name in written and name not in title_labels]
    order += [name for name in written if name not in defined]

    rows = "\n".join(_row(written[name]) for name in order)
    body = f"\n{rows}" if rows else ""
    return f'<table class="infobox">\n<caption>{caption}</caption>{body}\n</table>'


def _row(item: InfoboxField) -> str:
    return f'<tr><th scope="row">{escape(item.name)}</th><td>{_value(item.value)}</td></tr>'


def _value(value: str) -> str:
    """値を HTML にする。``<br />`` で行を分け、各行の内部リンク・太字を書き出す。"""
    writer = InlineWriter()
    lines: list[str] = []
    for piece in _BREAK.split(value.strip()):
        text = piece.strip()
        try:
            lines.append(writer.inline(parse_inline(text)))
        except MarkupError:
            lines.append(escape(text))
    return "<br>".join(lines)
