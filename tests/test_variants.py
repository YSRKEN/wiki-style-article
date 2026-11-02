from helpers import make_article
from wikiskill.checks import check_article
from wikiskill.model import (
    Article,
    Bold,
    BulletList,
    FixMark,
    FixRange,
    Paragraph,
    RefMark,
    RumorRange,
    Section,
    Text,
)
from wikiskill.variants import has_rumor, normal_view, rumor_view

_REFS = """
[refs.a]
kind = "web"
title = "確かな出典"
url = "https://example.com/a"
access_date = "2026-11-01"

[refs.b]
kind = "web"
title = "噂の出典"
url = "https://example.com/b"
access_date = "2026-11-01"
weak = true
"""


def _all_inline(article: Article) -> list[object]:
    """記事の本文と注釈に出てくる部品を、入れ子の中まで一列にする。"""
    found: list[object] = []

    def visit(parts: tuple[object, ...]) -> None:
        for part in parts:
            found.append(part)
            if isinstance(part, Bold | FixRange | RumorRange):
                visit(part.children)

    def blocks(items: tuple[Paragraph | BulletList, ...]) -> None:
        for block in items:
            if isinstance(block, Paragraph):
                visit(block.content)
            else:
                for item in block.items:
                    visit(item)

    def sections(items: tuple[Section, ...]) -> None:
        for section in items:
            blocks(section.blocks)
            sections(section.children)

    blocks(article.lead)
    sections(article.sections)
    for note in article.settings.notes:
        visit(note.text)
    return found


# --- has_rumor ----------------------------------------------------------------------


def test_噂の無い原稿は噂なし() -> None:
    assert has_rumor(make_article("本文。\n\n## 節\n\n本文。")) is False


def test_文の中の噂の範囲があれば噂あり() -> None:
    assert has_rumor(make_article("本文[!噂|という噂]。")) is True


def test_噂の節があれば噂あり() -> None:
    assert has_rumor(make_article("本文。\n\n## 歴史\n\n本文。\n\n### 騒動 [!噂]\n\n噂。")) is True


def test_注釈の中の噂の範囲も数える() -> None:
    article = make_article("本文[^n:x]。", '[notes.x]\ntext = "注[!噂|の噂]。"\n')
    assert has_rumor(article) is True


# --- 通常の版 -----------------------------------------------------------------------


def test_通常の版は噂の範囲を取り除き前後の文字を一つにまとめる() -> None:
    article = make_article("店は繁盛した[!噂|が、閉店が近いという]。")

    view = normal_view(article)

    assert view.lead == (Paragraph((Text("店は繁盛した。"),)),)


def test_通常の版は噂だけの段落と箇条の項目を取り除く() -> None:
    body = (
        "一つ目。\n\n[!噂|噂だけの段落。]\n\n"
        "- 項目一\n-  [!噂|噂の項目]  \n- 項目三\n\n- [!噂|全部噂]"
    )
    article = make_article(body)

    view = normal_view(article)

    assert view.lead == (
        Paragraph((Text("一つ目。"),)),
        BulletList(((Text("項目一"),), (Text("項目三"),))),
    )
    lists = [b for b in view.lead if isinstance(b, BulletList)]
    assert lists[0].item_lines == (9, 11)


def test_通常の版は噂の節を子の節ごと取り除く() -> None:
    body = (
        "導入。\n\n## 歴史\n\n本文。\n\n### 騒動 [!噂]\n\n噂。\n\n#### 余波\n\n余波。"
        "\n\n### 現在\n\n今。\n\n## 炎上 [!噂]\n\n炎上。"
    )
    article = make_article(body)

    view = normal_view(article)

    assert [s.title for s in view.sections] == ["歴史"]
    assert [c.title for c in view.sections[0].children] == ["現在"]


def test_通常の版は使われなくなった出典と注釈を外す() -> None:
    body = "本文[^a]。[!噂|噂がある[^b][!信頼性要検証][^n:x]。]"
    settings = _REFS + '\n[notes.x]\ntext = "噂の注釈[^b][!信頼性要検証]。"\n'
    article = make_article(body, settings)

    view = normal_view(article)

    assert [r.key for r in view.settings.references] == ["a"]
    assert view.settings.notes == ()


