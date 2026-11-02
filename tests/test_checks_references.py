from pathlib import Path

import pytest

from helpers import Finding, Level, make_article, only, rules
from helpers import run as run_all
from wikiskill.checks import check_article
from wikiskill.reader import read_article_file

REFERENCE_RULES = {
    "REF-UNDEFINED",
    "NOTE-UNDEFINED",
    "REF-UNUSED",
    "NOTE-UNUSED",
    "REF-WIKIPEDIA",
    "REF-WIKIPEDIA-NAME",
    "REF-DATE",
    "REF-ACCESS-DATE",
    "REF-URL",
    "LINK-URL",
    "REF-WEAK-UNMARKED",
}


def run(body: str = "本文。", settings: str = "") -> tuple[Finding, ...]:
    """出典に関わる規則の指摘だけを返す（本文の文体などの警告は別の試験で見る）。"""
    return tuple(f for f in run_all(body, settings) if f.rule in REFERENCE_RULES)


def ref(extra: str = "", key: str = "a") -> str:
    """出典を 1 件。``[refs.a]`` が 4 行目、kind が 5 行目、title が 6 行目、extra が 7 行目。"""
    return f'[refs.{key}]\nkind = "web"\ntitle = "題"\n{extra}'


def test_見本の原稿は何も引っかからない() -> None:
    sample = Path(__file__).parent / "fixtures" / "sample_article.md"
    assert check_article(read_article_file(sample)) == ()


def test_使った出典は引っかからない() -> None:
    assert run("本文[^a]。", ref()) == ()


def test_定義のない出典の印はエラー() -> None:
    findings = run("本文[^x]。")
    assert rules(findings) == ["REF-UNDEFINED"]
    assert findings[0].level is Level.ERROR
    assert findings[0].line == 5
    assert "x" in findings[0].message


def test_定義のない注釈の印はエラー() -> None:
    findings = run("一行目。\n\n本文[^n:y]。")
    assert rules(findings) == ["NOTE-UNDEFINED"]
    assert findings[0].level is Level.ERROR
    assert findings[0].line == 7
    assert "y" in findings[0].message


def test_出典の印と注釈の印は別の名前空間() -> None:
    # 出典 a があっても、注釈 a の定義がなければ [^n:a] はエラー。
    findings = run("本文[^a][^n:a]。", ref())
    assert rules(findings) == ["NOTE-UNDEFINED"]


def test_使われていない出典はエラーで定義の行を指す() -> None:
    findings = run("本文。", ref())
    assert rules(findings) == ["REF-UNUSED"]
    assert findings[0].level is Level.ERROR
    assert findings[0].line == 4
    assert "a" in findings[0].message


def test_注釈の本文で使った出典は使用済み() -> None:
    settings = ref() + '\n[notes.n]\ntext = "補足[^a]。"'
    assert run("本文[^n:n]。", settings) == ()


def test_使われていない注釈はエラー() -> None:
    findings = run("本文。", '[notes.n]\ntext = "補足。"')
    assert rules(findings) == ["NOTE-UNUSED"]
    assert findings[0].level is Level.ERROR
    assert findings[0].line == 5  # 注釈の text の行


def test_節や箇条書きの中の印も数える() -> None:
    body = "導入。\n\n## 節\n\n- 項目[^a]\n"
    assert run(body, ref()) == ()


def test_同じ出典を何度使ってもよい() -> None:
    assert run("甲[^a]。乙[^a]。", ref()) == ()


@pytest.mark.parametrize(
    "url",
    [
        "https://ja.wikipedia.org/wiki/%E6%97%A5%E6%9C%AC",
        "https://en.wikipedia.org/wiki/Japan",
        "https://ja.m.wikipedia.org/wiki/Japan",
        "http://WIKIPEDIA.ORG/wiki/Japan",
        "https://ja.wikipedia.org:443/wiki/Japan",
        "https://www.wikiwand.com/ja/articles/Japan",
        "https://www.weblio.jp/wkpja/content/Japan_Japan",
        "https://weblio.jp/wkpja/content/Japan",
    ],
)
def test_ウィキペディアと転載サイトを出典にするとエラー(url: str) -> None:
    findings = run("本文[^a]。", ref(f'url = "{url}"'))
    assert rules(findings) == ["REF-WIKIPEDIA"]
    assert findings[0].level is Level.ERROR
    assert findings[0].line == 7


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/wikipedia.org",
        "https://example.com/?from=ja.wikipedia.org",
        "https://notwikipedia.org/",
        "https://wikipedia.example.com/",
        "https://www.wikipediaexample.com/",
        "https://www.weblio.jp/content/Japan",
        "https://commons.wikimedia.org/wiki/File:A.jpg",
    ],
)
def test_ホスト名が一致しないものは引っかからない(url: str) -> None:
    assert run("本文[^a]。", ref(f'url = "{url}"')) == ()


def test_urlがなくても名前がウィキペディアなら警告() -> None:
    findings = run("本文[^a]。", '[refs.a]\nkind = "web"\ntitle = "日本 - Wikipedia"')
    assert rules(findings) == ["REF-WIKIPEDIA-NAME"]
    assert findings[0].level is Level.WARNING
    findings = run("本文[^a]。", ref('publisher = "ウィキペディア"'))
    assert rules(findings) == ["REF-WIKIPEDIA-NAME"]
    assert findings[0].line == 7


def test_urlがウィキペディアなら名前の警告は重ねない() -> None:
    settings = (
        '[refs.a]\nkind = "web"\ntitle = "日本 - Wikipedia"\n'
        'url = "https://ja.wikipedia.org/wiki/X"'
    )
    assert rules(run("本文[^a]。", settings)) == ["REF-WIKIPEDIA"]


