"""同梱画像（![キャプション](bundle:キー)）の目録と解決の試験。"""

import base64
from pathlib import Path

import pytest

from wikiskill.checks import check_article
from wikiskill.cli import main
from wikiskill.errors import MarkupError
from wikiskill.html_check import check_html
from wikiskill.html_writer import write_html
from wikiskill.images import (
    BUNDLE_LICENSES,
    DEFAULT_MANIFEST_PATH,
    MAX_BYTES,
    MEDIA_TYPES,
    BundleError,
    ImageError,
    bundle_key,
    data_uri,
    file_name,
    find_bundle,
    find_issue,
    is_bundle,
    load_manifest,
    parse_manifest,
    read_image,
)
from wikiskill.reader import read_article_file
from wikiskill.types import load_default_registry
from wikiskill.wikitext import write_wikitext

REGISTRY = load_default_registry()
UPDATED = "2026年11月2日 (月) 12:00 (JST)"
ASSETS = DEFAULT_MANIFEST_PATH.parent

# 1x1 の透過 PNG（同梱でない相対の道の挙動を確かめるため）
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _src(body: str = "", front: str = "", *, type_id: str = "concept") -> str:
    """小さな原稿を組む。``front`` は設定欄の ``title``・``type`` より後ろの TOML。"""
    return f'+++\ntitle = "テスト記事"\ntype = "{type_id}"\n{front}+++\n{body}'


def _file(tmp_path: Path, body: str, *, front: str = "", type_id: str = "concept") -> Path:
    """原稿を一時フォルダに書く。"""
    path = tmp_path / "原稿.md"
    path.write_text(_src(body, front, type_id=type_id), encoding="utf-8")
    return path


def _registry(type_id: str):
    return REGISTRY[type_id]


def _manifest(**overrides: str) -> str:
    """1 件だけの目録を組む（``overrides`` で項目を差し替える）。"""
    fields = {
        "key": "flags/jp.svg",
        "path": "flags/jp.svg",
        "file": "Flag of Japan.svg",
        "license": "PD",
        "source": "https://commons.wikimedia.org/wiki/File:Flag_of_Japan.svg",
    }
    fields.update(overrides)
    lines = ["[[images]]"]
    lines.extend(f'{name} = "{value}"' for name, value in fields.items())
    return "\n".join(lines) + "\n"


GOOD = _manifest()

BROKEN_MANIFESTS = [
    pytest.param("images = [", id="toml"),
    pytest.param('version = "1"\n' + GOOD, id="未知のトップレベル"),
    pytest.param(_manifest(year="2024"), id="未知の項目"),
    pytest.param(GOOD + GOOD, id="キーの重複"),
    pytest.param(_manifest(license="CC BY-SA 4.0"), id="ライセンス"),
    pytest.param(_manifest(path="flags/xx.svg"), id="実ファイルなし"),
    pytest.param(_manifest(path="/tmp/flag.svg"), id="絶対の道"),
    pytest.param(_manifest(path="../manifest.toml"), id="親への道"),
    pytest.param(_manifest(file="Flag|Japan.svg"), id="ファイル名の禁止文字"),
    pytest.param(_manifest(source="https://example.com/flag"), id="出典"),
    pytest.param("images = []", id="空"),
    pytest.param("images = [1]", id="表でない"),
]


# --- 目録の妥当性 ---------------------------------------------------------------


def test_目録は既定の道から読める() -> None:
    assert DEFAULT_MANIFEST_PATH.is_file()
    images = load_manifest()

    assert len(images) >= 40
    japan = images["flags/jp.svg"]
    assert japan.file == "Flag of Japan.svg"
    assert japan.license == "PD"
    assert japan.author == "Various"
    assert japan.path == ASSETS / "flags" / "jp.svg"


def test_目録の全件が同梱の方針を満たす() -> None:
    total = 0
    for key, image in load_manifest().items():
        assert image.key == key
        assert image.license in BUNDLE_LICENSES
        assert image.file.strip()
        assert not set(image.file) & set("[]|\\/")
        assert image.source.startswith("https://commons.wikimedia.org/wiki/File:")
        assert image.path.is_file()
        assert image.path.suffix.lower() in MEDIA_TYPES
        assert image.author is None or image.author.strip()
        size = image.path.stat().st_size
        assert size <= MAX_BYTES
        total += size
    assert total < 1024 * 1024


def test_同梱の容量は_1MiB_未満() -> None:
    total = sum(image.path.stat().st_size for image in load_manifest().values())

    assert total == 369059
    assert total < 1024 * 1024


