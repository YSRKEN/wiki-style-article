"""図（地図・議席図・グラフ）の SVG を書き出す試験。"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from wikiskill.cli import main
from wikiskill.figures import KINDS, render_figure
from wikiskill.figures.errors import FigureError

TINY_SHAPE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
    '<rect class="aa" width="10" height="10"/>'
    '<rect class="bb" width="20" height="10"/></svg>'
)

CIRCLE_PATTERN = re.compile(
    r'<circle cx="([0-9.]+)" cy="[0-9.]+" r="[0-9.]+" fill="(#[0-9a-f]+)"/>'
)


def _write(tmp_path: Path, text: str, name: str = "図.toml") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _shape(tmp_path: Path, text: str = TINY_SHAPE, name: str = "形.svg") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _data(tmp_path: Path, shape: Path, regions: str) -> Path:
    return _write(
        tmp_path,
        f"""
title = "試験の地図"
shape = "{shape}"
[colors]
red = "#cc0000"
blue = "#0000cc"
[regions]
{regions}
""",
    )


# --- 地図 -------------------------------------------------------------------------


def test_図の種類は地図と議席図とグラフ(tmp_path: Path) -> None:
    assert KINDS == ("map", "seats", "bars", "line", "pie", "pyramid")


def test_地図は地域を色で塗り分け凡例を下に置く(tmp_path: Path) -> None:
    data = _data(tmp_path, _shape(tmp_path), 'aa = "red"\nbb = "blue"')

    svg = render_figure("map", data)

    assert svg.startswith("<svg ")
    assert 'aria-label="試験の地図"' in svg
    assert "<title>試験の地図</title>" in svg
    assert ".aa { fill: #cc0000 !important; }" in svg
    assert ".bb { fill: #0000cc !important; }" in svg
    assert 'fill="#cc0000"' in svg
    assert ">red<" in svg
    assert ">blue<" in svg
    root = re.search(r'<svg[^>]*width="([0-9.]+)" height="([0-9.]+)"', svg)
    assert root is not None
    assert root.group(1) == "100"
    # 凡例の分だけ高さが増える
    assert float(root.group(2)) > 50.0


def test_地図は塗らない地域を既定の灰色にする(tmp_path: Path) -> None:
    data = _data(tmp_path, _shape(tmp_path), 'aa = "red"')

    svg = render_figure("map", data)

    assert "#d9d9d9 !important" in svg
    assert ".bb" in svg


def test_地図は色の指定を小文字にそろえる(tmp_path: Path) -> None:
    data = _data(tmp_path, _shape(tmp_path), 'aa = "red"')

    svg = render_figure("map", data)

    assert "#CC0000" not in svg
    assert ".aa { fill: #cc0000 !important; }" in svg


def test_地図の背景なし凡例なしは矩形を描かない(tmp_path: Path) -> None:
    shape = _shape(
        tmp_path,
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
        '<path class="aa" d="M0 0h10v10H0z"/>'
        '<path class="bb" d="M10 0h10v10H10z"/></svg>',
    )
    data = _data(tmp_path, shape, 'aa = "red"')
    data.write_text(
        data.read_text(encoding="utf-8").replace(
            'title = "試験の地図"', 'title = ""\nbackground = "none"\nlegend = false'
        ),
        encoding="utf-8",
    )

    svg = render_figure("map", data)

    assert "<rect" not in svg
    assert ">red<" not in svg


def test_地図の地域は大文字小文字を問わず照合する(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
title = "合衆国"
[colors]
democrat = "#2c5aa0"
[regions]
CA = "democrat"
""",
    )

    svg = render_figure("map", data)

    assert ".ca { fill: #2c5aa0 !important; }" in svg


def test_地図の形は引数の指定をデータより優先する(tmp_path: Path) -> None:
    data = _data(tmp_path, tmp_path / "ない.svg", 'aa = "red"')

    svg = render_figure("map", data, shape=str(_shape(tmp_path)))

    assert 'width="100"' in svg
    assert ".aa { fill: #cc0000 !important; }" in svg


def test_地図の形は_data_region_でも塗れる(tmp_path: Path) -> None:
    shape = _shape(
        tmp_path,
        '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20">'
        '<rect data-region="north" width="10" height="10"/></svg>',
    )
    data = _data(tmp_path, shape, 'north = "blue"')

    svg = render_figure("map", data)

    assert '[data-region="north"] { fill: #0000cc !important; }' in svg


def test_地図の形に無い地域は誤り(tmp_path: Path) -> None:
    data = _data(tmp_path, _shape(tmp_path), 'zz = "red"')

    with pytest.raises(FigureError, match="地域 'zz' が形に無い"):
        render_figure("map", data)


