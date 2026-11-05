"""原稿の類型と Infobox を、類型の定義と突き合わせる検査。

- 原稿の ``type`` が定義にない型 → エラー（``TYPE-UNKNOWN``）
- 定義の必須の項目が Infobox にない → エラー（``INFOBOX-MISSING``）
- 定義にない項目名が Infobox にある → 警告（``INFOBOX-UNKNOWN-FIELD``）
- 画像の項目の値が ``![キャプション](道)`` の形でない → エラー（``INFOBOX-IMAGE``）
- 画像の項目でない項目の値が ``![キャプション](道)`` の形 → 警告（``INFOBOX-IMAGE-UNDECLARED``）
- 画像の項目の画像にキャプションがない → 警告（``IMAGE-CAPTION``）
- 画像の項目の画像が読めない（無い・種類違い・大きすぎる） → エラー（``IMAGE-*``）
- ``[infobox]`` に ``_template`` がある（本家のテンプレートをそのまま使う）ときは、
  項目名が本家の引数名（か、その別名・ラベル）なので定義と突き合わせない。代わりに同梱の
  TemplateData（``assets/templatedata.toml``）があれば、解決できない項目名
  （``INFOBOX-UNKNOWN-FIELD``）と、必須の引数の欠け（``INFOBOX-MISSING``）を見る。
  同梱に無いテンプレートは素通しする。値が ``![キャプション](道)`` の形なら画像として扱い、
  キャプションと画像そのものだけを見る（``IMAGE-CAPTION``・``IMAGE-*``）

最初の二つは定義との突き合わせなので誤検出が無い。三つ目は、定義の項目が本家のテンプレートの
引数を全部は収録していない（番号つきの引数などを省いている）ため、正しい項目でも引っかかりうる。
そこで警告にとどめ、AI が定義の項目名と読み比べて直すか残すかを決める。
"""

from __future__ import annotations

from collections.abc import Iterator

from wikiskill.checks.finding import Finding, Level
from wikiskill.images import find_issue, split_value
from wikiskill.model import Article, InfoboxField
from wikiskill.templatedata import TemplateData, TemplateDataRegistry, load_default_templatedata
from wikiskill.types import ImageFormat, TypeRegistry

_NO_LINE = 1
"""読み取り結果が行を持たない指摘（``type`` や ``[infobox]`` の見出し）に使う、冒頭の行。"""


def _check_image(
    article: Article, item: InfoboxField, image_format: ImageFormat
) -> Iterator[Finding]:
    """画像の項目の値を検査する。

    形が違えば ``INFOBOX-IMAGE`` だけを返し、画像そのものは調べない。
    形が合っていればキャプションの有無（``IMAGE-CAPTION``）と、画像が読めるか（``IMAGE-*``）を見る。
    """
    parts = split_value(item.value)
    if parts is None:
        yield Finding(
            Level.ERROR,
            "INFOBOX-IMAGE",
            f"Infobox の「{item.name}」は画像の項目（書式 {image_format}）なので、"
            "![キャプション](道) の形で書く（道は原稿からの相対）",
            item.line,
        )
        return
    yield from _check_image_file(article, item, *parts)


def _check_image_file(
    article: Article, item: InfoboxField, caption: str, source: str
) -> Iterator[Finding]:
    """画像の値の形が合っているときの検査（キャプションの有無と、画像が読めるか）。"""
    if not caption:
        yield Finding(
            Level.WARNING,
            "IMAGE-CAPTION",
            f"Infobox の「{item.name}」の画像にキャプションがない"
            "（![キャプション](道) のキャプションを書く）",
            item.line,
        )
    issue = find_issue(source, article.base_dir)
    if issue is not None:
        yield Finding(Level.ERROR, issue[0], f"Infobox の「{item.name}」の{issue[1]}", item.line)


