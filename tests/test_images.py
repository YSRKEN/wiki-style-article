"""画像（![キャプション](画像の道)）の読み取り・書き出し・検査の試験。"""

import base64
import os
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from helpers import make_article
from wikiskill.checks import check_article
from wikiskill.checks.walk import iter_figures
from wikiskill.cli import main
from wikiskill.errors import MarkupError
from wikiskill.html_check import check_html
from wikiskill.html_writer import HtmlError, write_html
from wikiskill.images import MAX_BYTES, ImageError, find_issue, read_image, split_value
from wikiskill.model import Article, BulletList, Figure, Paragraph
from wikiskill.reader import read_article, read_article_file
from wikiskill.types import load_default_registry
from wikiskill.variants import normal_view, rumor_view
from wikiskill.wikitext import write_wikitext

REGISTRY = load_default_registry()
UPDATED = "2026年11月2日 (月) 12:00 (JST)"

# 1x1 の透過 PNG（中身は問わないので、実物の画像を置いておく）
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _src(body: str = "", front: str = "", *, type_id: str = "concept") -> str:
    """小さな原稿を組む。``front`` は設定欄の ``title``・``type`` より後ろの TOML。"""
    return f'+++\ntitle = "テスト記事"\ntype = "{type_id}"\n{front}+++\n{body}'


def _file(tmp_path: Path, body: str, *, front: str = "", type_id: str = "concept") -> Path:
    """原稿を一時フォルダに書く（画像はそのフォルダからの相対で置く）。"""
    path = tmp_path / "原稿.md"
    path.write_text(_src(body, front, type_id=type_id), encoding="utf-8")
    return path


def _registry(type_id: str):
    return REGISTRY[type_id]


def _render(source: str) -> str:
    article = read_article(source)
    return write_html(article, _registry(article.settings.type_id), updated=UPDATED)


def _article_html(
    tmp_path: Path, body: str, *, front: str = "", type_id: str = "concept"
) -> tuple[Path, str]:
    path = _file(tmp_path, body, front=front, type_id=type_id)
    (tmp_path / "zu.png").write_bytes(PNG)
    article = read_article_file(path)
    out = write_html(article, _registry(article.settings.type_id), updated=UPDATED)
    return path, out


def _figures(article: Article) -> list[Figure]:
    return list(iter_figures(article))


# --- 本文の読み取り -------------------------------------------------------------


def test_画像の行は導入部のまとまりになる() -> None:
    article = read_article(_src("前の段落。\n\n![図](zu.png)\n\n後の段落。\n"))

    kinds = [type(block) for block in article.lead]
    assert kinds == [Paragraph, Figure, Paragraph]
    figure = article.lead[1]
    assert isinstance(figure, Figure)
    assert (figure.caption, figure.source, figure.line) == ("図", "zu.png", 7)


def test_節の中の画像はその節のまとまりになる() -> None:
    article = read_article(_src("## 節\n\n![図](images/zu.png)\n"))

    assert article.lead == ()
    assert [type(block) for block in article.sections[0].blocks] == [Figure]


def test_画像の行の前後で段落は分かれる() -> None:
    article = read_article(_src("前の段落。\n![図](zu.png)\n後の段落。\n"))

    assert [type(block) for block in article.lead] == [Paragraph, Figure, Paragraph]


def test_画像の行は箇条書きを終わらせる() -> None:
    article = read_article(_src("- 一つ目\n- 二つ目\n\n![図](zu.png)\n"))

    kinds = [type(block) for block in article.lead]
    assert kinds == [BulletList, Figure]


def test_キャプションと道の前後の空白は落とす() -> None:
    article = read_article(_src("![  図  ](  zu.png  )\n"))

    figure = article.lead[0]
    assert isinstance(figure, Figure)
    assert (figure.caption, figure.source) == ("図", "zu.png")


def test_キャプションは空でも読める() -> None:
    article = read_article(_src("![](zu.png)\n"))

    figure = article.lead[0]
    assert isinstance(figure, Figure)
    assert figure.caption == ""


def test_行の途中の画像は弾く() -> None:
    with pytest.raises(MarkupError, match="単独") as caught:
        read_article(_src("本文。![図](zu.png) の続き。\n"))

    assert caught.value.line == 5


def test_画像の道が空なら弾く() -> None:
    with pytest.raises(MarkupError, match="道が空"):
        read_article(_src("![]()\n"))


def test_URLの画像は弾く() -> None:
    with pytest.raises(MarkupError, match="相対"):
        read_article(_src("![図](https://e.com/a.png)\n"))


def test_絶対の道の画像は弾く() -> None:
    for source in ("/a.png", "\\\\server\\a.png", "C:\\a.png"):
        with pytest.raises(MarkupError, match="相対"):
            read_article(_src(f"![図]({source})\n"))


