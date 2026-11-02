from pathlib import Path

import pytest

from wikiskill import cli
from wikiskill.wikipedia_refs import Citation, WikipediaError, parse_article, raw_url

_RAW = """{{Infobox 食品}}
'''試し'''は試しの食品である<ref>{{Cite web |和書 |url=https://example.com/a |title=記事の題
 |publisher=架空社 |date=2020-01-02
 |archive-url=https://web.archive.org/web/20200102000000/https://example.com/a
 |archive-date=2020-01-02}}</ref>。

== 歴史 ==
=== 開発 ===
開発された<ref name="news">{{Cite news|title=新聞の見出し|newspaper=[[架空新聞社|架空新聞]]|date=2001年4月1日|url=http://news.example.jp/x?id=1&p=2}}</ref>。
再掲<ref name="news" />。
裸の出典<ref>[https://example.org/bare 裸の題] 2010年</ref>。

== 脚注 ==
{{Reflist}}

== 参考文献 ==
* {{Cite book|和書|author=著者|title=本の題|publisher=出版社|year=1999|isbn=978-4-00-000000-0}}

== 関連項目 ==
* [[関連の記事A]]
* [[関連の記事B|表示の名]] - 説明

== 外部リンク ==
* [https://example.com/official 公式]
"""


def test_節の並びを段の深さつきで取り出す() -> None:
    article = parse_article("試し", _RAW)

    assert article.sections == (
        (2, "歴史"),
        (3, "開発"),
        (2, "脚注"),
        (2, "参考文献"),
        (2, "関連項目"),
        (2, "外部リンク"),
    )


def test_出典の題と元の_URL_と保存版の_URL_を切らずに取り出す() -> None:
    article = parse_article("試し", _RAW)

    first = article.citations[0]
    assert first == Citation(
        section="（導入部）",
        title="記事の題",
        source="架空社",
        date="2020-01-02",
        url="https://example.com/a",
        archive_url="https://web.archive.org/web/20200102000000/https://example.com/a",
    )


def test_名前つきの再掲は一つと数え_節を覚える() -> None:
    article = parse_article("試し", _RAW)

    news = [c for c in article.citations if c.title == "新聞の見出し"]
    assert len(news) == 1
    assert news[0].section == "開発"
    assert news[0].source == "架空新聞"
    assert news[0].url == "http://news.example.jp/x?id=1&p=2"


def test_テンプレートの無い裸の出典と参考文献の書籍も拾う() -> None:
    article = parse_article("試し", _RAW)

    titles = {c.title: c for c in article.citations}
    assert titles["裸の題"].url == "https://example.org/bare"
    assert titles["本の題"].section == "参考文献"
    assert titles["本の題"].url is None


def test_関連項目の記事名を取り出す() -> None:
    article = parse_article("試し", _RAW)

    assert article.related == ("関連の記事A", "関連の記事B")


def test_転送のページは転送先を返す() -> None:
    with pytest.raises(WikipediaError, match="転送") as caught:
        parse_article("旧名", "#転送 [[新しい名前]]")

    assert caught.value.redirect_to == "新しい名前"


def test_生のウィキテキストの_URL() -> None:
    assert raw_url("カップ ヌードル") == (
        "https://ja.wikipedia.org/w/index.php?title=%E3%82%AB%E3%83%83%E3%83%97_"
        "%E3%83%8C%E3%83%BC%E3%83%89%E3%83%AB&action=raw"
    )


def test_wikipedia_コマンドは節の並びと出典の一覧を出す(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from wikiskill import wikipedia_refs

    asked: list[str] = []

    def fake_raw(title: str, **_kwargs: object) -> str:
        asked.append(title)
        return _RAW

    monkeypatch.setattr(wikipedia_refs, "fetch_raw", fake_raw)
    monkeypatch.setenv("WIKISKILL_FETCH_STATE", str(tmp_path))

    code = cli.main(["wikipedia", "試し"])

    out = capsys.readouterr().out
    assert code == 0
    assert asked == ["試し"]
    lines = out.splitlines()
    # 節の並びは入れ子の箇条、出典は節ごとの見出しの下
    assert "- 歴史" in lines
    assert "  - 開発" in lines
    assert "### 開発" in lines
    assert "元: https://example.com/a" in out
    assert "保存版: https://web.archive.org/web/20200102000000/https://example.com/a" in out
    assert "出典 4 件（保存版つき 1 件）" in out
    assert "- 関連の記事A" in lines
    # 本家の本文は出さない
    assert "試しの食品である" not in out
