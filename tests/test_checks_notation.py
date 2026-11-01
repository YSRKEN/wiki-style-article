"""表記（約物・空白・全角半角・日付など）の規則の試験。

どの規則も「引っかかる例」と「引っかからない例（誤検出しやすい例を含む）」を並べる。
"""

import pytest

from helpers import Level, only, rules, run

ERROR_RULES = {
    "FULLWIDTH-SPACE",
    "HALFWIDTH-KANA",
    "FULLWIDTH-ALNUM",
    "FULLWIDTH-PUNCT",
    "REPEATED-PUNCT",
    "ZERO-PAD-DATE",
}


def hits(body: str, rule: str) -> list[str]:
    """本文を検査し、指定した規則の指摘を返す（規則 ID の一覧ではなく件数の確認用）。"""
    return [finding.rule for finding in only(run(body), rule)]


# --- エラーの規則 --------------------------------------------------------------


@pytest.mark.parametrize(
    ("rule", "text"),
    [
        ("FULLWIDTH-SPACE", "星　屑ラーメン"),
        ("FULLWIDTH-SPACE", "　段落の頭を字下げした。"),
        ("HALFWIDTH-KANA", "題名は｢ｽﾀｰﾀﾞｽﾄ｣と読む。"),
        ("FULLWIDTH-ALNUM", "第１巻が出た。"),
        ("FULLWIDTH-ALNUM", "ＡＢＣ放送で放映された。"),
        ("FULLWIDTH-PUNCT", "一つ，二つ。"),
        ("FULLWIDTH-PUNCT", "二つ．三つ。"),
        ("REPEATED-PUNCT", "終わった。。"),
        ("REPEATED-PUNCT", "しかし、、続いた。"),
        ("ZERO-PAD-DATE", "2016年01月に連載が始まった。"),
        ("ZERO-PAD-DATE", "3月05日に発売された。"),
        ("ZERO-PAD-DATE", "01日から始まる。"),
    ],
)
def test_エラーの表記は引っかかる(rule: str, text: str) -> None:
    findings = only(run(text), rule)
    assert len(findings) == 1
    assert findings[0].level is Level.ERROR
    assert findings[0].line == 5


@pytest.mark.parametrize(
    ("rule", "text"),
    [
        ("FULLWIDTH-SPACE", "月見里 ほたる（半角の空白）が描いた。"),
        ("HALFWIDTH-KANA", "ゲームのスターダスト。長音はーで伸ばす。"),
        ("FULLWIDTH-ALNUM", "第1巻とABC放送。"),
        ("FULLWIDTH-PUNCT", "一つ、二つ。三つ。1,000 の小数点 1.5 は半角。"),
        ("REPEATED-PUNCT", "終わった。続いた。「……」と言った。"),
        ("ZERO-PAD-DATE", "2016年10月に連載が始まった。"),
        ("ZERO-PAD-DATE", "2016年1月5日に発売された。"),
        ("ZERO-PAD-DATE", "100日間と10日と20日。"),
        ("ZERO-PAD-DATE", "第10月刊と2010年。"),
        ("ZERO-PAD-DATE", "01日本橋という番地名ではない記述。"),
    ],
)
def test_エラーの表記の誤検出しやすい例は引っかからない(rule: str, text: str) -> None:
    assert only(run(text), rule) == []


def test_見出しとinfoboxと注釈の本文も検査する() -> None:
    settings = '[infobox]\n"ジャンル" = "グルメ　漫画"\n[notes.n]\ntext = "注釈　です。"'
    findings = only(run("導入[^n:n]。\n\n## 概　要\n\n本文。", settings), "FULLWIDTH-SPACE")
    # infobox（5 行目）・注釈 text（7 行目）・見出し（11 行目）
    assert sorted(finding.line for finding in findings) == [5, 7, 11]


def test_同じ行の同じ指摘は一件にまとめる() -> None:
    findings = only(run("星　屑　ラーメン　です。"), "FULLWIDTH-SPACE")
    assert len(findings) == 1


# --- 警告の規則 --------------------------------------------------------------


