"""アンサイクロペディア風（百科事典の記事の形を借りて、嘘で書く記事）を作る。

原稿の形は同じプラグインの wiki スキルと同じ（+++ の設定欄＋Markdown の本文）。
ちがうのは、次の点。

- 出典は要らない。脚注（[^n:キー]）だけを使う。
- [[記事名]] は本家へのリンクではなく、赤リンク（まだ無い記事）として描く。
- 書き出すのは HTML 1 枚だけ。ウィキテキストは作らない（本家へ投稿しないため）。

使い方::

    python uncyclopedia.py check 原稿.md
    python uncyclopedia.py build 原稿.md [--out-dir 出力先] [--updated 2026-11-02]
    python uncyclopedia.py type [型の ID]
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NoReturn

_SKILL_DIR = Path(__file__).resolve().parents[1]
_SKILLS_DIR = _SKILL_DIR.parent
_WIKI_SCRIPTS = _SKILLS_DIR / "wiki" / "scripts"
if not (_WIKI_SCRIPTS / "wikiskill").is_dir():
    print(
        "同じフォルダに wiki スキルが要る（../wiki/scripts/wikiskill が見つからない）。"
        "wiki と uncyclopedia を並べて置くこと。",
        file=sys.stderr,
    )
    raise SystemExit(3)
sys.path.insert(0, str(_WIKI_SCRIPTS))

from wikiskill.checks.finding import Finding, Level  # noqa: E402
from wikiskill.checks.notation import check_notation  # noqa: E402
from wikiskill.checks.structure import check_structure  # noqa: E402
from wikiskill.errors import SourceError  # noqa: E402
from wikiskill.html_check import check_html  # noqa: E402
from wikiskill.html_inline import number_footnotes  # noqa: E402
from wikiskill.html_writer import write_html  # noqa: E402
from wikiskill.model import Article, Block, Paragraph, Text  # noqa: E402
from wikiskill.reader import read_article_file  # noqa: E402
from wikiskill.types import ArticleType, InfoboxField, InfoboxPart  # noqa: E402

#: 見た目は wiki スキルと共通の雛形を使う（本家ウィキペディアに寄せた骨格と CSS）。
TEMPLATE_PATH = _SKILL_DIR.parent / "wiki" / "assets" / "page-template.html"

#: 使える型と、Infobox に置くと面白い項目の候補。
TYPES: dict[str, tuple[str, tuple[str, ...]]] = {
    "thing": ("もの・道具", ("開発", "発売日", "価格", "重さ", "材質")),
    "food": ("食べもの・飲みもの", ("発祥", "主な産地", "値段", "賞味期限")),
    "place": ("場所", ("所在地", "面積", "人口", "標高")),
    "event": ("できごと", ("時期", "会場", "参加人数", "主催")),
    "person": ("架空の人物", ("生誕", "出身", "職業", "身長")),
    "work": ("作品", ("作者", "発表", "媒体", "巻数")),
    "organization": ("団体", ("設立", "本拠地", "構成員", "目的")),
    "creature": ("生きもの", ("分類", "生息地", "体長", "主食")),
    "sport": ("競技・遊び", ("考案", "人数", "使う物", "試合時間")),
    "concept": ("ことば・概念", ("提唱者", "初出", "分野", "関連")),
}

#: パロディでは定番なので見逃す規則（本家の「トリビア節は書くな」）。
_SKIPPED_RULES = frozenset({"TRIVIA-SECTION"})

#: ファイル名に使えない文字（バックスラッシュは chr で作る）。
_BAD_CHARS = frozenset(chr(92) + '/:*?"<>|')

_DEFINITION = re.compile("^[^。]{1,40}?(?:とは|は)")


#: 冒頭に必ず出すフィクションの帯（共有雛形の警告の枠 .ambox を借りる）。
_FICTION_BANNER = (
    '<div class="ambox" role="note">'
    "<b>この記事はフィクションです。</b>"
    "実在する人物・団体・製品・出来事とは関係ありません。"
    "</div>"
)

#: 共有雛形の頭に足すもの（赤リンクの色と、検索避け）。
_EXTRA_HEAD = (
    "<style>.redlink{color:#d73333}.redlink:hover{text-decoration:underline}</style>"
    '<meta name="robots" content="noindex, nofollow">'
)

#: 共有雛形の見出し語を、アンサイクロペディア向けに差し替える組（長いものから当てる）。
_LABELS: tuple[tuple[str, str], ...] = (
    ("Wikipedia風を検索", "アンサイクロペディアを検索"),
    (
        "出典: フリー百科事典『ウィキペディア（Wikipedia）』風のページ",
        "笑うための百科事典『アンサイクロペディア』風のページ",
    ),
    (
        "このページは Wikipedia そのものではなく、"
        "その見た目に寄せて作った Wikipedia風のページです。",
        "このページはアンサイクロペディアの本物ではなく、その見た目に寄せて作った冗談のページです。",
    ),
    ("WIKIPEDIA風", "アンサイクロペディア"),
    (" - Wikipedia風ページ</title>", " - アンサイクロペディア</title>"),
)

#: 共有雛形が内部リンクとして張る本家ウィキペディアへの a 要素。
_WIKI_LINK = re.compile(
    r'<a href="https://ja\.wikipedia\.org/wiki/[^"]*"[^>]*>(.*?)</a>', re.DOTALL
)


def _article_type(article: Article) -> ArticleType:
    """原稿の型から、書き出しに渡す類型を組む。

    Infobox の候補は型ごとに決めてあるので、原稿に書かれた項目をその順で並べる。
    """
    name, labels = TYPES[article.settings.type_id]
    fields = tuple(
        InfoboxField(label=label, param="param" + str(index), required=False, unverified=False)
        for index, label in enumerate(labels, start=1)
    )
    part = InfoboxPart(template="Infobox", placement="top", title_field=None, fields=fields)
    return ArticleType(id=article.settings.type_id, name=name, parents=(), infobox=(part,))


def _template_with_banner(template: str) -> str:
    """共有雛形に、フィクションの帯と赤リンク用の頭を差し込む。

    Parameters
    ----------
    template
        共有雛形の HTML。

    Returns
    -------
    str
        差し込みを済ませた雛形。あとは write_html に渡す。
    """
    marked = template.replace("</head>", _EXTRA_HEAD + "\n</head>")
    return marked.replace("{{NOTICES}}", "{{NOTICES}}\n" + _FICTION_BANNER)


def _labels(html: str) -> str:
    """共有雛形の見出し語を、アンサイクロペディア向けの言い方に変える。"""
    for old, new in _LABELS:
        html = html.replace(old, new)
    return html


_CATLINKS = re.compile(r'<div class="catlinks">.*?</div>', re.DOTALL)
_REDLINK = re.compile(r'<span class="redlink" title="[^"]*">([^<]*)</span>')


def _plain_categories(html: str) -> str:
    """カテゴリの札は、記事への赤リンクではなくただの文字にする。"""

    def swap(match: re.Match[str]) -> str:
        return _REDLINK.sub(r"\1", match.group(0))

    return _CATLINKS.sub(swap, html)


def _redlinks(html: str) -> str:
    """本家ウィキペディアへ張られた内部リンクを、赤リンクに変える。"""

    def swap(match: re.Match[str]) -> str:
        display = match.group(1)
        if display == "カテゴリ":
            # カテゴリの見出し語は、リンクではなくただの文字にする。
            return display
        return (
            '<span class="redlink" title="'
            + display
            + "（この記事はまだ無い）"
            + '">'
            + display
            + "</span>"
        )

    return _WIKI_LINK.sub(swap, html)


def render(article: Article, *, updated: str, template: str) -> str:
    """原稿を HTML 1 枚に組み立てる。

    Parameters
    ----------
    article
        読み込んだ原稿。
    updated
        最終更新の日付（YYYY-MM-DD か、日本語の日付の文）。
    template
        差し込み口を持つ雛形の HTML。

    Returns
    -------
    str
        差し込みを済ませた HTML。
    """
    html = write_html(
        article,
        _article_type(article),
        updated,
        template=_template_with_banner(template),
    )
    return _plain_categories(_redlinks(_labels(html)))


def _plain(blocks: tuple[Block, ...]) -> str:
    out: list[str] = []
    for block in blocks:
        if isinstance(block, Paragraph):
            out.append("".join(item.text for item in block.content if isinstance(item, Text)))
        else:
            for item in block.items:
                out.append("".join(part.text for part in item if isinstance(part, Text)))
    return " ".join(out)


def _check_lead(article: Article) -> list[Finding]:
    if not article.lead:
        return [
            Finding(
                level=Level.ERROR,
                rule="LEAD-MISSING",
                message="導入部が無い。最初の段落で「◯◯は…」と何の記事かを言い切る。",
                line=1,
            )
        ]
    first = next((block for block in article.lead if isinstance(block, Paragraph)), None)
    if first is None:
        return []
    if not _DEFINITION.match(_plain((first,))):
        return [
            Finding(
                level=Level.WARNING,
                rule="LEAD-DEFINITION",
                message="冒頭が「◯◯は…」「◯◯とは…」の形になっていない。"
                "パロディでも、まず何の記事かを一文で言い切ると読みやすい。",
                line=first.line,
            )
        ]
    return []


def _check_notes(article: Article) -> list[Finding]:
    out: list[Finding] = []
    if article.settings.references:
        out.append(
            Finding(
                level=Level.ERROR,
                rule="REF-NOT-ALLOWED",
                message="パロディでは出典（[refs.キー]）を使わない。"
                "脚注は [notes.キー] に書き、本文から [^n:キー] で指す。",
                line=1,
            )
        )
    try:
        numbering = number_footnotes(article)
    except Exception as error:
        return out + [Finding(level=Level.ERROR, rule="NOTE-BROKEN", message=str(error), line=1)]
    for note in article.settings.notes:
        if note.key in numbering.notes:
            continue
        key = note.key
        out.append(
            Finding(
                level=Level.ERROR,
                rule="NOTE-UNUSED",
                message="注釈 " + key + " が本文から参照されていない。"
                "本文の [^n:" + key + "] で指すか、[notes." + key + "] を消す。",
                line=note.line,
            )
        )
    return out


def check(article: Article) -> list[Finding]:
    """原稿を点検し、直すべき所を返す。

    Parameters
    ----------
    article
        読み込んだ原稿。

    Returns
    -------
    list[Finding]
        見つかった指摘（エラーと警告の両方）。
    """
    findings: list[Finding] = []
    if article.settings.type_id not in TYPES:
        findings.append(
            Finding(
                level=Level.ERROR,
                rule="TYPE-UNKNOWN",
                message="型 " + article.settings.type_id + " は知らない。"
                "使える型: " + ", ".join(TYPES) + "。",
                line=1,
            )
        )
    findings.extend(f for f in check_structure(article) if f.rule not in _SKIPPED_RULES)
    findings.extend(check_notation(article))
    findings.extend(_check_lead(article))
    findings.extend(_check_notes(article))
    findings.sort(key=lambda f: (f.line, f.rule))
    return findings


_REFS_HEADER = re.compile(r"\[\s*refs\.")


def _refs_finding(path: Path) -> Finding | None:
    """設定欄に出典のブロックがあれば、取り込みの前に指摘にする。

    設定欄の読み取りは出典の項目名に厳しく、先に読むと
    「未知の項目 'accessed' がある」のような、要らない所で止まる。
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for number, line in enumerate(text.splitlines(), start=1):
        if number == 1:
            if line.strip() != "+++":
                return None
            continue
        if line.strip() == "+++":
            return None
        if _REFS_HEADER.search(line):
            return Finding(
                level=Level.ERROR,
                rule="REF-NOT-ALLOWED",
                message="パロディでは出典（[refs.キー]）を使わない。"
                "脚注は [notes.キー] に書き、本文から [^n:キー] で指す。",
                line=number,
            )
    return None


