import shutil
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from wikiskill import cli
from wikiskill.cli import format_mark_date, format_updated, main
from wikiskill.html_check import check_html
from wikiskill.html_inline import HtmlError
from wikiskill.html_writer import write_html, write_html_both
from wikiskill.reader import read_article_file
from wikiskill.types import load_default_registry
from wikiskill.variants import normal_view, rumor_view
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
    shutil.copyfile(FIXTURES / "sample_figure.png", tmp_path / "sample_figure.png")
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


def test_build_は書き出しの例外を返して書き出さない(
    sample: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_args: object, **_kwargs: object) -> str:
        raise HtmlError("壊れた")

    monkeypatch.setattr(cli, "write_html", broken)

    code = main(["build", str(sample), "--updated", UPDATED])

    out = capsys.readouterr().out
    assert code == 1
    assert "[エラー] WRITE: 壊れた" in out
    assert not sample.with_suffix(".html").exists()
    assert not sample.with_suffix(".wikitext").exists()


def test_build_は書き出した_HTML_が検査を通らなければ書き出さない(
    sample: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def leftover(*_args: object, **_kwargs: object) -> str:
        return "<p>{{LEAD}}</p>\n"

    monkeypatch.setattr(cli, "write_html", leftover)

    code = main(["build", str(sample), "--updated", UPDATED])

    out = capsys.readouterr().out
    assert code == 1
    assert "[エラー] HTML-PLACEHOLDER:" in out
    assert not sample.with_suffix(".html").exists()
    assert not sample.with_suffix(".wikitext").exists()


def test_help_は終了コード_0(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--help"]) == 0
    assert "build" in capsys.readouterr().out


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


_RUMOR = """+++
title = "試験"
type = "concept"

[refs.a]
kind = "web"
title = "確かな出典"
url = "https://example.com/a"
access_date = "2026-11-01"

[refs.b]
kind = "web"
title = "噂の出典"
url = "https://example.com/b"
access_date = "2026-11-01"
weak = true

[notes.x]
text = "噂の注釈[^b][!信頼性要検証]。"
+++
'''試験'''は架空の概念である[^a]。[!噂|裏の意味があるという[^b][!信頼性要検証][^n:x]。]

## 概要

試験の概要[^a]。

## 騒動 [!噂]

炎上したという[^b][!信頼性要検証]。

### 余波

余波があった[!要出典]。
"""


def test_check_は噂のある原稿の両方の版を検査する(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # 噂の中の弱い出典に [!信頼性要検証] が無いのは、噂込みの版でだけエラーになる。
    broken = _RUMOR.replace("[^b][!信頼性要検証][^n:x]", "[^b][^n:x]")

    assert main(["check", str(_write(tmp_path, _RUMOR))]) == 0
    out = capsys.readouterr().out
    assert "REF-UNUSED" not in out
    assert main(["check", str(_write(tmp_path, broken, "壊れた.md"))]) == 1
    assert "[エラー] REF-WEAK-UNMARKED" in capsys.readouterr().out
    # 噂だけの段落を取り除くと、通常の版では節が空になる。
    empty = _RUMOR.replace("試験の概要[^a]。", "[!噂|試験の概要[^a]。]")
    assert main(["check", str(_write(tmp_path, empty, "空.md"))]) == 1
    assert "[エラー] EMPTY-SECTION" in capsys.readouterr().out


# --- type -------------------------------------------------------------------------


def test_type_は類型の一覧を基本型と細かい種類に分けて出す(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(["type"])

    out = capsys.readouterr().out
    lines = out.splitlines()
    assert code == 0
    assert "person-living  人物（存命）" in lines
    # 細かい種類は寄せ先の下に字下げして出す
    assert "  voice-actor  声優" in lines
    assert lines.index("person-living  人物（存命）") < lines.index("  voice-actor  声優")
    assert sum(1 for line in lines if line and not line.startswith(("  ", "#"))) == len(
        [t for t in REGISTRY if t.is_base]
    )


def test_type_に_ID_を渡すと原稿に貼る雛形を出す(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["type", "manga"])

    out = capsys.readouterr().out
    assert code == 0
    assert 'type = "manga"' in out
    assert "[infobox]" in out
    assert '"作者" = ""  # 必須' in out
    assert '"出版社" = ""  # 必須' in out
    assert "references/types/manga.md" in out


def test_type_の雛形は_TOML_として読めて項目は定義の順(capsys: pytest.CaptureFixture[str]) -> None:
    import tomllib

    main(["type", "manga"])

    data = tomllib.loads(capsys.readouterr().out)
    assert data["type"] == "manga"
    assert list(data["infobox"]) == [f.label for f in REGISTRY["manga"].fields]


@pytest.mark.parametrize("type_id", [t.id for t in REGISTRY])
def test_type_の雛形はどの類型でも定義の項目と寄せ先に合う(
    type_id: str, capsys: pytest.CaptureFixture[str]
) -> None:
    import tomllib

    article_type = REGISTRY[type_id]

    assert main(["type", type_id]) == 0

    out = capsys.readouterr().out
    data = tomllib.loads(out)
    assert data["type"] == type_id
    if article_type.has_infobox:
        assert list(data["infobox"]) == [f.label for f in article_type.fields]
        assert set(data["infobox"].values()) == {""}
    else:
        assert "infobox" not in data
    guides = [line for line in out.splitlines() if line.startswith("# 節の並びと書き方: ")]
    expected = article_type.parents or (type_id,)
    assert guides == [f"# 節の並びと書き方: references/types/{g}.md" for g in expected]


def test_type_の細かい種類は寄せ先の参照ファイルを案内する(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(["type", "voice-actor"])

    out = capsys.readouterr().out
    assert "references/types/person-living.md" in out
    assert "references/types/person-deceased.md" in out


def test_type_の_Infobox_の無い類型は表を出さない(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["type", "concept"])

    out = capsys.readouterr().out
    assert code == 0
    assert 'type = "concept"' in out
    assert "[infobox]" not in out
    assert "Infobox を持たない" in out


def test_type_の知らない_ID_は終了コード_2(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["type", "no-such-type"])

    assert code == 2
    assert "類型が見つからない" in capsys.readouterr().err


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


# --- 印の日付 ---------------------------------------------------------------------

_MARKED = "+++\ntitle = \"試験\"\ntype = \"concept\"\n+++\n'''試験'''は噂がある[!要出典]。\n"


def test_印の日付は年と月() -> None:
    assert format_mark_date(datetime(2026, 1, 4, 3, 5, tzinfo=UTC)) == "2026年1月"
    assert format_mark_date(datetime(2026, 11, 30, 23, 59)) == "2026年11月"


def test_build_は印と枠に今の現地時刻の年月を添える(tmp_path: Path) -> None:
    source = _write(tmp_path, _MARKED)
    before = format_mark_date(datetime.now().astimezone())
    code = main(["build", str(source), "--updated", UPDATED])
    after = format_mark_date(datetime.now().astimezone())

    assert code == 0
    html = source.with_suffix(".html").read_text(encoding="utf-8")
    wikitext = source.with_suffix(".wikitext").read_text(encoding="utf-8")
    assert any(f"（{d}）</div>" in html for d in (before, after))
    assert any(wikitext.startswith(f"{{{{出典の明記|date={d}}}}}\n") for d in (before, after))
    assert any(f"{{{{要出典|date={d}}}}}" in wikitext for d in (before, after))


# --- 噂のある原稿の build -----------------------------------------------------------


def test_build_は噂のある原稿から_HTML_1_本とウィキテキスト_2_本を書き出す(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _write(tmp_path, _RUMOR, "騒動.md")

    code = main(["build", str(source), "--updated", UPDATED])

    article = read_article_file(source)
    article_type = REGISTRY["concept"]
    mark_date = format_mark_date(datetime.now().astimezone())
    html_path = tmp_path / "騒動.html"
    normal_path = tmp_path / "騒動.wikitext"
    rumor_path = tmp_path / "騒動.噂込み.wikitext"
    assert code == 0
    html = html_path.read_text(encoding="utf-8")
    assert html == write_html_both(article, article_type, UPDATED, mark_date=mark_date)
    assert check_html(html) == ()
    assert normal_path.read_text(encoding="utf-8") == write_wikitext(
        normal_view(article), article_type, mark_date=mark_date
    )
    assert rumor_path.read_text(encoding="utf-8") == write_wikitext(
        rumor_view(article), article_type, mark_date=mark_date
    )
    out = capsys.readouterr().out
    assert out.count("書き出した: ") == 3
    assert f"書き出した: {html_path}" in out
    assert f"書き出した: {normal_path}" in out
    assert f"書き出した: {rumor_path}" in out
    assert "炎上したという" not in normal_path.read_text(encoding="utf-8")
    assert "炎上したという" in rumor_path.read_text(encoding="utf-8")


def test_build_は噂のある原稿も素の記法で書ける(tmp_path: Path) -> None:
    source = _write(tmp_path, _RUMOR)

    assert main(["build", str(source), "--updated", UPDATED, "--style", "plain"]) == 0

    article = read_article_file(source)
    rumor = (tmp_path / "原稿.噂込み.wikitext").read_text(encoding="utf-8")
    assert "<references" in rumor
    assert "{{Cite" not in rumor
    assert "炎上したという" in rumor
    assert "噂の出典" not in (tmp_path / "原稿.wikitext").read_text(encoding="utf-8")
    assert article.settings.title == "試験"


def test_build_は噂の無い原稿では噂込みのウィキテキストを書き出さない(sample: Path) -> None:
    assert main(["build", str(sample), "--updated", UPDATED]) == 0

    assert not sample.with_name(f"{sample.stem}.噂込み.wikitext").exists()
