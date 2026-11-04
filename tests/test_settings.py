from textwrap import dedent

import pytest

from wikiskill.errors import MarkupError, SettingsError
from wikiskill.model import (
    ExternalLink,
    InfoboxField,
    InternalLink,
    Note,
    NoteMark,
    Reference,
    RefMark,
    Settings,
    Text,
)
from wikiskill.settings import parse_settings


def parse(*parts: str) -> Settings:
    """設定欄の本文（``+++`` の行は含めない）を読む。TOML の 1 行目は原稿の 2 行目。"""
    toml = "\n".join(dedent(part).strip("\n") for part in parts)
    return parse_settings(toml, first_line=2)


MINIMAL = """
title = "星屑ラーメン"
type = "manga"
"""


def test_必須の項目だけで読める() -> None:
    assert parse(MINIMAL) == Settings(title="星屑ラーメン", type_id="manga")


def test_任意の項目をすべて読める() -> None:
    settings = parse(
        """
        title = "星屑ラーメン"
        reading = "ほしくずらーめん"
        type = "manga"
        defaultsort = "ほしくずらーめん"
        categories = ["架空の漫画", "2020年の漫画"]
        related = ["架空の記事", "別の架空の記事"]

        [[external_links]]
        title = "公式サイト"
        url = "https://example.com/"

        [[external_links]]
        title = "作者の公式ブログ"
        url = "https://example.org/blog"
        """
    )
    assert settings.reading == "ほしくずらーめん"
    assert settings.defaultsort == "ほしくずらーめん"
    assert settings.categories == ("架空の漫画", "2020年の漫画")
    assert settings.related == ("架空の記事", "別の架空の記事")
    assert settings.external_links == (
        ExternalLink("公式サイト", "https://example.com/"),
        ExternalLink("作者の公式ブログ", "https://example.org/blog"),
    )


def test_infobox_は書いた順を保つ() -> None:
    settings = parse(
        MINIMAL,
        """
        [infobox]
        "作者" = "月見里 ほたる"
        "ジャンル" = "グルメ漫画"
        "連載期間" = "2020年 - 2023年"
        """,
    )
    assert settings.infobox == (
        InfoboxField("作者", "月見里 ほたる"),
        InfoboxField("ジャンル", "グルメ漫画"),
        InfoboxField("連載期間", "2020年 - 2023年"),
    )


def test__template_はInfoboxの項目にせずテンプレートの名前として読む() -> None:
    settings = parse(
        MINIMAL,
        """
        [infobox]
        _template = "Infobox 人物"
        "職業" = "小説家"
        """,
    )
    assert settings.infobox_template == "Infobox 人物"
    assert settings.infobox == (InfoboxField("職業", "小説家"),)


def test__template_が無ければNone() -> None:
    assert parse(MINIMAL, '[infobox]\n"作者" = "甲"').infobox_template is None


def test__template_の前後の空白は落とす() -> None:
    settings = parse(MINIMAL, '[infobox]\n_template = "  Infobox 人物  "')

    assert settings.infobox_template == "Infobox 人物"


def test__template_が文字列でなければ誤り() -> None:
    with pytest.raises(SettingsError) as info:
        parse(MINIMAL, "[infobox]\n_template = 1")

    assert info.value.line == 5
    assert "_template" in info.value.message


def test__template_が空白だけなら誤り() -> None:
    with pytest.raises(SettingsError) as info:
        parse(MINIMAL, '[infobox]\n_template = "   "')

    assert info.value.line == 5
    assert "Infobox 人物" in info.value.message


def test__template_に使えない文字があれば誤り() -> None:
    with pytest.raises(SettingsError) as info:
        parse(MINIMAL, '[infobox]\n_template = "Infobox 人物|x"')

    assert info.value.line == 5
    assert "使えない文字" in info.value.message


def test__image_fields_は本家がファイル名だけを受け取る引数として読む() -> None:
    settings = parse(
        MINIMAL,
        '[infobox]\n_template = "Infobox 人物"\n_image_fields = ["画像", "地図"]',
    )

    assert settings.infobox_images == ("画像", "地図")


def test__image_fields_が無ければ空() -> None:
    assert parse(MINIMAL, '[infobox]\n_template = "Infobox 人物"').infobox_images == ()