def test_原稿の置き場を覚える(tmp_path: Path) -> None:
    path = _file(tmp_path, "本文。\n")

    assert read_article_file(path).base_dir == tmp_path


def test_文字列から読んだ記事は置き場が分からない() -> None:
    assert read_article(_src("本文。\n")).base_dir is None


# --- 値の分解 -------------------------------------------------------------------


def test_画像の値をキャプションと道に分ける() -> None:
    assert split_value("![図](images/zu.png)") == ("図", "images/zu.png")
    assert split_value("  ![図](images/zu.png)\t") == ("図", "images/zu.png")
    assert split_value("![ 図 ]( images/zu.png )") == ("図", "images/zu.png")
    assert split_value("![](zu.png)") == ("", "zu.png")


def test_画像の形でない値は分けない() -> None:
    for value in (
        "図",
        "![図]",
        "![図](zu.png) の説明",
        "前![図](zu.png)",
        "![図]（zu.png）",
    ):
        assert split_value(value) is None, value
    assert split_value("![図]()") is None


# --- HTML ---------------------------------------------------------------------


def test_画像はdataのURIとして埋め込む(tmp_path: Path) -> None:
    _, out = _article_html(tmp_path, "'''試験'''は本文。\n\n![図](zu.png)\n")

    encoded = base64.b64encode(PNG).decode("ascii")
    assert (
        f'<figure class="thumb"><img src="data:image/png;base64,{encoded}" alt="図">'
        "<figcaption>図</figcaption></figure>" in out
    )


def test_画像のキャプションの記号は逃がす(tmp_path: Path) -> None:
    _, out = _article_html(tmp_path, '本文。\n\n![A<B & "C"](zu.png)\n')

    assert 'alt="A&lt;B &amp; &quot;C&quot;"' in out
    assert "<figcaption>A&lt;B &amp; &quot;C&quot;</figcaption>" in out


def test_画像の名前の道でも名前だけを埋め込む(tmp_path: Path) -> None:
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "zu.png").write_bytes(PNG)
    path = _file(tmp_path, "'''試験'''は本文。\n\n![図](images/zu.png)\n")
    article = read_article_file(path)

    out = write_html(article, _registry(article.settings.type_id), updated=UPDATED)
    assert f'src="data:image/png;base64,{base64.b64encode(PNG).decode("ascii")}"' in out


def test_埋め込みは外部の資源と見なさない(tmp_path: Path) -> None:
    _, out = _article_html(tmp_path, "'''試験'''は本文。\n\n![図](zu.png)\n")

    assert [f.rule for f in check_html(out) if f.rule == "HTML-EXTERNAL-RESOURCE"] == []


def test_置き場の分からない記事は埋め込めない() -> None:
    with pytest.raises(HtmlError, match="行目の画像を埋め込めない"):
        _render(_src("'''試験'''は本文。\n\n![図](zu.png)\n"))


def test_画像が無ければ埋め込めない(tmp_path: Path) -> None:
    path = _file(tmp_path, "'''試験'''は本文。\n\n![図](nai.png)\n")
    article = read_article_file(path)

    with pytest.raises(HtmlError, match="画像が無い"):
        write_html(article, _registry(article.settings.type_id), updated=UPDATED)


def test_画像の種類が違えば埋め込めない(tmp_path: Path) -> None:
    (tmp_path / "zu.bmp").write_bytes(b"BMP")
    path = _file(tmp_path, "'''試験'''は本文。\n\n![図](zu.bmp)\n")
    article = read_article_file(path)

    with pytest.raises(HtmlError, match="種類ではない"):
        write_html(article, _registry(article.settings.type_id), updated=UPDATED)


def test_Infoboxの画像の項目もdataのURIとして埋め込む(tmp_path: Path) -> None:
    front = '[infobox]\n"地図" = "![図](zu.png)"\n'
    _, out = _article_html(tmp_path, "'''試験'''は本文。\n", front=front, type_id="election")

    encoded = base64.b64encode(PNG).decode("ascii")
    figure = (
        f'<figure class="thumb"><img src="data:image/png;base64,{encoded}" alt="図">'
        "<figcaption>図</figcaption></figure>"
    )
    assert f'<tr><th scope="row">地図</th><td>{figure}</td></tr>' in out


def test_Infoboxの画像の項目でも形が違えば文字のまま(tmp_path: Path) -> None:
    front = '[infobox]\n"地図" = "地図はこちら"\n'
    _, out = _article_html(tmp_path, "'''試験'''は本文。\n", front=front, type_id="election")

    assert '<tr><th scope="row">地図</th><td>地図はこちら</td></tr>' in out


