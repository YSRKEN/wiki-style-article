"""原稿が指す画像を読む。

画像は原稿からの相対の道か、同梱の目録のキー（``bundle:flags/jp.svg``）で指す。
HTML には画像そのものを data: の URI として埋め込み、ウィキテキストにはファイルの名前だけを
書く（本家では画像は別に上げるものなので、同梱のものは本家のファイル名で書く）。
"""

from __future__ import annotations

import base64
import re
import tomllib
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Final, cast

MEDIA_TYPES: Final[dict[str, str]] = {
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}
"""埋め込める画像の拡張子（小文字）と media type。"""

MAX_BYTES: Final[int] = 2 * 1024 * 1024
"""埋め込む画像の大きさの上限（2 MiB）。これより大きいと HTML が重くなりすぎる。"""

_EXTENSIONS = "・".join(sorted(MEDIA_TYPES))

BUNDLE_PREFIX: Final[str] = "bundle:"
"""同梱の画像を指す接頭辞。後ろに目録のキーを書く。"""

BUNDLE_LICENSES: Final[frozenset[str]] = frozenset({"PD", "CC0"})
"""同梱してよいライセンス（条件の無いパブリックドメインと CC0 だけ）。"""

DEFAULT_MANIFEST_PATH: Final[Path] = (
    Path(__file__).resolve().parents[2] / "assets" / "images" / "manifest.toml"
)
"""同梱の目録の既定の道（``skills/wiki/assets/images/manifest.toml``）。"""

_SOURCE_PREFIX: Final[str] = "https://commons.wikimedia.org/wiki/File:"
_FIELDS: Final[frozenset[str]] = frozenset({"key", "path", "file", "license", "source", "author"})
_FILE_FORBIDDEN: Final[frozenset[str]] = frozenset("[]|\\/")


class ImageError(Exception):
    """画像を埋め込めない（無い、種類が違う、大きすぎる、置き場が分からない）。"""


class BundleError(ImageError):
    """同梱の目録か同梱の画像に問題がある（目録が壊れている、キーが無い、実ファイルが無い）。"""


@dataclass(frozen=True)
class BundleImage:
    """同梱の画像 1 件。``path`` は実ファイルの道、``file`` は本家のファイル名。"""

    key: str
    path: Path
    file: str
    license: str
    source: str
    author: str | None


def media_type(source: str) -> str | None:
    """道から media type を返す。埋め込めない種類なら None。"""
    return MEDIA_TYPES.get(Path(source).suffix.lower())


def is_bundle(source: str) -> bool:
    """同梱の画像を指す道（``bundle:`` で始まる）か。"""
    return source.strip().startswith(BUNDLE_PREFIX)


def bundle_key(source: str) -> str:
    """同梱の画像を指す道から目録のキーを取り出す。"""
    return source.strip()[len(BUNDLE_PREFIX) :].strip()


def _text(entry: dict[str, object], name: str, where: str) -> str:
    """目録の 1 項目を、空でない文字列として取り出す。"""
    value = entry.get(name)
    if not isinstance(value, str) or value == "":
        raise BundleError(f"{where}: {name} は空でない文字列にする")
    return value