def test_通常の版は元から使われていない出典を残す() -> None:
    article = make_article("本文[^a]。", _REFS)

    view = normal_view(article)

    # 元の原稿で使われていない b は、どちらの版でも REF-UNUSED で知らせるために残す。
    assert [r.key for r in view.settings.references] == ["a", "b"]


def test_通常の版は観点の枠を外す() -> None:
    article = make_article("本文[!噂|噂]。", 'notices = ["出典の明記", "観点"]\n')

    assert normal_view(article).settings.notices == ("出典の明記",)


def test_通常の版は注釈の中の噂の範囲も取り除く() -> None:
    article = make_article("本文[^n:x]。", '[notes.x]\ntext = "注[!噂|の噂]だ。"\n')

    view = normal_view(article)

    assert view.settings.notes[0].text == (Text("注だ。"),)


def test_通常の版に噂の部品は残らない() -> None:
    body = "a[!噂|b'''c'''[!要出典]]d\n\n## 節 [!噂]\n\n噂。"
    view = normal_view(make_article(body))

    assert not has_rumor(view)
    assert not any(isinstance(p, RumorRange) for p in _all_inline(view))


# --- 噂込みの版 ---------------------------------------------------------------------


def test_噂込みの版は噂の範囲を中身にほどく() -> None:
    article = make_article("店は繁盛した[!噂|が、'''閉店'''が近い[!要出典]]という。")

    view = rumor_view(article)

    assert view.lead == (
        Paragraph(
            (
                Text("店は繁盛したが、"),
                Bold((Text("閉店"),)),
                Text("が近い"),
                FixMark("要出典"),
                Text("という。"),
            )
        ),
    )


def test_噂込みの版は噂の節の印を外して節を残す() -> None:
    article = make_article("導入。\n\n## 騒動 [!噂]\n\n噂。\n\n### 経緯\n\n経緯。")

    view = rumor_view(article)

    assert [s.title for s in view.sections] == ["騒動"]
    assert view.sections[0].rumor is False
    assert view.sections[0].children[0].title == "経緯"


def test_噂込みの版は観点の枠を足し重ねない() -> None:
    plain = make_article("本文[!噂|噂]。")
    already = make_article("本文[!噂|噂]。", 'notices = ["観点"]\n')

    assert rumor_view(plain).settings.notices == ("観点",)
    assert rumor_view(already).settings.notices == ("観点",)


def test_噂込みの版は出典と注釈をそのまま残す() -> None:
    article = make_article("本文[^a]。[!噂|噂[^b][!信頼性要検証]。]", _REFS)

    view = rumor_view(article)

    assert [r.key for r in view.settings.references] == ["a", "b"]
    assert RefMark("b") in _all_inline(view)


def test_噂の無い原稿の噂込みの版は元と同じ() -> None:
    article = make_article("本文[^a]。[^b][!信頼性要検証]", 'notices = ["観点"]\n' + _REFS)

    # 噂込みの版は、噂が無ければ観点の枠を足しも外しもしない（書いた notices のまま）。
    # 通常の版は噂の有無によらず観点を外す（cli は噂のある原稿にだけ二つの版を使う）。
    assert rumor_view(article) == article
    assert normal_view(article).settings.notices == ()


# --- 検査に渡せる -------------------------------------------------------------------


def test_どちらの版も検査にそのまま渡せる() -> None:
    body = (
        "'''試験'''は架空の人物である[^a]。"
        "[!噂|裏では別の名を名乗っていたという[^b][!信頼性要検証]。]\n\n"
        "## 経歴\n\n生まれた[^a]。\n\n## 騒動 [!噂]\n\n炎上したという[^b][!信頼性要検証]。"
    )
    article = make_article(body, _REFS)

    normal = check_article(normal_view(article))
    rumor = check_article(rumor_view(article))

    assert "REF-UNUSED" not in [f.rule for f in normal]
    assert "REF-UNUSED" not in [f.rule for f in rumor]
