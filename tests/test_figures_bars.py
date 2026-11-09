"""横棒グラフ（bars）の SVG を書き出す試験。"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from wikiskill.figures.bars import render_bars
from wikiskill.figures.errors import FigureError

ROOT_PATTERN = re.compile(
    r'<svg xmlns="http://www\.w3\.org/2000/svg" width="([0-9.]+)" height="([0-9.]+)" '
    r'viewBox="0 0 ([0-9.]+) ([0-9.]+)" role="img"'
)
BAR_PATTERN = re.compile(
    r'<rect x="([0-9.]+)" y="([0-9.]+)" width="([0-9.]+)" height="([0-9.]+)" fill="(#[0-9a-f]+)"/>'
)
LABEL_PATTERN = re.compile(
    r'<text x="([0-9.]+)" y="([0-9.]+)" text-anchor="end"[^>]*>([^<]*)</text>'
)
VALUE_PATTERN = re.compile(
    r'<text x="([0-9.]+)" y="([0-9.]+)" text-anchor="start"[^>]*>([^<]*)</text>'
)

TWO_BARS = """
title = "人口"
[[bar]]
label = "甲"
value = 2
[[bar]]
label = "乙"
value = 1
"""


def _write(tmp_path: Path, body: str, name: str = "棒.toml") -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def _render(tmp_path: Path, body: str) -> str:
    return render_bars(_write(tmp_path, body))


def test_棒グラフは寸法と題を書く(tmp_path: Path) -> None:
    svg = _render(tmp_path, TWO_BARS)

    root = ROOT_PATTERN.search(svg)

    assert root is not None
    assert root.group(1) == "408.8"
    assert root.group(2) == "96"
    assert root.group(3) == "408.8"
    assert root.group(4) == "96"
    assert 'aria-label="人口"' in svg
    assert "<title>人口</title>" in svg


def test_題が無ければ_aria_label_を書かない(tmp_path: Path) -> None:
    svg = _render(tmp_path, '[[bar]]\nlabel = "甲"\nvalue = 1\n')

    assert "aria-label" not in svg
    assert "<title>" not in svg
    assert svg.startswith("<svg ")
    assert svg.endswith("</svg>")


def test_ラベルは棒の左に右揃えで置く(tmp_path: Path) -> None:
    svg = _render(tmp_path, TWO_BARS)

    labels = LABEL_PATTERN.findall(svg)

    assert labels == [("52", "37.5", "甲"), ("52", "69.5", "乙")]


def test_棒の長さは_value_max_に比例する(tmp_path: Path) -> None:
    svg = _render(
        tmp_path,
        """
value_max = 200
[[bar]]
label = "甲"
value = 100
[[bar]]
label = "乙"
value = 50
""",
    )

    assert BAR_PATTERN.findall(svg) == [
        ("52", "20", "160", "24", "#2c5aa0"),
        ("52", "52", "80", "24", "#c0392b"),
    ]


def test_value_max_を省くと値の最大が満杯になる(tmp_path: Path) -> None:
    svg = _render(
        tmp_path,
        """
[[bar]]
label = "甲"
value = 5
[[bar]]
label = "乙"
value = 2.5
""",
    )

    assert [bar[2] for bar in BAR_PATTERN.findall(svg)] == ["320", "160"]


def test_色は_bar_の_color_が上級の_color_より強い(tmp_path: Path) -> None:
    svg = _render(
        tmp_path,
        """
color = "#123456"
[[bar]]
label = "甲"
value = 3
[[bar]]
label = "乙"
value = 2
color = "#abcdef"
[[bar]]
label = "丙"
value = 1
""",
    )

    root = ROOT_PATTERN.search(svg)

    assert [bar[4] for bar in BAR_PATTERN.findall(svg)] == [
        "#123456",
        "#abcdef",
        "#123456",
    ]
    assert root is not None
    assert root.group(2) == "128"


def test_色を省くとパレットの色を順に使う(tmp_path: Path) -> None:
    svg = _render(
        tmp_path,
        """