@pytest.mark.parametrize(
    ("rule", "text"),
    [
        ("ZERO-PAD-TIME", "03時に放送された。"),
        ("ZERO-PAD-TIME", "20時05分に放送された。"),
        ("SLASH-DATE", "2003/02/01に公開された。"),
        ("SLASH-DATE", "2003-02-01に公開された。"),
        ("ELLIPSIS", "そうか・・・と思った。"),
        ("ELLIPSIS", "そうか...と思った。"),
        ("ELLIPSIS", "そうか…と思った。"),
        ("WAVE-DASH", "1990〜1999年に連載された。"),
        ("WAVE-DASH", "1990～1999年に連載された。"),
        ("DASH", "三つ―一つ目、二つ目、三つ目。"),
        ("DASH", "出来事—その後。"),
        ("SYMBOL-NUMERAL", "第Ⅳ期が始まった。"),
        ("SYMBOL-NUMERAL", "①が最初の巻。"),
        ("SYMBOL-NUMERAL", "㈱架空出版が刊行した。"),
        ("SYMBOL-NUMERAL", "全長は150㎝。"),
        ("SMALL-KE", "1ヶ月で完結した。"),
        ("HONORIFIC", "月見里さんが描いた。"),
        ("HONORIFIC", "作者（故人）が遺した。"),
        ("POLITE-STYLE", "これは漫画作品です。"),
        ("POLITE-STYLE", "連載が始まりました。"),
        ("DIGIT-COMMA", "発行部数は1,000,000部。"),
        ("ASCII-QUOTE", 'タイトルは"Stardust"という。'),
        ("ASCII-QUOTE", "題は“Stardust”という。"),
    ],
)
def test_警告の表記は引っかかる(rule: str, text: str) -> None:
    findings = only(run(text), rule)
    assert len(findings) == 1, text
    assert findings[0].level is Level.WARNING
    assert findings[0].line == 5


@pytest.mark.parametrize(
    ("rule", "text"),
    [
        ("ZERO-PAD-TIME", "3時5分と10時と12時30分に放送された。"),
        ("SLASH-DATE", "1990-1999年と2003年2月1日。"),
        ("ELLIPSIS", "そうか……と思った。"),
        ("ELLIPSIS", "作品名は『あの日…』である。"),
        ("WAVE-DASH", "作品名は『君の名は〜』である。"),
        ("WAVE-DASH", "1990年 - 1999年に連載された。"),
        ("DASH", "長音のコーヒー、ラーメン。"),
        ("SYMBOL-NUMERAL", "第IV期と1巻とドラゴンクエストIII。"),
        ("SMALL-KE", "1か月で完結した。"),
        ("HONORIFIC", "『サザエさん』が放送された。"),
        ("HONORIFIC", "[[サザエさん]]が放送された。"),
        ("HONORIFIC", "'''サザエさん'''は漫画。"),
        ("HONORIFIC", "主人公は「サザエさん」と呼ばれる。"),
        ("HONORIFIC", "ほたるさんは作中の人物である。"),
        ("HONORIFIC", "作者は月見里 ほたるである。"),
        ("POLITE-STYLE", "作中で「そうです。」と述べる。"),
        ("POLITE-STYLE", "題は『ですます調のすすめ』である。"),
        ("POLITE-STYLE", "これは漫画作品である。連載された。"),
        ("DIGIT-COMMA", "発行部数は100万部で、1000部ではない。"),
        ("DIGIT-COMMA", "3,5 や a,b,c は数ではない。"),
        ("ASCII-QUOTE", "題は「Stardust」という。"),
    ],
)
def test_警告の表記の誤検出しやすい例は引っかからない(rule: str, text: str) -> None:
    assert only(run(text), rule) == [], text


def test_ケの小書きは固有名詞でも引っかかる_警告で読み直す() -> None:
    # 茅ヶ崎・三ヶ日のような固有名詞は正しい表記なので、エラーにはせず警告にとどめる。
    findings = only(run("茅ヶ崎市の出身。"), "SMALL-KE")
    assert [finding.level for finding in findings] == [Level.WARNING]


def test_誤検出しうる表記はエラーにしない() -> None:
    texts = ["1ヶ月", "〜", "―", "Ⅳ", "ですます調です。", "月見里さん", "・・・", "1,000"]
    for text in texts:
        assert not (set(rules(run(text))) & ERROR_RULES), text


def test_リンクの表示や太字の中の指摘は題名として見逃す() -> None:
    # 内部リンクの表示・太字は記事名や作品名なので、約物の指摘から外す。
    assert only(run("[[君の名は〜|君の名は〜]]を見た。"), "WAVE-DASH") == []
    assert only(run("'''ワンピースⅡ'''は漫画。"), "SYMBOL-NUMERAL") == []
    # ただし全角空白やゼロ詰めの日付のような、題名でも直すべきものは見逃さない。
    assert hits("[[星　屑]]を見た。", "FULLWIDTH-SPACE") == ["FULLWIDTH-SPACE"]


def test_脚注の印は文字として数えない() -> None:
    assert only(run("終わった[^a]。。"), "REPEATED-PUNCT") != []
    assert only(run("そう[^n:a]です。", '[notes.a]\ntext = "補足。"'), "POLITE-STYLE") != []
