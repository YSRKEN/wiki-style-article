"""Web のページを取り、本文を文字にして返す。

調べものの担当が使う取得の道具。Claude Code の WebFetch は web.archive.org を取れず、
Jina の Reader も鍵なしでは web.archive.org を止めている（2026-11-02 に確かめた）。
本家はしばしば保存版の URL を出典に使うので、標準ライブラリだけで取れるようにする。

- web.archive.org の保存版は、Wayback の飾りの無い形（``/web/<時刻>id_/<URL>``）に直して取る
- 同じホストへは間を空ける（web.archive.org は 15 秒。続けて送ると 429 で断られた）。担当が並んで
  別々のプロセスで取っても順番を守れるよう、間の記録をファイルに置く
- 429・503 なら、間を空けて一度だけ取り直す
- 元のページが 403・404・410・451 か、相手に届かなければ、web.archive.org の保存版を取る
- 証明書の検証で失敗したら（Windows の Python が OS の根の証明書を取ってこないため）、
  検証を外さずに、OS の仕組みで検証する curl で取り直す
- :func:`fetch_page` は HTML だけを扱い、PDF などは :class:`FetchError` にする。PDF は
  :func:`download_pdf` が、決めた置き場の下にだけ保存する（担当が ``Read`` で読む）。任意の
  保存先へ書ける ``curl -o`` を担当に許さずに済むよう、置き場と中身を確かめてから書く
"""

from __future__ import annotations

import contextlib
import json
import re
import shutil
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Generator
from dataclasses import dataclass, replace
from html.parser import HTMLParser
from pathlib import Path
from typing import TypeVar

__all__ = [
    "MAX_PDF_BYTES",
    "FetchError",
    "Page",
    "Pacer",
    "SavedPdf",
    "archive_raw_url",
    "decode_body",
    "download_pdf",
    "fetch_page",
    "html_to_text",
]

USER_AGENT = "wiki-style-article (+https://github.com/YSRKEN/wiki-style-article)"
ARCHIVE_HOST = "web.archive.org"
_INTERVALS = {ARCHIVE_HOST: 15.0}
_DEFAULT_INTERVAL = 1.0
_RETRY_STATUSES = frozenset({429, 503})
_ARCHIVE_STATUSES = frozenset({403, 404, 410, 451})
_ARCHIVE_PATH = re.compile(r"^/web/(\d{4,14})([a-z]{2}_)?/(.+)$")
MAX_PDF_BYTES = 100 * 1024 * 1024
"""保存する PDF の大きさの上限（100MB）。置き場を埋め尽くさないため。"""
_PDF_MAGIC = b"%PDF-"
_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL", *(f"{kind}{n}" for kind in ("COM", "LPT") for n in range(1, 10))}
)
_T = TypeVar("_T")


