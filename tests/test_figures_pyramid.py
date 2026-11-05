"""人口ピラミッド（pyramid）の SVG を書き出す試験。"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from wikiskill.figures.errors import FigureError
from wikiskill.figures.pyramid import render_pyramid

RECT_PATTERN = re.compile(
    r'<rect x="([0-9.]+)" y="([0-9.]+)" width="([0-9.]+)" height="20" fill="(#[0-9a-f]+)"/>'
)

VALUE_PATTERN = re.compile(
    r'<text x="([0-9.]+)" y="([0-9.]+)" text-anchor="(end|start)" '
    r'font-family="sans-serif" font-size="13" fill="#222222">([^<]*)</text>'
)

AGE_PATTERN = re.compile(
    r'<text x="([0-9.]+)" y="([0-9.]+)" text-anchor="middle" '
    r'font-family="sans-serif" font-size="15" fill="#222222">([^<]*)</text>'
)

HEADING_PATTERN = re.compile(
    r'<text x="([0-9.]+)" y="([0-9.]+)" text-anchor="middle" '
    r'font-family="sans-serif" font-size="15" font-weight="bold" fill="#222222">([^<]*)</text>'
)


def _write(tmp_path: Path, text: str, name: str = "人口.toml") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# --- 正常系 -----------------------------------------------------------------------


def test_人口ピラミッドは左右に棒を伸ばし中央に年齢を置く(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
title = "人口"
[[band]]
label = "0-4"
male = 100
female = 50
[[band]]
label = "5-9"
male = 60
female = 40
""",
    )

    svg = render_pyramid(data)

    assert svg.startswith(
        '<svg xmlns="http://www.w3.org/2000/svg" width="516.5" height="110" '
        'viewBox="0 0 516.5 110" role="img" aria-label="人口">'
    )
    assert "<title>人口</title>" in svg
    assert RECT_PATTERN.findall(svg) == [
        ("41.45", "44", "200", "#2c5aa0"),
        ("282.2", "44", "100", "#c0392b"),
        ("121.45", "70", "120", "#2c5aa0"),
        ("282.2", "70", "80", "#c0392b"),
    ]
    assert (
        '<text x="35.45" y="58" text-anchor="end" font-family="sans-serif" '
        'font-size="13" fill="#222222">100</text>'
    ) in svg
    assert (
        '<text x="388.2" y="58" text-anchor="start" font-family="sans-serif" '
        'font-size="13" fill="#222222">50</text>'
    ) in svg
    assert (
        '<text x="115.45" y="84" text-anchor="end" font-family="sans-serif" '
        'font-size="13" fill="#222222">60</text>'
    ) in svg
    assert (
        '<text x="368.2" y="84" text-anchor="start" font-family="sans-serif" '
        'font-size="13" fill="#222222">40</text>'
    ) in svg
    headings = HEADING_PATTERN.findall(svg)
    assert [(x, text) for x, _, text in headings] == [("141.45", "男性"), ("382.2", "女性")]
    ages = AGE_PATTERN.findall(svg)
    assert [text for _, _, text in ages] == ["0-4", "5-9"]
    assert ages[0][0] == ages[1][0]
    assert 241.45 < float(ages[0][0]) < 282.2
    assert svg.endswith("</svg>")


def test_人口ピラミッドは左右で同じ縮尺を使う(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[band]]
label = "0-4"
male = 100
female = 25
""",
    )

    svg = render_pyramid(data)

    assert RECT_PATTERN.findall(svg) == [
        ("41.45", "44", "200", "#2c5aa0"),
        ("282.2", "44", "50", "#c0392b"),
    ]


def test_人口ピラミッドの最大の棒は幅_200_になる(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[band]]
label = "0-4"
male = 30
female = 80
""",
    )

    svg = render_pyramid(data)

    rects = RECT_PATTERN.findall(svg)
    assert rects == [
        ("159.3", "44", "75", "#2c5aa0"),
        ("275.05", "44", "200", "#c0392b"),
    ]


def test_人口ピラミッドの値は単位と桁で書く(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
unit = "万人"
digits = 1
[[band]]
label = "0-4"
male = 12.34
female = 5.67
""",
    )

    svg = render_pyramid(data)

    assert svg.startswith(
        '<svg xmlns="http://www.w3.org/2000/svg" width="582.8" height="84" '
        'viewBox="0 0 582.8 84" role="img">'
    )
    assert ">12.3万人</text>" in svg
    assert ">5.7万人</text>" in svg
    assert RECT_PATTERN.findall(svg) == [
        ("74.6", "44", "200", "#2c5aa0"),
        ("315.35", "44", "91.9", "#c0392b"),
    ]


def test_人口ピラミッドの桁は_2_まで使える(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
unit = "万"
digits = 2
[[band]]
label = "0-4"
male = 12.34
female = 5.67
""",
    )

    svg = render_pyramid(data)

    assert ">12.34万</text>" in svg
    assert ">5.67万</text>" in svg


