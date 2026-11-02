import http.server
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from wikiskill import cli
from wikiskill.fetch import FetchError, Pacer, download_pdf

_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


class _Handler(http.server.BaseHTTPRequestHandler):
    """PDF を返す試しのサーバー。``/web/`` で始まる道は保存版のサイトの代わり。"""

    paths: list[str] = []

    def do_GET(self) -> None:  # noqa: N802 - http.server の決まった名前
        self.paths.append(self.path)
        if self.path in ("/papers/main.pdf", "/download?id=3", "/"):
            self._send(_PDF, "application/pdf")
            return
        if self.path.startswith("/web/") and self.path.endswith("/gone.pdf"):
            self._send(_PDF, "application/pdf")
            return
        if self.path == "/page.pdf":
            self._send("<title>案内</title><p>PDF ではない。</p>".encode(), "text/html")
            return
        if self.path == "/other.pdf":
            self._send(b"%PDF-1.7\n%%EOF\n", "application/octet-stream")
            return
        self.send_response(404)
        self.end_headers()

    def _send(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - 親の引数名
        pass


@pytest.fixture
def server() -> Iterator[str]:
    _Handler.paths = []
    httpd = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


@pytest.fixture
def pacer(tmp_path: Path) -> Pacer:
    return Pacer(tmp_path / "state", clock=lambda: 0.0, sleep=lambda _s: None)


def test_PDF_を置き場の下に_URL_の名前で保存する(server: str, pacer: Pacer, tmp_path: Path) -> None:
    out = tmp_path / "資料"

    saved = download_pdf(f"{server}/papers/main.pdf", out, pacer=pacer)

    assert saved.path == out / "main.pdf"
    assert saved.path.read_bytes() == _PDF
    assert saved.archive_reason is None


def test_名前の無い_URL_は_document_の名前にする(server: str, pacer: Pacer, tmp_path: Path) -> None:
    saved = download_pdf(f"{server}/", tmp_path, pacer=pacer)

    assert saved.path == tmp_path / "document.pdf"


def test_問い合わせの付いた_URL_でも置き場の外に出ない(
    server: str, pacer: Pacer, tmp_path: Path
) -> None:
    out = tmp_path / "資料"

    saved = download_pdf(f"{server}/download?id=3", out, pacer=pacer)

    assert saved.path.parent == out
    assert saved.path.suffix == ".pdf"


@pytest.mark.parametrize(
    ("path", "name"),
    [
        # 符号化した ../ や \ を混ぜても、置き場の外を指す名前にならない
        ("/a/..%2F..%2Fevil.pdf", "evil.pdf"),
        ("/a/..%5C..%5Cevil.pdf", "evil.pdf"),
        # Windows の予約名（デバイス名）は拡張子があってもデバイスに当たるので、名前を変える
        ("/CON.pdf", "CON_.pdf"),
        ("/files/lpt1.PDF", "lpt1_.pdf"),
        ("/..", "document.pdf"),
    ],
)
def test_ファイル名は置き場の直下を指す安全な名前にする(path: str, name: str) -> None:
    from wikiskill.fetch import _pdf_name  # pyright: ignore[reportPrivateUsage]

    assert _pdf_name(f"https://example.com{path}") == name


def test_同じ名前の別の中身は上書きせず番号を付ける(
    server: str, pacer: Pacer, tmp_path: Path
) -> None:
    (tmp_path / "other.pdf").write_bytes(b"%PDF-1.0\n")

    saved = download_pdf(f"{server}/other.pdf", tmp_path, pacer=pacer)

    assert saved.path == tmp_path / "other-2.pdf"
    assert (tmp_path / "other.pdf").read_bytes() == b"%PDF-1.0\n"


def test_同じ中身なら取り直しても増やさない(server: str, pacer: Pacer, tmp_path: Path) -> None:
    first = download_pdf(f"{server}/papers/main.pdf", tmp_path, pacer=pacer)
    second = download_pdf(f"{server}/papers/main.pdf", tmp_path, pacer=pacer)

    assert first.path == second.path
    assert sorted(p.name for p in tmp_path.glob("*.pdf")) == ["main.pdf"]


def test_PDF_でなければ例外で何も書かない(server: str, pacer: Pacer, tmp_path: Path) -> None:
    out = tmp_path / "資料"

    with pytest.raises(FetchError, match="PDF でない"):
        download_pdf(f"{server}/page.pdf", out, pacer=pacer)

    assert not out.exists()


def test_大きすぎる_PDF_は書かない(server: str, pacer: Pacer, tmp_path: Path) -> None:
    with pytest.raises(FetchError, match="大きすぎる"):
        download_pdf(f"{server}/papers/main.pdf", tmp_path, pacer=pacer, max_bytes=8)

    assert list(tmp_path.glob("*.pdf")) == []


def test_元が_404_なら保存版の_PDF_を取る(server: str, pacer: Pacer, tmp_path: Path) -> None:
    saved = download_pdf(
        f"{server}/gone.pdf", tmp_path, pacer=pacer, archive_base=server, archive_year=2019
    )

    assert saved.path == tmp_path / "gone.pdf"
    assert saved.fetched_url == f"{server}/web/2019id_/{server}/gone.pdf"
    assert saved.archive_reason == "HTTP 404"


def test_http_でない_URL_は例外(pacer: Pacer, tmp_path: Path) -> None:
    with pytest.raises(FetchError, match="http"):
        download_pdf("file:///etc/passwd", tmp_path, pacer=pacer)


# --- コマンド ---------------------------------------------------------------------


def test_pdf_は保存先と読み方を出す(
    server: str, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WIKISKILL_FETCH_STATE", str(tmp_path / "state"))
    out = tmp_path / "資料"

    code = cli.main(["pdf", f"{server}/papers/main.pdf", "--out-dir", str(out)])

    stdout = capsys.readouterr().out
    assert code == 0
    assert f"保存した: {out / 'main.pdf'}" in stdout
    assert "Read" in stdout


def test_pdf_は置き場を省けない(capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main(["pdf", "https://example.com/a.pdf"])

    assert code == 2
    assert "--out-dir" in capsys.readouterr().err


def test_pdf_で取れなければ終了コード_1(
    server: str, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WIKISKILL_FETCH_STATE", str(tmp_path / "state"))

    code = cli.main(["pdf", f"{server}/page.pdf", "--out-dir", str(tmp_path)])

    assert code == 1
    assert "PDF でない" in capsys.readouterr().err