def test_Infoboxの画像でない項目の画像の記法は文字として出す(tmp_path: Path) -> None:
    front = '[infobox]\n"選挙制度" = "![図](zu.png)"\n'
    _, out = _article_html(tmp_path, "'''試験'''は本文。\n", front=front, type_id="election")

    assert '<tr><th scope="row">選挙制度</th><td>![図](zu.png)</td></tr>' in out
    assert "<figure" not in out.split('<table class="infobox">')[1].split("</table>")[0]


# --- ウィキテキスト -------------------------------------------------------------


def test_ウィキテキストはファイルの名前だけを書く() -> None:
    article = read_article(_src("'''試験'''は本文。\n\n![図](images/zu.png)\n"))

    out = write_wikitext(article, _registry(article.settings.type_id))
    assert "[[ファイル:zu.png|thumb|図]]" in out


def test_ウィキテキストのキャプションの縦棒は逃がす() -> None:
    article = read_article(_src("本文。\n\n![A|B](zu.png)\n"))

    out = write_wikitext(article, _registry(article.settings.type_id))
    assert "[[ファイル:zu.png|thumb|A&#124;B]]" in out


def test_節の中の画像もウィキテキストに出る() -> None:
    article = read_article(_src("## 節\n\n![図](zu.png)\n"))

    out = write_wikitext(article, _registry(article.settings.type_id))
    assert "== 節 ==" in out
    assert "[[ファイル:zu.png|thumb|図]]" in out


# --- 検査 ---------------------------------------------------------------------


def test_画像の無い原稿は実物を見ない() -> None:
    findings = check_article(make_article("'''試験'''は本文。\n\n![図](nai.png)\n"))

    assert findings == ()


def test_画像が無ければエラー(tmp_path: Path) -> None:
    path = _file(tmp_path, "'''試験'''は本文。\n\n![図](nai.png)\n")
    findings = check_article(read_article_file(path))

    assert [(f.rule, f.level.label, f.line) for f in findings] == [("IMAGE-MISSING", "エラー", 7)]
    assert "画像が無い: nai.png" in findings[0].message


def test_画像の種類が違えばエラー() -> None:
    findings = check_article(make_article("'''試験'''は本文。\n\n![図](zu.bmp)\n"))

    assert [(f.rule, f.line) for f in findings] == [("IMAGE-TYPE", 7)]
    assert ".png" in findings[0].message


def test_検査でも絶対の道はエラー() -> None:
    article = make_article("'''試験'''は本文。\n")
    article = replace(
        article, lead=(*article.lead, Figure(caption="図", source="/tmp/zu.png", line=7))
    )

    assert [(f.rule, f.line) for f in check_article(article)] == [("IMAGE-PATH", 7)]


@pytest.mark.parametrize(
    "source",
    [
        "/tmp/zu.png",
        r"\tmp\zu.png",
        "C:/x.png",
        r"C:\x.png",
        "C:x.png",
        r"\\server\share\x.png",
        "../x.png",
        "images/../../x.png",
        r"images\..\x.png",
        r"images/..\x.png",
    ],
)
@pytest.mark.parametrize("with_base_dir", [False, True])
def test_原稿の外を指す画像の道はOSによらず弾く(
    tmp_path: Path, source: str, with_base_dir: bool
) -> None:
    assert find_issue(source, tmp_path if with_base_dir else None) == (
        "IMAGE-PATH",
        f"画像は原稿からの相対の道で指す: {source}",
    )


@pytest.mark.parametrize("source", ["images/zu.png", "zu.png", r"images\zu.png"])
@pytest.mark.parametrize("with_base_dir", [False, True])
def test_原稿からの相対の画像の道は弾かない(
    tmp_path: Path, source: str, with_base_dir: bool
) -> None:
    issue = find_issue(source, tmp_path if with_base_dir else None)

    assert issue is None or issue[0] != "IMAGE-PATH"


def test_画像が大きすぎればエラー(tmp_path: Path) -> None:
    (tmp_path / "big.png").write_bytes(b"x" * (MAX_BYTES + 1))
    path = _file(tmp_path, "'''試験'''は本文。\n\n![図](big.png)\n")
    findings = check_article(read_article_file(path))

    assert [(f.rule, f.line) for f in findings] == [("IMAGE-TOO-LARGE", 7)]
    assert f"{MAX_BYTES} バイトまで" in findings[0].message


def test_画像の大きさが上限ちょうどなら通る(tmp_path: Path) -> None:
    (tmp_path / "zu.png").write_bytes(b"x" * MAX_BYTES)
    path = _file(tmp_path, "'''試験'''は本文。\n\n![図](zu.png)\n")

    assert check_article(read_article_file(path)) == ()