def test_人口ピラミッドの値が_0_なら棒を出さず値だけ出す(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[band]]
label = "0-4"
male = 0
female = 5
""",
    )

    svg = render_pyramid(data)

    assert RECT_PATTERN.findall(svg) == [("267.9", "44", "200", "#c0392b")]
    assert svg.count(">0</text>") == 1
    assert svg.count(">5</text>") == 1
    assert "#2c5aa0" not in svg
    assert "#c0392b" in svg
    assert svg.startswith(
        '<svg xmlns="http://www.w3.org/2000/svg" width="495.05" height="84" '
        'viewBox="0 0 495.05 84" role="img">'
    )


def test_人口ピラミッドは値を入力順に上から並べる(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[band]]
label = "10-14"
male = 1
female = 1
[[band]]
label = "15-19"
male = 2
female = 2
[[band]]
label = "20-24"
male = 3
female = 3
""",
    )

    svg = render_pyramid(data)

    ages = AGE_PATTERN.findall(svg)
    assert [text for _, _, text in ages] == ["10-14", "15-19", "20-24"]
    ys = [float(y) for _, y, _ in ages]
    assert ys == [59, 85, 111]


def test_人口ピラミッドは既定の見出しと色を使う(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[band]]
label = "0-4"
male = 10
female = 10
""",
    )

    svg = render_pyramid(data)

    headings = HEADING_PATTERN.findall(svg)
    assert [text for _, _, text in headings] == ["男性", "女性"]
    assert 'fill="#2c5aa0"' in svg
    assert 'fill="#c0392b"' in svg


def test_人口ピラミッドの見出しと色を変えられる(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
male_label = "男"
female_label = "女"
male_color = "#123ABC"
female_color = "#0f0"
[[band]]
label = "0-4"
male = 10
female = 10
""",
    )

    svg = render_pyramid(data)

    assert [text for _, _, text in HEADING_PATTERN.findall(svg)] == ["男", "女"]
    assert 'fill="#123abc"' in svg
    assert 'fill="#0f0"' in svg
    assert "#2c5aa0" not in svg
    assert "#c0392b" not in svg


def test_人口ピラミッドの_title_は_aria_label_と_title_要素に出す(
    tmp_path: Path,
) -> None:
    data = _write(
        tmp_path,
        """
title = "人口 & ピラミッド"
[[band]]
label = "0-4"
male = 1
female = 2
""",
    )

    svg = render_pyramid(data)

    assert 'aria-label="人口 &amp; ピラミッド"' in svg
    assert "<title>人口 &amp; ピラミッド</title>" in svg


def test_人口ピラミッドの_title_が空なら出さない(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[band]]
label = "0-4"
male = 1
female = 2
""",
    )

    svg = render_pyramid(data)

    assert "aria-label" not in svg
    assert "<title>" not in svg
    assert 'role="img">' in svg


def test_人口ピラミッドのラベルは_xml_用にエスケープする(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[band]]
label = "0-4<歳>"
male = 1
female = 2
""",
    )

    svg = render_pyramid(data)

    assert ">0-4&lt;歳&gt;</text>" in svg
    assert "<歳>" not in svg


# --- 異常系 -----------------------------------------------------------------------