def _parse_entry(entry: object, *, base_dir: Path) -> BundleImage:
    """目録の 1 件を読み、同梱の画像にする。壊れていれば BundleError。"""
    if not isinstance(entry, dict):
        raise BundleError("同梱の目録の images の各件は表にする")
    table = cast("dict[str, object]", entry)
    where = "同梱の目録"
    unknown = sorted(set(table) - _FIELDS)
    if unknown:
        raise BundleError(f"{where}に知らない項目がある: {', '.join(unknown)}")
    key = _text(table, "key", where)
    where = f"同梱の目録の {key}"
    raw_path = _text(table, "path", where)
    relative = Path(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise BundleError(f"{where}: path は目録からの相対で .. を含めない: {raw_path}")
    if media_type(raw_path) is None:
        raise BundleError(f"{where}: 埋め込めない種類の画像: {raw_path}")
    actual = base_dir / relative
    if not actual.is_file():
        raise BundleError(f"{where}: 同梱の画像が無い: {raw_path}")
    file = _text(table, "file", where)
    forbidden = sorted(set(file) & _FILE_FORBIDDEN)
    if forbidden:
        raise BundleError(f"{where}: 本家のファイル名に使えない文字がある: {' '.join(forbidden)}")
    license_value = _text(table, "license", where)
    if license_value not in BUNDLE_LICENSES:
        allowed = "・".join(sorted(BUNDLE_LICENSES))
        raise BundleError(f"{where}: ライセンスは {allowed} だけ: {license_value}")
    source = _text(table, "source", where)
    if not source.startswith(_SOURCE_PREFIX):
        raise BundleError(f"{where}: source は Commons のファイルページの URL にする: {source}")
    author: str | None = None
    if "author" in table:
        author = _text(table, "author", where)
    return BundleImage(
        key=key,
        path=actual,
        file=file,
        license=license_value,
        source=source,
        author=author,
    )


def parse_manifest(text: str, *, base_dir: Path) -> dict[str, BundleImage]:
    """目録（TOML）を読み、キーから同梱の画像への対応を返す。壊れていれば BundleError。"""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise BundleError(f"同梱の目録を TOML として読めない: {error}") from error
    unknown = sorted(set(data) - {"images"})
    if unknown:
        raise BundleError(f"同梱の目録に知らない項目がある: {', '.join(unknown)}")
    raw_entries = data.get("images")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise BundleError("同梱の目録には images を 1 件以上書く")
    entries = cast("list[object]", raw_entries)
    images: dict[str, BundleImage] = {}
    for entry in entries:
        image = _parse_entry(entry, base_dir=base_dir)
        if image.key in images:
            raise BundleError(f"同梱の目録でキーが重複している: {image.key}")
        images[image.key] = image
    return images


def read_manifest(path: Path) -> dict[str, BundleImage]:
    """目録のファイルを読み、キーから同梱の画像への対応を返す。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise BundleError(f"同梱の目録を読めない: {path}（{error.strerror}）") from error
    return parse_manifest(text, base_dir=path.parent)


@cache
def load_manifest() -> dict[str, BundleImage]:
    """既定の目録を読む（読み込みは 1 回だけ）。"""
    return read_manifest(DEFAULT_MANIFEST_PATH)


def find_bundle(source: str) -> BundleImage | None:
    """同梱の画像を目録から引く。同梱でない、または目録に無ければ None。"""
    if not is_bundle(source):
        return None
    return load_manifest().get(bundle_key(source))


def file_name(source: str) -> str:
    """ウィキテキストに書くファイルの名前（同梱なら本家の名前、でなければ道の最後）。"""
    image = find_bundle(source)
    if image is not None:
        return image.file
    if is_bundle(source):
        raise BundleError(f"同梱の目録に無い画像: {bundle_key(source)}")
    return Path(source).name


IMAGE_PATTERN: Final[re.Pattern[str]] = re.compile(r"!\[(?P<caption>[^\]]*)\]\((?P<source>[^)]*)\)")
"""原稿に書く画像の値（``![キャプション](道)``）の形。本文と Infobox で同じ形を使う。"""

_INDENT = " \t"


def split_value(text: str) -> tuple[str, str] | None:
    """画像の値（``![キャプション](道)``）を（キャプション, 道）に分ける。

    形が違うときと道が空のときは None。道が相対かどうかは見ない（``find_issue`` の仕事）。
    """
    matched = IMAGE_PATTERN.fullmatch(text.strip(_INDENT))
    if matched is None:
        return None
    caption = matched.group("caption").strip(_INDENT)
    source = matched.group("source").strip(_INDENT)
    if not source:
        return None
    return caption, source


def _size_issue(path: Path, source: str) -> tuple[str, str] | None:
    """実ファイルの大きさを見て、大きすぎるなら理由を返す。"""
    try:
        size = path.stat().st_size
    except OSError:
        return ("IMAGE-MISSING", f"画像が無い: {source}")
    if size > MAX_BYTES:
        return (
            "IMAGE-TOO-LARGE",
            f"画像が大きすぎる（{size} バイト。{MAX_BYTES} バイトまで）",
        )
    return None


def find_issue(source: str, base_dir: Path | None) -> tuple[str, str] | None:
    """画像を埋め込めない理由を（規則の ID、文面）で返す。埋め込めるなら None。

    ``base_dir`` が None（原稿の置き場が分からない）ときは、道と種類だけを見て、
    実物の有無と大きさは見ない。同梱の画像（``bundle:``）は目録と同梱の実ファイルを見る。
    """
    if is_bundle(source):
        image = find_bundle(source)
        if image is None:
            return ("IMAGE-MISSING", f"画像が無い: {source}")
        return _size_issue(image.path, source)
    if Path(source).is_absolute():
        return ("IMAGE-PATH", f"画像は原稿からの相対の道で指す: {source}")
    if media_type(source) is None:
        return (
            "IMAGE-TYPE",
            f"埋め込める画像の種類ではない（{_EXTENSIONS} のどれかにする）",
        )
    if base_dir is None:
        return None
    path = base_dir / source
    if not path.is_file():
        return ("IMAGE-MISSING", f"画像が無い: {source}")
    return _size_issue(path, source)


def read_image(source: str, base_dir: Path | None) -> tuple[str, bytes]:
    """画像を読み、(media type, 中身) を返す。同梱の画像は目録の指す実ファイルを読む。"""
    image = find_bundle(source)
    if is_bundle(source):
        if image is None:
            raise ImageError(f"同梱の目録に無い画像: {bundle_key(source)}")
        path = image.path
    elif base_dir is None:
        raise ImageError("原稿の置き場が分からないので画像を読めない")
    else:
        path = base_dir / source
    issue = find_issue(source, base_dir)
    if issue is not None:
        raise ImageError(issue[1])
    kind = media_type(path.name)
    if kind is None:  # find_issue が弾いているので、ここへは来ない。
        raise ImageError(f"埋め込める画像の種類ではない（{_EXTENSIONS} のどれかにする）")
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ImageError(f"画像を読めない: {source}（{error.strerror}）") from error
    return kind, data


def data_uri(source: str, base_dir: Path | None) -> str:
    """画像を data: の URI にする（HTML に埋め込むため）。"""
    kind, data = read_image(source, base_dir)
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{kind};base64,{encoded}"
