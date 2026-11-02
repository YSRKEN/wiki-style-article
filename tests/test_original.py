"""外国語の引用に原文を添える記法 ``[!原文|言語タグ|文]`` の試験。"""

import pytest

from helpers import make_article, only, rules, run
from wikiskill.checks import check_article_variants
from wikiskill.errors import MarkupError
from wikiskill.html_inline import InlineWriter
from wikiskill.html_writer import write_html
from wikiskill.inline import parse_inline
from wikiskill.model import Bold, FixRange, Original, Paragraph, RumorRange, Text
from wikiskill.reader import read_article
from wikiskill.types import load_default_registry
from wikiskill.variants import normal_view, rumor_view
from wikiskill.wikitext import WikitextStyle, write_wikitext

REGISTRY = load_default_registry()
EN = "Their work disregarded the blur in the imaging process."


def _src(body: str) -> str:
    return f'+++\ntitle = "テスト記事"\ntype = "concept"\n+++\n{body}'


def _wikitext(body: str, style: WikitextStyle = "wikipedia") -> str:
    article = read_article(_src(body))
    return write_wikitext(article, REGISTRY["concept"], style=style)


def _parts(blocks: tuple[object, ...]) -> list[object]:
    """段落の部品を、入れ子の中まで一列にする。"""
    found: list[object] = []

    def visit(items: tuple[object, ...]) -> None:
        for item in items:
            found.append(item)
            if isinstance(item, Bold | FixRange | RumorRange):
                visit(item.children)

    for block in blocks:
        assert isinstance(block, Paragraph)
        visit(block.content)
    return found


# --- 読み取り -------------------------------------------------------------------


def test_原文は言語タグと文を持つ() -> None:
    assert parse_inline(f"（原文：[!原文|en|{EN}]）") == (
        Text("（原文："),
        Original("en", EN),
        Text("）"),
    )


def test_原文の文には縦棒と対の角括弧を書ける() -> None:
    assert parse_inline("[!原文|en|a | b [sic] c]") == (Original("en", "a | b [sic] c"),)


def test_原文の前後の空白は取る() -> None:
    assert parse_inline("[!原文|de|  Guten Tag  ]") == (Original("de", "Guten Tag"),)


@pytest.mark.parametrize("tag", ["en", "en-US", "zh-Hans", "ko", "de", "zh-Hant-TW", "sr-Latn-RS"])
def test_言語タグは_bcp47_の形なら通る(tag: str) -> None:
    assert parse_inline(f"[!原文|{tag}|x]") == (Original(tag, "x"),)


@pytest.mark.parametrize(
    ("text", "keyword"),
    [
        ("[!原文|e|x]", "言語タグ"),
        ("[!原文|english|x]", "言語タグ"),
        ("[!原文||x]", "言語タグ"),
        ("[!原文|en_US|x]", "言語タグ"),
        ("[!原文|en US|x]", "言語タグ"),
        ("[!原文|en|]", "空"),
        ("[!原文|en|   ]", "空"),
        ("[!原文]", "|"),
        ("[!原文|en]", "|"),
        ("[!原文|en|閉じない", "閉じていない"),
        ("[!原文|en|a [^k] b]", "脚注"),
        ("[!原文|en|a [[b]] c]", "内部リンク"),
        ("'''太字[!原文|en|x]'''", "太字"),
        ("[!要出典範囲|文[!原文|en|x]]", "入れ子"),
    ],
)
def test_壊れた原文は行番号つきのエラー(text: str, keyword: str) -> None:
    with pytest.raises(MarkupError) as info:
        parse_inline(text, 7)
    assert info.value.line == 7
    assert keyword in info.value.message


def test_原文は噂の範囲の中に入れ子にできる() -> None:
    assert parse_inline("[!噂|訳（原文：[!原文|en|x]）]") == (
        RumorRange((Text("訳（原文："), Original("en", "x"), Text("）"))),
    )


def test_噂の範囲の中の原文のエラーは中の位置の行を指す() -> None:
    def line_of(offset: int) -> int:
        return 3 if offset < 6 else 4

    with pytest.raises(MarkupError) as info:
        parse_inline("[!噂|文。[!原文|e|x]]", line_of)
    assert info.value.line == 4


def test_脚注の印は原文の外に置ける() -> None:
    parts = parse_inline("訳[^a]（原文：[!原文|en|x]）[^a]")
    assert Original("en", "x") in parts


# --- 書き出し -------------------------------------------------------------------


