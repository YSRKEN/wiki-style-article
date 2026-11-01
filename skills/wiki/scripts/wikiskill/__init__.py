"""日本語版 Wikipedia 風の記事を作るスキルのスクリプト群。

原稿の読み取りは :func:`read_article`・:func:`read_article_file` から使う。
読み取り結果のデータ型は :mod:`wikiskill.model`、例外は :mod:`wikiskill.errors` にある。
類型の定義は :func:`load_default_registry`、原稿の検査は :func:`check_article` から使う。
"""

from wikiskill.checks import Finding, Level, check_article
from wikiskill.errors import FrontMatterError, MarkupError, SettingsError, SourceError
from wikiskill.model import Article
from wikiskill.reader import read_article, read_article_file
from wikiskill.types import (
    ArticleType,
    TypeRegistry,
    TypeRegistryError,
    UnknownTypeError,
    load_default_registry,
)

__all__ = [
    "Article",
    "ArticleType",
    "Finding",
    "FrontMatterError",
    "Level",
    "MarkupError",
    "SettingsError",
    "SourceError",
    "TypeRegistry",
    "TypeRegistryError",
    "UnknownTypeError",
    "check_article",
    "load_default_registry",
    "read_article",
    "read_article_file",
]