def test__image_fields_は_template_と一緒でなければ誤り() -> None:
    with pytest.raises(SettingsError) as info:
        parse(MINIMAL, '[infobox]\n_image_fields = ["画像"]')

    assert info.value.line == 5
    assert "_template" in info.value.message


def test__image_fields_が並びでなければ誤り() -> None:
    with pytest.raises(SettingsError) as info:
        parse(MINIMAL, '[infobox]\n_template = "Infobox 人物"\n_image_fields = "画像"')

    assert "_image_fields" in info.value.message


def test__image_fields_に使えない文字があれば誤り() -> None:
    with pytest.raises(SettingsError) as info:
        parse(MINIMAL, '[infobox]\n_template = "Infobox 人物"\n_image_fields = ["画|像"]')

    assert "使えない引数名" in info.value.message


def test_出典は種類ごとの項目を読み書いた順を保つ() -> None:
    settings = parse(
        MINIMAL,
        """
        [refs.z-web]
        kind = "web"
        title = "公式サイト"
        url = "https://example.com/"
        publisher = "架空出版"
        date = "2020-04-01"
        access_date = "2026-11-01"

        [refs.a_book]
        kind = "book"
        title = "星屑ラーメン 1"
        author = "月見里 ほたる"
        isbn = "978-4-00-000000-0"
        pages = "12-15"
        note = "初版"

        [refs.n1]
        kind = "news"
        title = "連載開始"
        work = "架空新聞"
        """,
    )
    assert settings.references == (
        Reference(
            key="z-web",
            kind="web",
            title="公式サイト",
            url="https://example.com/",
            publisher="架空出版",
            date="2020-04-01",
            access_date="2026-11-01",
        ),
        Reference(
            key="a_book",
            kind="book",
            title="星屑ラーメン 1",
            author="月見里 ほたる",
            isbn="978-4-00-000000-0",
            pages="12-15",
            note="初版",
        ),
        Reference(key="n1", kind="news", title="連載開始", work="架空新聞"),
    )


def test_注釈の本文は文中の記法を読む() -> None:
    settings = parse(
        MINIMAL,
        """
        [notes.yomi]
        text = "読みは[[架空の記事|別記事]]を参照[^a]。[^n:other]も見よ。"

        [notes.other]
        text = "ただの注釈。"
        """,
    )
    assert [note.key for note in settings.notes] == ["yomi", "other"]
    assert settings.notes[0] == Note(
        "yomi",
        (
            Text("読みは"),
            InternalLink("架空の記事", "別記事"),
            Text("を参照"),
            RefMark("a"),
            Text("。"),
            NoteMark("other"),
            Text("も見よ。"),
        ),
    )
    assert settings.notes[1] == Note("other", (Text("ただの注釈。"),))