class FetchError(Exception):
    """ページを取れなかったときの例外。文面に理由（HTTP の番号など）を含む。

    Parameters
    ----------
    message : str
        理由の文。
    status : int | None
        HTTP の番号。HTTP の誤りでなければ None。
    unreachable : bool
        名前解決や接続など、相手に届かなかったとき True。
    """

    def __init__(
        self, message: str, *, status: int | None = None, unreachable: bool = False
    ) -> None:
        super().__init__(message)
        self.status = status
        self.unreachable = unreachable


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
    archive_reason : str | None
        元のページが取れず保存版を取ったときの、元の理由（``HTTP 404`` など）。元が取れたら None。
    """

    url: str
    fetched_url: str
    title: str
    text: str
    archive_reason: str | None = None


@dataclass(frozen=True, slots=True)
class SavedPdf:
    """保存した PDF。

    Parameters
    ----------
    url : str
        頼まれた URL。
    fetched_url : str
        実際に取りに行った URL（保存版なら ``id_`` の形）。
    path : Path
        保存したファイル。同じ中身が既にあれば、そのファイル。
    size : int
        バイト数。
    archive_reason : str | None
        元が取れず保存版を取ったときの、元の理由。元が取れたら None。
    """

    url: str
    fetched_url: str
    path: Path
    size: int
    archive_reason: str | None = None


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


def fetch_page(
    url: str,
    *,
    pacer: Pacer,
    timeout: float = 60.0,
    archive_year: int | None = None,
    archive_base: str = f"https://{ARCHIVE_HOST}",
) -> Page:
    """ページを取り、題と本文の文字を返す。元のページが無ければ保存版を取る。

    元の URL が 403・404・410・451 か、名前解決などの通信の失敗なら、web.archive.org の保存版
    （``/web/<年>id_/<元の URL>``。いちばん近い時期の保存版へ転送される）を取る。500 のような
    一時的な誤りでは試さない。保存版の URL を渡されたときは、その保存版だけを取る。

    Parameters
    ----------
    url : str
        ``http://`` か ``https://`` の URL。保存版なら ``id_`` の形に直して取る。
    pacer : Pacer
        同じホストへの間を空ける仕組み。
    archive_year : int | None
        保存版を探す年。省くと今年（いちばん新しい保存版に近い）。
    archive_base : str
        保存版のサイトの根。試験で差し替える。

    Raises
    ------
    FetchError
        URL が http(s) でない、HTTP の誤り、通信の失敗、HTML でないとき。保存版も取れなければ、
        元と保存版の両方の理由を文面に含む。
    """
    page, _fetched, reason = _with_archive(
        url,
        lambda target: _fetch_once(url, target, pacer=pacer, timeout=timeout),
        archive_year=archive_year,
        archive_base=archive_base,
    )
    return page if reason is None else replace(page, archive_reason=reason)


def download_pdf(
    url: str,
    out_dir: Path,
    *,
    pacer: Pacer,
    timeout: float = 120.0,
    archive_year: int | None = None,
    archive_base: str = f"https://{ARCHIVE_HOST}",
    max_bytes: int = MAX_PDF_BYTES,
) -> SavedPdf:
    """PDF を取り、``out_dir`` の直下に保存する。元のページが無ければ保存版を取る。

    ファイル名は URL の末尾から作り、ファイル名に使えない字は ``_`` にする。同じ名前の別の中身が
    あれば上書きせず ``-2`` のような番号を付け、同じ中身があればそれを返す。保存版へ回す条件は
    :func:`fetch_page` と同じ。

    Parameters
    ----------
    url : str
        ``http://`` か ``https://`` の URL。
    out_dir : Path
        保存先のフォルダ。無ければ作る。この外には書かない。
    pacer : Pacer
        同じホストへの間を空ける仕組み。
    archive_year : int | None
        保存版を探す年。省くと今年。
    archive_base : str
        保存版のサイトの根。試験で差し替える。
    max_bytes : int
        保存する大きさの上限。

    Raises
    ------
    FetchError
        取れない、中身が PDF でない（``%PDF-`` で始まらない）、大きすぎるとき。
        このときは何も書かない。
    """

    def get(target: str) -> tuple[bytes, str]:
        data, _content_type, final_url = _fetch_bytes(target, pacer=pacer, timeout=timeout)
        return data, final_url

    data, fetched, reason = _with_archive(
        url, get, archive_year=archive_year, archive_base=archive_base
    )
    if _PDF_MAGIC not in data[:1024]:
        raise FetchError(f"PDF でない中身（先頭が %PDF- でない）: {fetched}")
    if len(data) > max_bytes:
        raise FetchError(
            f"PDF が大きすぎる（{len(data)} バイト。上限 {max_bytes} バイト）: {fetched}"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    path = _store(out_dir, _pdf_name(url), data)
    return SavedPdf(url, fetched, path, len(data), archive_reason=reason)


def _with_archive(
    url: str,
    get: Callable[[str], tuple[_T, str]],
    *,
    archive_year: int | None,
    archive_base: str,
) -> tuple[_T, str, str | None]:
    """``get`` で取り、元のページが無ければ保存版を ``get`` で取る。

    ``get`` は取る URL を受け取り、（中身, 転送された先の URL）を返す。戻り値は
    （中身, 取りに行った URL, 保存版を取った理由。元が取れたら None）。
    """
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        raise FetchError(f"http か https の URL だけを取れる: {url}")
    target = archive_raw_url(url)
    is_archive = target != url or urllib.parse.urlsplit(url).hostname == ARCHIVE_HOST
    try:
        result, final_url = get(target)
    except FetchError as error:
        if is_archive or (error.status not in _ARCHIVE_STATUSES and not error.unreachable):
            raise
        reason = f"HTTP {error.status}" if error.status is not None else "通信の失敗"
        failure: FetchError | None = error
    else:
        if is_archive or not _moved_to_top(url, final_url):
            return result, target, None
        reason = "トップページへの転送"
        failure = None
    year = archive_year or time.localtime().tm_year
    snapshot = f"{archive_base.rstrip('/')}/web/{year}id_/{url}"
    try:
        archived, _ = get(snapshot)
    except FetchError as error:
        first = str(failure) if failure is not None else f"{reason}: {url}"
        raise FetchError(f"{first}。保存版も取れなかった（{error}）") from error
    return archived, snapshot, reason


def _moved_to_top(url: str, final_url: str) -> bool:
    """深い階層の URL が、サイトの根へ転送されたか（消えたページをトップへ送るサイト）。"""
    asked = urllib.parse.urlsplit(url)
    landed = urllib.parse.urlsplit(final_url)
    # 根に ?mode=… のような問い合わせが付いて返るサイトもあるので、問い合わせは見ない
    return asked.path.strip("/") != "" and landed.path.strip("/") == ""


def _fetch_once(url: str, target: str, *, pacer: Pacer, timeout: float) -> tuple[Page, str]:
    """``target`` を取り、HTML のページと、転送された先の URL を返す。"""
    data, content_type, final_url = _fetch_bytes(target, pacer=pacer, timeout=timeout)
    if "html" not in content_type.lower():
        raise FetchError(f"HTML でないページ（{content_type or '種類が不明'}）: {target}")
    title, text = html_to_text(decode_body(data, content_type))
    return Page(url=url, fetched_url=target, title=title, text=text), final_url


def _fetch_bytes(target: str, *, pacer: Pacer, timeout: float) -> tuple[bytes, str, str]:
    """``target`` を 1 回（429・503 なら 2 回）取る。（中身, 種類, 転送された先の URL）を返す。"""
    host = urllib.parse.urlsplit(target).hostname or ""
    for attempt in range(2):
        pacer.wait(host, extra=0.0 if attempt == 0 else _INTERVALS.get(host, _DEFAULT_INTERVAL))
        try:
            return _get(target, timeout)
        except urllib.error.HTTPError as error:
            if error.code in _RETRY_STATUSES and attempt == 0:
                continue
            raise FetchError(
                f"HTTP {error.code} で取れなかった: {target}", status=error.code
            ) from error
        except urllib.error.URLError as error:
            if not isinstance(error.reason, ssl.SSLCertVerificationError):
                raise FetchError(f"取れなかった（{error}）: {target}", unreachable=True) from error
            # Windows の Python は、OS が必要なときに取ってくる根の証明書を読まないので、
            # 一部のサイトで検証に失敗する。検証は外さず、OS の仕組みで検証する curl で取り直す。
            if shutil.which("curl") is None:
                raise FetchError(
                    f"証明書を検証できず、取り直す curl も無い（{error.reason}）: {target}"
                ) from error
            return _get_with_curl(target, timeout)
        except (TimeoutError, OSError) as error:
            raise FetchError(f"取れなかった（{error}）: {target}") from error
    raise FetchError(f"取り直しても取れなかった: {target}")


def _pdf_name(url: str) -> str:
    """URL の末尾から PDF のファイル名を作る。使えない字は ``_`` にし、無ければ ``document``。"""
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path)
    stem = path.rstrip("/").rsplit("/", 1)[-1]
    stem = re.sub(r"\.pdf$", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"[^\w.-]+", "_", stem).strip("._-")[:80]
    if stem.split(".", 1)[0].upper() in _RESERVED_NAMES:
        # Windows では CON.pdf のような名前も装置を指し、ファイルにならない。
        stem += "_"
    return f"{stem or 'document'}.pdf"


def _store(out_dir: Path, name: str, data: bytes) -> Path:
    """``out_dir`` の直下に書く。同じ名前の別の中身には番号を付け、同じ中身ならそれを返す。"""
    stem = name.removesuffix(".pdf")
    number = 1
    while True:
        path = out_dir / (name if number == 1 else f"{stem}-{number}.pdf")
        try:
            with path.open("xb") as file:
                file.write(data)
        except FileExistsError:
            if path.read_bytes() == data:
                return path
            number += 1
            continue
        return path


# --- 下請け -----------------------------------------------------------------------


def _get(url: str, timeout: float) -> tuple[bytes, str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - 上で http(s) に限った
        content_type = response.headers.get("Content-Type", "")
        return response.read(), content_type, response.geturl()


def _get_with_curl(url: str, timeout: float) -> tuple[bytes, str, str]:
    """コマンドの curl で取る。本文は一時ファイルに書かせ、番号と種類だけを標準出力で受け取る。"""
    with tempfile.TemporaryDirectory() as folder:
        body = Path(folder) / "body"
        done = subprocess.run(  # noqa: S603 - 引数は固定の並びで、URL は http(s) に限った
            ["curl", "-sS", "-L", "--max-time", str(int(timeout)), "-A", USER_AGENT,
             "-o", str(body), "-w", "%{http_code} %{url_effective} %{content_type}", url],
            capture_output=True,
            text=True,
            check=False,
        )  # fmt: skip
        if done.returncode != 0:
            raise FetchError(
                f"curl でも取れなかった（{done.stderr.strip()}）: {url}", unreachable=True
            )
        code, final_url, content_type = ([*done.stdout.strip().split(" ", 2), "", ""])[:3]
        if not code.startswith("2"):
            raise FetchError(
                f"HTTP {code} で取れなかった（curl）: {url}",
                status=int(code) if code.isdigit() else None,
            )
        return body.read_bytes(), content_type, final_url or url


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
