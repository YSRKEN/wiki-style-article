"""アンサイクロペディア風のスキル（uncyclopedia）が、原稿を検査して HTML を書き出せるかを見る。"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).parents[1] / "plugins" / "wiki-style-article" / "skills" / "uncyclopedia"
SCRIPT = SKILL / "scripts" / "uncyclopedia.py"
#: 見た目は wiki スキルと共通の雛形を借りる。
WIKI_TEMPLATE = SKILL.parent / "wiki" / "assets" / "page-template.html"

SAMPLE = """+++
title = "三時のおやつ"
reading = "さんじのおやつ"
type = "concept"
categories = ["習慣", "食文化"]
related = ["四時のおやつ"]

[notes.origin]
text = "名称の由来には異説もあるが、誰も確かめていない。"
+++

'''三時のおやつ'''とは、午後三時ごろに何かを食べる習慣である。守らないと機嫌が悪くなるとされる[^n:origin]。

## 歴史

起源は諸説ある。有力なのは、午後三時に小腹が空くという説である。

## 方法

実施方法は単純である。

- 時刻を確認する
- 何かを用意する
"""


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _frontmatter() -> dict[str, str]:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md の先頭にフロントマターが無い"
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(": ")
        fields[key] = value
    return fields


def test_フロントマターが共通仕様に収まり_名前はフォルダと同じ() -> None:
    fields = _frontmatter()

    assert fields["name"] == SKILL.name
    assert 0 < len(fields["description"]) <= 1024
    assert 0 < len(fields["compatibility"]) <= 500


def test_確認なしで流せるシェルは_uncyclopedia_sh_だけ() -> None:
    fields = _frontmatter()

    assert re.findall(r"Bash\([^)]*\)", fields["allowed-tools"]) == ["Bash(sh *uncyclopedia.sh* *)"]


def test_名指しする参照ファイルはすべてある() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    named = set(re.findall(r"references/[a-z-]+\.md", text))
    assert named
    assert all((SKILL / path).is_file() for path in named), named


def test_見た目は_wiki_スキルの雛形を借りる() -> None:
    assert WIKI_TEMPLATE.is_file()
    assert not (SKILL / "assets").exists(), "独自の雛形は持たない"

    template = WIKI_TEMPLATE.read_text(encoding="utf-8")
    for placeholder in (
        "{{PAGE_TITLE}}",
        "{{INFOBOX}}",
        "{{LEAD}}",
        "{{SECTIONS}}",
        "{{FOOTNOTES}}",
    ):
        assert placeholder in template, placeholder


def test_見本の原稿はエラー無しで通り_本家風の_html_を書き出す(tmp_path: Path) -> None:
    path = _write(tmp_path, "sample.md", SAMPLE)

    checked = _run("check", str(path))
    assert checked.returncode == 0, checked.stdout + checked.stderr

    built = _run("build", str(path), "--updated", "2026-11-02")
    assert built.returncode == 0, built.stdout + built.stderr

    html = (tmp_path / "三時のおやつ.html").read_text(encoding="utf-8")
    assert "<title>三時のおやつ - アンサイクロペディア</title>" in html
    assert '<span class="logo-t">アンサイクロペディア</span>' in html
    assert "笑うための百科事典『アンサイクロペディア』風のページ" in html
    assert "アンサイクロペディアの本物ではなく" in html
    assert 'content="noindex' in html
    assert "パロディ事典" not in html
    assert not re.search(r'(?:src|href)="https?://', html)


def test_フィクションの帯は雛形の差し込み口から入る(tmp_path: Path) -> None:
    path = _write(tmp_path, "sample.md", SAMPLE)

    built = _run("build", str(path), "--updated", "2026-11-02")
    assert built.returncode == 0, built.stdout + built.stderr

    html = (tmp_path / "三時のおやつ.html").read_text(encoding="utf-8")
    assert '<div class="ambox" role="note"><b>この記事はフィクションです。</b>' in html
    assert "実在する人物・団体・製品・出来事とは関係ありません。" in html


def test_赤リンクは本家へのリンクにせず_その場で描く(tmp_path: Path) -> None:
    text = SAMPLE.replace("午後三時に小腹が空くという説", "[[三時のおやつ標準時]] という説")
    path = _write(tmp_path, "sample.md", text)

    built = _run("build", str(path), "--updated", "2026-11-02")
    assert built.returncode == 0, built.stdout + built.stderr

    html = (tmp_path / "三時のおやつ.html").read_text(encoding="utf-8")
    assert '<span class="redlink" title="三時のおやつ標準時（この記事はまだ無い）">' in html
    assert "ja.wikipedia.org" not in html


def test_カテゴリの札は赤リンクにしない(tmp_path: Path) -> None:
    path = _write(tmp_path, "sample.md", SAMPLE)

    built = _run("build", str(path), "--updated", "2026-11-02")
    assert built.returncode == 0, built.stdout + built.stderr

    html = (tmp_path / "三時のおやつ.html").read_text(encoding="utf-8")
    assert '<div class="catlinks">カテゴリ: <ul>' in html
    assert "<li>習慣</li>" in html
    assert "習慣（この記事はまだ無い）" not in html


def test_知らない型は止める(tmp_path: Path) -> None:
    path = _write(tmp_path, "bad.md", SAMPLE.replace('type = "concept"', 'type = "widget"'))

    checked = _run("check", str(path))

    assert checked.returncode == 1
    assert "TYPE-UNKNOWN" in checked.stdout


def test_使われない注釈は止める(tmp_path: Path) -> None:
    path = _write(tmp_path, "bad.md", SAMPLE.replace("[^n:origin]", ""))

    checked = _run("check", str(path))

    assert checked.returncode == 1
    assert "NOTE-UNUSED" in checked.stdout


def test_出典を使うと止める(tmp_path: Path) -> None:
    refs = '\n[refs.book]\ntitle = "本"\nurl = "https://example.com/"\naccess_date = 2025-01-01\n'
    text = SAMPLE.replace("[notes.origin]", refs.strip() + "\n\n[notes.origin]")
    text = text.replace("[^n:origin]", "")
    path = _write(tmp_path, "bad.md", text)

    checked = _run("check", str(path))

    assert checked.returncode == 1
    assert "REF-NOT-ALLOWED" in checked.stdout
    assert "未知の項目" not in checked.stderr


_WIKI_BANNER = (
    "ユーモア欠落症患者のために、ウィキペディアの専門家気取りたちが"
    "「三時のおやつ」の項目を執筆していません。"
)


def _built(tmp_path: Path, text: str) -> str:
    path = _write(tmp_path, "sample.md", text)
    built = _run("build", str(path), "--updated", "2026-11-02")
    assert built.returncode == 0, built.stdout + built.stderr
    html = (tmp_path / "三時のおやつ.html").read_text(encoding="utf-8")
    # バナーは本物と同じく語を太字にするので、文を比べるときは太字の札を外す
    return re.sub(r"</?b>", "", html)


def test_ロゴは_W_ではなくジャガイモ(tmp_path: Path) -> None:
    html = _built(tmp_path, SAMPLE)

    assert '<span class="logo-w">🥔</span>' in html
    assert '<span class="logo-w">W</span>' not in html


def test_ウィキペディアのバナーは関連項目の見出しの直後に一度だけ出る(tmp_path: Path) -> None:
    html = _built(tmp_path, SAMPLE)

    assert html.count(_WIKI_BANNER) == 1
    heading = html.index(">関連項目</h2>")
    banner = html.index(_WIKI_BANNER)
    first_item = html.index("四時のおやつ（この記事はまだ無い）")
    assert heading < banner < first_item
    assert '<span class="uncyc-globe" aria-hidden="true">🌐</span>' in html


def test_関連項目が無ければバナーはカテゴリの前に出る(tmp_path: Path) -> None:
    html = _built(tmp_path, SAMPLE.replace('related = ["四時のおやつ"]\n', ""))

    assert ">関連項目</h2>" not in html
    assert html.count(_WIKI_BANNER) == 1
    assert html.index(_WIKI_BANNER) < html.index('<div class="catlinks">')


def test_バナーの題名は_HTML_として逃がす(tmp_path: Path) -> None:
    text = SAMPLE.replace('title = "三時のおやつ"', 'title = "三時<のおやつ>"').replace(
        "'''三時のおやつ'''", "'''三時<のおやつ>'''"
    )
    path = _write(tmp_path, "sample.md", text)
    built = _run("build", str(path), "--updated", "2026-11-02")
    assert built.returncode == 0, built.stdout + built.stderr

    html = re.sub(r"</?b>", "", next(tmp_path.glob("*.html")).read_text(encoding="utf-8"))
    assert "「三時&lt;のおやつ&gt;」の項目を執筆していません。" in html
