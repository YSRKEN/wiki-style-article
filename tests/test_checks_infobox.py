"""Infobox を類型の定義と突き合わせる規則の試験。"""

from pathlib import Path
from textwrap import dedent

import pytest

from helpers import Level, only
from wikiskill.checks import Finding, check_article
from wikiskill.model import Article
from wikiskill.reader import read_article, read_article_file
from wikiskill.types import TypeRegistry, load_default_registry, parse_registry

# 試験用の小さな定義。person は名前（title_field）・生年月日（必須）・職業（必須）・出身地、
# note は Infobox を持たない型。
REGISTRY = parse_registry(
    dedent(
        """
        [[type]]
        id = "person"
        name = "人物"
        [[type.infobox]]
        template = "Infobox 人物"
        title_field = "名前"
        required = ["生年月日", "職業"]
        [type.infobox.fields]
        "名前" = "名前"
        "生年月日" = "生年月日"
        "職業" = "職業"
        "出身地" = "出身地"

        [[type]]
        id = "tv"
        name = "番組"
        [[type.infobox]]
        template = "Header"
        required = ["局"]
        [type.infobox.fields]
        "局" = "放送局"
        [[type.infobox]]
        template = "Body"
        required = ["開始"]
        [type.infobox.fields]
        "開始" = "放送開始"

        [[type]]
        id = "note"
        name = "覚え書き"
        no_infobox = true

        [[type]]
        id = "vote"
        name = "投票"
        [[type.infobox]]
        template = "Infobox 投票"
        [type.infobox.fields]
        "地図" = "map_image"
        "備考" = "note"
        [type.infobox.image_fields]
        "地図" = "name"
        """
    )
)


def article(type_id: str, infobox: str = "") -> Article:
    """``type`` が 3 行目、``[infobox]`` が 4 行目（書けば）、項目が 5 行目から始まる原稿。"""
    table = f"[infobox]\n{infobox.strip(chr(10))}\n" if infobox else ""
    return read_article(
        f"+++\ntitle = \"試験\"\ntype = \"{type_id}\"\n{table}+++\n\n'''試験'''は例。\n"
    )


def run(type_id: str, infobox: str = "", registry: TypeRegistry = REGISTRY) -> tuple[Finding, ...]:
    return check_article(article(type_id, infobox), registry)


def article_at(tmp_path: Path, type_id: str, infobox: str) -> Article:
    """原稿をファイルに書いて読む。画像の実物を探す基準のフォルダが入る。"""
    table = f"[infobox]\n{infobox.strip(chr(10))}\n" if infobox else ""
    path = tmp_path / "原稿.md"
    path.write_text(
        f'+++\ntitle = "試験"\ntype = "{type_id}"\n{table}+++\n\n試験の本文。\n',
        encoding="utf-8",
    )
    return read_article_file(path)


# --- TYPE-UNKNOWN ------------------------------------------------------------


def test_定義にない型はエラー() -> None:
    findings = only(run("person-living-x"), "TYPE-UNKNOWN")
    assert len(findings) == 1
    assert findings[0].level is Level.ERROR
    assert findings[0].line == 1
    assert "person-living-x" in findings[0].message


def test_定義にある型は引っかからない() -> None:
    assert only(run("person", '"生年月日" = "1990年"\n"職業" = "作家"'), "TYPE-UNKNOWN") == []


def test_型が未知のときは項目の検査をしない() -> None:
    findings = run("nothing", '"何か" = "値"')
    assert [f.rule for f in findings] == ["TYPE-UNKNOWN"]


# --- INFOBOX-MISSING ---------------------------------------------------------


def test_必須の項目が無ければ項目ごとにエラー() -> None:
    findings = only(run("person", '"出身地" = "東京"'), "INFOBOX-MISSING")
    assert len(findings) == 2
    assert all(f.level is Level.ERROR for f in findings)
    assert {("生年月日" in f.message, "職業" in f.message) for f in findings} == {
        (True, False),
        (False, True),
    }
    # 行は Infobox の最初の項目の行（5 行目）
    assert {f.line for f in findings} == {5}


def test_Infoboxが無い原稿でも必須の欠けを見つける() -> None:
    findings = only(run("person"), "INFOBOX-MISSING")
    assert len(findings) == 2
    assert {f.line for f in findings} == {1}


