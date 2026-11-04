"""原稿の ``[infobox]`` を、右寄せの Infobox の表（HTML）にする。

- 行の並びは類型の定義の順。項目名は日本語のまま表の見出しセルに出す
- 定義にない項目は、定義の項目の後ろに原稿に書いた順で並べる（捨てない）
- Infobox を持たない類型では出さない。値のある項目が一つもなければ出さない
- ``[infobox]`` に ``_template`` があれば、本家のテンプレートをそのまま使う書き方として、
  定義に関係なく書かれた項目をすべて並べる（見出しは項目名のまま）。値が
  ``![キャプション](道)`` なら画像として埋め込む
- 定義の ``title_field`` の項目は行にせず、表の見出し（caption）にする。原稿に書かれていなければ
  記事名が見出しになる（ウィキテキストの書き出しが記事名で埋めるのと同じ）
- 値の空白だけの項目は「書かれていない」ものとして扱う

値はウィキテキストの記法で書かれうる（``[[リンク]]``・``<br />``）ので、内部リンク・太字・改行だけを
HTML にし、ほかは文字のまま出す。記法が壊れている値も文字のまま出す。

画像の項目（定義の ``image_fields``）は、値が ``![キャプション](道)`` なら画像として埋め込む。
形の違う値は文字のまま出す（書式の誤りは検査が指摘する）。
"""

from __future__ import annotations

import re
from pathlib import Path

from wikiskill.errors import MarkupError
from wikiskill.html_escape import escape
from wikiskill.html_inline import InlineWriter, figure_html
from wikiskill.images import split_value
from wikiskill.inline import parse_inline
from wikiskill.model import Figure, InfoboxField, Settings
from wikiskill.types import ArticleType

_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)


def build_infobox_html(
    settings: Settings, article_type: ArticleType, *, base_dir: Path | None = None
) -> str:
    """Infobox の表を書き出す。

    Parameters
    ----------
    settings : Settings
        原稿の設定欄。
    article_type : ArticleType
        記事の類型。
    base_dir : Path | None
        画像の道を解く基準のディレクトリ（原稿のあるディレクトリ）。

    Returns
    -------
    str
        ``<table class="infobox">``。出さないときは空文字列。
    """
    if settings.infobox_template:
        return _generic(settings, base_dir)
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

    rows = "\n".join(_row(written[name], article_type, base_dir) for name in order)
    body = f"\n{rows}" if rows else ""
    return f'<table class="infobox">\n<caption>{caption}</caption>{body}\n</table>'


def _generic(settings: Settings, base_dir: Path | None) -> str:
    """本家のテンプレートをそのまま使うときの表。項目名をそのまま見出しにする。"""
    written = [f for f in settings.infobox if f.value.strip()]
    if not written:
        return ""
    rows = "\n".join(_generic_row(item, base_dir) for item in written)
    return f'<table class="infobox">\n<caption>{escape(settings.title)}</caption>\n{rows}\n</table>'


def _generic_row(item: InfoboxField, base_dir: Path | None) -> str:
    cell = _image_value(item, base_dir)
    if cell is None:
        cell = _value(item.value)
    return f'<tr><th scope="row">{escape(item.name)}</th><td>{cell}</td></tr>'


def _row(item: InfoboxField, article_type: ArticleType, base_dir: Path | None) -> str:
    cell = _image(item, article_type, base_dir)
    if cell is None:
        cell = _value(item.value)
    return f'<tr><th scope="row">{escape(item.name)}</th><td>{cell}</td></tr>'


def _image(item: InfoboxField, article_type: ArticleType, base_dir: Path | None) -> str | None:
    """画像の項目なら画像の HTML を返す。そうでないときと値の形が違うときは None。"""
    field = article_type.find_field(item.name)
    if field is None or field.image is None:
        return None
    return _image_value(item, base_dir)


def _image_value(item: InfoboxField, base_dir: Path | None) -> str | None:
    """値が ``![キャプション](道)`` なら画像の HTML を返す。違う形のときは None。"""
    parts = split_value(item.value)
    if parts is None:
        return None
    caption, source = parts
    figure = Figure(caption=caption, source=source, line=item.line)
    return figure_html(figure, base_dir)


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
