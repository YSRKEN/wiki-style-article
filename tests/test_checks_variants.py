from helpers import make_article, only, rules
from wikiskill.checks import Level, check_article, check_article_variants
from wikiskill.types import load_default_registry

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


def test_噂の無い原稿は今までの検査と同じ() -> None:
    article = make_article("本文[^a]。\n\n　字下げ。", _REFS)
    registry = load_default_registry()

    assert check_article_variants(article, registry) == check_article(article, registry)


def test_噂込みの版にだけある指摘も出す() -> None:
    # 弱い出典に [!信頼性要検証] が無いのは、噂込みの版でだけエラーになる。
    article = make_article("本文[^a]。[!噂|噂がある[^b]。]", _REFS)

    findings = check_article_variants(article)

    assert len(only(findings, "REF-WEAK-UNMARKED")) == 1
    assert only(findings, "REF-WEAK-UNMARKED")[0].level is Level.ERROR


def test_通常の版にだけある指摘も出す() -> None:
    # 噂だけの段落を取り除くと、通常の版では節が空になる。
    article = make_article("本文。\n\n## 騒動\n\n[!噂|噂だけの段落。]")

    findings = check_article_variants(article)

    assert "EMPTY-SECTION" in rules(findings)
    assert "EMPTY-SECTION" not in rules(check_article(make_article("本文。\n\n## 騒動\n\n噂。")))


def test_同じ指摘が両方の版に出たら一つにまとめる() -> None:
    article = make_article("　字下げした本文。[!噂|噂。]")

    findings = check_article_variants(article)

    assert len(only(findings, "FULLWIDTH-SPACE")) == 1


def test_噂の中だけで使う出典は使われていないことにならない() -> None:
    body = (
        "本文[^a]。[!噂|噂がある[^b][!信頼性要検証]。]\n\n"
        "## 騒動 [!噂]\n\n炎上[^b][!信頼性要検証]。"
    )
    article = make_article(body, _REFS)

    assert "REF-UNUSED" not in rules(check_article_variants(article))


def test_元から使われていない出典は知らせる() -> None:
    article = make_article("本文[^a]。[!噂|噂。]", _REFS)

    unused = only(check_article_variants(article), "REF-UNUSED")

    assert len(unused) == 1
    assert "b" in unused[0].message


def test_指摘は行番号の順に並ぶ() -> None:
    body = "本文[^nai]。[!噂|噂[^b]。]\n\n## 節\n\n　字下げ。"
    article = make_article(body, _REFS)

    lines = [finding.line for finding in check_article_variants(article)]

    assert lines == sorted(lines)
