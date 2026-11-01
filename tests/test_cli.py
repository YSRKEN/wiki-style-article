import shutil
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from wikiskill.cli import format_updated, main
from wikiskill.html_writer import write_html
from wikiskill.reader import read_article_file
from wikiskill.types import load_default_registry
from wikiskill.wikitext import write_wikitext

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "sample_article.md"
UPDATED = "2026年11月2日 (月) 12:00 (JST)"
REGISTRY = load_default_registry()

_BROKEN = "+++\ntitle = \"試験\"\ntype = \"concept\"\n+++\n'''試験'''は本文[^nai]。\n"


@pytest.fixture
def sample(tmp_path: Path) -> Path:
    """見本の原稿を一時フォルダへ写したもの（書き出しが見本の隣に出るため）。"""
    path = tmp_path / "星屑ラーメン.md"
    shutil.copyfile(SAMPLE, path)
    return path


def _write(tmp_path: Path, text: str, name: str = "原稿.md") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# --- build ------------------------------------------------------------------------


def test_build_は原稿の隣に_HTML_とウィキテキストを書き出す(
    sample: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["build", str(sample), "--updated", UPDATED])

    article = read_article_file(SAMPLE)
    article_type = REGISTRY[article.settings.type_id]
    html = sample.with_suffix(".html")
    wikitext = sample.with_suffix(".wikitext")
    assert code == 0
    assert html.read_text(encoding="utf-8") == write_html(article, article_type, UPDATED)
    assert wikitext.read_text(encoding="utf-8") == write_wikitext(article, article_type)
    # Windows でも改行は LF のまま書く
    assert b"\r\n" not in html.read_bytes()
    assert b"\r\n" not in wikitext.read_bytes()
    out = capsys.readouterr().out
    assert f"書き出した: {html}" in out
    assert f"書き出した: {wikitext}" in out


def test_build_は警告を一覧して書き出す(sample: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["build", str(sample), "--updated", UPDATED])

    out = capsys.readouterr().out
    assert code == 0
    # 見本の「連載期間」は漫画の定義にない（定義では「発表期間」）
    assert "[警告] INFOBOX-UNKNOWN-FIELD:" in out
    assert "連載期間" in out
    assert "エラー 0 件、警告 1 件" in out


def test_build_の素の記法(sample: Path) -> None:
    main(["build", str(sample), "--updated", UPDATED, "--style", "plain"])

    article = read_article_file(SAMPLE)
    expected = write_wikitext(article, REGISTRY[article.settings.type_id], style="plain")
    assert sample.with_suffix(".wikitext").read_text(encoding="utf-8") == expected


def test_build_は書き出し先のフォルダを指定できる(sample: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "出力"

    code = main(["build", str(sample), "--updated", UPDATED, "--out-dir", str(out_dir)])

    assert code == 0
    assert (out_dir / "星屑ラーメン.html").is_file()
    assert (out_dir / "星屑ラーメン.wikitext").is_file()
    assert not sample.with_suffix(".html").exists()


def test_build_は最終更新を省くと現地時刻を入れる(sample: Path) -> None:
    before = datetime.now().astimezone()
    main(["build", str(sample)])
    after = datetime.now().astimezone()

    html = sample.with_suffix(".html").read_text(encoding="utf-8")
    assert format_updated(before) in html or format_updated(after) in html


def test_build_はエラーがあれば書き出さずに終了コード_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _write(tmp_path, _BROKEN)

    code = main(["build", str(source), "--updated", UPDATED])

    out = capsys.readouterr().out
    assert code == 1
    assert "5 行目 [エラー] REF-UNDEFINED:" in out
    assert "エラー 1 件" in out
    assert "書き出していない" in out
    assert not source.with_suffix(".html").exists()
    assert not source.with_suffix(".wikitext").exists()


def test_build_は読み取れない原稿を行番号つきで返す(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _write(tmp_path, '+++\ntitle = "試験"\n本文\n')

    code = main(["build", str(source), "--updated", UPDATED])

    out = capsys.readouterr().out
    assert code == 1
    assert "1 行目 [エラー] READ:" in out
    assert "+++" in out
    assert not source.with_suffix(".html").exists()


def test_build_は知らない類型をエラーにする(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _write(tmp_path, '+++\ntitle = "試験"\ntype = "no-such-type"\n+++\n本文。\n')

    code = main(["build", str(source), "--updated", UPDATED])

    assert code == 1
    assert "[エラー] TYPE-UNKNOWN:" in capsys.readouterr().out
    assert not source.with_suffix(".html").exists()


def test_build_は原稿が無ければ終了コード_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["build", str(tmp_path / "無い.md")])

    assert code == 2
    assert "原稿が見つからない" in capsys.readouterr().err


def test_引数の誤りは終了コード_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["build"]) == 2
    assert main(["build", "x.md", "--style", "fancy"]) == 2
    assert main([]) == 2
    capsys.readouterr()


# --- check ------------------------------------------------------------------------


def test_check_は検査だけして書き出さない(sample: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["check", str(sample)])

    out = capsys.readouterr().out
    assert code == 0
    assert "[警告] INFOBOX-UNKNOWN-FIELD:" in out
    assert "書き出した" not in out
    assert not sample.with_suffix(".html").exists()
    assert not sample.with_suffix(".wikitext").exists()


def test_check_はエラーがあれば終了コード_1(tmp_path: Path) -> None:
    assert main(["check", str(_write(tmp_path, _BROKEN))]) == 1


# --- 最終更新の日時 ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (
            datetime(2026, 11, 2, 12, 0, tzinfo=timezone(timedelta(hours=9))),
            "2026年11月2日 (月) 12:00 (JST)",
        ),
        (datetime(2026, 1, 4, 3, 5, tzinfo=UTC), "2026年1月4日 (日) 03:05 (UTC)"),
        (
            datetime(2026, 11, 7, 23, 59, tzinfo=timezone(timedelta(hours=5, minutes=30))),
            "2026年11月7日 (土) 23:59 (UTC+05:30)",
        ),
        (
            datetime(2026, 11, 1, 8, 0, tzinfo=timezone(timedelta(hours=-5))),
            "2026年11月1日 (日) 08:00 (UTC-05:00)",
        ),
    ],
)
def test_最終更新の日時は本家のフッタの形(moment: datetime, expected: str) -> None:
    assert format_updated(moment) == expected


def test_時差の無い日時は受け付けない() -> None:
    with pytest.raises(ValueError, match="時差"):
        format_updated(datetime(2026, 11, 2, 12, 0))