@pytest.mark.parametrize("date", ["2020-09-01", "2020-09", "2020", "1999-12-31", "2024-02-29"])
def test_dateの正しい形は引っかからない(date: str) -> None:
    assert run("本文[^a]。", ref(f'date = "{date}"')) == ()


@pytest.mark.parametrize(
    "date",
    [
        "2020/09/01",
        "2020-9-1",
        "2020年9月1日",
        "2020-13-01",
        "2023-02-29",
        "20200901",
        "2020-09-1",
        "",
    ],
)
def test_dateの誤った形はエラー(date: str) -> None:
    findings = run("本文[^a]。", ref(f'date = "{date}"'))
    assert rules(findings) == ["REF-DATE"]
    assert findings[0].level is Level.ERROR
    assert findings[0].line == 7


def test_access_dateは年月日まで要る() -> None:
    assert run("本文[^a]。", ref('access_date = "2026-11-01"')) == ()
    for bad in ("2026-11", "2026", "2026/11/01", "2026-11-31"):
        findings = run("本文[^a]。", ref(f'access_date = "{bad}"'))
        assert rules(findings) == ["REF-ACCESS-DATE"], bad
        assert findings[0].level is Level.ERROR


@pytest.mark.parametrize(
    "url", ["https://example.com", "http://example.com/a?b=c#d", "https://例え.jp/パス"]
)
def test_urlの正しい形は引っかからない(url: str) -> None:
    assert run("本文[^a]。", ref(f'url = "{url}"')) == ()


@pytest.mark.parametrize(
    "url",
    [
        "example.com",
        "www.example.com/a",
        "ftp://example.com/a",
        "https://",
        "https:///a",
        "javascript:alert(1)",
        "https://exa mple.com",
    ],
)
def test_urlの誤った形はエラー(url: str) -> None:
    findings = run("本文[^a]。", ref(f'url = "{url}"'))
    assert rules(findings) == ["REF-URL"]
    assert findings[0].level is Level.ERROR


def test_外部リンクのurlも見る() -> None:
    settings = '[[external_links]]\ntitle = "公式"\nurl = "example.com"'
    findings = run("本文。", settings)
    assert rules(findings) == ["LINK-URL"]
    assert findings[0].level is Level.ERROR
    assert findings[0].line == 4  # [[external_links]] の見出しの行
    ok = '[[external_links]]\ntitle = "公式"\nurl = "https://example.com"'
    assert run("本文。", ok) == ()


def test_結果は行の順に並ぶ() -> None:
    findings = run("甲[^x]。\n\n乙[^n:y]。", ref())
    lines = [finding.line for finding in findings]
    assert lines == sorted(lines)
    assert len(findings) == 3


def test_補助の行番号の約束() -> None:
    article = make_article("本文。", ref())
    assert article.lead[0].line == 8
    assert only(check_article(article), "REF-UNUSED")[0].line == 4


# --- 弱い出典 -----------------------------------------------------------------


def weak(key: str = "a") -> str:
    """弱い出典を 1 件。``[refs.a]`` が 4 行目。"""
    return ref("weak = true\n", key)


def test_弱い出典の直後に信頼性要検証があれば通る() -> None:
    assert run("本文[^a][!信頼性要検証]。", weak()) == ()


def test_弱い出典の直後に信頼性要検証が無ければエラー() -> None:
    findings = run("一行目。\n本文[^a]。", weak())
    assert rules(findings) == ["REF-WEAK-UNMARKED"]
    assert findings[0].level is Level.ERROR
    # 段落の先頭の行（設定欄が 4 行なので本文は 9 行目から）。
    assert findings[0].line == 9
    assert "[refs.a]" in findings[0].message
    assert "[!信頼性要検証]" in findings[0].message


def test_弱い出典と信頼性要検証の間に出典の印が続いてもよい() -> None:
    settings = weak("a") + "\n" + ref("", "b")
    assert run("本文[^a][^b][!信頼性要検証]。", settings) == ()


def test_間に文字や別の印があればエラー() -> None:
    assert rules(run("本文[^a]。[!信頼性要検証]", weak())) == ["REF-WEAK-UNMARKED"]
    assert rules(run("本文[^a][!要出典]。", weak())) == ["REF-WEAK-UNMARKED"]


def test_弱い出典を使うたびに見る() -> None:
    findings = run("甲[^a][!信頼性要検証]。乙[^a]。\n\n丙[^a]。", weak())
    assert rules(findings) == ["REF-WEAK-UNMARKED", "REF-WEAK-UNMARKED"]
    assert [f.line for f in findings] == [9, 11]


def test_弱くない出典には印は要らない() -> None:
    assert run("本文[^a]。", ref("weak = false\n")) == ()


def test_箇条書きと範囲の印の中の弱い出典も見る() -> None:
    assert rules(run("- 項目[^a]", weak())) == ["REF-WEAK-UNMARKED"]
    assert run("[!要出典範囲|範囲[^a]][!信頼性要検証]。", weak()) == ()
    assert rules(run("[!要出典範囲|範囲[^a]]。", weak())) == ["REF-WEAK-UNMARKED"]


def test_注釈の中の弱い出典も見て行は注釈の本文の行() -> None:
    settings = weak() + '\n[notes.n]\ntext = "注[^a]"'
    findings = run("本文[^n:n]。", settings)
    assert rules(findings) == ["REF-WEAK-UNMARKED"]
    assert findings[0].line == 10


def test_弱い出典でもウィキペディアは出典にできない() -> None:
    settings = ref('url = "https://ja.wikipedia.org/wiki/A"\nweak = true\n')
    assert "REF-WIKIPEDIA" in rules(run("本文[^a][!信頼性要検証]。", settings))
