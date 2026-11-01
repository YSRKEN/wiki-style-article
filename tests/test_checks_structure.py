"""記事の構造（空の節・導入部の太字・自己リンク・節名）の規則の試験。"""

import pytest

from helpers import Level, only, run


def test_中身のない節はエラー() -> None:
    findings = only(run("'''試験'''は例。\n\n## 空の節\n\n## 次の節\n\n本文。"), "EMPTY-SECTION")
    assert len(findings) == 1
    assert findings[0].level is Level.ERROR
    assert findings[0].line == 7
    assert "空の節" in findings[0].message


def test_子の節だけを持つ節と本文のある節は空ではない() -> None:
    body = "'''試験'''は例。\n\n## 親\n\n### 子\n\n本文。\n\n## 別\n\n- 項目\n"
    assert only(run(body), "EMPTY-SECTION") == []


def test_末尾の空の子の節も見つける() -> None:
    findings = only(run("'''試験'''は例。\n\n## 親\n\n本文。\n\n### 空の子"), "EMPTY-SECTION")
    assert [finding.line for finding in findings] == [11]


def test_導入部の最初の段落に太字がなければ警告() -> None:
    findings = only(run("試験は例である。"), "LEAD-NO-BOLD")
    assert len(findings) == 1
    assert findings[0].level is Level.WARNING
    assert findings[0].line == 5


@pytest.mark.parametrize(
    "body",
    [
        "'''試験'''は例である。",
        "例として'''試験'''がある。\n\n## 節\n\n本文。",
    ],
)
def test_導入部に太字があれば引っかからない(body: str) -> None:
    assert only(run(body), "LEAD-NO-BOLD") == []


def test_導入部が空のときは太字の警告を出さない() -> None:
    assert only(run("## 節\n\n本文。"), "LEAD-NO-BOLD") == []


def test_自分の記事へのリンクはエラー() -> None:
    findings = only(run("'''試験'''は[[試験]]の例。"), "SELF-LINK")
    assert len(findings) == 1
    assert findings[0].level is Level.ERROR
    assert findings[0].line == 5


def test_表示を変えた自己リンクもエラー() -> None:
    assert len(only(run("'''試験'''は[[試験|これ]]の例。"), "SELF-LINK")) == 1


def test_別の記事へのリンクは自己リンクではない() -> None:
    body = "'''試験'''は[[試験問題]]の例で、[[試験 (曖昧さ回避)]]ではない。"
    assert only(run(body), "SELF-LINK") == []


def test_曖昧さ回避の括弧つきの題でも自己リンクを見つける() -> None:
    body = "'''試験'''は[[試験 (漫画)]]を指す。"
    assert len(only(run(body, title="試験 (漫画)"), "SELF-LINK")) == 1


@pytest.mark.parametrize(
    "title", ["トリビア", "豆知識", "余談", "その他", "エピソード", "作品の小ネタ"]
)
def test_雑多な内容の節名は警告(title: str) -> None:
    findings = only(run(f"'''試験'''は例。\n\n## {title}\n\n本文。"), "TRIVIA-SECTION")
    assert len(findings) == 1
    assert findings[0].level is Level.WARNING
    assert findings[0].line == 7


@pytest.mark.parametrize("title", ["概要", "あらすじ", "登場人物", "その他の作品", "制作"])
def test_ふつうの節名は引っかからない(title: str) -> None:
    assert only(run(f"'''試験'''は例。\n\n## {title}\n\n本文。"), "TRIVIA-SECTION") == []