def test_必須の項目が揃っていれば引っかからない() -> None:
    assert only(run("person", '"生年月日" = "1990年"\n"職業" = "作家"'), "INFOBOX-MISSING") == []


def test_title_fieldの項目は無くても欠けとしない() -> None:
    findings = only(run("person", '"生年月日" = "1990年"\n"職業" = "作家"'), "INFOBOX-MISSING")
    assert findings == []
    assert all("名前" not in f.message for f in only(run("person"), "INFOBOX-MISSING"))


def test_値が空白だけの必須の項目は欠けとする() -> None:
    findings = only(run("person", '"生年月日" = "1990年"\n"職業" = "  "'), "INFOBOX-MISSING")
    assert len(findings) == 1
    assert "職業" in findings[0].message
    assert findings[0].line == 5


def test_部品をまたいで必須の項目を見る() -> None:
    findings = only(run("tv", '"局" = "架空放送"'), "INFOBOX-MISSING")
    assert len(findings) == 1
    assert "開始" in findings[0].message


def test_Infoboxを持たない型では必須の検査をしない() -> None:
    assert only(run("note"), "INFOBOX-MISSING") == []


# --- INFOBOX-UNKNOWN-FIELD ---------------------------------------------------


def test_定義にない項目名は警告() -> None:
    infobox = '"生年月日" = "1990年"\n"職業" = "作家"\n"血液型" = "A型"'
    findings = only(run("person", infobox), "INFOBOX-UNKNOWN-FIELD")
    assert len(findings) == 1
    assert findings[0].level is Level.WARNING
    assert findings[0].line == 7
    assert "血液型" in findings[0].message


def test_定義にある項目名は引っかからない() -> None:
    infobox = '"名前" = "試験"\n"生年月日" = "1990年"\n"職業" = "作家"\n"出身地" = "東京"'
    assert only(run("person", infobox), "INFOBOX-UNKNOWN-FIELD") == []


def test_Infoboxを持たない型にInfoboxを書くと警告() -> None:
    findings = only(run("note", '"何か" = "値"'), "INFOBOX-UNKNOWN-FIELD")
    assert len(findings) == 1
    assert findings[0].line == 5
    assert "Infobox を持たない" in findings[0].message


def test_Infoboxを持たない型でInfoboxが無ければ何も出ない() -> None:
    assert run("note") == ()


# --- 画像の項目（INFOBOX-IMAGE・IMAGE-CAPTION・IMAGE-*）----------------------


def test_画像の項目が画像の形でなければエラー() -> None:
    findings = only(run("vote", '"地図" = "地図はこちら"'), "INFOBOX-IMAGE")
    assert len(findings) == 1
    assert findings[0].level is Level.ERROR
    assert findings[0].line == 5
    assert "地図" in findings[0].message
    assert "![キャプション](道)" in findings[0].message


def test_画像の項目が形通りなら基準のフォルダが無ければ画像そのものは見ない() -> None:
    assert run("vote", '"地図" = "![選挙区](images/map.png)"') == ()


def test_画像のキャプションが空なら警告() -> None:
    findings = only(run("vote", '"地図" = "![](images/map.png)"'), "IMAGE-CAPTION")
    assert len(findings) == 1
    assert findings[0].level is Level.WARNING
    assert findings[0].line == 5
    assert "地図" in findings[0].message


def test_画像の道が絶対ならエラー() -> None:
    findings = only(run("vote", '"地図" = "![選挙区](/tmp/map.png)"'), "IMAGE-PATH")
    assert len(findings) == 1
    assert findings[0].level is Level.ERROR
    assert "相対" in findings[0].message


def test_画像の種類が違えばエラー() -> None:
    findings = only(run("vote", '"地図" = "![選挙区](images/map.txt)"'), "IMAGE-TYPE")
    assert len(findings) == 1
    assert "種類ではない" in findings[0].message


def test_画像の実物が無ければエラー(tmp_path: Path) -> None:
    source = '"地図" = "![選挙区](images/map.png)"'
    findings = only(check_article(article_at(tmp_path, "vote", source), REGISTRY), "IMAGE-MISSING")
    assert len(findings) == 1
    assert findings[0].level is Level.ERROR
    assert "画像が無い: images/map.png" in findings[0].message