def _load(path: Path) -> Article:
    try:
        return read_article_file(path)
    except SourceError as error:
        line = getattr(error, "line", 0)
        message = getattr(error, "message", str(error))
        print(str(path) + ": " + str(line) + " 行目: " + message, file=sys.stderr)
        raise SystemExit(1) from error


def _print_findings(findings: list[Finding]) -> None:
    for finding in findings:
        print(finding)


def _errors(findings: list[Finding]) -> int:
    return sum(1 for finding in findings if finding.level is Level.ERROR)


def _today() -> str:
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).strftime("%Y-%m-%d")


def _safe_name(title: str) -> str:
    chars = ["_" if (ch in _BAD_CHARS or ch.isspace()) else ch for ch in title]
    return "".join(chars).strip("_") or "article"


def cmd_check(path: Path) -> int:
    """原稿を検査し、指摘を出して終了コードを返す。

    Parameters
    ----------
    path
        原稿の場所。

    Returns
    -------
    int
        エラーがあれば 1、無ければ 0。
    """
    early = _refs_finding(path)
    if early is not None:
        _print_findings([early])
        print("エラー 1 件・警告 0 件。直すまで書き出さない。")
        return 1
    article = _load(path)
    findings = check(article)
    _print_findings(findings)
    errors = _errors(findings)
    warnings = len(findings) - errors
    if errors:
        print(f"エラー {errors} 件・警告 {warnings} 件。直すまで書き出さない。")
        return 1
    print("エラー 0 件・警告 " + str(warnings) + " 件。書き出せる。")
    return 0


