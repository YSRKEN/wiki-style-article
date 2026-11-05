"""折れ線グラフの SVG を書き出す試験。"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from wikiskill.figures.errors import FigureError
from wikiskill.figures.line import FONT_SIZE, render_line
from wikiskill.figures.svg import text_width


def _line(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "折れ線.toml"
    path.write_text(body, encoding="utf-8")
    return path


SIMPLE = """
title = "人口の推移"
labels = ["2020", "2021", "2022"]

[[series]]
name = "甲"
color = "#cc0000"
values = [1, 2, 3]
"""


def test_折れ線グラフは線と点を系列の色で描く(tmp_path: Path) -> None:
    data = _line(
        tmp_path,
        """
title = "人口の推移"
labels = ["2020", "2021", "2022"]

[[series]]
name = "甲"
color = "#cc0000"
values = [1, 2, 3]

[[series]]
name = "乙"
color = "#0000cc"
values = [3, 2, 1]
""",
    )

    svg = render_line(data)

    assert svg.startswith("<svg ")
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg
    assert 'role="img"' in svg
    root = re.search(r'<svg[^>]*width="([0-9.]+)" height="([0-9.]+)"', svg)
    assert root is not None
    assert root.group(1) == "652"
    assert root.group(2) == "406"
    assert svg.count("<path ") == 2
    assert 'stroke="#cc0000"' in svg
    assert 'stroke="#0000cc"' in svg
    assert svg.count('stroke-width="2.5"') == 2
    assert svg.count('fill="none"') == 2
    assert svg.count('stroke-linejoin="round"') == 2
    assert svg.count("<circle ") == 6
    assert svg.count('r="3.5"') == 6
    assert svg.count('stroke="#dddddd"') == 5
    assert svg.count('stroke="#999999"') == 2
    assert ">甲<" in svg
    assert ">乙<" in svg


def test_折れ線グラフのラベルと凡例の位置(tmp_path: Path) -> None:
    svg = render_line(_line(tmp_path, SIMPLE))

    # x のラベルはプロットの下 20px に中点そろえで置く。
    assert 'y="340" text-anchor="middle"' in svg
    assert '<text x="72" y="340"' in svg
    assert '<text x="632" y="340"' in svg
    # 凡例は x ラベルの下に置く。
    assert '<g transform="translate(72,356)">' in svg
    assert 'x1="72"' in svg
    assert 'x2="632"' in svg


@pytest.mark.parametrize(("count", "dots"), [(24, 24), (25, 0)])
def test_折れ線グラフの点は_24_個までなら描く(tmp_path: Path, count: int, dots: int) -> None:
    labels = ", ".join(f'"{index}"' for index in range(count))
    values = ", ".join(str(index) for index in range(count))
    data = _line(
        tmp_path,
        f"""
labels = [{labels}]

[[series]]
name = "甲"
values = [{values}]
""",
    )

    svg = render_line(data)

    assert svg.count("<circle ") == dots
    assert svg.count("<path ") == 1


def test_折れ線グラフの_x_ラベルは重なる分を間引く(tmp_path: Path) -> None:
    labels = ", ".join(f'"第{index}期"' for index in range(40))
    values = ", ".join(str(index) for index in range(40))
    data = _line(
        tmp_path,
        f"""
labels = [{labels}]

[[series]]
name = "甲"
values = [{values}]
""",
    )

    svg = render_line(data)

    shown = svg.count('text-anchor="middle"')
    assert 0 < shown < 40
    assert ">第0期<" in svg
    assert ">第1期<" not in svg


def test_折れ線グラフの_x_ラベルは狭くなければ全て出す(tmp_path: Path) -> None:
    data = _line(
        tmp_path,
        """
labels = ["A", "B", "C"]

[[series]]
name = "甲"
values = [1, 2, 3]
""",
    )

    svg = render_line(data)

    assert svg.count('text-anchor="middle"') == 3
    for label in ("A", "B", "C"):
        assert f">{label}<" in svg


def test_折れ線グラフの目盛りは_5_本で既定の桁は_0(tmp_path: Path) -> None:
    data = _line(
        tmp_path,
        """
labels = ["一", "二"]

[[series]]
name = "甲"
values = [0, 10]
""",
    )

    svg = render_line(data)

    assert svg.count('stroke="#dddddd"') == 5
    assert ">0<" in svg
    assert ">2<" in svg
    assert ">5<" in svg
    assert ">8<" in svg
    assert ">10<" in svg


def test_折れ線グラフの単位と桁を目盛りに付ける(tmp_path: Path) -> None:
    data = _line(
        tmp_path,
        """
