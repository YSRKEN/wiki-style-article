"""日本語版 Wikipedia 風の記事を作るスキルのスクリプト群。

原稿の読み取りは :func:`read_article`・:func:`read_article_file` から使う。
読み取り結果のデータ型は :mod:`wikiskill.model`、例外は :mod:`wikiskill.errors` にある。
類型の定義は :func:`load_default_registry`、原稿の検査は :func:`check_article` から使う。
書き出しは :func:`write_wikitext`・:func:`write_html`、HTML の検査は :func:`check_html` から使う。
噂のある原稿は :func:`has_rumor` で見分け、:func:`normal_view`・:func:`rumor_view` で二つの版に
分ける。検査は :func:`check_article_variants`、HTML は :func:`write_html_both` で一枚に入れる。
読み取りから書き出しまでを 1 回で流すコマンドは :mod:`wikiskill.cli`（``python -m wikiskill``）。
"""

from wikiskill.checks import Finding, Level, check_article, check_article_variants
from wikiskill.errors import FrontMatterError, MarkupError, SettingsError, SourceError
from wikiskill.html_check import HtmlFinding, check_html
from wikiskill.html_writer import write_html, write_html_both
from wikiskill.model import Article
from wikiskill.reader import read_article, read_article_file
from wikiskill.types import (
    ArticleType,
    TypeRegistry,
    TypeRegistryError,
    UnknownTypeError,
    load_default_registry,
)
from wikiskill.variants import has_rumor, normal_view, rumor_view
from wikiskill.wikitext import write_wikitext

__all__ = [
    "Article",
    "ArticleType",
    "Finding",
    "HtmlFinding",
    "FrontMatterError",
    "Level",
    "MarkupError",
    "SettingsError",
    "SourceError",
    "TypeRegistry",
    "TypeRegistryError",
    "UnknownTypeError",
    "check_article",
    "check_article_variants",
    "check_html",
    "has_rumor",
    "load_default_registry",
    "normal_view",
    "read_article",
    "read_article_file",
    "rumor_view",
    "write_html",
    "write_html_both",
    "write_wikitext",
]
