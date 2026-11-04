"""TemplateData（本家テンプレートの引数定義）の試験。"""

from pathlib import Path

import pytest

from helpers import Level, only
from wikiskill.checks import Finding
from wikiskill.checks.infobox import check_infobox
from wikiskill.cli import main
from wikiskill.html_infobox import build_infobox_html
from wikiskill.model import Article
from wikiskill.reader import read_article
from wikiskill.templatedata import (
    DuplicateTemplateError,
    TemplateData,
    TemplateDataRegistry,
    TemplateDataSchemaError,
    TemplateParam,
    normalize_template_name,
    parse_templatedata,
    read_templatedata_file,
    template_data_from_page,
    write_templatedata_file,
)
from wikiskill.types import load_default_registry
from wikiskill.wikitext_infobox import build_infobox

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample_figure.png"

TYPES = load_default_registry()

DATA = TemplateData(
    name="Infobox 試験",
    description="試験用のテンプレート",
    params=(
        TemplateParam(name="氏名", label="名前", aliases=("name",), required=True),
        TemplateParam(name="画像", aliases=("image",), image=True),
        TemplateParam(name="肩書", label="職業"),
    ),
)
REGISTRY = TemplateDataRegistry(templates=(DATA,))


def _article(front: str, *, type_id: str = "person-living") -> Article:
    """前書きに front を足した原稿を読む。"""
    return read_article(f'+++\ntitle = "試験"\ntype = "{type_id}"\n{front}+++\n\n本文。\n')


def _infobox_front(*items: str, template: str = "Infobox 試験") -> str:
    """[infobox] の前書きを組み立てる。項目は 6 行目から始まる。"""
    body = "".join(f"{item}\n" for item in items)
    return f'[infobox]\n_template = "{template}"\n{body}'


def _findings(front: str, registry: TemplateDataRegistry | None = REGISTRY) -> tuple[Finding, ...]:
    """原稿の検査結果をまとめて返す。registry が None なら同梱の定義を使う。"""
    return tuple(check_infobox(_article(front), TYPES, templatedata=registry))


# --- TOML の往復 -------------------------------------------------------------------


def test_書き出したTOMLを読み直すと同じ定義になる(tmp_path: Path) -> None:
    path = tmp_path / "templatedata.toml"

    write_templatedata_file(REGISTRY, path, fetched="2026-11-05")

    text = path.read_text(encoding="utf-8")
    assert text.startswith("# ja.wikipedia の TemplateData")
    assert "# 取得日: 2026-11-05" in text
    assert '"画像"' in text
    assert read_templatedata_file(path) == REGISTRY


def test_壊れたTOMLは専用の例外で落ちる() -> None:
    with pytest.raises(TemplateDataSchemaError):
        parse_templatedata('[[template]\nname = "A"\n')
    with pytest.raises(TemplateDataSchemaError):
        parse_templatedata("[[template]]\nname = 1\n")
    with pytest.raises(TemplateDataSchemaError):
        parse_templatedata('[[template]]\nname = "A"\n未知 = 1\n')


def test_同じ名前のテンプレートが二度出てきたら例外() -> None:
    text = '[[template]]\nname = "A"\n[[template]]\nname = "A"\n'

    with pytest.raises(DuplicateTemplateError):
        parse_templatedata(text)


# --- 引数名とラベルの解決 -----------------------------------------------------------


def test_引数名でも別名でもラベルでも同じ引数に解決する() -> None:
    data = REGISTRY.find("Infobox 試験")
    assert data is not None

    assert data.resolve_name("氏名") == "氏名"
    assert data.resolve_name("name") == "氏名"
    assert data.resolve_name("名前") == "氏名"
    assert data.resolve_name("出身地") is None


def test_引数名の完全一致は別名やラベルより優先する() -> None:
    data = TemplateData(
        name="Infobox 優先",
        params=(
            TemplateParam(name="共通", aliases=("別",)),
            TemplateParam(name="別の引数", aliases=("共通",)),
        ),
    )

    param = data.resolve("共通")

    assert param is not None
    assert param.name == "共通"