def test_html_は_span_に言語を付ける() -> None:
    html = InlineWriter().inline(parse_inline(f"（原文：[!原文|en-US|{EN}]）"))
    assert html == f'（原文：<span lang="en-US">{EN}</span>）'


def test_html_の原文の文字は逃がす() -> None:
    html = InlineWriter().inline(parse_inline("[!原文|en|a<b & c>]"))
    assert html == '<span lang="en">a&lt;b &amp; c&gt;</span>'


def test_html_全体の書き出しにも入る() -> None:
    article = read_article(_src(f"訳（原文：[!原文|en|{EN}]）\n"))
    out = write_html(article, REGISTRY["concept"], updated="2026年11月2日 (月) 12:00 (JST)")
    assert f'<span lang="en">{EN}</span>' in out


def test_ウィキテキストは_lang_テンプレートで包む() -> None:
    out = _wikitext(f"訳（原文：[!原文|en|{EN}]）\n")
    assert out == f"訳（原文：{{{{lang|en|{EN}}}}}）\n"


def test_ウィキテキストの_plain_はタグを付けず文字だけ() -> None:
    out = _wikitext(f"訳（原文：[!原文|en|{EN}]）\n", "plain")
    assert out == f"訳（原文：{EN}）\n"


def test_ウィキテキストの_lang_の中の縦棒と等号は逃がす() -> None:
    assert _wikitext("[!原文|en|a | b]\n") == "{{lang|en|a &#124; b}}\n"
    assert _wikitext("[!原文|en|E = mc2]\n") == "{{lang|en|2=E = mc2}}\n"


def test_ウィキテキストの_plain_の文字は記法に読まれない形に逃がす() -> None:
    assert _wikitext("[!原文|en|a <b> {c}]\n", "plain") == "a &lt;b> &#123;c&#125;\n"


# --- 検査 -----------------------------------------------------------------------

_FOREIGN = 'He said "hello", then left... 3,000 times (Ａ)　ok, "quoted" and very important.'


def test_原文の中は和文用の検査にかけない() -> None:
    assert run(f"'''彼'''は去った（原文：[!原文|en|{_FOREIGN}]）。") == ()


@pytest.mark.parametrize(
    ("rule", "body"),
    [
        ("ASCII-QUOTE", '訳が "引用" になっている（原文：[!原文|en|x]）。'),
        ("FULLWIDTH-PUNCT", "訳，（原文：[!原文|en|x]）。"),
        ("WORD-PUFFERY", "非常に長い（原文：[!原文|en|x]）。"),
        ("FULLWIDTH-ALNUM", "第１巻（原文：[!原文|en|x]）。"),
    ],
)
def test_原文の外の和文は今までどおり検査する(rule: str, body: str) -> None:
    assert rule in rules(run(body))


def test_原文の外の指摘と中の文字は別々に数える() -> None:
    findings = run('訳は "これ" である（原文：[!原文|en|He said "no".]）。')
    assert len(only(findings, "ASCII-QUOTE")) == 1


def test_原文の中の鉤括弧は引用の範囲を作らない() -> None:
    # 原文の中の「 が、あとの和文の見逃しの範囲を広げてしまわない。
    assert "WORD-PUFFERY" in rules(run("[!原文|ja|「]の後に非常に長い。"))


# --- 二つの版との組み合わせ -------------------------------------------------------


def test_噂の範囲の中の原文は通常の版で噂ごと消え噂込みの版で残る() -> None:
    article = make_article("本文。[!噂|訳（原文：[!原文|en|x]）。]")
    assert Original("en", "x") not in _parts(normal_view(article).lead)
    assert Original("en", "x") in _parts(rumor_view(article).lead)


def test_噂の外の原文は両方の版に残る() -> None:
    article = make_article("訳（原文：[!原文|en|x]）。[!噂|噂。]")
    for view in (normal_view(article), rumor_view(article)):
        assert Original("en", "x") in _parts(view.lead)


def test_二つの版の検査でも原文の中は見逃す() -> None:
    article = make_article("'''本文'''[!噂|訳（原文：[!原文|en|very \"important\" 3,000]）。]")
    assert check_article_variants(article) == ()


def test_噂込みの版のウィキテキストに_lang_が出る() -> None:
    article = read_article(_src("[!噂|訳（原文：[!原文|en|x]）。]本文。\n"))
    out = write_wikitext(rumor_view(article), REGISTRY["concept"])
    assert "{{lang|en|x}}" in out
