"""パロディ百科（百科事典の記事の形を借りて、嘘で書く記事）を作る。

原稿の形は同じプラグインの wiki スキルと同じ（+++ の設定欄＋Markdown の本文）。
ちがうのは、次の点。

- 出典は要らない。脚注（[^n:キー]）だけを使う。
- [[記事名]] は本家へのリンクではなく、赤リンク（まだ無い記事）として描く。
- 書き出すのは HTML 1 枚だけ。ウィキテキストは作らない（本家へ投稿しないため）。

使い方::

    python parody.py check 原稿.md
    python parody.py build 原稿.md [--out-dir 出力先] [--updated 2026-11-02]
    python parody.py type [型の ID]
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
        "wiki と wiki-parody を並べて置くこと。",
        file=sys.stderr,
    )
    raise SystemExit(3)
sys.path.insert(0, str(_WIKI_SCRIPTS))

from wikiskill.checks.finding import Finding, Level  # noqa: E402
from wikiskill.checks.notation import check_notation  # noqa: E402
from wikiskill.checks.structure import check_structure  # noqa: E402
from wikiskill.errors import SourceError  # noqa: E402
from wikiskill.html_check import check_html  # noqa: E402
from wikiskill.html_escape import escape  # noqa: E402
from wikiskill.html_inline import (  # noqa: E402
    InlineWriter,
    Numbering,
    blocks_html,
    note_item_id,
    note_mark_id,
    number_footnotes,
)
from wikiskill.inline import parse_inline  # noqa: E402
from wikiskill.model import (  # noqa: E402
    Article,
    Block,
    Inline,
    InternalLink,
    Paragraph,
    Section,
    Text,
)
from wikiskill.reader import read_article_file  # noqa: E402

TEMPLATE_PATH = _SKILL_DIR / "assets" / "parody-template.html"

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


class ParodyWriter(InlineWriter):
    """[[記事名]] を赤リンク（まだ無い記事）として描く。"""

    def _one(self, item: Inline) -> str:
        if isinstance(item, InternalLink):
            title = escape(item.target + "（この記事はまだ無い）")
            return '<span class="redlink" title="' + title + '">' + escape(item.display) + "</span>"
        return super()._one(item)


def _title_text(section: Section) -> str:
    return section.title


def _redlink(name: str) -> str:
    return (
        '<span class="redlink" title="'
        + escape(name + "（この記事はまだ無い）")
        + '">'
        + escape(name)
        + "</span>"
    )


def _infobox(article: Article) -> str:
    fields = article.settings.infobox
    if not fields:
        return ""
    writer = ParodyWriter(None)
    rows = "\n".join(
        '<tr><th scope="row">'
        + escape(field.name)
        + "</th><td>"
        + writer.inline(parse_inline(field.value, field.line))
        + "</td></tr>"
        for field in fields
    )
    return (
        '<table class="infobox">\n'
        + "<caption>"
        + escape(article.settings.title)
        + "</caption>\n"
        + "<tbody>\n"
        + rows
        + "\n</tbody>\n</table>"
    )


def _sections(writer: ParodyWriter, sections: tuple[Section, ...]) -> tuple[str, str]:
    """目次と本文の節を、同じ順で作る。"""
    toc: list[str] = []
    body: list[str] = []
    counter = 0

    def walk(items: tuple[Section, ...]) -> None:
        nonlocal counter
        for section in items:
            counter += 1
            anchor = "sec-" + str(counter)
            level = min(max(section.level, 2), 4)
            title = escape(_title_text(section))
            toc.append(f'<li class="lv{level}"><a href="#{anchor}">{title}</a></li>')
            body.append(
                "<h"
                + str(level)
                + ' id="'
                + anchor
                + '">'
                + title
                + '<a class="anchor" href="#'
                + anchor
                + '" aria-label="この節へのリンク">#</a>'
                + "</h"
                + str(level)
                + ">"
            )
            body.extend(blocks_html(writer, section.blocks))
            walk(section.children)

    walk(sections)
    nav = ""
    if toc:
        nav = '<nav class="toc">\n<ol>\n' + "\n".join(toc) + "\n</ol>\n</nav>"
    return nav, "\n".join(body)


def _notes(article: Article, numbering: Numbering, writer: InlineWriter) -> str:
    if not numbering.notes:
        return ""
    plain = ParodyWriter(None)
    by_key = {note.key: note for note in article.settings.notes}
    items: list[str] = []
    for key, number in sorted(numbering.notes.items(), key=lambda pair: pair[1]):
        note = by_key.get(key)
        if note is None:
            continue
        back = " ".join(
            '<a href="#' + note_mark_id(number, nth) + '">↑</a>'
            for nth in range(1, writer.note_uses[key] + 1)
        )
        items.append(
            '<li id="'
            + note_item_id(number)
            + '">'
            + plain.inline(note.text)
            + ' <span class="backlink">'
            + back
            + "</span></li>"
        )
    if not items:
        return ""
    return (
        '<section class="notes">\n<h2 id="notes">注</h2>\n'
        '<ol class="references">\n' + "\n".join(items) + "\n</ol>\n</section>"
    )


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
    numbering = number_footnotes(article)
    writer = ParodyWriter(numbering)
    lead = "\n".join(blocks_html(writer, article.lead))
    toc, body = _sections(writer, article.sections)
    notes = _notes(article, numbering, writer)
    if article.settings.related:
        names = "".join("<li>" + _redlink(name) + "</li>" for name in article.settings.related)
        body = body + '\n<h2 id="related">関連項目</h2>\n<ul>\n' + names + "\n</ul>"
    type_name = TYPES[article.settings.type_id][0]
    categories = " ".join(_redlink(name) for name in article.settings.categories)
    parts = {
        "TITLE": escape(article.settings.title),
        "TYPE_NAME": escape(type_name),
        "INFOBOX": _infobox(article),
        "LEAD": lead,
        "SECTIONS": body,
        "TOC": toc,
        "NOTES": notes,
        "CATEGORIES": categories,
        "UPDATED": escape(updated),
    }
    html = template
    for name, value in parts.items():
        html = html.replace("{{" + name + "}}", value)
    return html


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
        prog="parody.py", description="パロディ百科の記事を検査・書き出しする。"
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
