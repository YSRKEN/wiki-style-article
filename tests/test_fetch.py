import http.server
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from wikiskill import cli
from wikiskill.fetch import (
    FetchError,
    Pacer,
    archive_raw_url,
    decode_body,
    fetch_page,
    html_to_text,
)

# --- 保存版の URL -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://web.archive.org/web/20160101000000/https://www.example.com/a",
            "https://web.archive.org/web/20160101000000id_/https://www.example.com/a",
        ),
        # 年だけ・飾りの印つきでも、印を id_ に置き換える
        (
            "https://web.archive.org/web/2016/https://example.com/",
            "https://web.archive.org/web/2016id_/https://example.com/",
        ),
        (
            "http://web.archive.org/web/20160101000000if_/http://example.com/",
            "https://web.archive.org/web/20160101000000id_/http://example.com/",
        ),
        # すでに id_ なら変えない
        (
            "https://web.archive.org/web/2016id_/https://example.com/",
            "https://web.archive.org/web/2016id_/https://example.com/",
        ),
        # 保存版でない URL は変えない
        ("https://example.com/web/2016/x", "https://example.com/web/2016/x"),
        ("https://web.archive.org/", "https://web.archive.org/"),
    ],
)
def test_保存版の_URL_は飾りの無い形に直す(url: str, expected: str) -> None:
    assert archive_raw_url(url) == expected


# --- HTML から本文の文字へ --------------------------------------------------------


def test_題と本文を取り出しスクリプトと見た目の部品は捨てる() -> None:
    html = """<html><head><title> 星屑 &amp; ラーメン </title>
    <style>p{color:red}</style><script>var x = "<p>捨てる</p>";</script></head>
    <body><nav>メニュー</nav><h1>見出し</h1><p>一段落目の
    文。</p><ul><li>項目A</li><li>項目B</li></ul><h2>小見出し</h2><p>二段落目。<br>改行のあと。</p>
    <noscript>捨てる</noscript></body></html>"""

    title, text = html_to_text(html)

    assert title == "星屑 & ラーメン"
    assert "捨てる" not in text
    assert "color" not in text
    lines = text.splitlines()
    assert "# 見出し" in lines
    assert "## 小見出し" in lines
    assert "一段落目の 文。" in lines
    assert "- 項目A" in lines
    assert "改行のあと。" in lines
    assert "\n\n\n" not in text


def test_題が無ければ空文字() -> None:
    assert html_to_text("<p>本文</p>") == ("", "本文")


# --- 文字コード -------------------------------------------------------------------


def test_文字コードは見出しの指定を先に使う() -> None:
    data = "日本語".encode("shift_jis")

    assert decode_body(data, "text/html; charset=Shift_JIS") == "日本語"


def test_見出しに無ければ_meta_の指定を使う() -> None:
    data = '<meta charset="euc-jp"><p>日本語</p>'.encode("euc_jp")

    assert "日本語" in decode_body(data, "text/html")


def test_指定が無ければ_UTF8_として読み壊れた所は置き換える() -> None:
    data = "日本語".encode() + b"\xff"

    assert decode_body(data, None).startswith("日本語")


# --- 間の空け方 -------------------------------------------------------------------


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def test_同じホストへの二度目は間を空けて待つ(tmp_path: Path) -> None:
    clock = _Clock()
    pacer = Pacer(tmp_path, clock=clock.time, sleep=clock.sleep)

    pacer.wait("web.archive.org")
    pacer.wait("web.archive.org")

    assert clock.slept == [pytest.approx(15.0)]


def test_ホストが違えば待たない(tmp_path: Path) -> None:
    clock = _Clock()
    pacer = Pacer(tmp_path, clock=clock.time, sleep=clock.sleep)

    pacer.wait("web.archive.org")
    pacer.wait("example.com")

    assert clock.slept == []


def test_間の記録は別の呼び出しとも分け合う(tmp_path: Path) -> None:
    # 担当が並んで別々のプロセスでコマンドを流しても、記録のファイルで順番を守る
    clock = _Clock()
    Pacer(tmp_path, clock=clock.time, sleep=clock.sleep).wait("web.archive.org")
    clock.now += 5

    Pacer(tmp_path, clock=clock.time, sleep=clock.sleep).wait("web.archive.org")

    assert clock.slept == [pytest.approx(10.0)]


# --- 取りに行く -------------------------------------------------------------------


