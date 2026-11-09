"""アンサイクロペディア風のスキル（uncyclopedia）が、原稿を検査して HTML を書き出せるかを見る。"""

from __future__ import annotations

import base64
import re
import subprocess
import sys
from pathlib import Path

import pytest

from wikiskill.html_check import check_html

SKILL = Path(__file__).parents[1] / "plugins" / "wiki-style-article" / "skills" / "uncyclopedia"
SCRIPT = SKILL / "scripts" / "uncyclopedia.py"
#: Wikipedia 風の見た目は wiki スキルと共通の雛形を借りる。
WIKI_TEMPLATE = SKILL.parent / "wiki" / "assets" / "page-template.html"
CLASSIC_TEMPLATE = SKILL / "assets" / "page-template.html"

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


def test_wikipedia_の見た目は_wiki_スキルの雛形を借りる() -> None:
    assert WIKI_TEMPLATE.is_file()

    template = WIKI_TEMPLATE.read_text(encoding="utf-8")
    for placeholder in (
        "{{PAGE_TITLE}}",
        "{{INFOBOX}}",
        "{{LEAD}}",
        "{{SECTIONS}}",
        "{{FOOTNOTES}}",
    ):
        assert placeholder in template, placeholder


@pytest.mark.parametrize("look", ["classic", "wikipedia"])
def test_見本の原稿はエラー無しで通り_本家風の_html_を書き出す(tmp_path: Path, look: str) -> None:
    path = _write(tmp_path, "sample.md", SAMPLE)

    checked = _run("check", str(path))
    assert checked.returncode == 0, checked.stdout + checked.stderr

    built = _run("build", str(path), "--updated", "2026-11-02", "--look", look)
    assert built.returncode == 0, built.stdout + built.stderr

    html = (tmp_path / "三時のおやつ.html").read_text(encoding="utf-8")
    assert "<title>三時のおやつ - アンサイクロペディア</title>" in html
    logo_class = "logo-t" if look == "wikipedia" else "logo-name"
    assert f'<span class="{logo_class}">アンサイクロペディア</span>' in html
    assert "笑うための百科事典『アンサイクロペディア』風のページ" in html
    assert "アンサイクロペディアの本物ではなく" in html
    assert '<meta name="robots" content="noindex, nofollow">' in html
    assert not check_html(html)
    assert "パロディ事典" not in html
    assert not re.search(r'(?:src|href)="https?://', html)


@pytest.mark.parametrize("look", ["classic", "wikipedia"])
def test_フィクションの帯は雛形の差し込み口から入る(tmp_path: Path, look: str) -> None:
    path = _write(tmp_path, "sample.md", SAMPLE)

    built = _run("build", str(path), "--updated", "2026-11-02", "--look", look)
    assert built.returncode == 0, built.stdout + built.stderr

    html = (tmp_path / "三時のおやつ.html").read_text(encoding="utf-8")
    assert '<div class="ambox" role="note"><b>この記事はフィクションです。</b>' in html
    assert "実在する人物・団体・製品・出来事とは関係ありません。" in html
    assert html.count("この記事はフィクションです。") == 1
    assert html.index("この記事はフィクションです。") < html.index("<p>")


@pytest.mark.parametrize("look", ["classic", "wikipedia"])
def test_赤リンクは本家へのリンクにせず_その場で描く(tmp_path: Path, look: str) -> None:
    text = SAMPLE.replace("午後三時に小腹が空くという説", "[[三時のおやつ標準時]] という説")
    path = _write(tmp_path, "sample.md", text)

    built = _run("build", str(path), "--updated", "2026-11-02", "--look", look)
    assert built.returncode == 0, built.stdout + built.stderr

    html = (tmp_path / "三時のおやつ.html").read_text(encoding="utf-8")
    assert '<span class="redlink" title="三時のおやつ標準時（この記事はまだ無い）">' in html
    assert "ja.wikipedia.org" not in html


@pytest.mark.parametrize("look", ["classic", "wikipedia"])
def test_カテゴリの札は赤リンクにしない(tmp_path: Path, look: str) -> None:
    path = _write(tmp_path, "sample.md", SAMPLE)

    built = _run("build", str(path), "--updated", "2026-11-02", "--look", look)
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


