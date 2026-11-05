"""原稿の ``[infobox]`` をウィキテキストにする。

- 本家の形: 類型の定義に従って、日本語の項目名をテンプレートの引数名に写し、
  Infobox テンプレートを重ねる
- 素の記法: テンプレートを使わず、日本語の項目名のまま ``{| class="infobox"`` の表にする
- 本家のテンプレートをそのまま使う: ``[infobox]`` に ``_template`` があれば、残りの項目名を
  本家の引数名として ``{{テンプレート名|引数 = 値}}`` にする（``plain`` のときは表のまま）。
  項目名は、同梱の TemplateData（``assets/templatedata.toml``）があれば引数名・別名・ラベルで
  解決し、ウィキテキストには必ず引数名で出す。TemplateData の型が ``wiki-file-name`` の引数は、
  ``_image_fields`` を書いていないとき ``name`` の書式（ファイル名だけを渡す）にする

値が空の項目は「書かれていない」ものとして扱う。Infobox テンプレートに書き出せない項目
（類型の定義にない項目名、Infobox を持たない類型の項目）は捨てずに HTML コメントで残す。

画像の項目（定義の ``image_fields``）は、値の ``![キャプション](道)`` を定義の書式に従って
``名前だけ`` または ``[[ファイル:名前|thumb|キャプション]]`` にする。形の違う値はそのまま出す。
"""

from __future__ import annotations

from dataclasses import dataclass

from wikiskill.images import file_name, split_value
from wikiskill.model import InfoboxField, Settings
from wikiskill.templatedata import TemplateData, TemplateDataRegistry, load_default_templatedata
from wikiskill.types import ArticleType, ImageFormat, InfoboxPart
from wikiskill.wikitext_escape import escape_template_value, escape_text

_TABLE_OPEN = (
    '{| class="infobox" cellpadding="4" style="float: right; clear: right; width: 22em; '
    "margin: 0 0 1em 1em; border: 1px solid #a2a9b1; border-collapse: collapse; "
    'background-color: #f8f9fa; font-size: 90%;"'
)
_TITLE_ROW = '! colspan="2" style="background-color: #ccf; text-align: center;" | '
_LABEL_CELL = '! scope="row" style="text-align: left; vertical-align: top;" | '


@dataclass(frozen=True)
class InfoboxText:
    """書き出した Infobox。置き場所ごとに分けてある。

    Attributes
    ----------
    top : str
        記事の最上部（導入部の前）に置く分。なければ空文字列。
    lead : str
        導入部の中（第一段落の前）に置く分。なければ空文字列。
    """

    top: str = ""
    lead: str = ""


def written_items(settings: Settings) -> tuple[InfoboxField, ...]:
    """値が空でない Infobox の項目を、原稿に書いた順に返す。"""
    return tuple(f for f in settings.infobox if f.value.strip())


def unknown_labels(settings: Settings, article_type: ArticleType) -> tuple[str, ...]:
    """類型の定義にない項目名を、原稿に書いた順に返す。値が空の項目は数えない。

    Infobox を持たない類型では、書かれた項目名がすべて対象になる。
    """
    if settings.infobox_template:
        # 本家のテンプレートをそのまま使うときは、項目名がすべて引数名なので捨てる項目はない。
        return ()
    known = {f.label for f in article_type.fields}
    return tuple(f.name for f in written_items(settings) if f.name not in known)


def build_infobox(
    settings: Settings,
    article_type: ArticleType,
    *,
    plain: bool = False,
    templatedata: TemplateDataRegistry | None = None,
) -> InfoboxText:
    """Infobox を書き出す。

    Parameters
    ----------
    settings : Settings
        原稿の設定欄。
    article_type : ArticleType
        記事の類型。
    plain : bool
        真なら素の記法（表）、偽なら本家の形（テンプレート）。
    templatedata : TemplateDataRegistry or None
        ``_template`` の引数の定義。省くと同梱の ``assets/templatedata.toml`` を使う。

    Returns
    -------
    InfoboxText
        置き場所ごとのウィキテキスト。値のある項目が一つもなければ、どちらも空。
    """
    items = written_items(settings)
    if not items:
        return InfoboxText()
    if plain:
        return _plain(settings, article_type, items)
    if settings.infobox_template:
        registry = load_default_templatedata() if templatedata is None else templatedata
        return _generic(
            settings.infobox_template,
            items,
            settings.infobox_images,
            registry.find(settings.infobox_template),
        )
    return _wikipedia(settings, article_type, items)


# --- 本家のテンプレートをそのまま使う -------------------------------------------------