unit = "万人"
digits = 1
labels = ["一", "二"]

[[series]]
name = "甲"
values = [0, 10]
""",
    )

    svg = render_line(data)

    assert ">0.0万人<" in svg
    assert ">5.0万人<" in svg
    assert ">10.0万人<" in svg


def test_折れ線グラフの_y_min_と_y_max_をそのまま使う(tmp_path: Path) -> None:
    data = _line(
        tmp_path,
        """
y_min = 0
y_max = 100
labels = ["一", "二"]

[[series]]
name = "甲"
values = [10, 20]
""",
    )

    svg = render_line(data)

    assert ">25<" in svg
    assert ">50<" in svg
    assert ">75<" in svg
    assert ">100<" in svg


def test_折れ線グラフの下限は負の値で切り下げる(tmp_path: Path) -> None:
    data = _line(
        tmp_path,
        """
digits = 1
labels = ["一", "二"]

[[series]]
name = "甲"
values = [-3, 7]
""",
    )

    svg = render_line(data)

    assert ">-5.0<" in svg
    assert ">10.0<" in svg
    assert svg.count('stroke="#dddddd"') == 5


def test_折れ線グラフの上限は切りのよい値に切り上げる(tmp_path: Path) -> None:
    data = _line(
        tmp_path,
        """
labels = ["一", "二"]

[[series]]
name = "甲"
values = [0, 37]
""",
    )

    svg = render_line(data)

    assert ">25<" in svg
    assert ">50<" in svg


def test_折れ線グラフの題は_aria_label_と_title_要素に入る(tmp_path: Path) -> None:
    svg = render_line(_line(tmp_path, SIMPLE))

    assert 'aria-label="人口の推移"' in svg
    assert "<title>人口の推移</title>" in svg


def test_折れ線グラフの題が空なら付けない(tmp_path: Path) -> None:
    data = _line(
        tmp_path,
        """
labels = ["一", "二"]

[[series]]
name = "甲"
values = [1, 2]
""",
    )

    svg = render_line(data)

    assert "aria-label" not in svg
    assert "<title>" not in svg


def test_折れ線グラフの色を省くと決まった色を使う(tmp_path: Path) -> None:
    data = _line(
        tmp_path,
        """
labels = ["一", "二"]

[[series]]
name = "甲"
values = [1, 2]

[[series]]
name = "乙"
values = [2, 1]
""",
    )

    svg = render_line(data)

    assert 'stroke="#2c5aa0"' in svg
    assert 'stroke="#c0392b"' in svg


def test_折れ線グラフは_XML_の実体参照に直す(tmp_path: Path) -> None:
    data = _line(
        tmp_path,
        """
title = "A&B"
labels = ["x<1", "x>2"]

[[series]]
name = "甲&乙"
values = [1, 2]
""",
    )

    svg = render_line(data)

    assert 'aria-label="A&amp;B"' in svg
    assert "<title>A&amp;B</title>" in svg
    assert "x&lt;1" in svg
    assert "x&gt;2" in svg
    assert ">甲&amp;乙<" in svg


def test_折れ線グラフの知らない項目は誤り(tmp_path: Path) -> None:
    data = _line(
        tmp_path,
        """
note = "メモ"
labels = ["一", "二"]

[[series]]
name = "甲"
values = [1, 2]
""",
    )

    with pytest.raises(FigureError, match="知らない項目がある: note"):
        render_line(data)


def test_折れ線グラフの系列の知らない項目は誤り(tmp_path: Path) -> None:
    data = _line(
        tmp_path,
        """
labels = ["一", "二"]

[[series]]
name = "甲"
values = [1, 2]
note = "メモ"
""",
    )

    with pytest.raises(FigureError, match="知らない項目がある: note"):
        render_line(data)


def test_折れ線グラフの_labels_が_1_件なら誤り(tmp_path: Path) -> None:
    data = _line(
        tmp_path,
        """
labels = ["一"]

[[series]]
name = "甲"
values = [1]
""",
    )

    with pytest.raises(FigureError, match="labels は 2 件以上書く"):
        render_line(data)


def test_折れ線グラフの_labels_に空の項目があれば誤り(tmp_path: Path) -> None:
    data = _line(
        tmp_path,
        """
labels = ["一", " "]

