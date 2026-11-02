"""Web のページを取り、本文を文字にして返す。

調べものの担当が使う取得の道具。Claude Code の WebFetch は web.archive.org を取れず、
Jina の Reader も鍵なしでは web.archive.org を止めている（2026-11-02 に確かめた）。
本家はしばしば保存版の URL を出典に使うので、標準ライブラリだけで取れるようにする。

- web.archive.org の保存版は、Wayback の飾りの無い形（``/web/<時刻>id_/<URL>``）に直して取る
- 同じホストへは間を空ける（web.archive.org は 15 秒。続けて送ると 429 で断られた）。担当が並んで
  別々のプロセスで取っても順番を守れるよう、間の記録をファイルに置く
- 429・503 なら、間を空けて一度だけ取り直す
- HTML だけを扱う。PDF などは :class:`FetchError` にする
"""

from __future__ import annotations

import contextlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Generator
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

__all__ = [
    "FetchError",
    "Page",
    "Pacer",
    "archive_raw_url",
    "decode_body",
    "fetch_page",
    "html_to_text",
]

USER_AGENT = "wiki-style-article (+https://github.com/YSRKEN/wiki-style-article)"
ARCHIVE_HOST = "web.archive.org"
_INTERVALS = {ARCHIVE_HOST: 15.0}
_DEFAULT_INTERVAL = 1.0
_RETRY_STATUSES = frozenset({429, 503})
_ARCHIVE_PATH = re.compile(r"^/web/(\d{4,14})([a-z]{2}_)?/(.+)$")


class FetchError(Exception):
    """ページを取れなかったときの例外。文面に理由（HTTP の番号など）を含む。"""


@dataclass(frozen=True, slots=True)
class Page:
    """取ったページ。

    Parameters
    ----------
    url : str
        頼まれた URL。
    fetched_url : str
        実際に取りに行った URL（保存版なら ``id_`` の形）。
    title : str
        ページの題。無ければ空文字。
    text : str
        本文を文字にしたもの。見出しは ``#``、箇条は ``- `` で始まる行になる。
    """

    url: str
    fetched_url: str
    title: str
    text: str


def archive_raw_url(url: str) -> str:
    """web.archive.org の保存版の URL を、飾りの無い ``id_`` の形に直す。

    Parameters
    ----------
    url : str
        URL。保存版でなければそのまま返す。

    Returns
    -------
    str
        ``https://web.archive.org/web/<時刻>id_/<元の URL>``。
    """
    parts = urllib.parse.urlsplit(url)
    if parts.hostname != ARCHIVE_HOST:
        return url
    match = _ARCHIVE_PATH.match(parts.path)
    if match is None:
        return url
    stamp, _flag, target = match.groups()
    rest = f"{target}?{parts.query}" if parts.query else target
    return f"https://{ARCHIVE_HOST}/web/{stamp}id_/{rest}"


def decode_body(data: bytes, content_type: str | None) -> str:
    """応答の中身を文字にする。見出しの指定、``<meta>`` の指定、UTF-8 の順に試す。"""
    for charset in (_charset_of(content_type or ""), _meta_charset(data)):
        if charset:
            with contextlib.suppress(LookupError, UnicodeDecodeError):
                return data.decode(charset)
    return data.decode("utf-8", errors="replace")


def html_to_text(html: str) -> tuple[str, str]:
    """HTML から題と本文の文字を取り出す。

    スクリプト・スタイル・ナビゲーションなどは捨てる。見出しは ``#`` を重ね、箇条は ``- `` を付けた
    行にする。段落ごとに行を分け、続く空行は一つにまとめる。

    Returns
    -------
    tuple[str, str]
        題と本文。
    """
    parser = _TextParser()
    parser.feed(html)
    parser.close()
    return parser.title, parser.text()


