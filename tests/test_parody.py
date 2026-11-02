"""パロディ百科のスキル（wiki-parody）が、原稿を検査して HTML を書き出せるかを見る。"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).parents[1] / "plugins" / "wiki-style-article" / "skills" / "wiki-parody"
SCRIPT = SKILL / "scripts" / "parody.py"

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


def test_確認なしで流せるシェルは_parody_sh_だけ() -> None:
    fields = _frontmatter()

    assert re.findall(r"Bash\([^)]*\)", fields["allowed-tools"]) == ["Bash(sh *parody.sh* *)"]


def test_名指しする参照ファイルと雛形はすべてある() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    named = set(re.findall(r"(references/[a-z-]+\.md|assets/[a-z-]+\.html)", text))
    assert named
    assert all((SKILL / path).is_file() for path in named), named


def test_見本の原稿はエラー無しで通り_書き出した_HTML_は外部の資源を読まない(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, "sample.md", SAMPLE)

    checked = _run("check", str(path))
    assert checked.returncode == 0, checked.stdout + checked.stderr

    built = _run("build", str(path), "--updated", "2026-11-02")
    assert built.returncode == 0, built.stdout + built.stderr

    html = (tmp_path / "三時のおやつ.html").read_text(encoding="utf-8")
    assert 'content="noindex' in html
    assert "この記事は<span>フィクション</span>です" in html
    assert "http://" not in html and "https://" not in html
    assert "ja.wikipedia.org" not in html


def test_赤リンクは本家へのリンクにせず_その場で描く(tmp_path: Path) -> None:
    text = SAMPLE.replace("午後三時に小腹が空くという説", "[[三時のおやつ標準時]] という説")
    path = _write(tmp_path, "sample.md", text)

    built = _run("build", str(path), "--updated", "2026-11-02")
    assert built.returncode == 0, built.stdout + built.stderr

    html = (tmp_path / "三時のおやつ.html").read_text(encoding="utf-8")
    assert 'class="redlink"' in html
    assert "ja.wikipedia.org" not in html


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