def test_画像でない項目に画像の記法を書くと宣言漏れの警告() -> None:
    findings = only(run("vote", '"備考" = "![図](images/map.png)"'), "INFOBOX-IMAGE-UNDECLARED")
    assert len(findings) == 1
    assert findings[0].level is Level.WARNING
    assert findings[0].line == 5
    assert "備考" in findings[0].message
    assert "image_fields" in findings[0].message


def test_画像でない項目に画像の記法があっても画像の検査はしない() -> None:
    assert only(run("vote", '"備考" = "![図](/tmp/map.png)"'), "IMAGE-PATH") == []


def test_画像の項目には宣言漏れの警告を出さない() -> None:
    assert (
        only(run("vote", '"地図" = "![選挙区](images/map.png)"'), "INFOBOX-IMAGE-UNDECLARED") == []
    )


def test_定義にない項目名は宣言漏れの警告と重ねない() -> None:
    findings = run(
        "person", '"生年月日" = "1900年"\n"職業" = "作家"\n"似顔絵" = "![顔](images/x.png)"'
    )
    assert [f.rule for f in findings] == ["INFOBOX-UNKNOWN-FIELD"]


# --- 任意のテンプレート（_template） ----------------------------------------------


def test_任意のテンプレートでは定義との突き合わせをしない() -> None:
    # 似顔絵は定義に無い項目名だが、任意のテンプレートの項目名は本家の引数名なので警告しない。
    findings = run("person", '_template = "Infobox 人物"\n"似顔絵" = "![顔](images/x.png)"')

    assert findings == ()


def test_任意のテンプレートでも画像の項目の道を検査する() -> None:
    source = '_template = "Infobox 人物"\n"似顔絵" = "![顔](/tmp/x.png)"'
    findings = only(run("person", source), "IMAGE-PATH")

    assert len(findings) == 1
    assert findings[0].level is Level.ERROR
    assert findings[0].line == 6
    assert "相対" in findings[0].message


def test_任意のテンプレートでも画像のキャプションが空なら警告() -> None:
    source = '_template = "Infobox 人物"\n"似顔絵" = "![](images/x.png)"'
    findings = only(run("person", source), "IMAGE-CAPTION")

    assert len(findings) == 1
    assert findings[0].level is Level.WARNING
    assert findings[0].line == 6
    assert "似顔絵" in findings[0].message


def test_任意のテンプレートでも画像の実物が無ければエラー(tmp_path: Path) -> None:
    source = '_template = "Infobox 人物"\n"似顔絵" = "![顔](images/x.png)"'
    findings = only(
        check_article(article_at(tmp_path, "person", source), REGISTRY), "IMAGE-MISSING"
    )

    assert len(findings) == 1
    assert findings[0].level is Level.ERROR
    assert "画像が無い: images/x.png" in findings[0].message


# --- check_article の入口 ----------------------------------------------------


def test_registryを渡さなければ類型の規則は動かない() -> None:
    assert check_article(article("nothing", '"何か" = "値"')) == ()


def test_既定の定義も渡せる() -> None:
    findings = check_article(article("meme"), load_default_registry())
    assert findings == ()
    unknown = check_article(article("nothing"), load_default_registry())
    assert [f.rule for f in unknown] == ["TYPE-UNKNOWN"]


def test_既定の定義で見本の原稿を検査すると必須は揃い連載期間だけ警告() -> None:
    from pathlib import Path

    sample = Path(__file__).parent / "fixtures" / "sample_article.md"
    findings = check_article(read_article_file(sample), load_default_registry())
    assert [(f.rule, f.line) for f in findings] == [("INFOBOX-UNKNOWN-FIELD", 13)]
    assert "連載期間" in findings[0].message


def test_指摘は行番号の順に並ぶ() -> None:
    infobox = '"出身地" = "東京"\n"血液型" = "A型"'
    lines = [f.line for f in run("person", infobox)]
    assert lines == sorted(lines)


@pytest.mark.parametrize("type_id", [t.id for t in load_default_registry()])
def test_既定の定義の全部の型で必須の項目が揃えば何も出ない(type_id: str) -> None:
    article_type = load_default_registry()[type_id]
    lines = "\n".join(f'"{f.label}" = "値"' for f in article_type.required_fields)
    findings = check_article(article(type_id, lines), load_default_registry())
    assert findings == ()
