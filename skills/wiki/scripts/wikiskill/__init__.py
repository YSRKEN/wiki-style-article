"""日本語版 Wikipedia 風の記事を作るスキルのスクリプト群。

原稿の読み取りは :func:`read_article`・:func:`read_article_file` から使う。
読み取り結果のデータ型は :mod:`wikiskill.model`、例外は :mod:`wikiskill.errors` にある。
"""

from wikiskill.errors import FrontMatterError, MarkupError, SettingsError, SourceError
from wikiskill.model import Article
from wikiskill.reader import read_article, read_article_file

__all__ = [
    "Article",
    "FrontMatterError",
    "MarkupError",
    "SettingsError",
    "SourceError",
    "read_article",
    "read_article_file",
]