@pytest.mark.parametrize(
    ("toml", "line", "keyword"),
    [
        # title がない: 設定欄全体の問題なので冒頭の +++ の行
        ('type = "manga"', 1, "title"),
        ('title = "題"', 1, "type"),
        # 型の誤り: その項目の行
        ('title = 1\ntype = "manga"', 2, "title"),
        ('title = ""\ntype = "manga"', 2, "title"),
        ('title = "題"\ntype = "Manga"', 3, "type"),
        ('title = "題"\ntype = "manga"\nreading = 1', 4, "reading"),
        ('title = "題"\ntype = "manga"\ncategories = "x"', 4, "categories"),
        ('title = "題"\ntype = "manga"\ncategories = ["x", 1]', 4, "categories"),
        ('title = "題"\ntype = "manga"\nrelated = [1]', 4, "related"),
        ('title = "題"\ntype = "manga"\ninfobox = "x"', 4, "infobox"),
        ('title = "題"\ntype = "manga"\nunknown = "x"', 4, "unknown"),
        ('title = "題"\ntype = "manga"\n[infobox]\n"生年" = 1990', 5, "生年"),
        # 出典
        ('title = "題"\ntype = "manga"\n[refs.a]\ntitle = "t"', 4, "kind"),
        ('title = "題"\ntype = "manga"\n[refs.a]\nkind = "web"', 4, "title"),
        ('title = "題"\ntype = "manga"\n[refs.a]\nkind = "blog"\ntitle = "t"', 5, "kind"),
        ('title = "題"\ntype = "manga"\n[refs.a]\nkind = "web"\ntitle = "t"\nurl = 1', 7, "url"),
        ('title = "題"\ntype = "manga"\n[refs.a]\nkind = "web"\ntitle = "t"\nfoo = "x"', 7, "foo"),
        ('title = "題"\ntype = "manga"\n[refs."日本語"]\nkind = "web"\ntitle = "t"', 4, "キー"),
        ('title = "題"\ntype = "manga"\nrefs = "x"', 4, "refs"),
        ('title = "題"\ntype = "manga"\n[refs]\na = "x"', 5, "a"),
        (
            'title = "題"\ntype = "manga"\n[refs.a]\nkind = "web"\ntitle = "t"\nweak = "yes"',
            7,
            "weak",
        ),
        ('title = "題"\ntype = "manga"\n[refs.a]\nkind = "web"\ntitle = "t"\nweak = 1', 7, "weak"),
        # 警告の枠
        ('title = "題"\ntype = "manga"\nnotices = "観点"', 4, "notices"),
        ('title = "題"\ntype = "manga"\nnotices = [1]', 4, "notices"),
        ('title = "題"\ntype = "manga"\nnotices = ["中立"]', 4, "中立"),
        # 注釈
        ('title = "題"\ntype = "manga"\n[notes.a]\ntext = 1', 5, "text"),
        ('title = "題"\ntype = "manga"\n[notes.a]\nfoo = "x"', 5, "foo"),
        ('title = "題"\ntype = "manga"\n[notes.a]', 4, "text"),
        # 外部リンク
        ('title = "題"\ntype = "manga"\n[[external_links]]\ntitle = "t"', 4, "url"),
        ('title = "題"\ntype = "manga"\n[[external_links]]\nurl = "u"', 4, "title"),
        (
            'title = "題"\ntype = "manga"\n[[external_links]]\ntitle = "t"\nurl = "u"\n'
            '[[external_links]]\ntitle = "t"\nurl = 1',
            9,
            "url",
        ),
    ],
)
def test_設定欄の誤りは原稿の行番号つきのエラー(toml: str, line: int, keyword: str) -> None:
    with pytest.raises(SettingsError) as info:
        parse_settings(toml, first_line=2)
    assert info.value.line == line, info.value
    assert keyword in info.value.message


def test_TOML_として読めなければ原稿の行番号つきのエラー() -> None:
    toml = 'title = "題"\ntype = \n'
    with pytest.raises(SettingsError) as info:
        parse_settings(toml, first_line=2)
    assert info.value.line == 3
    assert "TOML" in info.value.message
    assert "at line" not in info.value.message


def test_引用符のない日本語の項目名には直し方を添える() -> None:
    toml = 'title = "題"\ntype = "manga"\n[infobox]\n作者 = "月見里 ほたる"'
    with pytest.raises(SettingsError) as info:
        parse_settings(toml, first_line=2)
    assert info.value.line == 5
    assert '"作者" = ' in info.value.message


def test_同じキーの重複は_TOML_のエラー() -> None:
    toml = 'title = "題"\ntitle = "別"\ntype = "manga"'
    with pytest.raises(SettingsError) as info:
        parse_settings(toml, first_line=2)
    assert info.value.line == 3


def test_注釈の本文の記法の誤りは_text_の行を指す() -> None:
    toml = 'title = "題"\ntype = "manga"\n[notes.a]\ntext = "[[閉じない"'
    with pytest.raises(MarkupError) as info:
        parse_settings(toml, first_line=2)
    assert info.value.line == 5
    assert "[[" in info.value.message


def test_出典の_weak_は真偽値で既定は偽() -> None:
    settings = parse(
        MINIMAL,
        """
        [refs.a]
        kind = "web"
        title = "攻略 Wiki"
        weak = true

        [refs.b]
        kind = "web"
        title = "公式"
        """,
    )
    assert [r.weak for r in settings.references] == [True, False]
    assert Reference(key="b", kind="web", title="公式").weak is False


def test_警告の枠の_notices_を読む() -> None:
    settings = parse(MINIMAL, 'notices = ["観点", "独自研究"]')
    assert settings.notices == ("観点", "独自研究")
    assert parse(MINIMAL).notices == ()
