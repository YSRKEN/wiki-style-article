"""原稿（冒頭の TOML の設定欄 ＋ Markdown の本文）を読み取って記事にする。

原稿の形は次のとおり（詳しくは ``docs/source-format.md``）。

.. code-block:: text

    +++
    title = "記事名"
    type = "person"
    +++
    導入部の段落。

    ## 節

    本文。

ファイルは UTF-8。冒頭の ``+++`` の行から次の ``+++`` の行までが設定欄で、その後が本文。
"""

from __future__ import annotations

import re
from pathlib import Path

from wikiskill.body import parse_body
from wikiskill.errors import FrontMatterError, SourceError
from wikiskill.model import Article
from wikiskill.settings import parse_settings

_DELIMITER = "+++"
_NEWLINE = re.compile(r"\r\n|\r|\n")


def read_article(text: str, base_dir: Path | None = None) -> Article:
    """原稿の文字列を読み取って記事にする。

    Parameters
    ----------
    text : str
        原稿の全文。改行コードは問わず、先頭の BOM は無視する。
    base_dir : Path | None
        原稿の置き場。画像の道はこの場所からの相対として読む。文字列から読むときは None で、
        画像を使う記事は :func:`read_article_file` で読む。

    Returns
    -------
    Article
        設定欄・導入部・節の木を持つ、変更できない記事。

    Raises
    ------
    FrontMatterError
        設定欄を囲む ``+++`` の行がない、または閉じていないとき。
    SettingsError
        設定欄の TOML や項目が誤っているとき。
    MarkupError
        本文や文中の記法が誤っているとき。
    """
    lines = _NEWLINE.split(text.removeprefix("﻿"))
    if lines[0].rstrip() != _DELIMITER:
        raise FrontMatterError(f"原稿は設定欄の始まりの {_DELIMITER} の行から書き始める", 1)

    closing = next(
        (index for index in range(1, len(lines)) if lines[index].rstrip() == _DELIMITER),
        None,
    )
    if closing is None:
        raise FrontMatterError(f"設定欄が {_DELIMITER} の行で閉じていない", 1)

    # lines の添字 i は原稿の i + 1 行目。設定欄は 2 行目から、本文は閉じの次の行から。
    settings = parse_settings("\n".join(lines[1:closing]), first_line=2)
    lead, sections = parse_body(lines[closing + 1 :], first_line=closing + 2)
    return Article(settings=settings, lead=lead, sections=sections, base_dir=base_dir)


def read_article_file(path: str | Path) -> Article:
    """原稿のファイルを UTF-8 として読み取って記事にする。

    Parameters
    ----------
    path : str | Path
        原稿のファイル。

    Returns
    -------
    Article
        設定欄・導入部・節の木を持つ、変更できない記事。

    Raises
    ------
    SourceError
        UTF-8 として読めないとき。ほかは :func:`read_article` と同じ。
    """
    data = Path(path).read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        line = data[: exc.start].count(b"\n") + 1
        raise SourceError("UTF-8 として読めない文字がある", line) from exc
    return read_article(text, Path(path).parent)