def _built(tmp_path: Path, text: str, *args: str) -> str:
    path = _write(tmp_path, "sample.md", text)
    built = _run("build", str(path), "--updated", "2026-11-02", *args)
    assert built.returncode == 0, built.stdout + built.stderr
    html = (tmp_path / "三時のおやつ.html").read_text(encoding="utf-8")
    # バナーは本物と同じく語を太字にするので、文を比べるときは太字の札を外す
    return re.sub(r"</?b>", "", html)


@pytest.mark.parametrize("look", ["classic", "wikipedia"])
def test_ロゴは_W_ではなくジャガイモ(tmp_path: Path, look: str) -> None:
    html = _built(tmp_path, SAMPLE, "--look", look)

    logo_class = "logo-w" if look == "wikipedia" else "logo-mark"
    assert f'<span class="{logo_class}">🥔</span>' in html
    assert '<span class="logo-w">W</span>' not in html


@pytest.mark.parametrize("look", ["classic", "wikipedia"])
def test_ウィキペディアのバナーは関連項目の見出しの直後に一度だけ出る(
    tmp_path: Path, look: str
) -> None:
    html = _built(tmp_path, SAMPLE, "--look", look)

    assert html.count(_WIKI_BANNER) == 1
    heading = html.index(">関連項目</h2>")
    banner = html.index(_WIKI_BANNER)
    first_item = html.index("四時のおやつ（この記事はまだ無い）")
    assert heading < banner < first_item
    assert re.search(r'>関連項目</h2>.*?</div>\s*<div class="uncyc-wikibox"', html)
    assert '<span class="uncyc-globe" aria-hidden="true">🌐</span>' in html


@pytest.mark.parametrize("look", ["classic", "wikipedia"])
def test_関連項目が無ければバナーはカテゴリの前に出る(tmp_path: Path, look: str) -> None:
    html = _built(tmp_path, SAMPLE.replace('related = ["四時のおやつ"]\n', ""), "--look", look)

    assert ">関連項目</h2>" not in html
    assert html.count(_WIKI_BANNER) == 1
    assert html.index(_WIKI_BANNER) < html.index('<div class="catlinks">')


@pytest.mark.parametrize("look", ["classic", "wikipedia"])
def test_バナーの題名は_HTML_として逃がす(tmp_path: Path, look: str) -> None:
    text = SAMPLE.replace('title = "三時のおやつ"', 'title = "三時<のおやつ>"').replace(
        "'''三時のおやつ'''", "'''三時<のおやつ>'''"
    )
    path = _write(tmp_path, "sample.md", text)
    built = _run("build", str(path), "--updated", "2026-11-02", "--look", look)
    assert built.returncode == 0, built.stdout + built.stderr

    html = re.sub(r"</?b>", "", next(tmp_path.glob("*.html")).read_text(encoding="utf-8"))
    assert "「三時&lt;のおやつ&gt;」の項目を執筆していません。" in html


def test_既定と_classic_は旧スキン風の同じ出力になる(tmp_path: Path) -> None:
    _built(tmp_path, SAMPLE)
    default = (tmp_path / "三時のおやつ.html").read_text(encoding="utf-8")

    assert '<aside class="side"' in default
    assert '<div class="toc"' in default
    _built(tmp_path, SAMPLE, "--look", "classic")
    classic = (tmp_path / "三時のおやつ.html").read_text(encoding="utf-8")
    assert default == classic


def test_wikipedia_は今までの共有雛形の出力と同じになる(tmp_path: Path) -> None:
    _built(tmp_path, SAMPLE, "--template", str(WIKI_TEMPLATE))
    previous = (tmp_path / "三時のおやつ.html").read_text(encoding="utf-8")
    _built(tmp_path, SAMPLE, "--look", "wikipedia")
    wikipedia = (tmp_path / "三時のおやつ.html").read_text(encoding="utf-8")

    assert wikipedia == previous
    assert '<aside class="side"' not in wikipedia
    assert '<span class="logo-t">アンサイクロペディア</span>' in wikipedia
    assert "アンサイクロペディアを検索" in wikipedia