def test_画像のキャプションが空なら警告() -> None:
    findings = check_article(make_article("'''試験'''は本文。\n\n![](zu.png)\n"))

    assert [(f.rule, f.level.label, f.line) for f in findings] == [("IMAGE-CAPTION", "警告", 7)]


def test_正しい画像は指摘なし(tmp_path: Path) -> None:
    path, _ = _article_html(tmp_path, "'''試験'''は本文。\n\n![図](zu.png)\n")

    assert check_article(read_article_file(path)) == ()


def test_画像は導入部から節へ順に並ぶ() -> None:
    article = read_article(
        _src("![導入](a.png)\n\n## 節\n\n![節](b.png)\n\n### 子\n\n![子](c.png)\n")
    )

    assert [figure.source for figure in _figures(article)] == ["a.png", "b.png", "c.png"]


# --- 噂版・通常版 ---------------------------------------------------------------


_RUMOR = "## 節 [!噂]\n\n![図](zu.png)\n"


def test_通常版にも噂版にも画像が残る(tmp_path: Path) -> None:
    path = _file(tmp_path, "本文。\n\n## 節\n\n![図](zu.png)\n")
    article = read_article_file(path)

    for view in (normal_view(article), rumor_view(article)):
        assert [figure.source for figure in _figures(view)] == ["zu.png"]
        assert view.base_dir == tmp_path


def test_噂の節の画像は通常版で落ちる() -> None:
    article = read_article(_src("本文。\n\n" + _RUMOR))

    assert [figure.source for figure in _figures(normal_view(article))] == []
    assert [figure.source for figure in _figures(rumor_view(article))] == ["zu.png"]


# --- 通し（build） --------------------------------------------------------------


def test_buildは画像を埋め込んだhtmlとファイル名のウィキテキストを書く(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _file(tmp_path, "'''試験'''は'''試験'''は本文。\n\n![図](zu.png)\n")
    (tmp_path / "zu.png").write_bytes(PNG)

    code = main(["build", str(path), "--updated", UPDATED])

    capsys.readouterr()
    html = path.with_suffix(".html").read_text(encoding="utf-8")
    wikitext = path.with_suffix(".wikitext").read_text(encoding="utf-8")
    assert code == 0
    assert "data:image/png;base64," in html
    assert "[[ファイル:zu.png|thumb|図]]" in wikitext
    assert [f.rule for f in check_html(html) if f.rule == "HTML-EXTERNAL-RESOURCE"] == []


def _image_link(link: Path, target: Path, kind: str) -> None:
    """試験用のリンクを作り、環境が対応していなければ飛ばす。

    Parameters
    ----------
    link
        作るリンクの道。
    target
        リンク先の道。
    kind
        directory・file はシンボリックリンク、junction はジャンクション。
    """
    try:
        if kind == "junction":
            if os.name != "nt":
                pytest.skip("ジャンクションは Windows でのみ試す")
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True,
                check=False,
            )
            if result.returncode:
                pytest.skip("この環境ではジャンクションを作れない")
        else:
            link.symlink_to(target, target_is_directory=kind == "directory")
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"この環境ではリンクを作れない: {error}")
    assert link.resolve() == target.resolve()


@pytest.mark.parametrize("kind", ["directory", "file", "junction"])
def test_原稿の外を指すリンクの画像は弾く(tmp_path: Path, kind: str) -> None:
    base_dir = tmp_path / "原稿"
    base_dir.mkdir()
    outside = tmp_path / "原稿の外"
    outside.mkdir()
    image = outside / "zu.png"
    image.write_bytes(PNG)
    link = base_dir / ("link.png" if kind == "file" else "images")
    _image_link(link, image if kind == "file" else outside, kind)
    source = "link.png" if kind == "file" else "images/zu.png"

    assert find_issue(source, base_dir) == (
        "IMAGE-PATH",
        f"画像は原稿からの相対の道で指す: {source}",
    )
    with pytest.raises(ImageError) as caught:
        read_image(source, base_dir)
    assert str(caught.value) == f"画像は原稿からの相対の道で指す: {source}"


@pytest.mark.parametrize("kind", ["directory", "file", "junction"])
def test_原稿の中を指すリンクの画像は読める(tmp_path: Path, kind: str) -> None:
    inside = tmp_path / "images"
    inside.mkdir()
    image = inside / "zu.png"
    image.write_bytes(PNG)
    link = tmp_path / ("link.png" if kind == "file" else "link")
    _image_link(link, image if kind == "file" else inside, kind)
    source = "link.png" if kind == "file" else "link/zu.png"

    assert find_issue(source, tmp_path) is None
    assert read_image(source, tmp_path) == ("image/png", PNG)