@pytest.mark.parametrize("text", BROKEN_MANIFESTS)
def test_壊れた目録は例外で止まる(text: str) -> None:
    with pytest.raises(BundleError):
        parse_manifest(text, base_dir=ASSETS)


# --- 解決 ---------------------------------------------------------------------


def test_同梱のキーは目録の実ファイルに解決する() -> None:
    image = find_bundle("bundle:flags/jp.svg")

    assert image is not None
    assert image.key == "flags/jp.svg"
    assert image.path == ASSETS / "flags" / "jp.svg"
    assert find_bundle(" bundle: flags/jp.svg ") is not None
    assert find_bundle("zu.png") is None
    assert is_bundle("bundle:flags/jp.svg")
    assert not is_bundle("images/zu.png")
    assert bundle_key("bundle: flags/jp.svg ") == "flags/jp.svg"


def test_相対の道の扱いは変わらない(tmp_path: Path) -> None:
    (tmp_path / "zu.png").write_bytes(PNG)

    assert file_name("zu.png") == "zu.png"
    assert file_name("images/zu.png") == "zu.png"
    assert find_issue("zu.png", tmp_path) is None
    assert find_issue("zu.png", None) is None
    assert read_image("zu.png", tmp_path) == ("image/png", PNG)


@pytest.mark.parametrize(
    "source",
    [
        pytest.param("https://e.com/a.png", id="URL"),
        pytest.param("/a.png", id="絶対の道"),
        pytest.param("C:\\a.png", id="ドライブ"),
        pytest.param("bundleless:flags/jp.svg", id="bundle 以外のスキーム"),
    ],
)
def test_同梱の接頭辞以外は今まで通り弾く(tmp_path: Path, source: str) -> None:
    """``bundle:`` を通すために URL と絶対の道の検査を緩めていないこと。"""
    path = _file(tmp_path, f"![図]({source})\n")

    with pytest.raises(MarkupError, match="相対"):
        read_article_file(path)


def test_目録に無いキーは画像無しになる() -> None:
    assert find_bundle("bundle:flags/zz.svg") is None
    assert find_issue("bundle:flags/zz.svg", None) == (
        "IMAGE-MISSING",
        "画像が無い: bundle:flags/zz.svg",
    )
    with pytest.raises(BundleError):
        file_name("bundle:flags/zz.svg")
    with pytest.raises(ImageError):
        read_image("bundle:flags/zz.svg", None)


def test_data_uri_は同梱の実ファイルを埋め込む() -> None:
    uri = data_uri("bundle:flags/jp.svg", None)

    assert uri.startswith("data:image/svg+xml;base64,")
    encoded = uri.split(",", 1)[1]
    assert base64.b64decode(encoded) == (ASSETS / "flags" / "jp.svg").read_bytes()


def test_ウィキテキストのファイル名は本家の名前になる() -> None:
    assert file_name("bundle:flags/jp.svg") == "Flag of Japan.svg"
    assert file_name("bundle:flags/cn.svg") == "Flag of the People's Republic of China.svg"
    assert file_name("bundle:flags/gb.svg") == "Flag of the United Kingdom (3-5).svg"


# --- 書き出し ----------------------------------------------------------------


def test_原稿の同梱画像はhtmlとウィキテキストに書ける(tmp_path: Path) -> None:
    path = _file(tmp_path, "'''テスト記事'''は島国。\n\n![日の丸](bundle:flags/jp.svg)\n")
    article = read_article_file(path)

    html = write_html(article, _registry(article.settings.type_id), updated=UPDATED)
    wikitext = write_wikitext(article, _registry(article.settings.type_id))

    assert "data:image/svg+xml;base64," in html
    assert "[[ファイル:Flag of Japan.svg|thumb|日の丸]]" in wikitext
    assert check_article(article) == ()


# --- 通し（build） --------------------------------------------------------------


def test_buildは同梱画像を埋め込む(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _file(tmp_path, "'''テスト記事'''は島国。\n\n![日の丸](bundle:flags/jp.svg)\n")

    code = main(["build", str(path), "--updated", UPDATED])

    capsys.readouterr()
    html = path.with_suffix(".html").read_text(encoding="utf-8")
    wikitext = path.with_suffix(".wikitext").read_text(encoding="utf-8")
    assert code == 0
    assert "data:image/svg+xml;base64," in html
    assert "[[ファイル:Flag of Japan.svg|thumb|日の丸]]" in wikitext
    assert [f.rule for f in check_html(html) if f.rule == "HTML-EXTERNAL-RESOURCE"] == []
