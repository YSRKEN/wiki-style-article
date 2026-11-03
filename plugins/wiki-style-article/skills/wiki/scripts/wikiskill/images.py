"""原稿が指す画像を読む。

画像は原稿からの相対の道で指す。HTML には画像そのものを data: の URI として埋め込み、
ウィキテキストにはファイルの名前だけを書く（本家では画像は別に上げるものなので）。
"""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Final

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


class ImageError(Exception):
    """画像を埋め込めない（無い、種類が違う、大きすぎる、置き場が分からない）。"""


def media_type(source: str) -> str | None:
    """道から media type を返す。埋め込めない種類なら None。"""
    return MEDIA_TYPES.get(Path(source).suffix.lower())


def file_name(source: str) -> str:
    """ウィキテキストに書くファイルの名前（道の最後の部分）。"""
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


def find_issue(source: str, base_dir: Path | None) -> tuple[str, str] | None:
    """画像を埋め込めない理由を（規則の ID、文面）で返す。埋め込めるなら None。

    ``base_dir`` が None（原稿の置き場が分からない）ときは、道と種類だけを見て、
    実物の有無と大きさは見ない。
    """
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
    size = path.stat().st_size
    if size > MAX_BYTES:
        return (
            "IMAGE-TOO-LARGE",
            f"画像が大きすぎる（{size} バイト。{MAX_BYTES} バイトまで）",
        )
    return None


def read_image(source: str, base_dir: Path | None) -> tuple[str, bytes]:
    """画像を読み、(media type, 中身) を返す。"""
    if base_dir is None:
        raise ImageError("原稿の置き場が分からないので画像を読めない")
    issue = find_issue(source, base_dir)
    if issue is not None:
        raise ImageError(issue[1])
    kind = media_type(source)
    if kind is None:  # find_issue が弾いているので、ここへは来ない。
        raise ImageError(f"埋め込める画像の種類ではない（{_EXTENSIONS} のどれかにする）")
    try:
        data = (base_dir / source).read_bytes()
    except OSError as error:
        raise ImageError(f"画像を読めない: {source}（{error.strerror}）") from error
    return kind, data


def data_uri(source: str, base_dir: Path | None) -> str:
    """画像を data: の URI にする（HTML に埋め込むため）。"""
    kind, data = read_image(source, base_dir)
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{kind};base64,{encoded}"