def test_引数名とラベルが別の引数を指すときは決めない() -> None:
    data = TemplateData(
        name="Infobox 曖昧",
        params=(
            TemplateParam(name="甲", aliases=("共通",)),
            TemplateParam(name="乙", label="共通"),
        ),
    )

    assert data.resolve("共通") is None


def test_テンプレート名の接頭辞と下線をそろえる() -> None:
    assert normalize_template_name("Template:Infobox 人物") == "Infobox 人物"
    assert normalize_template_name("テンプレート:Infobox_人物") == "Infobox 人物"
    assert normalize_template_name("  Infobox  人物 ") == "Infobox 人物"


# --- 応答からの組み立て -------------------------------------------------------------


def test_応答のページから引数の定義を作る() -> None:
    page = {
        "title": "Template:Infobox 試験",
        "description": {"ja": "試験用のテンプレート"},
        "params": {
            "画像": {
                "label": None,
                "type": "wiki-file-name",
                "required": False,
                "aliases": ["image"],
                "description": {"ja": "顔写真"},
            },
            "氏名": {"label": {"ja": "名前"}, "type": "string", "required": True},
        },
    }

    data = template_data_from_page(page)

    assert data is not None
    assert data.name == "Infobox 試験"
    assert data.description == "試験用のテンプレート"
    image = data.resolve("image")
    assert image is not None
    assert image.name == "画像"
    assert image.image is True
    name = data.resolve("名前")
    assert name is not None
    assert name.name == "氏名"
    assert name.required is True


def test_応答に定義が無いページは何も作らない() -> None:
    assert template_data_from_page({"title": "Template:X", "missing": True}) is None


def test_引数が0件でも定義として扱う() -> None:
    data = template_data_from_page({"title": "Template:X", "params": {}})

    assert data == TemplateData(name="X")


# --- ウィキテキストへの書き出し -----------------------------------------------------


def test_別名で書いた項目も引数名で書き出す() -> None:
    front = _infobox_front('"name" = "甲野 乙女"')

    out = build_infobox(_article(front).settings, TYPES["person-living"], templatedata=REGISTRY)

    assert out.top == "{{Infobox 試験\n| 氏名 = 甲野 乙女\n}}"


def test_ラベルで書いた項目も引数名で書き出す() -> None:
    front = _infobox_front('"名前" = "甲野 乙女"')

    out = build_infobox(_article(front).settings, TYPES["person-living"], templatedata=REGISTRY)

    assert out.top == "{{Infobox 試験\n| 氏名 = 甲野 乙女\n}}"


def test_解決できない項目名は原稿のまま書き出す() -> None:
    front = _infobox_front('"出身地" = "東京"')

    out = build_infobox(_article(front).settings, TYPES["person-living"], templatedata=REGISTRY)

    assert out.top == "{{Infobox 試験\n| 出身地 = 東京\n}}"


def test_画像の引数は_image_fields_が無ければファイル名だけ渡す() -> None:
    front = _infobox_front('"image" = "![顔](images/顔.png)"')

    out = build_infobox(_article(front).settings, TYPES["person-living"], templatedata=REGISTRY)

    assert out.top == "{{Infobox 試験\n| 画像 = 顔.png\n}}"


def test__image_fields_を書いてあればそちらを優先する() -> None:
    front = (
        '[infobox]\n_template = "Infobox 試験"\n_image_fields = ["写真"]\n'
        '"画像" = "![甲野乙女](images/顔.png)"\n'
    )

    out = build_infobox(_article(front).settings, TYPES["person-living"], templatedata=REGISTRY)

    assert out.top == "{{Infobox 試験\n| 画像 = [[ファイル:顔.png|thumb|甲野乙女]]\n}}"


def test_同梱の定義でも別名を引数名に直す() -> None:
    front = '[infobox]\n_template = "Infobox 人物"\n"image" = "![顔](images/顔.png)"\n'

    out = build_infobox(_article(front).settings, TYPES["person-living"])

    assert out.top == "{{Infobox 人物\n| 画像 = 顔.png\n}}"