[[bar]]
label = "甲"
value = 3
[[bar]]
label = "乙"
value = 1
""",
    )

    assert [bar[4] for bar in BAR_PATTERN.findall(svg)] == ["#2c5aa0", "#c0392b"]


def test_sort_value_は大きい順に並べる(tmp_path: Path) -> None:
    svg = _render(
        tmp_path,
        """
sort = "value"
[[bar]]
label = "甲"
value = 1
[[bar]]
label = "乙"
value = 3
[[bar]]
label = "丙"
value = 2
""",
    )

    assert [text for _, _, text in LABEL_PATTERN.findall(svg)] == ["乙", "丙", "甲"]
    # 色は並べ替える前の書いた順で選ぶ。
    assert [bar[4] for bar in BAR_PATTERN.findall(svg)] == [
        "#c0392b",
        "#2e8b57",
        "#2c5aa0",
    ]


def test_sort_label_は名前の順に並べる(tmp_path: Path) -> None:
    svg = _render(
        tmp_path,
        """
sort = "label"
[[bar]]
label = "い"
value = 2
[[bar]]
label = "あ"
value = 3
[[bar]]
label = "う"
value = 1
""",
    )

    assert [text for _, _, text in LABEL_PATTERN.findall(svg)] == ["あ", "い", "う"]


def test_sort_を省くと書いた順に並べる(tmp_path: Path) -> None:
    svg = _render(
        tmp_path,
        """
[[bar]]
label = "甲"
value = 3
[[bar]]
label = "乙"
value = 1
[[bar]]
label = "丙"
value = 2
""",
    )

    assert [text for _, _, text in LABEL_PATTERN.findall(svg)] == ["甲", "乙", "丙"]


def test_値は桁と単位をつけて書く(tmp_path: Path) -> None:
    svg = _render(
        tmp_path,
        """
digits = 1
unit = "万人"
[[bar]]
label = "甲"
value = 1234.5
""",
    )

    root = ROOT_PATTERN.search(svg)

    assert VALUE_PATTERN.findall(svg) == [("378", "37.5", "1,234.5万人")]
    assert root is not None
    assert root.group(1) == "493.6"
    assert root.group(2) == "64"


def test_値が_0_の棒は矩形を出さず値のラベルだけ書く(tmp_path: Path) -> None:
    svg = _render(
        tmp_path,
        """
