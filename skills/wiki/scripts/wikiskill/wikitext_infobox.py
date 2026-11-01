"""原稿の ``[infobox]`` をウィキテキストにする。

- 本家の形: 類型の定義に従って、日本語の項目名をテンプレートの引数名に写し、
  Infobox テンプレートを重ねる
- 素の記法: テンプレートを使わず、日本語の項目名のまま ``{| class="infobox"`` の表にする

値が空の項目は「書かれていない」ものとして扱う。Infobox テンプレートに書き出せない項目
（類型の定義にない項目名、Infobox を持たない類型の項目）は捨てずに HTML コメントで残す。
"""

from __future__ import annotations

from dataclasses import dataclass

from wikiskill.model import InfoboxField, Settings
from wikiskill.types import ArticleType, InfoboxPart
from wikiskill.wikitext_escape import escape_template_value

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
    known = {f.label for f in article_type.fields}
    return tuple(f.name for f in written_items(settings) if f.name not in known)


def build_infobox(
    settings: Settings, article_type: ArticleType, *, plain: bool = False
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
    return _wikipedia(settings, article_type, items)


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
        rows += ["|-", _LABEL_CELL + field.name, "| " + escape_template_value(field.value.strip())]
    rows.append("|}")
    table = "\n".join(rows)
    if article_type.infobox[0].placement == "lead":
        return InfoboxText(lead=table)
    return InfoboxText(top=table)


# --- 共通 -------------------------------------------------------------------------


def _dropped_comment(dropped: list[tuple[str, str]]) -> str:
    """書き出せなかった項目を HTML コメントにする。コメントの中に ``--`` は書けないので直す。"""
    lines = ["<!-- Infobox に書き出せなかった項目:"]
    lines += [f"{name} = {value}".replace("--", "- -") for name, value in dropped]
    lines.append("-->")
    return "\n".join(lines)
