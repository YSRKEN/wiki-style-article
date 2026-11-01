from pathlib import Path

import pytest

from wikiskill.errors import FrontMatterError, MarkupError, SettingsError, SourceError
from wikiskill.model import (
    Bold,
    BulletList,
    ExternalLink,
    InfoboxField,
    InternalLink,
    Note,
    NoteMark,
    Paragraph,
    Reference,
    RefMark,
    Section,
    Text,
)
from wikiskill.reader import read_article, read_article_file

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "sample_article.md"


def test_見本の原稿を読める() -> None:
    article = read_article_file(SAMPLE)

    settings = article.settings
    assert settings.title == "星屑ラーメン"
    assert settings.reading == "ほしくずらーめん"
    assert settings.type_id == "manga"
    assert settings.defaultsort == "ほしくずらーめん"
    assert settings.categories == ("架空の漫画作品", "グルメ漫画")
    assert settings.related == ("架空の屋台文化", "月見里 ほたる")
    assert settings.infobox == (
        InfoboxField("ジャンル", "グルメ漫画"),
        InfoboxField("作者", "月見里 ほたる"),
        InfoboxField("出版社", "架空出版"),
        InfoboxField("連載期間", "2020年4月 - 2023年3月"),
    )
    assert [ref.key for ref in settings.references] == ["official", "vol1", "news-start"]
    assert settings.references[1] == Reference(
        key="vol1",
        kind="book",
        title="星屑ラーメン 第1巻",
        author="月見里 ほたる",
        publisher="架空出版",
        date="2020-09-01",
        isbn="978-4-00-000000-0",
        pages="3-20",
    )
    assert settings.notes == (
        Note("yomi", (Text("題名の読みは単行本の表記による"), RefMark("vol1"), Text("。"))),
        Note(
            "stall",
            (
                Text("作中の屋台は"),
                InternalLink("架空の屋台文化", "屋台"),
                Text("がモデルとされる。"),
            ),
        ),
    )
    assert settings.external_links == (ExternalLink("公式サイト", "https://example.com/hoshikuzu"),)


def test_見本の原稿の導入部を読める() -> None:
    article = read_article_file(SAMPLE)

    assert article.lead == (
        Paragraph(
            (
                Bold((Text("星屑ラーメン"),)),
                Text("（ほしくずらーめん）は、"),
                InternalLink("月見里 ほたる", None),
                Text("による日本の"),
                InternalLink("グルメ漫画", None),
                Text("。2020年4月から2023年3月まで連載された"),
                RefMark("news-start"),
                Text("。題名の読み方には補足がある"),
                NoteMark("yomi"),
                Text("。"),
            )
        ),
    )


def test_見本の原稿の節の木を読める() -> None:
    article = read_article_file(SAMPLE)

    assert [(s.level, s.title) for s in article.sections] == [
        (2, "概要"),
        (2, "登場する店"),
        (2, "年表"),
    ]
    overview, shops, timeline = article.sections
    assert overview.blocks == (
        Paragraph(
            (
                Text(
                    "夜の街に現れる屋台のラーメン店を舞台にした作品。"
                    "客の悩みを一杯のラーメンが解きほぐす、一話完結の形をとる"
                ),
                RefMark("official"),
                RefMark("vol1"),
                Text("。"),
            )
        ),
    )
    assert shops.blocks == ()
    assert [(s.level, s.title) for s in shops.children] == [(3, "屋台「天の川」"), (3, "常連客")]
    stall = shops.children[0]
    assert stall.children == (
        Section(
            4,
            "メニュー",
            (
                BulletList(
                    (
                        (Text("醤油ラーメン"),),
                        (Text("塩ラーメン"),),
                        (Text("星屑ラーメン（季節限定）"),),
                    )
                ),
            ),
            (),
        ),
    )
    assert timeline.blocks == (
        BulletList(
            (
                (Text("2020年4月 - 連載開始"),),
                (Text("2023年3月 - 連載終了"), RefMark("news-start")),
            )
        ),
    )


def test_読み取り結果は変更できない() -> None:
    article = read_article_file(SAMPLE)
    with pytest.raises(AttributeError):
        article.settings = article.settings  # type: ignore[misc]


def test_設定欄だけで本文が空でも読める() -> None:
    article = read_article('+++\ntitle = "題"\ntype = "meme"\n+++\n')
    assert article.settings.title == "題"
    assert article.lead == ()
    assert article.sections == ()


def test_改行コードや_BOM_の違いを吸収する() -> None:
    text = '﻿+++\r\ntitle = "題"\r\ntype = "meme"\r\n+++\r\n導入\r\n。\r\n'
    article = read_article(text)
    assert article.lead == (Paragraph((Text("導入。"),)),)


def test_本文のエラーの行番号は原稿ファイル全体での行() -> None:
    text = '+++\ntitle = "題"\ntype = "meme"\n+++\n導入。\n\n# 使えない見出し\n'
    with pytest.raises(MarkupError) as info:
        read_article(text)
    assert info.value.line == 7


def test_設定欄のエラーの行番号は原稿ファイル全体での行() -> None:
    text = '+++\ntitle = "題"\ntype = 1\n+++\n本文\n'
    with pytest.raises(SettingsError) as info:
        read_article(text)
    assert info.value.line == 3


@pytest.mark.parametrize(
    "text",
    [
        "",
        "本文だけ\n",
        '\ntitle = "題"\ntype = "meme"\n+++\n',
        '+++\ntitle = "題"\ntype = "meme"\n',
    ],
)
def test_設定欄の枠が壊れていれば_FrontMatterError(text: str) -> None:
    with pytest.raises(FrontMatterError) as info:
        read_article(text)
    assert info.value.line == 1


def test_すべての例外は_SourceError_の仲間() -> None:
    assert issubclass(FrontMatterError, SourceError)
    assert issubclass(SettingsError, SourceError)
    assert issubclass(MarkupError, SourceError)


def test_UTF_8_として読めないファイルは行番号つきのエラー(tmp_path: Path) -> None:
    path = tmp_path / "broken.md"
    path.write_bytes(b'+++\ntitle = "\xff"\ntype = "meme"\n+++\n')
    with pytest.raises(SourceError) as info:
        read_article_file(path)
    assert info.value.line == 2
    assert "UTF-8" in info.value.message