def cmd_build(path: Path, out_dir: Path | None, updated: str, template_path: Path) -> int:
    """原稿を検査し、通ったら HTML を書き出す。

    Parameters
    ----------
    path
        原稿の場所。
    out_dir
        書き出し先。None なら原稿と同じフォルダ。
    updated
        最終更新の日付。
    template_path
        使う雛形の場所。

    Returns
    -------
    int
        書き出したら 0、止まったら 1。
    """
    early = _refs_finding(path)
    if early is not None:
        _print_findings([early])
        print("エラーがあるので書き出さない（先に check を通す）。")
        return 1
    article = _load(path)
    findings = check(article)
    _print_findings(findings)
    if _errors(findings):
        print("エラーがあるので書き出さない（先に check を通す）。")
        return 1
    template = template_path.read_text(encoding="utf-8")
    html = render(article, updated=updated, template=template)
    problems = check_html(html)
    if problems:
        for problem in problems:
            print(problem)
        print("組み立てた HTML に " + str(len(problems)) + " 件の不備があるので書き出さない。")
        return 1
    target_dir = out_dir or path.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / (_safe_name(article.settings.title) + ".html")
    target.write_text(html, encoding="utf-8")
    print("書き出した: " + str(target) + " (" + format(len(html.encode("utf-8")), ",") + " バイト)")
    headings = len(article.sections)
    notes = len(article.settings.notes)
    print(f"見出し {headings} 本（親のみ）・注 {notes} 件")
    return 0