class Pacer:
    """同じホストへの取得の間を空ける。間の記録はフォルダの中のファイルに置く。

    Parameters
    ----------
    state_dir : Path
        記録を置くフォルダ。別々のプロセスで同じフォルダを使えば、順番を分け合える。
    clock, sleep
        時刻と待ち方。試験で差し替える。
    """

    def __init__(
        self,
        state_dir: Path,
        *,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._dir = state_dir
        self._clock = clock
        self._sleep = sleep

    def wait(self, host: str, *, extra: float = 0.0) -> None:
        """前の取得から決まった間が経つまで待ち、次の番を記録する。"""
        interval = _INTERVALS.get(host, _DEFAULT_INTERVAL) + extra
        self._dir.mkdir(parents=True, exist_ok=True)
        with self._lock():
            state = self._read()
            ready = float(state.get(host, 0.0))
            now = self._clock()
            if ready > now:
                self._sleep(ready - now)
                now = ready
            state[host] = now + interval
            (self._dir / "pacer.json").write_text(json.dumps(state), encoding="utf-8")

    def _read(self) -> dict[str, float]:
        path = self._dir / "pacer.json"
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(loaded, dict):
            return {}
        return {str(k): float(v) for k, v in loaded.items() if isinstance(v, int | float)}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]

    @contextlib.contextmanager
    def _lock(self) -> Generator[None]:
        # フォルダの作成は原子的なので、並んだプロセスのうち一つだけが記録を書き換えられる
        lock = self._dir / "pacer.lock"
        deadline = time.monotonic() + 120
        while True:
            try:
                lock.mkdir()
                break
            except FileExistsError:
                if time.monotonic() > deadline:
                    # 持ち主が落ちて残った錠とみなして外す
                    with contextlib.suppress(OSError):
                        lock.rmdir()
                time.sleep(0.05)
        try:
            yield
        finally:
            with contextlib.suppress(OSError):
                lock.rmdir()


def fetch_page(url: str, *, pacer: Pacer, timeout: float = 60.0) -> Page:
    """ページを取り、題と本文の文字を返す。

    Parameters
    ----------
    url : str
        ``http://`` か ``https://`` の URL。保存版なら ``id_`` の形に直して取る。
    pacer : Pacer
        同じホストへの間を空ける仕組み。

    Raises
    ------
    FetchError
        URL が http(s) でない、HTTP の誤り、通信の失敗、HTML でないとき。
    """
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        raise FetchError(f"http か https の URL だけを取れる: {url}")
    target = archive_raw_url(url)
    host = urllib.parse.urlsplit(target).hostname or ""
    for attempt in range(2):
        pacer.wait(host, extra=0.0 if attempt == 0 else _INTERVALS.get(host, _DEFAULT_INTERVAL))
        try:
            data, content_type = _get(target, timeout)
        except urllib.error.HTTPError as error:
            if error.code in _RETRY_STATUSES and attempt == 0:
                continue
            raise FetchError(f"HTTP {error.code} で取れなかった: {target}") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise FetchError(f"取れなかった（{error}）: {target}") from error
        if "html" not in content_type.lower():
            raise FetchError(f"HTML でないページ（{content_type or '種類が不明'}）: {target}")
        title, text = html_to_text(decode_body(data, content_type))
        return Page(url=url, fetched_url=target, title=title, text=text)
    raise FetchError(f"取り直しても取れなかった: {target}")


# --- 下請け -----------------------------------------------------------------------


def _get(url: str, timeout: float) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - 上で http(s) に限った
        content_type = response.headers.get("Content-Type", "")
        return response.read(), content_type


def _charset_of(content_type: str) -> str | None:
    match = re.search(r"charset=([\w.:-]+)", content_type, re.IGNORECASE)
    return match.group(1) if match else None


def _meta_charset(data: bytes) -> str | None:
    head = data[:4096].decode("ascii", errors="ignore")
    match = re.search(r"""<meta[^>]+charset=["']?([\w.:-]+)""", head, re.IGNORECASE)
    return match.group(1) if match else None


_SKIP = frozenset({"script", "style", "noscript", "template", "svg", "nav", "head"})
_BLOCK = frozenset(
    {"p", "div", "section", "article", "header", "footer", "main", "aside", "ul", "ol", "table",
     "tr", "blockquote", "pre", "figure", "figcaption", "dl", "dt", "dd", "form", "hr"}
)  # fmt: skip
_HEADINGS = {f"h{n}": n for n in range(1, 7)}


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self._lines: list[str] = []
        self._current: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
            return
        if tag in _SKIP:
            self._skip_depth += 1
            return
        if tag == "br":
            self._flush()
        elif tag in _BLOCK or tag in _HEADINGS or tag == "li":
            self._flush()
            if tag in _HEADINGS:
                self._current.append("#" * _HEADINGS[tag] + " ")
            elif tag == "li":
                self._current.append("- ")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag in _SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK or tag in _HEADINGS or tag == "li":
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
            return
        if self._skip_depth:
            return
        self._current.append(data)

    def _flush(self) -> None:
        line = re.sub(r"\s+", " ", "".join(self._current)).strip()
        self._current = []
        if line and line not in ("-", "- ") and not re.fullmatch(r"#+", line):
            self._lines.append(line)

    def close(self) -> None:
        super().close()
        self._flush()
        self.title = re.sub(r"\s+", " ", self.title).strip()

    def text(self) -> str:
        return "\n".join(self._lines)
