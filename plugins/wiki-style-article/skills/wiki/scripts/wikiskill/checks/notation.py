"""表記（空白・全角半角・約物・日付・数字）の規則。

根拠は「Wikipedia:表記ガイド」。エラーは、見つかれば原稿の書き間違いと言える
もの（全角空白、半角カナ、全角の英数字、ゼロ詰めの日付など）に限る。作品名・固有名詞に
正当な例外があるもの（波ダッシュ、ローマ数字、「ヶ」、敬称など）は警告にとどめる。
振り分けの理由は ``docs/checks.md``。
"""

from __future__ import annotations

from collections.abc import Iterator

from wikiskill.checks.finding import Finding, Level
from wikiskill.checks.patterns import Pattern, Skip, pattern, scan
from wikiskill.checks.text import iter_units
from wikiskill.model import Article

_E = Level.ERROR
_W = Level.WARNING

_KANJI_OR_KATAKANA = r"一-鿿ァ-ヺ々"

PATTERNS: tuple[Pattern, ...] = (
    # --- エラー: 見つかれば書き間違い -------------------------------------------
    pattern(
        "FULLWIDTH-SPACE",
        _E,
        "　",
        "全角空白がある（字下げや位置合わせに使わない。半角空白にするか削る）",
        Skip.NOTHING,
    ),
    pattern(
        "HALFWIDTH-KANA",
        _E,
        "[｡-ﾟ]+",
        "半角カナがある（全角のカナで書く）",
        Skip.NOTHING,
    ),
    pattern(
        "FULLWIDTH-ALNUM",
        _E,
        "[０-９Ａ-Ｚａ-ｚ]+",
        "全角の英数字がある（半角で書く）",
        Skip.NOTHING,
    ),
    pattern(
        "FULLWIDTH-PUNCT",
        _E,
        "[，．]",
        "全角のカンマ・ピリオドがある（和文の句読点は「、」「。」）",
        Skip.NOTHING,
    ),
    pattern(
        "REPEATED-PUNCT",
        _E,
        "。{2,}|、{2,}",
        "句読点が重なっている",
        Skip.NOTHING,
    ),
    pattern(
        "ZERO-PAD-DATE",
        _E,
        r"(?<!\d)0\d月|(?<!\d)0\d日(?!本)",
        "日付が 0 詰めになっている（「3月5日」のように 0 を付けない）",
        Skip.NOTHING,
    ),
    # --- 警告: 作品名・固有名詞などに正当な例外がありうる --------------------------
    pattern(
        "ZERO-PAD-TIME",
        _W,
        r"(?<!\d)0\d(?:時|分)",
        "時刻が 0 詰めになっている（「3時5分」のように 0 を付けない）",
    ),
    pattern(
        "SLASH-DATE",
        _W,
        r"(?<!\d)\d{4}[/-]\d{1,2}[/-]\d{1,2}(?!\d)",
        "年月日を数字と記号だけで書いている（「2003年2月1日」と書く）",
    ),
    pattern(
        "ELLIPSIS",
        _W,
        r"・{3,}|\.{3,}|(?<!…)…(?!…)",
        "三点リーダの形が違う（「…」を 2 つ重ねて「……」と書く）",
    ),
    pattern(
        "WAVE-DASH",
        _W,
        "[〜～]",
        "波ダッシュ・全角チルダがある（範囲は「1990年 - 1999年」のように半角のハイフンで書く。"
        "固有名称の正式な表記なら残す）",
    ),
    pattern(
        "DASH",
        _W,
        "[—―]",
        "ダッシュがある（使わない。長音は「ー」。固有名称の正式な表記なら残す）",
    ),
    pattern(
        "SYMBOL-NUMERAL",
        _W,
        "[Ⅰ-ↈ①-⓿❶-➓㈠-㉃㊀-㊰㌀-㏿]",
        "ローマ数字・丸数字・全角 1 字の略記号がある（「IV」「1」「株式会社」「センチメートル」の"
        "ように書く。固有名詞の正式名称なら残す）",
    ),
    pattern(
        "SMALL-KE",
        _W,
        "ヶ",
        "「ヶ」がある（「1か月」のように書く。茅ヶ崎・三ヶ日のような固有名詞なら残す）",
    ),
    pattern(
        "HONORIFIC",
        _W,
        rf"(?<=[{_KANJI_OR_KATAKANA}])さん|[（(]故人[）)]",
        "人名に敬称や「故人」が付いていないか確かめる（付けない）",
        Skip.QUOTES,
    ),
    pattern(
        "POLITE-STYLE",
        _W,
        r"(?:です|ます|でした|ました|ません|でしょう|ましょう)(?=[。、]|$)",
        "文が敬体（です・ます）になっていないか確かめる（解説文は常体の「である」にそろえる）",
        Skip.QUOTES,
    ),
    pattern(
        "DIGIT-COMMA",
        _W,
        r"(?<![\d,.])\d{1,3}(?:,\d{3})+(?![\d,])",
        "数が 3 桁のカンマ区切りになっている（「万」「億」で区切るのを基本にする）",
    ),
    pattern(
        "ASCII-QUOTE",
        _W,
        '"[^"]*"|“[^”]*”',
        '和文に引用符（" "）が使われている（「」や『』を使う）',
    ),
)
"""表記の規則の一覧。"""


def check_notation(article: Article) -> Iterator[Finding]:
    """本文・見出し・Infobox の値・注釈の本文の表記を検査する。"""
    yield from scan(iter_units(article), PATTERNS)