[[bar]]
label = "甲"
value = 0
[[bar]]
label = "乙"
value = 5
""",
    )

    assert BAR_PATTERN.findall(svg) == [("52", "52", "320", "24", "#c0392b")]
    assert VALUE_PATTERN.findall(svg) == [("58", "37.5", "0"), ("378", "69.5", "5")]


def test_文字は_XML_の実体参照に直す(tmp_path: Path) -> None:
    svg = _render(tmp_path, 'title = "A & B"\n[[bar]]\nlabel = "A&B"\nvalue = 1\n')

    assert 'aria-label="A &amp; B"' in svg
    assert "A&amp;B" in svg


def test_同じデータなら同じ_SVG_になる(tmp_path: Path) -> None:
    data = _write(tmp_path, TWO_BARS)

    assert render_bars(data) == render_bars(data)


def test_棒グラフの知らない項目は誤り(tmp_path: Path) -> None:
    data = _write(tmp_path, 'note = "メモ"\n[[bar]]\nlabel = "甲"\nvalue = 1\n')

    with pytest.raises(FigureError, match="知らない項目がある: note"):
        render_bars(data)


def test_棒グラフの_bar_の知らない項目は誤り(tmp_path: Path) -> None:
    data = _write(tmp_path, '[[bar]]\nlabel = "甲"\nvalue = 1\nnote = "メモ"\n')

    with pytest.raises(FigureError, match="知らない項目がある: note"):
        render_bars(data)


def test_バーが無ければ誤り(tmp_path: Path) -> None:
    data = _write(tmp_path, 'title = "空"\n')

    with pytest.raises(FigureError, match="bar は 1 つ以上の表の並びで書く"):
        render_bars(data)


def test_バーが空の並びなら誤り(tmp_path: Path) -> None:
    data = _write(tmp_path, "bar = []\n")

    with pytest.raises(FigureError, match="bar は 1 つ以上の表の並びで書く"):
        render_bars(data)


def test_ラベルが空なら誤り(tmp_path: Path) -> None:
    data = _write(tmp_path, '[[bar]]\nlabel = ""\nvalue = 1\n')

    with pytest.raises(FigureError, match="bar の label が空"):
        render_bars(data)


def test_ラベルが重複すれば誤り(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        '[[bar]]\nlabel = "甲"\nvalue = 1\n[[bar]]\nlabel = "甲"\nvalue = 2\n',
    )

    with pytest.raises(FigureError, match="label が重複している: 甲"):
        render_bars(data)


def test_ラベルが文字列でなければ誤り(tmp_path: Path) -> None:
    data = _write(tmp_path, "[[bar]]\nlabel = 1\nvalue = 1\n")

    with pytest.raises(FigureError, match="label は文字列で書く"):
        render_bars(data)


def test_値が文字列なら誤り(tmp_path: Path) -> None:
    data = _write(tmp_path, '[[bar]]\nlabel = "甲"\nvalue = "1"\n')

    with pytest.raises(FigureError, match="value は数で書く: 甲"):
        render_bars(data)


def test_値が真偽なら誤り(tmp_path: Path) -> None:
    data = _write(tmp_path, '[[bar]]\nlabel = "甲"\nvalue = true\n')

    with pytest.raises(FigureError, match="value は数で書く: 甲"):
        render_bars(data)


def test_値が負なら誤り(tmp_path: Path) -> None:
    data = _write(tmp_path, '[[bar]]\nlabel = "甲"\nvalue = -1\n')

    with pytest.raises(FigureError, match="value は 0 以上の数で書く: 甲"):
        render_bars(data)


def test_値が非有限なら誤り(tmp_path: Path) -> None:
    data = _write(tmp_path, '[[bar]]\nlabel = "甲"\nvalue = nan\n')

    with pytest.raises(FigureError, match="value は 0 以上の数で書く: 甲"):
        render_bars(data)


def test_桁が範囲外なら誤り(tmp_path: Path) -> None:
    data = _write(tmp_path, 'digits = 3\n[[bar]]\nlabel = "甲"\nvalue = 1\n')

    with pytest.raises(FigureError, match="digits は 0 から 2 の整数で書く"):
        render_bars(data)


def test_桁が整数でなければ誤り(tmp_path: Path) -> None:
    data = _write(tmp_path, 'digits = 1.0\n[[bar]]\nlabel = "甲"\nvalue = 1\n')

    with pytest.raises(FigureError, match="digits は 0 から 2 の整数で書く"):
        render_bars(data)


def test_並べ方が知らない値なら誤り(tmp_path: Path) -> None:
    data = _write(tmp_path, 'sort = "year"\n[[bar]]\nlabel = "甲"\nvalue = 1\n')

    with pytest.raises(FigureError, match="sort は value か label で書く: 'year'"):
        render_bars(data)


def test_value_max_が値の最大より小さければ誤り(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        'value_max = 9\n[[bar]]\nlabel = "甲"\nvalue = 10\n',
    )

    with pytest.raises(FigureError, match="value_max は値の最大以上で書く"):
        render_bars(data)


def test_value_max_が数でなければ誤り(tmp_path: Path) -> None:
    data = _write(tmp_path, 'value_max = "100"\n[[bar]]\nlabel = "甲"\nvalue = 1\n')

    with pytest.raises(FigureError, match="value_max は数で書く"):
        render_bars(data)


def test_上級の色の書式が違えば誤り(tmp_path: Path) -> None:
    data = _write(tmp_path, 'color = "red"\n[[bar]]\nlabel = "甲"\nvalue = 1\n')

    with pytest.raises(FigureError, match="色は #rgb か #rrggbb の形で書く: 'red'"):
        render_bars(data)


def test_バーの色の書式が違えば誤り(tmp_path: Path) -> None:
    data = _write(tmp_path, '[[bar]]\nlabel = "甲"\nvalue = 1\ncolor = "blue"\n')

    with pytest.raises(FigureError, match="色は #rgb か #rrggbb の形で書く: 'blue'"):
        render_bars(data)