class _Handler(http.server.BaseHTTPRequestHandler):
    hits: dict[str, int] = {}

    def do_GET(self) -> None:  # noqa: N802 - http.server の決まった名前
        count = self.hits.get(self.path, 0) + 1
        self.hits[self.path] = count
        if self.path == "/busy" and count == 1:
            self.send_response(429)
            self.end_headers()
            return
        if self.path == "/missing":
            self.send_response(404)
            self.end_headers()
            return
        if self.path == "/pdf":
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.end_headers()
            self.wfile.write(b"%PDF-1.4")
            return
        body = "<title>試し</title><p>本文です。</p>".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - 親の引数名
        pass


@pytest.fixture
def server() -> Iterator[str]:
    _Handler.hits = {}
    httpd = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


@pytest.fixture
def pacer(tmp_path: Path) -> Pacer:
    clock = _Clock()
    return Pacer(tmp_path, clock=clock.time, sleep=clock.sleep)


def test_ページを取って題と本文を返す(server: str, pacer: Pacer) -> None:
    page = fetch_page(f"{server}/ok", pacer=pacer)

    assert page.title == "試し"
    assert page.text == "本文です。"
    assert page.fetched_url == f"{server}/ok"


def test_429_なら間を空けて一度だけ取り直す(server: str, pacer: Pacer) -> None:
    page = fetch_page(f"{server}/busy", pacer=pacer)

    assert page.text == "本文です。"
    assert _Handler.hits["/busy"] == 2


def test_取れなければ理由つきの例外(server: str, pacer: Pacer) -> None:
    with pytest.raises(FetchError, match="404"):
        fetch_page(f"{server}/missing", pacer=pacer)


def test_HTML_でないページは例外(server: str, pacer: Pacer) -> None:
    with pytest.raises(FetchError, match="application/pdf"):
        fetch_page(f"{server}/pdf", pacer=pacer)


def test_http_でない_URL_は例外(pacer: Pacer) -> None:
    with pytest.raises(FetchError, match="http"):
        fetch_page("file:///etc/passwd", pacer=pacer)


def test_証明書の検証で失敗したら_curl_で取り直す(
    pacer: Pacer, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ssl
    import urllib.error

    from wikiskill import fetch

    def broken(_url: str, _timeout: float) -> tuple[bytes, str]:
        raise urllib.error.URLError(ssl.SSLCertVerificationError("unable to get local issuer"))

    calls: list[str] = []

    def by_curl(url: str, _timeout: float) -> tuple[bytes, str]:
        calls.append(url)
        return "<title>題</title><p>curl の本文</p>".encode(), "text/html; charset=utf-8"

    monkeypatch.setattr(fetch, "_get", broken)
    monkeypatch.setattr(fetch, "_get_with_curl", by_curl)

    page = fetch_page("https://example.com/", pacer=pacer)

    assert page.text == "curl の本文"
    assert calls == ["https://example.com/"]


def test_curl_が無ければ証明書の失敗をそのまま返す(
    pacer: Pacer, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ssl
    import urllib.error

    from wikiskill import fetch

    def broken(_url: str, _timeout: float) -> tuple[bytes, str]:
        raise urllib.error.URLError(ssl.SSLCertVerificationError("unable to get local issuer"))

    monkeypatch.setattr(fetch, "_get", broken)

    def no_command(_name: str) -> str | None:
        return None

    monkeypatch.setattr(fetch.shutil, "which", no_command)

    with pytest.raises(FetchError, match="証明書"):
        fetch_page("https://example.com/", pacer=pacer)


# --- コマンド ---------------------------------------------------------------------


def test_fetch_は題と本文を出す(
    server: str, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WIKISKILL_FETCH_STATE", str(tmp_path))

    code = cli.main(["fetch", f"{server}/ok"])

    out = capsys.readouterr().out
    assert code == 0
    assert "題: 試し" in out
    assert "本文です。" in out


def test_fetch_は長い本文を区切って続きの取り方を出す(
    server: str, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WIKISKILL_FETCH_STATE", str(tmp_path))

    code = cli.main(["fetch", f"{server}/ok", "--max-chars", "2"])

    out = capsys.readouterr().out
    assert code == 0
    assert "本文" in out
    assert "です。" not in out
    assert "--offset 2" in out


def test_fetch_で取れなければ終了コード_1_と控えの案内(
    server: str, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WIKISKILL_FETCH_STATE", str(tmp_path))

    code = cli.main(["fetch", f"{server}/missing"])

    err = capsys.readouterr().err
    assert code == 1
    assert "404" in err
    assert "r.jina.ai" in err