def cmd_type(type_id: str | None) -> int:
    """型の一覧か、1 つの型の雛形を出す。

    Parameters
    ----------
    type_id
        型の ID。None なら一覧。

    Returns
    -------
    int
        出したら 0、知らない型なら 2。
    """
    if type_id is None:
        for key, (name, _fields) in TYPES.items():
            print(key + "  " + name)
        return 0
    if type_id not in TYPES:
        print("知らない型: " + type_id, file=sys.stderr)
        return 2
    name, fields = TYPES[type_id]
    rows = "\n".join('"' + field + '" = "…"' for field in fields)
    print("# 型 " + type_id + "（" + name + "）の雛形")
    print("+++")
    print('title = "題名"')
    print('reading = "よみ"')
    print('type = "' + type_id + '"')
    print("")
    print("[infobox]")
    print(rows)
    print("")
    print("[notes.origin]")
    print('text = "この注釈は本文から [^n:origin] で指す。キーは英数字・ハイフン・下線だけ。"')
    print("+++")
    print("")
    print("'''題名'''（よみ）とは、…。")
    print("")
    print("== 概要 ==")
    print("")
    print("…。")
    return 0


def main(argv: list[str]) -> int:
    """コマンド行から受け取って、check・build・type のどれかを流す。

    Parameters
    ----------
    argv
        引数（プログラム名を除く）。

    Returns
    -------
    int
        終了コード。
    """
    parser = argparse.ArgumentParser(
        prog="uncyclopedia.py", description="アンサイクロペディア風の記事を検査・書き出しする。"
    )
    sub = parser.add_subparsers(dest="command")
    p_check = sub.add_parser("check", help="原稿を検査する")
    p_check.add_argument("source", type=Path)
    p_build = sub.add_parser("build", help="HTML を書き出す")
    p_build.add_argument("source", type=Path)
    p_build.add_argument("--out-dir", type=Path, default=None)
    p_build.add_argument("--updated", default=None)
    p_build.add_argument("--template", type=Path, default=TEMPLATE_PATH)
    p_type = sub.add_parser("type", help="型の一覧と雛形を出す")
    p_type.add_argument("type_id", nargs="?")
    args = parser.parse_args(argv)
    if args.command == "check":
        return cmd_check(args.source)
    if args.command == "build":
        return cmd_build(args.source, args.out_dir, args.updated or _today(), args.template)
    if args.command == "type":
        return cmd_type(args.type_id)
    parser.print_help()
    return 2


def _run() -> NoReturn:
    raise SystemExit(main(sys.argv[1:]))


if __name__ == "__main__":
    _run()
