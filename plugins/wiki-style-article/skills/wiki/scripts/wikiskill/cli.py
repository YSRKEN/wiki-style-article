"""原稿を読み、検査し、HTML とウィキテキストを書き出すコマンドの入口。

使い方::

    python -m wikiskill build 原稿.md [--style plain] [--out-dir 出力先] [--updated 日時]
    python -m wikiskill check 原稿.md
    python -m wikiskill type [類型の ID]
    python -m wikiskill fetch URL [--max-chars 字数] [--offset 字数] [--archive-year 年]
    python -m wikiskill wikipedia 記事名

``build`` は原稿の隣（``--out-dir`` で変えられる）に ``<原稿の名前>.html`` と
``<原稿の名前>.wikitext`` を書き出す。``check`` は検査だけして何も書き出さない。
``type`` は類型の一覧か、原稿の設定欄に貼る ``type`` と Infobox の雛形を出す。
``fetch`` は Web のページを取り、題と本文の文字を出す（調べものの担当が使う。
:mod:`wikiskill.fetch`）。``wikipedia`` は本家の記事の節の並びと出典の一覧を出す
（:mod:`wikiskill.wikipedia_refs`）。``build`` は、印と冒頭の警告の枠に今の現地時刻の年月
（``2026年11月``）を添える。

出力は 1 行に 1 件で、検査の指摘（``12 行目 [警告] RULE: …``）、件数のまとめ、
書き出したファイルの順。終了コードは次のとおり。

- 0: 書き出した（``check`` ではエラーが無かった）。警告があっても 0
- 1: 原稿にエラーがあって書き出していない。指摘を見て原稿を直す
  （``fetch``・``wikipedia`` ではページを取れなかった）
- 2: 呼び方の誤り（引数・原稿のファイルが無い）

詳しくは ``docs/cli.md``。
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import tempfile
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import NoReturn

from wikiskill import wikipedia_refs
from wikiskill.checks import Finding, Level, check_article
from wikiskill.errors import SourceError
from wikiskill.fetch import FetchError, Pacer, fetch_page
from wikiskill.html_check import check_html
from wikiskill.html_inline import HtmlError
from wikiskill.html_writer import write_html
from wikiskill.reader import read_article_file
from wikiskill.types import ArticleType, load_default_registry
from wikiskill.wikitext import WIKITEXT_STYLES, WikitextError, WikitextStyle, write_wikitext

__all__ = ["format_mark_date", "format_updated", "main", "run"]

_WEEKDAYS = "月火水木金土日"
_JST = timedelta(hours=9)


def main(argv: Sequence[str] | None = None) -> int:
    """コマンドを流して、終了コードを返す。

    Parameters
    ----------
    argv : Sequence[str] | None
        コマンドの引数（プログラム名は含めない）。省くと ``sys.argv[1:]``。

    Returns
    -------
    int
        終了コード。0・1・2 の意味はモジュールの説明のとおり。
    """
    try:
        args = _parser().parse_args(argv)
    except SystemExit as stop:
        # argparse は誤りでも --help でも抜けようとする。呼ぶ側へ終了コードで返す。
        return stop.code if isinstance(stop.code, int) else 2
    if args.command == "type":
        return _type(args.type_id)
    if args.command == "wikipedia":
        return _wikipedia(args.title)
    if args.command == "fetch":
        return _fetch(
            args.url, max_chars=args.max_chars, offset=args.offset, archive_year=args.archive_year
        )
    source = Path(args.source)
    if not source.is_file():
        print(f"原稿が見つからない: {source}", file=sys.stderr)
        return 2
    if args.command == "check":
        return _check(source)
    now = datetime.now().astimezone()
    return _build(
        source,
        style=args.style,
        out_dir=Path(args.out_dir) if args.out_dir else source.parent,
        updated=args.updated or format_updated(now),
        mark_date=format_mark_date(now),
    )


def run() -> NoReturn:
    """``python -m wikiskill`` などから呼ぶ。出力を UTF-8 にして :func:`main` を流す。"""
    # Windows で PYTHONUTF8 が立っていないと、出力が cp932 になり、AI が読むと文字化けする。
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    sys.exit(main())


def format_updated(moment: datetime) -> str:
    """最終更新の日時を、本家のフッタの形（``2026年11月2日 (月) 12:00 (JST)``）にする。

    Parameters
    ----------
    moment : datetime
        時差つきの日時。現地時刻なら ``datetime.now().astimezone()``。

    Returns
    -------
    str
        日付・曜日・時刻・時間帯。時間帯は UTC+9 なら ``JST``、時差 0 なら ``UTC``、
        ほかは ``UTC+05:30`` の形。

    Raises
    ------
    ValueError
        時差の無い日時を渡したとき。
    """
    offset = moment.utcoffset()
    if offset is None:
        raise ValueError("時差の無い日時は受け付けない。datetime.now().astimezone() を渡す")
    weekday = _WEEKDAYS[moment.weekday()]
    return (
        f"{moment.year}年{moment.month}月{moment.day}日 ({weekday}) "
        f"{moment:%H:%M} ({_zone_name(offset)})"
    )


def format_mark_date(moment: datetime) -> str:
    """印と冒頭の警告の枠に添える日付を、本家の ``date=`` の形（``2026年11月``）にする。

    Parameters
    ----------
    moment : datetime
        日時。現地時刻なら ``datetime.now().astimezone()``。

    Returns
    -------
    str
        年と月（月は 0 詰めしない）。
    """
    return f"{moment.year}年{moment.month}月"


# --- 下請け -----------------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wikiskill", description="Wikipedia風の記事の原稿を検査して書き出す。"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="検査して、HTML とウィキテキストを書き出す")
    build.add_argument("source", help="原稿のファイル（UTF-8 の Markdown）")
    build.add_argument(
        "--style",
        choices=WIKITEXT_STYLES,
        default="wikipedia",
        help="ウィキテキストの書き方。wikipedia は本家の形（既定）、plain は素の記法",
    )
    build.add_argument("--out-dir", help="書き出し先のフォルダ。省くと原稿と同じフォルダ")
    build.add_argument("--updated", help="最終更新の日時の文字列。省くと今の現地時刻")

    check = commands.add_parser("check", help="検査だけして、何も書き出さない")
    check.add_argument("source", help="原稿のファイル（UTF-8 の Markdown）")

    kind = commands.add_parser(
        "type", help="類型の一覧を出す。ID を渡すと、原稿の設定欄に貼る Infobox の雛形を出す"
    )
    kind.add_argument("type_id", nargs="?", help="類型の ID（例 manga）。省くと一覧")

    fetch = commands.add_parser("fetch", help="Web のページを取り、題と本文の文字を出す")
    fetch.add_argument("url", help="取るページの URL（http か https）")
    fetch.add_argument(
        "--max-chars", type=int, default=30000, help="出す本文の字数の上限（既定 30000）"
    )
    fetch.add_argument("--offset", type=int, default=0, help="本文の何字目から出すか（既定 0）")
    fetch.add_argument(
        "--archive-year",
        type=int,
        help="元のページが無いときに探す保存版の年（例 2016）。省くと今年に近い保存版",
    )

    wiki = commands.add_parser("wikipedia", help="本家の記事の節の並びと出典の一覧を出す")
    wiki.add_argument("title", help="本家の記事名（例 カップヌードル）")
    return parser


def _state_dir() -> Path:
    return Path(
        os.environ.get("WIKISKILL_FETCH_STATE")
        or str(Path(tempfile.gettempdir()) / "wiki-style-article-fetch")
    )


def _wikipedia(title: str) -> int:
    pacer = Pacer(_state_dir())
    try:
        try:
            raw = wikipedia_refs.fetch_raw(title, pacer=pacer)
            article = wikipedia_refs.parse_article(title, raw)
        except wikipedia_refs.WikipediaError as error:
            if error.redirect_to is None:
                raise
            target = error.redirect_to
            print(
                f"「{title}」は「{target}」への転送なので、転送先を読む（本家に 2 回問い合わせた）"
            )
            title = target
            article = wikipedia_refs.parse_article(
                title, wikipedia_refs.fetch_raw(title, pacer=pacer)
            )
    except wikipedia_refs.WikipediaError as error:
        print(f"[エラー] WIKIPEDIA: {error}", file=sys.stderr)
        return 1
    archived = sum(1 for c in article.citations if c.archive_url)
    print(f"記事: {title}（https://ja.wikipedia.org/wiki/{title.replace(' ', '_')}）")
    print(f"出典 {len(article.citations)} 件（保存版つき {archived} 件）。")
    print("本家の本文は写さず、節の並びと出典の手がかりにだけ使う。本家そのものは出典にしない。")
    print()
    print("## 節の並び")
    for level, heading in article.sections:
        print(f"{'  ' * (level - 2)}- {heading}")
    print()
    print("## 出典（節ごと）")
    current = None
    for citation in article.citations:
        if citation.section != current:
            current = citation.section
            print(f"### {current}")
        print("- " + " ｜ ".join(x for x in (citation.title, citation.source, citation.date) if x))
        if citation.url:
            print(f"  元: {citation.url}")
        if citation.archive_url:
            print(f"  保存版: {citation.archive_url}")
    return 0


def _fetch(url: str, *, max_chars: int, offset: int, archive_year: int | None) -> int:
    try:
        page = fetch_page(url, pacer=Pacer(_state_dir()), archive_year=archive_year)
    except FetchError as error:
        print(f"[エラー] FETCH: {error}", file=sys.stderr)
        print(
            "取れないときは、WebFetch で https://r.jina.ai/<URL> を取る（鍵なしの Jina。"
            "web.archive.org は止められている）。",
            file=sys.stderr,
        )
        return 1
    end = min(len(page.text), offset + max_chars)
    print(f"題: {page.title}")
    print(f"URL: {page.url}")
    if page.archive_reason is not None:
        reason = page.archive_reason
        print(f"取った URL: {page.fetched_url}（元のページが {reason} のため保存版を取った）")
    elif page.fetched_url != page.url:
        print(f"取った URL: {page.fetched_url}")
    print(f"本文: 全 {len(page.text)} 字のうち {offset}〜{end} 字目")
    print("---")
    print(page.text[offset:end])
    if end < len(page.text):
        print("---")
        print(f"続きは --offset {end} を付けて流し直す。")
    return 0


def _check(source: Path) -> int:
    findings = _read_and_check(source)
    return 1 if findings is None or _has_error(findings) else 0


def _build(
    source: Path, *, style: WikitextStyle, out_dir: Path, updated: str, mark_date: str
) -> int:
    findings = _read_and_check(source)
    if findings is None or _has_error(findings):
        print("エラーを直すまで書き出していない。")
        return 1

    # 検査を通った原稿なので、読み直しても同じ記事になる。
    article = read_article_file(source)
    article_type = load_default_registry()[article.settings.type_id]
    try:
        html = write_html(article, article_type, updated, mark_date=mark_date)
        wikitext = write_wikitext(article, article_type, style=style, mark_date=mark_date)
    except (HtmlError, WikitextError) as error:
        print(f"[エラー] WRITE: {error}")
        print("書き出していない。")
        return 1
    html_findings = check_html(html)
    if html_findings:
        for finding in html_findings:
            print(f"[エラー] {finding}")
        print("書き出した HTML が検査を通らないので書き出していない（スクリプトの不具合の恐れ）。")
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    for suffix, text in ((".html", html), (".wikitext", wikitext)):
        path = out_dir / f"{source.stem}{suffix}"
        # Windows でも改行を LF のまま書く（本家のウィキテキストも LF）。
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"書き出した: {path}")
    return 0


def _type(type_id: str | None) -> int:
    registry = load_default_registry()
    if type_id is None:
        print("# 基本型と、その下に字下げした細かい種類。原稿の type に ID を書く。")
        for base in registry:
            if base.is_base:
                print(f"{base.id}  {base.name}")
                for kind in registry.kinds_of(base.id):
                    print(f"  {kind.id}  {kind.name}")
        return 0
    found = registry.find(type_id)
    if found is None:
        print(f"類型が見つからない: {type_id}（一覧は type を引数なしで流す）", file=sys.stderr)
        return 2
    print(_skeleton(found))
    return 0


def _skeleton(article_type: ArticleType) -> str:
    """原稿の設定欄に貼る ``type`` と ``[infobox]`` の雛形。"""
    guides = article_type.parents or (article_type.id,)
    lines = [f"# {article_type.name}（{article_type.id}）"]
    lines += [f"# 節の並びと書き方: references/types/{guide}.md" for guide in guides]
    lines.append(f'type = "{article_type.id}"')
    if not article_type.has_infobox:
        lines.append("# この類型は Infobox を持たない。原稿に Infobox の欄は書かない。")
        return "\n".join(lines)
    templates = " ＋ ".join(part.template for part in article_type.infobox)
    lines += [
        f"# Infobox: {templates}",
        "# 「必須」の項目は必ず埋める。ほかは分かる項目だけ埋め、分からない項目は行ごと消す。",
        "",
        "[infobox]",
    ]
    for part in article_type.infobox:
        for field in part.fields:
            notes = ["必須"] if field.required else []
            if field.label == part.title_field:
                notes.append("書かなければ記事名")
            comment = f"  # {'、'.join(notes)}" if notes else ""
            lines.append(f'{_toml_string(field.label)} = ""{comment}')
    return "\n".join(lines)


def _toml_string(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _read_and_check(source: Path) -> tuple[Finding, ...] | None:
    """原稿を読んで検査し、指摘と件数を出す。読み取れなければ ``None``。"""
    try:
        article = read_article_file(source)
    except SourceError as error:
        print(f"{error.line} 行目 [エラー] READ: {error.message}")
        _print_counts(errors=1, warnings=0)
        return None
    findings = check_article(article, load_default_registry())
    for finding in findings:
        print(finding)
    errors = sum(1 for finding in findings if finding.level is Level.ERROR)
    _print_counts(errors=errors, warnings=len(findings) - errors)
    return findings


def _print_counts(*, errors: int, warnings: int) -> None:
    print(f"エラー {errors} 件、警告 {warnings} 件。")
    if warnings:
        print("警告は前後を読み直し、直すか残すかを決める。")


def _has_error(findings: tuple[Finding, ...]) -> bool:
    return any(finding.level is Level.ERROR for finding in findings)


def _zone_name(offset: timedelta) -> str:
    if offset == _JST:
        return "JST"
    if not offset:
        return "UTC"
    sign = "+" if offset > timedelta(0) else "-"
    minutes = abs(offset) // timedelta(minutes=1)
    return f"UTC{sign}{minutes // 60:02}:{minutes % 60:02}"
