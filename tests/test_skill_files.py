"""AI が読むスキルの文書（SKILL.md と references/）が、定義やスクリプトと食い違わないかを見る。"""

import re
import tomllib
from pathlib import Path

import pytest

from wikiskill import check_article, read_article
from wikiskill.types import load_default_registry

SKILL = Path(__file__).parents[1] / "plugins" / "wiki-style-article" / "skills" / "wiki"
REFERENCES = SKILL / "references"
REGISTRY = load_default_registry()
BASE_IDS = [t.id for t in REGISTRY if t.is_base]

TYPE_HEADINGS = [
    "## 節の並び",
    "## 導入部",
    "## 調べる観点の下敷き",
    "## この類型の作法",
    "## 第一文の例",
]


def _frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md の先頭にフロントマターが無い"
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(": ")
        fields[key] = value
    return fields


def _blocks(text: str, fence: str, lang: str) -> list[str]:
    pattern = rf"^{re.escape(fence)}{lang}\n(.*?)\n{re.escape(fence)}$"
    return re.findall(pattern, text, re.DOTALL | re.MULTILINE)


# --- SKILL.md ---------------------------------------------------------------------


RUMOR = SKILL.parent / "wiki-with-rumor"
BOTH = SKILL.parent / "wiki-both"


@pytest.mark.parametrize("folder", [SKILL, RUMOR, BOTH], ids=lambda p: p.name)
def test_SKILL_md_のフロントマターは共通仕様の上限に収まる(folder: Path) -> None:
    fields = _frontmatter((folder / "SKILL.md").read_text(encoding="utf-8"))

    # 共通仕様（agentskills.io）: name はフォルダ名と同じ。
    # description は 1024 字、compatibility は 500 字まで。
    assert fields["name"] == folder.name
    assert 0 < len(fields["description"]) <= 1024
    assert 0 < len(fields["compatibility"]) <= 500


@pytest.mark.parametrize("folder", [SKILL, RUMOR, BOTH], ids=lambda p: p.name)
def test_wiki_sh_を確認なしで流せるよう許す(folder: Path) -> None:
    # 担当が取得のコマンドを流すたびに、利用者へ許可の確認が出ないようにする
    fields = _frontmatter((folder / "SKILL.md").read_text(encoding="utf-8"))

    assert "Bash(sh *wiki.sh* *)" in fields["allowed-tools"]


@pytest.mark.parametrize("folder", [RUMOR, BOTH], ids=lambda p: p.name)
def test_隣のスキルを使うスキルが指すファイルはすべてある(folder: Path) -> None:
    text = (folder / "SKILL.md").read_text(encoding="utf-8")

    named = set(re.findall(r"`(\.\./wiki[a-z-]*/[A-Za-z0-9_./-]+)`", text))
    assert named
    assert all((folder / path).exists() for path in named), named


def test_SKILL_md_が名指しする参照ファイルはすべてある() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    named = set(re.findall(r"`(references/[a-z/-]+\.md)`", text))
    assert named
    assert all((SKILL / path).is_file() for path in named), named


# --- 類型のファイル ---------------------------------------------------------------


@pytest.mark.parametrize("type_id", BASE_IDS)
def test_基本型ごとに類型のファイルがあり見出しが決まった順に並ぶ(type_id: str) -> None:
    path = REFERENCES / "types" / f"{type_id}.md"
    text = path.read_text(encoding="utf-8")

    assert text.startswith(f"# {REGISTRY[type_id].name}（`{type_id}`）")
    positions = [text.find(f"\n{heading}\n") for heading in TYPE_HEADINGS]
    assert -1 not in positions, f"{path.name} に足りない見出しがある"
    assert positions == sorted(positions), f"{path.name} の見出しの順が違う"


@pytest.mark.parametrize("type_id", BASE_IDS)
def test_細かい種類のある基本型だけが差分の節を持ち_ID_をすべて挙げる(type_id: str) -> None:
    text = (REFERENCES / "types" / f"{type_id}.md").read_text(encoding="utf-8")
    kinds = REGISTRY.kinds_of(type_id)

    assert ("\n## 細かい種類の差分\n" in text) == bool(kinds)
    for kind in kinds:
        assert f"`{kind.id}`" in text, f"{type_id}.md に {kind.id} が無い"


def test_類型のファイルは基本型の分だけある() -> None:
    names = sorted(p.stem for p in (REFERENCES / "types").glob("*.md"))

    assert names == sorted(BASE_IDS)


@pytest.mark.parametrize("path", sorted(REFERENCES.rglob("*.md")), ids=lambda p: p.name)
def test_参照ファイルに本家のテンプレートを書かない(path: Path) -> None:
    # 原稿にテンプレートを書かせないため、見本にも出さない（スクリプトが書き出す）
    assert "{{" not in path.read_text(encoding="utf-8")


# --- 原稿の見本と材料の見本 -------------------------------------------------------


def test_原稿の書き方の見本は検査を指摘なしで通る() -> None:
    text = (REFERENCES / "source-format.md").read_text(encoding="utf-8")
    sample = next(block for block in _blocks(text, "```", "text") if block.startswith("+++"))

    article = read_article(sample + "\n")
    assert check_article(article, REGISTRY) == ()


def test_材料の見本の出典は原稿の設定欄としてそのまま読める() -> None:
    text = (REFERENCES / "research.md").read_text(encoding="utf-8")
    material = _blocks(text, "````", "markdown")[0]
    refs_toml = _blocks(material, "```", "toml")[0]
    facts = material.split("## 事実", 1)[1]

    title = 'title = "見本"\ntype = "meme"\n'
    refs = tomllib.loads(refs_toml)["refs"]
    # 弱い出典の印のすぐ後には [!信頼性要検証] が要る（材料の書き手も同じ決まりで原稿に写す）
    marks = "".join(
        f"[^{key}]" + ("[!信頼性要検証]" if ref.get("weak") else "") for key, ref in refs.items()
    )
    body = "'''見本'''は本文。" + marks
    article = read_article(f"+++\n{title}\n{refs_toml}\n+++\n{body}\n")
    assert check_article(article, REGISTRY) == ()
    # 事実に付けた印が、見本の出典のキーを指している
    used = set(re.findall(r"\[\^([a-z0-9_-]+)\]", facts))
    assert used and used <= set(tomllib.loads(refs_toml)["refs"])
