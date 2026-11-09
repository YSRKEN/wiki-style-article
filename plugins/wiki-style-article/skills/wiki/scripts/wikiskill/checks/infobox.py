"""原稿の類型と Infobox を、類型の定義と突き合わせる検査。

- 原稿の ``type`` が定義にない型 → エラー（``TYPE-UNKNOWN``）
- 定義の必須の項目が Infobox にない → エラー（``INFOBOX-MISSING``）
- 定義にない項目名が Infobox にある → 警告（``INFOBOX-UNKNOWN-FIELD``）
- 画像の項目の値が ``![キャプション](道)`` の形でない → エラー（``INFOBOX-IMAGE``）
- 画像の項目の画像にキャプションがない → 警告（``IMAGE-CAPTION``）
- 画像の項目の画像が読めない（無い・種類違い・大きすぎる） → エラー（``IMAGE-*``）

最初の二つは定義との突き合わせなので誤検出が無い。三つ目は、定義の項目が本家のテンプレートの
引数を全部は収録していない（番号つきの引数などを省いている）ため、正しい項目でも引っかかりうる。
そこで警告にとどめ、AI が定義の項目名と読み比べて直すか残すかを決める。
"""

from __future__ import annotations

from collections.abc import Iterator

from wikiskill.checks.finding import Finding, Level
from wikiskill.images import find_issue, split_value
from wikiskill.model import Article, InfoboxField
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
    caption, source = parts
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


def check_infobox(article: Article, registry: TypeRegistry) -> Iterator[Finding]:
    """原稿の類型と Infobox を、類型の定義と突き合わせて検査する。

    Parameters
    ----------
    article : Article
        検査する記事。
    registry : TypeRegistry
        突き合わせる類型の定義。

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