def test_地図の色の名前が_colors_に無ければ誤り(tmp_path: Path) -> None:
    data = _data(tmp_path, _shape(tmp_path), 'aa = "green"')

    with pytest.raises(FigureError, match="colors に無い"):
        render_figure("map", data)


def test_地図の知らない項目は誤り(tmp_path: Path) -> None:
    data = _data(tmp_path, _shape(tmp_path), 'aa = "red"')
    data.write_text(
        data.read_text(encoding="utf-8").replace(
            'title = "試験の地図"', 'title = "試験の地図"\nfoo = true'
        ),
        encoding="utf-8",
    )

    with pytest.raises(FigureError, match="知らない項目がある: foo"):
        render_figure("map", data)


def test_地図の色の書式が違えば誤り(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        f"""
shape = "{_shape(tmp_path)}"
[colors]
red = "赤"
[regions]
aa = "red"
""",
    )

    with pytest.raises(FigureError, match="#rgb か #rrggbb"):
        render_figure("map", data)


def test_地図の形が見つからなければ誤り(tmp_path: Path) -> None:
    data = _write(
        tmp_path,
        """
shape = "ない地図"
[colors]
red = "#cc0000"
[regions]
aa = "red"
""",
    )

    with pytest.raises(FigureError, match="地図の形が見つからない: ない地図"):
        render_figure("map", data)


def test_色を塗れる地域が無い形は誤り(tmp_path: Path) -> None:
    shape = _shape(
        tmp_path,
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
        '<rect width="10" height="10"/></svg>',
    )
    data = _data(tmp_path, shape, 'aa = "red"')

    with pytest.raises(FigureError, match="色を塗れる地域が無い"):
        render_figure("map", data)


def test_幅と高さの無い形は誤り(tmp_path: Path) -> None:
    shape = _shape(
        tmp_path,
        '<svg xmlns="http://www.w3.org/2000/svg"><rect class="aa" width="10" height="10"/></svg>',
    )
    data = _data(tmp_path, shape, 'aa = "red"')

    with pytest.raises(FigureError, match="幅と高さ"):
        render_figure("map", data)


# --- 議席図 -----------------------------------------------------------------------


def _seats(tmp_path: Path, body: str) -> Path:
    return _write(tmp_path, f'title = "議席"\n{body}', name="議席.toml")


def test_議席図は半円に並べ左から政党の順に塗る(tmp_path: Path) -> None:
    data = _seats(
        tmp_path,
        """
[[party]]
name = "甲党"
seats = 3
color = "#cc0000"
[[party]]
name = "乙党"
seats = 2
color = "#0000cc"
""",
    )

    svg = render_figure("seats", data)

    circles = CIRCLE_PATTERN.findall(svg)
    assert len(circles) == 5
    assert [fill for _, fill in circles] == ["#cc0000"] * 3 + ["#0000cc"] * 2
    red = [float(x) for x, fill in circles if fill == "#cc0000"]
    blue = [float(x) for x, fill in circles if fill == "#0000cc"]
    assert max(red) < min(blue)
    assert "合計 5 議席" in svg
    assert "甲党（3）" in svg
    assert "乙党（2）" in svg
    assert 'aria-label="議席"' in svg


def test_議席図は議席の無い政党を凡例に出さない(tmp_path: Path) -> None:
    data = _seats(
        tmp_path,
        """
[[party]]
name = "甲党"
seats = 2
color = "#cc0000"
[[party]]
name = "空党"
seats = 0
color = "#00cc00"
""",
    )

    svg = render_figure("seats", data)

    assert svg.count("<circle ") == 2
    assert "甲党（2）" in svg
    assert "空党" not in svg


def test_議席図の合計が_0_なら誤り(tmp_path: Path) -> None:
    data = _seats(
        tmp_path,
        """
[[party]]
name = "空党"
seats = 0
color = "#00cc00"
""",
    )

    with pytest.raises(FigureError, match="議席の合計が 0"):
        render_figure("seats", data)


def test_議席図の議席が負なら誤り(tmp_path: Path) -> None:
    data = _seats(
        tmp_path,
        """
[[party]]
name = "甲党"
seats = -1
color = "#cc0000"
""",
    )

    with pytest.raises(FigureError, match="seats は 0 以上の整数"):
        render_figure("seats", data)


def test_議席図の政党の名前が重複すれば誤り(tmp_path: Path) -> None:
    data = _seats(
        tmp_path,
        """
[[party]]
name = "甲党"
seats = 1
color = "#cc0000"
[[party]]
name = "甲党"
seats = 2
color = "#0000cc"
""",
    )

    with pytest.raises(FigureError, match="name が重複している: 甲党"):
        render_figure("seats", data)


def test_議席図に政党が無ければ誤り(tmp_path: Path) -> None:
    data = _seats(tmp_path, "")

    with pytest.raises(FigureError, match="party は 1 つ以上の表の並びで書く"):
        render_figure("seats", data)