# --- HTML への書き出し -------------------------------------------------------------


def test_別名で書いた項目の見出しはラベルにする() -> None:
    article = _article(_infobox_front('"name" = "甲野 乙女"'))

    out = build_infobox_html(article.settings, TYPES["person-living"], templatedata=REGISTRY)

    assert '<th scope="row">名前</th><td>甲野 乙女</td>' in out


def test_解決できない項目の見出しは原稿の項目名にする() -> None:
    article = _article(_infobox_front('"出身地" = "東京"'))

    out = build_infobox_html(article.settings, TYPES["person-living"], templatedata=REGISTRY)

    assert '<th scope="row">出身地</th><td>東京</td>' in out


def test_画像の引数の値は図として埋め込む(tmp_path: Path) -> None:
    (tmp_path / "顔.png").write_bytes(FIXTURE.read_bytes())
    article = _article(_infobox_front('"image" = "![顔](顔.png)"'))

    out = build_infobox_html(
        article.settings, TYPES["person-living"], base_dir=tmp_path, templatedata=REGISTRY
    )

    assert '<th scope="row">画像</th>' in out
    assert '<img src="data:image/png;base64,' in out


def test_画像の引数でも形の違う値は文字のまま書き出す() -> None:
    article = _article(_infobox_front('"画像" = "顔写真"'))

    out = build_infobox_html(article.settings, TYPES["person-living"], templatedata=REGISTRY)

    assert '<th scope="row">画像</th><td>顔写真</td>' in out


# --- 検査 -------------------------------------------------------------------------


def test_定義に無い項目名は警告() -> None:
    findings = _findings(_infobox_front('"氏名" = "甲野 乙女"', '"出身地" = "東京"'))

    assert [f.rule for f in findings] == ["INFOBOX-UNKNOWN-FIELD"]
    assert findings[0].level is Level.WARNING
    assert findings[0].line == 7
    assert "出身地" in findings[0].message


def test_必須の引数が原稿に無ければエラー() -> None:
    findings = _findings(_infobox_front('"画像" = "顔.png"'))

    assert [f.rule for f in findings] == ["INFOBOX-MISSING"]
    assert findings[0].level is Level.ERROR
    assert findings[0].line == 6
    assert "名前" in findings[0].message


def test_同梱に無いテンプレートは何も言わない() -> None:
    front = _infobox_front('"似顔絵" = "顔.png"', template="Infobox 存在しない")

    assert _findings(front) == ()


def test_引数が0件のテンプレートは未知扱いしない() -> None:
    empty = TemplateDataRegistry(templates=(TemplateData(name="Infobox 空"),))
    front = _infobox_front('"何か" = "値"', template="Infobox 空")

    assert _findings(front, empty) == ()


def test_同梱の定義に無い項目名は警告する() -> None:
    front = '[infobox]\n_template = "Infobox 人物"\n"似顔絵" = "顔.png"\n'

    findings = only(_findings(front, None), "INFOBOX-UNKNOWN-FIELD")

    assert len(findings) == 1
    assert findings[0].level is Level.WARNING
    assert findings[0].line == 6
    assert "似顔絵" in findings[0].message


# --- コマンド ---------------------------------------------------------------------


def test_同梱の一覧を出す(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["templatedata"]) == 0

    out = capsys.readouterr().out
    assert "テンプレート" in out
    assert "引数" in out
    assert "- Infobox 人物（" in out


def test_同梱に無い名前は知らせて終わる(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["templatedata", "--template", "Infobox 存在しない"]) == 2

    assert "同梱に無い" in capsys.readouterr().err


def test_from_types_は型の参照先を数える(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["templatedata", "--from-types"]) == 0

    out = capsys.readouterr().out
    assert "型の定義が参照するテンプレート" in out
    assert "TemplateData が無く、同梱に載せられない" in out
