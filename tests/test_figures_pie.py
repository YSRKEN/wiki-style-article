"""円グラフの SVG を書き出す試験。"""

from __future__ import annotations

from pathlib import Path

import pytest

from wikiskill.figures.errors import FigureError
from wikiskill.figures.pie import render_pie

WHERE = "円グラフのデータ"


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "図.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_円グラフは扇形と凡例を書く(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
title = "得票率"
[[slice]]
label = "a"
value = 60
[[slice]]
label = "b"
value = 30
[[slice]]
label = "c"
value = 10
""",
    )

    svg = render_pie(data)

    assert svg.startswith("<svg ")
    assert svg.endswith("</svg>")
    assert 'role="img"' in svg
    assert 'aria-label="得票率"' in svg
    assert "<title>得票率</title>" in svg
    assert svg.count("<path ") == 3
    assert 'fill="#2c5aa0"' in svg
    assert 'fill="#c0392b"' in svg
    assert 'fill="#2e8b57"' in svg
    assert "a（60.0%）" in svg
    assert "b（30.0%）" in svg
    assert "c（10.0%）" in svg


def test_切片が一つなら円を描く(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[slice]]
label = "賛成"
value = 5
""",
    )

    svg = render_pie(data)

    assert svg.count("<circle ") == 1
    assert "<path " not in svg
    assert ">100.0%<" in svg
    assert "aria-label" not in svg
    assert "<title>" not in svg


def test_内側には六パーセント以上の割合だけ書く(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[slice]]
label = "a"
value = 90
[[slice]]
label = "b"
value = 5
[[slice]]
label = "c"
value = 5
""",
    )

    svg = render_pie(data)

    assert ">90.0%<" in svg
    assert ">5.0%<" not in svg
    assert "b（5.0%）" in svg


def test_単位と桁を付けた値を凡例に書く(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
unit = "万票"
digits = 1
[[slice]]
label = "a"
value = 1234.5
[[slice]]
label = "b"
value = 823
""",
    )

    svg = render_pie(data)

    assert "a（1,234.5万票・60.0%）" in svg
    assert "b（823.0万票・40.0%）" in svg


def test_色を指定できる(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[slice]]
label = "a"
value = 1
color = "#ABC"
""",
    )

    svg = render_pie(data)

    assert 'fill="#abc"' in svg


def test_合計が百でなくても割合を計算する(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[slice]]
label = "a"
value = 2
[[slice]]
label = "b"
value = 1
""",
    )

    svg = render_pie(data)

    assert "a（66.7%）" in svg
    assert "b（33.3%）" in svg


def test_百八十度を超える切片は大きな弧で描く(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[slice]]
label = "a"
value = 9
[[slice]]
label = "b"
value = 1
""",
    )

    svg = render_pie(data)

    assert "A 96 96 0 1 1 " in svg
    assert "A 96 96 0 0 1 " in svg


def test_知らない項目は断る(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
note = "x"
[[slice]]
label = "a"
value = 1
""",
    )

    with pytest.raises(FigureError, match="円グラフのデータ に知らない項目がある: note"):
        render_pie(data)


def test_切片が空なら断る(tmp_path: Path) -> None:
    data = _write(tmp_path, 'title = "空"\n')

    with pytest.raises(FigureError, match="円グラフのデータ の slice が空"):
        render_pie(data)


def test_切片が表でなければ断る(tmp_path: Path) -> None:
    data = _write(tmp_path, 'slice = ["a"]\n')

    with pytest.raises(FigureError, match="円グラフのデータ の slice は表で書く"):
        render_pie(data)


def test_名前が空なら断る(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[slice]]
label = ""
value = 1
""",
    )

    with pytest.raises(FigureError, match="円グラフのデータ の slice の label が空"):
        render_pie(data)


def test_名前が重複したら断る(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[slice]]
label = "a"
value = 1
[[slice]]
label = "a"
value = 2
""",
    )

    with pytest.raises(FigureError, match="円グラフのデータ の slice の label が重複している: a"):
        render_pie(data)


def test_値が数でなければ断る(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[slice]]
label = "a"
value = "10"
""",
    )

    with pytest.raises(FigureError, match="円グラフのデータ の slice の value は数で書く: a"):
        render_pie(data)


@pytest.mark.parametrize("value", ["0", "-2"])
def test_値が零以下なら断る(tmp_path: Path, value: str) -> None:
    data = _write(
        tmp_path,
        f"""
[[slice]]
label = "a"
value = {value}
""",
    )

    with pytest.raises(
        FigureError, match="円グラフのデータ の slice の value は 0 より大きい数で書く: a"
    ):
        render_pie(data)


def test_桁数が範囲外なら断る(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
digits = 3
[[slice]]
label = "a"
value = 1
""",
    )

    with pytest.raises(FigureError, match="円グラフのデータ の digits は 0 から 2 の整数で書く"):
        render_pie(data)


def test_色の形が違えば断る(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
[[slice]]
label = "a"
value = 1
color = "red"
""",
    )

    with pytest.raises(FigureError, match="円グラフのデータ の slice の color の色は #rgb"):
        render_pie(data)