def _generic(
    name: str,
    items: tuple[InfoboxField, ...],
    image_names: tuple[str, ...] = (),
    data: TemplateData | None = None,
) -> InfoboxText:
    """項目名を本家の引数名として、テンプレートをそのまま組む。

    値は既定で ``file`` の書式として扱う。``![キャプション](道)`` は
    ``[[ファイル:名前|thumb|キャプション]]`` になり、素のファイル名やそのほかの値はそのまま渡る。
    ``image_names``（``[infobox]`` の ``_image_fields``）に並べた引数は ``name`` の書式にして、
    ファイル名だけを渡す（本家が ``File:`` を包む引数）。

    ``data``（``_template`` の TemplateData）があれば、項目名を引数名・別名・ラベルの順に解決し、
    ウィキテキストには引数名で出す。``_image_fields`` が無いときは、型が ``wiki-file-name`` の
    引数を ``name`` の書式にする。
    """
    image_fields = set(image_names)
    if data is not None and not image_names:
        image_fields |= set(data.image_params(item.name for item in items))
    lines = [f"{{{{{name}"]
    for item in items:
        param = data.resolve(item.name) if data is not None else None
        arg_name = param.name if param is not None else item.name
        image_format: ImageFormat | None = (
            "name" if arg_name in image_fields or item.name in image_fields else "file"
        )
        value = _render_value(image_format, item.value.strip())
        lines.append(f"| {arg_name} = {escape_template_value(value)}")
    lines.append("}}")
    return InfoboxText(top="\n".join(lines))


# --- 本家の形 ---------------------------------------------------------------------


def _wikipedia(
    settings: Settings, article_type: ArticleType, items: tuple[InfoboxField, ...]
) -> InfoboxText:
    values = {f.name: f.value.strip() for f in items}
    placed: dict[str, list[str]] = {"top": [], "lead": []}
    for part in article_type.infobox:
        placed[part.placement].append(_template(part, values, settings.title))
    # 定義にない項目は、最後の部品の直後に（部品がなければ最上部に）コメントとして残す。
    dropped = [(name, values[name]) for name in unknown_labels(settings, article_type)]
    if dropped:
        place = article_type.infobox[-1].placement if article_type.infobox else "top"
        placed[place].append(_dropped_comment(dropped))
    return InfoboxText(top="\n".join(placed["top"]), lead="\n".join(placed["lead"]))


def _template(part: InfoboxPart, values: dict[str, str], title: str) -> str:
    lines: list[str] = []
    for field in part.fields:
        value = values.get(field.label)
        if value is None and field.label == part.title_field:
            value = title
        if value is not None:
            value = _render_value(field.image, value)
            lines.append(f"| {field.param} = {escape_template_value(value)}")
    if not lines:
        return f"{{{{{part.template}}}}}"
    return "\n".join([f"{{{{{part.template}", *lines, "}}"])


# --- 素の記法 ---------------------------------------------------------------------


def _plain(
    settings: Settings, article_type: ArticleType, items: tuple[InfoboxField, ...]
) -> InfoboxText:
    if not article_type.has_infobox:
        comment = _dropped_comment([(f.name, f.value.strip()) for f in items])
        return InfoboxText(top=comment)
    rows = [_TABLE_OPEN, "|-", _TITLE_ROW + settings.title]
    for field in items:
        defined = article_type.find_field(field.name)
        image_format = defined.image if defined is not None else None
        value = _render_value(image_format, field.value.strip())
        rows += ["|-", _LABEL_CELL + field.name, "| " + escape_template_value(value)]
    rows.append("|}")
    table = "\n".join(rows)
    if article_type.infobox[0].placement == "lead":
        return InfoboxText(lead=table)
    return InfoboxText(top=table)


# --- 共通 -------------------------------------------------------------------------


def _render_value(image_format: ImageFormat | None, value: str) -> str:
    """画像の項目なら、書式に従ったウィキテキストにする。形の違う値はそのまま返す。"""
    if image_format is None:
        return value
    parts = split_value(value)
    if parts is None:
        return value
    caption, source = parts
    name = _link_safe(file_name(source))
    if image_format == "name":
        return name
    if not caption:
        return f"[[ファイル:{name}|thumb]]"
    return f"[[ファイル:{name}|thumb|{_link_safe(caption)}]]"


def _link_safe(text: str) -> str:
    """``[[...]]`` の中に置く文字がリンクを閉じないように直す。"""
    return escape_text(text, pipes=True).replace("]", "&#93;")


def _dropped_comment(dropped: list[tuple[str, str]]) -> str:
    """書き出せなかった項目を HTML コメントにする。コメントの中に ``--`` は書けないので直す。"""
    lines = ["<!-- Infobox に書き出せなかった項目:"]
    lines += [f"{name} = {value}".replace("--", "- -") for name, value in dropped]
    lines.append("-->")
    return "\n".join(lines)