def test_人口ピラミッドの知らない項目は誤り(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
title = "人口"
note = "メモ"
[[band]]
label = "0-4"
male = 1
female = 2
""",
    )

    with pytest.raises(FigureError, match="知らない項目がある: note"):
        render_pyramid(data)


def test_人口ピラミッドの_band_が無ければ誤り(tmp_path: Path) -> None:
    data = _write(tmp_path, 'title = "人口"\n')

    with pytest.raises(FigureError, match="band は 1 つ以上の表の並びで書く"):
        render_pyramid(data)


def test_人口ピラミッドのデータが空なら誤り(tmp_path: Path) -> None:
    data = _write(tmp_path, "")

    with pytest.raises(FigureError, match="band は 1 つ以上の表の並びで書く"):
        render_pyramid(data)


def test_人口ピラミッドの_band_が空の並びなら誤り(tmp_path: Path) -> None:
    data = _write(tmp_path, "band = []\n")

    with pytest.raises(FigureError, match="band は 1 つ以上の表の並びで書く"):
        render_pyramid(data)


def test_人口ピラミッドの_band_が表の並びでなければ誤り(tmp_path: Path) -> None:
    data = _write(tmp_path, 'band = "0-4"\n')

    with pytest.raises(FigureError, match="band は 1 つ以上の表の並びで書く"):
        render_pyramid(data)


def test_人口ピラミッドの_band_の要素が表でなければ誤り(tmp_path: Path) -> None:
    data = _write(tmp_path, "band = [1]\n")

    with pytest.raises(FigureError, match="band の要素は表で書く"):
        render_pyramid(data)


def test_人口ピラミッドのラベルが空なら誤り(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[band]]
label = "  "
male = 1
female = 2
""",
    )

    with pytest.raises(FigureError, match="band の label が空"):
        render_pyramid(data)


def test_人口ピラミッドのラベルが重複すれば誤り(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[band]]
label = "0-4"
male = 1
female = 2
[[band]]
label = "0-4"
male = 3
female = 4
""",
    )

    with pytest.raises(FigureError, match="label が重複している: 0-4"):
        render_pyramid(data)


def test_人口ピラミッドの値が負なら誤り(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[band]]
label = "0-4"
male = -1
female = 2
""",
    )

    with pytest.raises(FigureError, match="male は 0 以上の有限の数で書く: -1"):
        render_pyramid(data)


def test_人口ピラミッドの値が真偽値なら誤り(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[band]]
label = "0-4"
male = 1
female = true
""",
    )

    with pytest.raises(FigureError, match="female は 0 以上の有限の数で書く: True"):
        render_pyramid(data)


def test_人口ピラミッドの値が有限でなければ誤り(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[band]]
label = "0-4"
male = inf
female = 2
""",
    )

    with pytest.raises(FigureError, match="male は 0 以上の有限の数で書く: inf"):
        render_pyramid(data)


def test_人口ピラミッドの値が無ければ誤り(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[band]]
label = "0-4"
female = 2
""",
    )

    with pytest.raises(FigureError, match="male は 0 以上の有限の数で書く: None"):
        render_pyramid(data)


def test_人口ピラミッドの桁数が範囲外なら誤り(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
digits = 3
[[band]]
label = "0-4"
male = 1
female = 2
""",
    )

    with pytest.raises(FigureError, match="digits は 0 から 2 の整数で書く: 3"):
        render_pyramid(data)


def test_人口ピラミッドの桁数が整数でなければ誤り(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
digits = "1"
[[band]]
label = "0-4"
male = 1
female = 2
""",
    )

    with pytest.raises(FigureError, match="digits は 0 から 2 の整数で書く: '1'"):
        render_pyramid(data)


def test_人口ピラミッドの桁数が真偽値なら誤り(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
digits = true
[[band]]
label = "0-4"
male = 1
female = 2
""",
    )

    with pytest.raises(FigureError, match="digits は 0 から 2 の整数で書く: True"):
        render_pyramid(data)


def test_人口ピラミッドの色の書式が違えば誤り(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
male_color = "red"
[[band]]
label = "0-4"
male = 1
female = 2
""",
    )

    with pytest.raises(FigureError, match="male_color の色は #rgb か #rrggbb"):
        render_pyramid(data)


def test_人口ピラミッドの女性の色の書式が違えば誤り(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
female_color = "#12345"
[[band]]
label = "0-4"
male = 1
female = 2
""",
    )

    with pytest.raises(FigureError, match="female_color の色は #rgb か #rrggbb"):
        render_pyramid(data)


def test_人口ピラミッドの_band_の知らない項目は誤り(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[band]]
label = "0-4"
male = 1
female = 2
note = "メモ"
""",
    )

    with pytest.raises(FigureError, match="知らない項目がある: note"):
        render_pyramid(data)


def test_人口ピラミッドの_title_が文字列でなければ誤り(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
title = 1
[[band]]
label = "0-4"
male = 1
female = 2
""",
    )

    with pytest.raises(FigureError, match="title は文字列で書く"):
        render_pyramid(data)


def test_人口ピラミッドの_unit_が文字列でなければ誤り(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
unit = 1
[[band]]
label = "0-4"
male = 1
female = 2
""",
    )

    with pytest.raises(FigureError, match="unit は文字列で書く"):
        render_pyramid(data)
