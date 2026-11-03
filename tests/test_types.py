from pathlib import Path
from textwrap import dedent

import pytest

from wikiskill.types import (
    ArticleType,
    DuplicateTypeError,
    InfoboxError,
    InfoboxField,
    InfoboxPart,
    ParentNotBaseError,
    TypeRegistry,
    TypeRegistryError,
    TypeSchemaError,
    UnknownParentError,
    UnknownTypeError,
    load_default_registry,
    parse_registry,
    read_registry_file,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

BASE_IDS = {
    "person-living",
    "person-deceased",
    "manga",
    "anime",
    "game",
    "film",
    "novel-drama",
    "event",
    "place",
    "organization",
    "product",
    "concept",
    "meme",
    "music-work",
    "racehorse",
    "country-municipality",
    "law",
    "species",
    "festival",
}


def parse(text: str) -> TypeRegistry:
    return parse_registry(dedent(text))


MINIMAL = """
    [[type]]
    id = "manga"
    name = "漫画"
    [[type.infobox]]
    template = "Infobox animanga/Manga"
    required = ["作者"]
    [type.infobox.fields]
    "作者" = "作者"
    "出版社" = "出版社"
"""


# --- 同梱の定義 ------------------------------------------------------------------


def test_同梱の定義が読めて型は19の基本型を含む() -> None:
    registry = load_default_registry()
    assert {t.id for t in registry if t.is_base} == BASE_IDS
    assert len(BASE_IDS) == 19


def test_同梱の定義の細かい種類はすべて基本型へ寄せている() -> None:
    registry = load_default_registry()
    kinds = [t for t in registry if not t.is_base]
    assert kinds, "細かい種類が一つもない"
    for kind in kinds:
        for parent_id in kind.parents:
            assert registry[parent_id].is_base


def test_同梱の定義の細かい種類は指定された寄せ先に入っている() -> None:
    registry = load_default_registry()
    expected = {
        "voice-actor": "person-living",
        "singer": "person-living",
        "baseball-player": "person-living",
        "band": "organization",
        "comedy-duo": "organization",
        "soccer-club": "organization",
        "government-agency": "organization",
        "academic-body": "organization",
        "railcar": "product",
        "aircraft": "product",
        "automobile": "product",
        "software": "product",
        "web-service": "product",
        "court-case": "event",
        "album": "music-work",
    }
    for kind_id, parent_id in expected.items():
        assert parent_id in registry[kind_id].parents, kind_id


def test_概念とネットミームと判例はinfoboxを持たない() -> None:
    registry = load_default_registry()
    for type_id in ("concept", "meme", "court-case"):
        article_type = registry[type_id]
        assert not article_type.has_infobox
        assert article_type.infobox == ()


def test_漫画のinfoboxは3部構成で必須が決まっている() -> None:
    manga = load_default_registry()["manga"]
    assert [p.template for p in manga.infobox] == [
        "Infobox animanga/Header",
        "Infobox animanga/Manga",
        "Infobox animanga/Footer",
    ]
    assert {f.label for f in manga.required_fields} >= {"作者", "出版社"}


def test_アニメのinfoboxは3部構成() -> None:
    anime = load_default_registry()["anime"]
    assert [p.template for p in anime.infobox] == [
        "Infobox animanga/Header",
        "Infobox animanga/TVAnime",
        "Infobox animanga/Footer",
    ]
    assert {"放送局", "放送開始"} <= {f.label for f in anime.required_fields}


def test_法令のテンプレートは導入部の中に置く() -> None:
    law = load_default_registry()["law"]
    assert [p.placement for p in law.infobox] == ["lead"]
    assert law.infobox[0].template == "日本の法令"


def test_ほかのinfoboxは記事の最上部に置く() -> None:
    registry = load_default_registry()
    for article_type in registry:
        if article_type.id == "law":
            continue
        assert all(part.placement == "top" for part in article_type.infobox), article_type.id


def test_存命と故人の人物は没年月日の欄の有無で分かれる() -> None:
    registry = load_default_registry()
    living = registry["person-living"]
    deceased = registry["person-deceased"]
    assert living.find_field("没年月日") is None
    assert deceased.find_field("没年月日") is not None
    assert "没年月日" in {f.label for f in deceased.required_fields}


def test_すべての型で必須の項目は並びの中にあり名前は空でない() -> None:
    for article_type in load_default_registry():
        assert article_type.name
        labels = [f.label for f in article_type.fields]
        assert len(labels) == len(set(labels)), article_type.id
        assert all(f.param for f in article_type.fields)


def test_idから型を引ける() -> None:
    registry = load_default_registry()
    assert registry["manga"].name == "漫画"
    assert registry.find("manga") is registry["manga"]
    assert "manga" in registry
    assert "no-such-type" not in registry
    assert registry.find("no-such-type") is None


def test_存在しないidを引くと専用の例外() -> None:
    with pytest.raises(UnknownTypeError) as info:
        load_default_registry()["no-such-type"]
    assert "no-such-type" in str(info.value)


def test_基本型から細かい種類を引ける() -> None:
    registry = load_default_registry()
    assert "band" in {t.id for t in registry.kinds_of("organization")}
    assert registry.kinds_of("meme") == ()


def test_ファイルからも読める() -> None:
    path = (
        REPO_ROOT / "plugins" / "wiki-style-article" / "skills" / "wiki" / "assets" / "types.toml"
    )
    assert len(read_registry_file(path)) == len(load_default_registry())


def read_type_tables() -> dict[str, tuple[str, list[str]]]:
    """docs/types.md の一覧表を、節の名前とセルの並びで返す。"""
    document = (REPO_ROOT / "docs" / "types.md").read_text(encoding="utf-8")
    rows: dict[str, tuple[str, list[str]]] = {}
    section = ""
    for line in document.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            section = stripped.lstrip("#").strip()
            continue
        if section not in {"基本型", "細かい種類"} or not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not cells[0].startswith("`"):
            continue
        rows[cells[0].strip("`")] = (section, cells)
    return rows


def split_cell(cell: str, separator: str) -> list[str]:
    return [p.strip().strip("`") for p in cell.split(separator) if p.strip().strip("`")]


def test_型の一覧文書の表が定義と一致する() -> None:
    registry = load_default_registry()
    rows = read_type_tables()
    assert sorted(rows) == sorted(t.id for t in registry)

    problems: list[str] = []
    for article_type in registry:
        type_id = article_type.id
        section, cells = rows[type_id]
        expected_columns = 4 if section == "基本型" else 5
        if len(cells) != expected_columns:
            problems.append(f"{type_id}: 列数 {len(cells)}（{expected_columns} のはず）")
            continue
        if section == "基本型":
            parents_cell, template_cell, required_cell = "", cells[2], cells[3]
        else:
            parents_cell, template_cell, required_cell = cells[2], cells[3], cells[4]

        parents = list(article_type.parents)
        documented_parents = split_cell(parents_cell, "、")
        if documented_parents != parents:
            problems.append(f"{type_id}: 寄せ先が {documented_parents}（定義は {parents}）")

        if template_cell.startswith("なし"):
            documented_templates: list[str] = []
        else:
            documented_templates = split_cell(template_cell.split("（")[0], "＋")
        templates = [part.template for part in article_type.infobox]
        if documented_templates != templates:
            problems.append(f"{type_id}: テンプレートが {documented_templates}（{templates}）")

        documented_required = [] if required_cell in {"―", "-"} else split_cell(required_cell, "、")
        required = [f.label for f in article_type.required_fields]
        if documented_required != required:
            problems.append(f"{type_id}: 必須の項目が {documented_required}（定義は {required}）")

    assert problems == []


# --- 読み取り結果の形 ------------------------------------------------------------


def test_最小の定義を読める() -> None:
    registry = parse(MINIMAL)
    manga = registry["manga"]
    assert manga == ArticleType(
        id="manga",
        name="漫画",
        parents=(),
        infobox=(
            InfoboxPart(
                template="Infobox animanga/Manga",
                placement="top",
                title_field=None,
                fields=(
                    InfoboxField(label="作者", param="作者", required=True, unverified=False),
                    InfoboxField(label="出版社", param="出版社", required=False, unverified=False),
                ),
            ),
        ),
    )
    assert manga.is_base
    assert manga.has_infobox


def test_項目の並びは書いた順を保つ() -> None:
    registry = parse(
        """
        [[type]]
        id = "film"
        name = "映画"
        [[type.infobox]]
        template = "Infobox Film"
        [type.infobox.fields]
        "監督" = "監督"
        "作品名" = "作品名"
        "公開" = "公開"
        """
    )
    assert [f.label for f in registry["film"].fields] == ["監督", "作品名", "公開"]


def test_日本語の項目名とテンプレートの引数名を別々に持てる() -> None:
    registry = parse(
        """
        [[type]]
        id = "author"
        name = "作家"
        [[type.infobox]]
        template = "Infobox 作家"
        [type.infobox.fields]
        "生年月日" = "birth_date"
        """
    )
    field = registry["author"].fields[0]
    assert (field.label, field.param) == ("生年月日", "birth_date")


def test_未確認の印を読める() -> None:
    registry = parse(
        """
        [[type]]
        id = "film"
        name = "映画"
        [[type.infobox]]
        template = "Infobox Film"
        unverified = ["配給"]
        [type.infobox.fields]
        "監督" = "監督"
        "配給" = "配給"
        """
    )
    unverified = {f.label: f.unverified for f in registry["film"].fields}
    assert unverified == {"監督": False, "配給": True}


def test_複数の部品で全体の項目名が重ならなければ並べられる() -> None:
    registry = parse(
        """
        [[type]]
        id = "anime"
        name = "アニメ"
        [[type.infobox]]
        template = "Infobox animanga/Header"
        [type.infobox.fields]
        "ジャンル" = "ジャンル"
        [[type.infobox]]
        template = "Infobox animanga/TVAnime"
        required = ["放送局"]
        [type.infobox.fields]
        "放送局" = "放送局"
        [[type.infobox]]
        template = "Infobox animanga/Footer"
        [type.infobox.fields]
        "ウィキプロジェクト" = "ウィキプロジェクト"
        """
    )
    anime = registry["anime"]
    assert [p.template for p in anime.infobox] == [
        "Infobox animanga/Header",
        "Infobox animanga/TVAnime",
        "Infobox animanga/Footer",
    ]
    assert [f.label for f in anime.fields] == ["ジャンル", "放送局", "ウィキプロジェクト"]
    assert [f.label for f in anime.required_fields] == ["放送局"]


def test_infoboxを持たない型はno_infoboxで明示する() -> None:
    registry = parse(
        """
        [[type]]
        id = "meme"
        name = "ネットミーム"
        no_infobox = true
        """
    )
    assert not registry["meme"].has_infobox
    assert registry["meme"].fields == ()


def test_細かい種類は寄せ先を複数持てる() -> None:
    registry = parse(
        """
        [[type]]
        id = "person-living"
        name = "人物（存命）"
        no_infobox = true
        [[type]]
        id = "person-deceased"
        name = "人物（故人）"
        no_infobox = true
        [[type]]
        id = "actor"
        name = "俳優"
        parents = ["person-living", "person-deceased"]
        no_infobox = true
        """
    )
    assert registry["actor"].parents == ("person-living", "person-deceased")
    assert not registry["actor"].is_base
    assert [t.id for t in registry.kinds_of("person-deceased")] == ["actor"]


def test_記事名を既定値にする項目を指定できる() -> None:
    registry = parse(
        """
        [[type]]
        id = "film"
        name = "映画"
        [[type.infobox]]
        template = "Infobox Film"
        title_field = "作品名"
        required = ["監督"]
        [type.infobox.fields]
        "作品名" = "作品名"
        "監督" = "監督"
        """
    )
    part = registry["film"].infobox[0]
    assert part.title_field == "作品名"
    assert [f.label for f in registry["film"].required_fields] == ["監督"]


# --- 壊れた定義 ------------------------------------------------------------------


def test_例外はすべて共通の基底を持つ() -> None:
    for error in (
        TypeSchemaError,
        DuplicateTypeError,
        UnknownParentError,
        ParentNotBaseError,
        InfoboxError,
        UnknownTypeError,
    ):
        assert issubclass(error, TypeRegistryError)


def test_TOMLとして読めないと専用の例外() -> None:
    with pytest.raises(TypeSchemaError, match="TOML"):
        parse_registry("[[type]\nid = ")


def test_型が一つもないと専用の例外() -> None:
    with pytest.raises(TypeSchemaError, match="type"):
        parse_registry("")


def test_重複したidは専用の例外() -> None:
    with pytest.raises(DuplicateTypeError, match="manga"):
        parse(
            """
            [[type]]
            id = "manga"
            name = "漫画"
            no_infobox = true
            [[type]]
            id = "manga"
            name = "別の漫画"
            no_infobox = true
            """
        )


def test_使えないidは専用の例外() -> None:
    for bad in ("Manga", "man_ga", "manga2", "-manga", "manga-", ""):
        with pytest.raises(TypeSchemaError, match="id"):
            parse(
                f"""
                [[type]]
                id = "{bad}"
                name = "漫画"
                no_infobox = true
                """
            )


def test_寄せ先が無いと専用の例外() -> None:
    with pytest.raises(UnknownParentError, match="person-living"):
        parse(
            """
            [[type]]
            id = "voice-actor"
            name = "声優"
            parents = ["person-living"]
            no_infobox = true
            """
        )


def test_寄せ先が細かい種類だと専用の例外() -> None:
    with pytest.raises(ParentNotBaseError, match="actor"):
        parse(
            """
            [[type]]
            id = "person-living"
            name = "人物（存命）"
            no_infobox = true
            [[type]]
            id = "actor"
            name = "俳優"
            parents = ["person-living"]
            no_infobox = true
            [[type]]
            id = "child-actor"
            name = "子役"
            parents = ["actor"]
            no_infobox = true
            """
        )


def test_自分自身への寄せは専用の例外() -> None:
    with pytest.raises(ParentNotBaseError, match="manga"):
        parse(
            """
            [[type]]
            id = "manga"
            name = "漫画"
            parents = ["manga"]
            no_infobox = true
            """
        )


def test_寄せ先は空にできず重複もできない() -> None:
    with pytest.raises(TypeSchemaError, match="parents"):
        parse(
            """
            [[type]]
            id = "x"
            name = "x"
            parents = []
            no_infobox = true
            """
        )
    with pytest.raises(TypeSchemaError, match="parents"):
        parse(
            """
            [[type]]
            id = "x"
            name = "x"
            parents = ["a", "a"]
            no_infobox = true
            """
        )


def test_必須の項目が並びに無いと専用の例外() -> None:
    with pytest.raises(InfoboxError, match="出版社"):
        parse(
            """
            [[type]]
            id = "manga"
            name = "漫画"
            [[type.infobox]]
            template = "Infobox animanga/Manga"
            required = ["作者", "出版社"]
            [type.infobox.fields]
            "作者" = "作者"
            """
        )


def test_未確認の項目が並びに無いと専用の例外() -> None:
    with pytest.raises(InfoboxError, match="配給"):
        parse(
            """
            [[type]]
            id = "film"
            name = "映画"
            [[type.infobox]]
            template = "Infobox Film"
            unverified = ["配給"]
            [type.infobox.fields]
            "監督" = "監督"
            """
        )


def test_必須の項目が重複して書かれていると専用の例外() -> None:
    with pytest.raises(InfoboxError, match="作者"):
        parse(
            """
            [[type]]
            id = "manga"
            name = "漫画"
            [[type.infobox]]
            template = "Infobox animanga/Manga"
            required = ["作者", "作者"]
            [type.infobox.fields]
            "作者" = "作者"
            """
        )


def test_部品をまたいで項目名が重なると専用の例外() -> None:
    with pytest.raises(InfoboxError, match="ジャンル"):
        parse(
            """
            [[type]]
            id = "anime"
            name = "アニメ"
            [[type.infobox]]
            template = "Infobox animanga/Header"
            [type.infobox.fields]
            "ジャンル" = "ジャンル"
            [[type.infobox]]
            template = "Infobox animanga/TVAnime"
            [type.infobox.fields]
            "ジャンル" = "genre"
            """
        )


def test_同じ部品の中で引数名が重なると専用の例外() -> None:
    with pytest.raises(InfoboxError, match="birth_date"):
        parse(
            """
            [[type]]
            id = "author"
            name = "作家"
            [[type.infobox]]
            template = "Infobox 作家"
            [type.infobox.fields]
            "生年月日" = "birth_date"
            "誕生日" = "birth_date"
            """
        )


def test_infoboxの部品が空だと専用の例外() -> None:
    with pytest.raises(InfoboxError, match="Infobox 作家"):
        parse(
            """
            [[type]]
            id = "author"
            name = "作家"
            [[type.infobox]]
            template = "Infobox 作家"
            [type.infobox.fields]
            """
        )


def test_infoboxの有無を明示しないと専用の例外() -> None:
    with pytest.raises(InfoboxError, match="no_infobox"):
        parse(
            """
            [[type]]
            id = "manga"
            name = "漫画"
            """
        )


def test_no_infoboxとinfoboxの両方を書くと専用の例外() -> None:
    with pytest.raises(InfoboxError, match="no_infobox"):
        parse(MINIMAL.replace('name = "漫画"', 'name = "漫画"\n    no_infobox = true'))


def test_no_infoboxがfalseのままinfoboxも無いと専用の例外() -> None:
    with pytest.raises(InfoboxError, match="no_infobox"):
        parse(
            """
            [[type]]
            id = "manga"
            name = "漫画"
            no_infobox = false
            """
        )


def test_置き場所の値が不正だと専用の例外() -> None:
    with pytest.raises(TypeSchemaError, match="placement"):
        parse(MINIMAL.replace('required = ["作者"]', 'placement = "bottom"'))


def test_未知の項目は書き間違いとしてエラー() -> None:
    with pytest.raises(TypeSchemaError, match="nmae"):
        parse(
            """
            [[type]]
            id = "meme"
            nmae = "ミーム"
            no_infobox = true
            """
        )
    with pytest.raises(TypeSchemaError, match="requird"):
        parse(MINIMAL.replace("required =", "requird ="))
    with pytest.raises(TypeSchemaError, match="extra"):
        parse_registry('extra = 1\n[[type]]\nid = "meme"\nname = "x"\nno_infobox = true\n')


def test_必須のキーが無いと専用の例外() -> None:
    with pytest.raises(TypeSchemaError, match="name"):
        parse(
            """
            [[type]]
            id = "meme"
            no_infobox = true
            """
        )
    with pytest.raises(TypeSchemaError, match="template"):
        parse(
            """
            [[type]]
            id = "meme"
            name = "x"
            [[type.infobox]]
            [type.infobox.fields]
            "a" = "a"
            """
        )
    with pytest.raises(TypeSchemaError, match="fields"):
        parse(
            """
            [[type]]
            id = "meme"
            name = "x"
            [[type.infobox]]
            template = "T"
            """
        )


def test_値の型が違うと専用の例外() -> None:
    with pytest.raises(TypeSchemaError, match="name"):
        parse(
            """
            [[type]]
            id = "meme"
            name = 3
            no_infobox = true
            """
        )
    with pytest.raises(TypeSchemaError, match="no_infobox"):
        parse(
            """
            [[type]]
            id = "meme"
            name = "x"
            no_infobox = "yes"
            """
        )
    with pytest.raises(TypeSchemaError, match="作者"):
        parse(MINIMAL.replace('"作者" = "作者"', '"作者" = 3'))
    with pytest.raises(TypeSchemaError, match="required"):
        parse(MINIMAL.replace('required = ["作者"]', 'required = "作者"'))


def test_記事名を既定値にする項目が並びに無いと専用の例外() -> None:
    with pytest.raises(InfoboxError, match="作品名"):
        parse(
            """
            [[type]]
            id = "film"
            name = "映画"
            [[type.infobox]]
            template = "Infobox Film"
            title_field = "作品名"
            [type.infobox.fields]
            "監督" = "監督"
            """
        )


def test_記事名を既定値にする項目を必須にすると専用の例外() -> None:
    with pytest.raises(InfoboxError, match="作品名"):
        parse(
            """
            [[type]]
            id = "film"
            name = "映画"
            [[type.infobox]]
            template = "Infobox Film"
            title_field = "作品名"
            required = ["作品名"]
            [type.infobox.fields]
            "作品名" = "作品名"
            """
        )


def test_画像の項目と書式を指定できる() -> None:
    registry = parse(
        """
        [[type]]
        id = "election"
        name = "選挙"
        [[type.infobox]]
        template = "Infobox Election"
        [type.infobox.fields]
        "候補者" = "candidate"
        "地図" = "map_image"
        "写真" = "image"
        [type.infobox.image_fields]
        "地図" = "name"
        "写真" = "file"
        """
    )

    images = {f.label: f.image for f in registry["election"].fields}
    assert images == {"候補者": None, "地図": "name", "写真": "file"}


def test_同梱の選挙の地図は素のファイル名で書く() -> None:
    field = load_default_registry()["election"].find_field("地図")

    assert field is not None
    assert field.image == "name"


def test_画像の書式がnameでもfileでもなければ専用の例外() -> None:
    with pytest.raises(TypeSchemaError, match="書式"):
        parse(
            """
            [[type]]
            id = "election"
            name = "選挙"
            [[type.infobox]]
            template = "Infobox Election"
            [type.infobox.fields]
            "地図" = "map_image"
            [type.infobox.image_fields]
            "地図" = "thumb"
            """
        )


def test_画像の項目が並びに無いと専用の例外() -> None:
    with pytest.raises(InfoboxError, match="地図"):
        parse(
            """
            [[type]]
            id = "election"
            name = "選挙"
            [[type.infobox]]
            template = "Infobox Election"
            [type.infobox.fields]
            "候補者" = "candidate"
            [type.infobox.image_fields]
            "地図" = "name"
            """
        )


def test_記事名を既定値にする項目を画像にすると専用の例外() -> None:
    with pytest.raises(InfoboxError, match="作品名"):
        parse(
            """
            [[type]]
            id = "film"
            name = "映画"
            [[type.infobox]]
            template = "Infobox Film"
            title_field = "作品名"
            [type.infobox.fields]
            "作品名" = "作品名"
            [type.infobox.image_fields]
            "作品名" = "name"
            """
        )