[[series]]
name = "甲"
values = [1, 2]
""",
    )

    with pytest.raises(FigureError, match="labels に空の項目がある"):
        render_line(data)


def test_折れ線グラフの_labels_が並びでなければ誤り(tmp_path: Path) -> None:
    data = _line(
        tmp_path,
        """
labels = "2020"

[[series]]
name = "甲"
values = [1, 2]
""",
    )

    with pytest.raises(FigureError, match="labels は文字列の並びで書く"):
        render_line(data)


def test_折れ線グラフに_series_が無ければ誤り(tmp_path: Path) -> None:
    data = _line(tmp_path, 'labels = ["一", "二"]\n')

    with pytest.raises(FigureError, match="series が空"):
        render_line(data)


def test_折れ線グラフの_values_の数が合わなければ誤り(tmp_path: Path) -> None:
    data = _line(
        tmp_path,
        """
labels = ["一", "二"]

[[series]]
name = "甲"
values = [1, 2, 3]
""",
    )

    with pytest.raises(FigureError, match="values の数が labels と違う: 甲"):
        render_line(data)


@pytest.mark.parametrize("bad", ['"多い"', "true"])
def test_折れ線グラフの_values_が数でなければ誤り(tmp_path: Path, bad: str) -> None:
    data = _line(
        tmp_path,
        f"""
labels = ["一", "二"]

[[series]]
name = "甲"
values = [1, {bad}]
""",
    )

    with pytest.raises(FigureError, match="values は数で書く: 甲"):
        render_line(data)


def test_折れ線グラフの系列の名前が重複すれば誤り(tmp_path: Path) -> None:
    data = _line(
        tmp_path,
        """
labels = ["一", "二"]

[[series]]
name = "甲"
values = [1, 2]

[[series]]
name = "甲"
values = [2, 1]
""",
    )

    with pytest.raises(FigureError, match="name が重複している: 甲"):
        render_line(data)


def test_折れ線グラフの系列の名前が空なら誤り(tmp_path: Path) -> None:
    data = _line(
        tmp_path,
        """
labels = ["一", "二"]

[[series]]
name = ""
values = [1, 2]
""",
    )

    with pytest.raises(FigureError, match="name が空"):
        render_line(data)


@pytest.mark.parametrize("bad", ["3", "-1", "true", "1.5"])
def test_折れ線グラフの_digits_が範囲外なら誤り(tmp_path: Path, bad: str) -> None:
    data = _line(
        tmp_path,
        f"""
digits = {bad}
labels = ["一", "二"]

[[series]]
name = "甲"
values = [1, 2]
""",
    )

    with pytest.raises(FigureError, match="digits は 0 から 2 の整数で書く"):
        render_line(data)


def test_折れ線グラフの_y_min_が_y_max_以上なら誤り(tmp_path: Path) -> None:
    data = _line(
        tmp_path,
        """
y_min = 10
y_max = 10
labels = ["一", "二"]

[[series]]
name = "甲"
values = [1, 2]
""",
    )

    with pytest.raises(FigureError, match="y_min は y_max より小さく書く"):
        render_line(data)


def test_折れ線グラフの_y_min_が数でなければ誤り(tmp_path: Path) -> None:
    data = _line(
        tmp_path,
        """
y_min = "底"
labels = ["一", "二"]

[[series]]
name = "甲"
values = [1, 2]
""",
    )

    with pytest.raises(FigureError, match="y_min は数で書く"):
        render_line(data)


def test_折れ線グラフの色の書式が違えば誤り(tmp_path: Path) -> None:
    data = _line(
        tmp_path,
        """
labels = ["一", "二"]

[[series]]
name = "甲"
color = "red"
values = [1, 2]
""",
    )

    with pytest.raises(FigureError, match="#rgb か #rrggbb"):
        render_line(data)


def test_長い目盛りのラベルが左で切れない(tmp_path: Path) -> None:
    data = _line(
        tmp_path,
        """
title = "人口"
unit = "万人"
digits = 1
labels = ["2000年", "2020年"]

[[series]]
name = "東京都"
values = [1206.4, 1404.8]
""",
    )

    svg = render_line(data)

    ticks = re.findall(
        r'<text x="([0-9.]+)" y="[0-9.]+" text-anchor="end"[^>]*>([^<]+)</text>', svg
    )
    assert len(ticks) == 5
    for x, text in ticks:
        assert float(x) - text_width(text, FONT_SIZE) >= 0.0