def test_議席図の色の書式が違えば誤り(tmp_path: Path) -> None:
    data = _seats(
        tmp_path,
        """
[[party]]
name = "甲党"
seats = 1
color = "red"
""",
    )

    with pytest.raises(FigureError, match="#rgb か #rrggbb"):
        render_figure("seats", data)


def test_議席図の知らない項目は誤り(tmp_path: Path) -> None:
    data = _seats(
        tmp_path,
        """
[[party]]
name = "甲党"
seats = 1
color = "#cc0000"
note = "メモ"
""",
    )

    with pytest.raises(FigureError, match="知らない項目がある: note"):
        render_figure("seats", data)


def test_議席図に形は使えない(tmp_path: Path) -> None:
    data = _seats(
        tmp_path,
        """
[[party]]
name = "甲党"
seats = 1
color = "#cc0000"
""",
    )

    with pytest.raises(FigureError, match="議席図に形（shape）は使えない"):
        render_figure("seats", data, shape="us-states")


def test_知らない図の種類は誤り(tmp_path: Path) -> None:
    with pytest.raises(FigureError, match="知らない図の種類: histogram"):
        render_figure("histogram", tmp_path / "図.toml")


# --- グラフ -----------------------------------------------------------------------


def test_グラフに形は使えない(tmp_path: Path) -> None:
    with pytest.raises(FigureError, match="円グラフに形（shape）は使えない"):
        render_figure("pie", tmp_path / "図.toml", shape="us-states")


@pytest.mark.parametrize(
    ("kind", "body", "expected"),
    [
        ("bars", 'title = "人口"\n[[bar]]\nlabel = "甲"\nvalue = 2', "人口"),
        (
            "line",
            'title = "推移"\nlabels = ["2020", "2021"]\n[[series]]\nname = "甲"\nvalues = [1, 2]',
            "推移",
        ),
        (
            "pie",
            'title = "得票率"\n[[slice]]\nlabel = "a"\nvalue = 60'
            '\n[[slice]]\nlabel = "b"\nvalue = 40',
            "<path ",
        ),
        ("pyramid", 'title = "年齢"\n[[band]]\nlabel = "0-4"\nmale = 100\nfemale = 50', "<rect "),
    ],
)
def test_グラフは種類の名前で描ける(tmp_path: Path, kind: str, body: str, expected: str) -> None:
    data = _write(tmp_path, body, name=f"{kind}.toml")

    svg = render_figure(kind, data)

    assert svg.startswith("<svg ")
    assert expected in svg


# --- CLI --------------------------------------------------------------------------


def test_CLI_の_figure_は地図を書き出す(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data = _data(tmp_path, _shape(tmp_path), 'aa = "red"')
    out = tmp_path / "図" / "地図.svg"

    code = main(["figure", "map", str(data), "--out", str(out)])

    assert code == 0
    assert out.is_file()
    assert ".aa { fill: #cc0000 !important; }" in out.read_text(encoding="utf-8")
    assert f"書き出した: {out}" in capsys.readouterr().out


def test_CLI_の_figure_は形を引数で受け取る(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = _data(tmp_path, tmp_path / "ない.svg", 'aa = "red"')
    out = tmp_path / "地図.svg"

    code = main(["figure", "map", str(data), "--out", str(out), "--shape", str(_shape(tmp_path))])

    assert code == 0
    assert 'width="100"' in out.read_text(encoding="utf-8")
    assert capsys.readouterr().err == ""


def test_CLI_の_figure_は議席図を書き出す(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = _seats(
        tmp_path,
        """
[[party]]
name = "甲党"
seats = 2
color = "#cc0000"
""",
    )
    out = tmp_path / "議席.svg"

    code = main(["figure", "seats", str(data), "--out", str(out)])

    assert code == 0
    assert "合計 2 議席" in out.read_text(encoding="utf-8")
    assert capsys.readouterr().err == ""


def test_CLI_の_figure_は円グラフを書き出す(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = _write(
        tmp_path,
        'title = "得票率"\n[[slice]]\nlabel = "a"\nvalue = 60\n[[slice]]\nlabel = "b"\nvalue = 40',
        name="円.toml",
    )
    out = tmp_path / "円.svg"

    code = main(["figure", "pie", str(data), "--out", str(out)])

    assert code == 0
    assert "a（60.0%）" in out.read_text(encoding="utf-8")
    assert capsys.readouterr().err == ""


def test_CLI_の_figure_はデータの誤りを報告する(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = _data(tmp_path, _shape(tmp_path), 'zz = "red"')
    out = tmp_path / "地図.svg"

    code = main(["figure", "map", str(data), "--out", str(out)])

    assert code == 1
    assert not out.exists()
    captured = capsys.readouterr()
    assert "[エラー] FIGURE: " in captured.err
    assert "zz" in captured.err