def _check_generic(article: Article, data: TemplateData | None) -> Iterator[Finding]:
    """本家のテンプレートをそのまま使うときの検査。

    項目名は本家の引数名か、その別名・ラベル。``data``（``_template`` の TemplateData）が
    あれば、解決できない項目名（``INFOBOX-UNKNOWN-FIELD``）と、必須の引数の欠け
    （``INFOBOX-MISSING``、型付きの Infobox と同じ重み）を見る。``data`` が無い（同梱に
    載っていない）テンプレートは、型の定義と同じく素通しする。引数が 0 件のテンプレートも、
    「引数なし」として未知扱いしない。
    """
    written = article.settings.infobox
    for item in written:
        parts = split_value(item.value)
        if parts is not None:
            yield from _check_image_file(article, item, *parts)
    if data is None or not data.params:
        return
    filled = {item.name for item in written if item.value.strip()}
    line = written[0].line if written else _NO_LINE
    for param in data.missing_required(filled):
        yield Finding(
            Level.ERROR,
            "INFOBOX-MISSING",
            f"{data.name} の Infobox に必須の項目「{param.heading}」がない（[infobox] に書く）",
            line,
        )
    for item in written:
        if data.resolve(item.name) is None:
            yield Finding(
                Level.WARNING,
                "INFOBOX-UNKNOWN-FIELD",
                f"Infobox の項目「{item.name}」は本家のテンプレート「{data.name}」の引数に"
                "ないので、ウィキテキストに書き出せない（引数名かラベルに直すか、本文に"
                "移すか、消す）",
                item.line,
            )


def check_infobox(
    article: Article, registry: TypeRegistry, *, templatedata: TemplateDataRegistry | None = None
) -> Iterator[Finding]:
    """原稿の類型と Infobox を、類型の定義と突き合わせて検査する。

    Parameters
    ----------
    article : Article
        検査する記事。
    registry : TypeRegistry
        突き合わせる類型の定義。
    templatedata : TemplateDataRegistry or None
        ``_template`` の引数の定義。省くと同梱の ``assets/templatedata.toml`` を使う。

    Yields
    ------
    Finding
        見つかった指摘。型が定義にないときは ``TYPE-UNKNOWN`` だけで、項目は検査しない。

    Notes
    -----
    読み取り結果は ``type`` の行と ``[infobox]`` の見出しの行を持たない。そのため
    ``TYPE-UNKNOWN`` は冒頭の行、``INFOBOX-MISSING`` は Infobox の最初の項目の行
    （項目が一つもなければ冒頭の行）を指す。
    """
    type_id = article.settings.type_id
    article_type = registry.find(type_id)
    if article_type is None:
        yield Finding(
            Level.ERROR,
            "TYPE-UNKNOWN",
            f"type {type_id!r} は類型の定義にない（docs/types.md の一覧にある ID を書く）",
            _NO_LINE,
        )
        return

    written = article.settings.infobox
    if article.settings.infobox_template:
        data_registry = load_default_templatedata() if templatedata is None else templatedata
        yield from _check_generic(article, data_registry.find(article.settings.infobox_template))
        return
    if article_type.has_infobox:
        filled = {item.name for item in written if item.value.strip()}
        line = written[0].line if written else _NO_LINE
        for field in article_type.required_fields:
            if field.label not in filled:
                yield Finding(
                    Level.ERROR,
                    "INFOBOX-MISSING",
                    f"{article_type.name}（{type_id}）の Infobox に必須の項目「{field.label}」"
                    "がない（[infobox] に書く）",
                    line,
                )

    for item in written:
        defined = article_type.find_field(item.name) if article_type.has_infobox else None
        if defined is not None:
            if defined.image is not None:
                yield from _check_image(article, item, defined.image)
            elif split_value(item.value) is not None:
                yield Finding(
                    Level.WARNING,
                    "INFOBOX-IMAGE-UNDECLARED",
                    f"Infobox の「{item.name}」は画像の項目として宣言されていないのに"
                    "![キャプション](道) の形になっている（値はそのままウィキテキストの引数に"
                    "入る。画像なら型の定義の image_fields に宣言する）",
                    item.line,
                )
            continue
        reason = (
            "定義にない"
            if article_type.has_infobox
            else f"{article_type.name}（{type_id}）は Infobox を持たない"
        )
        yield Finding(
            Level.WARNING,
            "INFOBOX-UNKNOWN-FIELD",
            f"Infobox の項目「{item.name}」は{reason}ので、ウィキテキストに書き出せない"
            "（定義の項目名に直すか、本文に移すか、消す）",
            item.line,
        )