def test_知らない見た目は_argparse_の誤りで止まる(tmp_path: Path) -> None:
    path = _write(tmp_path, "sample.md", SAMPLE)

    built = _run("build", str(path), "--look", "unknown")

    assert built.returncode == 2
    assert "invalid choice" in built.stderr
    assert not list(tmp_path.glob("*.html"))


@pytest.mark.parametrize("look_args", [(), ("--look", "classic"), ("--look", "wikipedia")])
def test_指定した雛形は見た目の選択より優先する(tmp_path: Path, look_args: tuple[str, ...]) -> None:
    template = _write(
        tmp_path,
        "custom.html",
        WIKI_TEMPLATE.read_text(encoding="utf-8").replace(
            "<body>", '<body data-template="custom">'
        ),
    )

    html = _built(tmp_path, SAMPLE, *look_args, "--template", str(template))

    assert '<body data-template="custom">' in html
    assert '<aside class="side"' not in html
    assert not check_html(html)


def test_classic_は差し込み口がそろい_運営とは関係がないと断る() -> None:
    template = CLASSIC_TEMPLATE.read_text(encoding="utf-8")

    assert set(re.findall(r"\{\{([A-Z_]+)\}\}", template)) == {
        "PAGE_TITLE",
        "VARIANT_STYLE",
        "VARIANT_SWITCH",
        "VARIANT_OPEN",
        "NOTICES",
        "LEAD",
        "TOC",
        "SECTIONS",
        "FOOTNOTES",
        "RELATED",
        "EXTERNAL_LINKS",
        "CATEGORIES",
        "VARIANT_CLOSE",
        "RUMOR_VARIANT",
        "UPDATED",
        "VARIANT_SCRIPT",
    }
    footer = template.split('<footer class="foot">', 1)[1].split("</footer>", 1)[0]
    assert "アンサイクロペディアの運営とは関係がなく" in footer


@pytest.mark.parametrize("look", ["classic", "wikipedia"])
def test_infobox_のある原稿も通り_classic_には箱を出さない(tmp_path: Path, look: str) -> None:
    text = SAMPLE.replace("[notes.origin]", '[infobox]\n"提唱者" = "おやつ協会"\n\n[notes.origin]')

    html = _built(tmp_path, text, "--look", look)

    if look == "classic":
        assert "おやつ協会" not in html
        assert '<table class="infobox"' not in html
    else:
        assert "おやつ協会" in html
        assert '<table class="infobox"' in html
    assert not check_html(html)


@pytest.mark.parametrize("definition", [True, False])
def test_導入部の先頭の画像を読み飛ばして次の段落の定義を検査する(
    tmp_path: Path, definition: bool
) -> None:
    text = SAMPLE.replace(
        "'''三時のおやつ'''とは、", "![定義ではない図。](zu.png)\n\n'''三時のおやつ'''とは、"
    )
    if not definition:
        text = text.replace("'''三時のおやつ'''とは、", "午後三時ごろ。")
    path = _write(tmp_path, "sample.md", text)

    checked = _run("check", str(path))

    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert ("LEAD-DEFINITION" in checked.stdout) is not definition


@pytest.mark.parametrize("look", ["classic", "wikipedia"])
def test_本文の画像をdataのURIで埋め込みHTMLの検査を通る(tmp_path: Path, look: str) -> None:
    data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    (tmp_path / "zu.png").write_bytes(data)
    text = SAMPLE.replace("## 歴史", "![おやつの図](zu.png)\n\n## 歴史")
    path = _write(tmp_path, "sample.md", text)

    built = _run("build", str(path), "--updated", "2026-11-02", "--look", look)

    assert built.returncode == 0, built.stdout + built.stderr
    html = (tmp_path / "三時のおやつ.html").read_text(encoding="utf-8")
    assert f'src="data:image/png;base64,{base64.b64encode(data).decode("ascii")}"' in html
    assert "<figcaption>おやつの図</figcaption>" in html
    assert not check_html(html)
