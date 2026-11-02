"""本家の記事から、節の並びと出典の一覧を取り出す。

調べる工程の最初に、本家の記事を読んで節の並びと元の資料の手がかりを拾う。
WebFetch で生のウィキテキストを読むと、小さなモデルが要約して返すので、長い URL
（とくに保存版の URL）が途中で切れる（2026-11-02 の試運転で起きた）。そこで、生の
ウィキテキストを 1 回だけ取り、出典を機械で取り出して、URL を切らずに出す。

本家の本文は取り出さない。写さないためで、使うのは節の並びと出典の手がかりだけ。
"""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from wikiskill.fetch import USER_AGENT, Pacer

__all__ = [
    "Citation",
    "WikipediaArticle",
    "WikipediaError",
    "fetch_raw",
    "parse_article",
    "raw_url",
]

WIKIPEDIA_HOST = "ja.wikipedia.org"
LEAD = "（導入部）"

_HEADING = re.compile(r"^(={2,6})\s*(.+?)\s*\1\s*$", re.MULTILINE)
_REF = re.compile(r"<ref(?:\s[^>]*?)?(?<!/)>(.*?)</ref\s*>", re.DOTALL | re.IGNORECASE)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_BRACKET_LINK = re.compile(r"\[(https?://[^\s\]]+)\s+([^\]]+)\]")
_BARE_URL = re.compile(r"https?://[^\s\]|}<]+")
_REDIRECT = re.compile(r"^\s*#(?:転送|REDIRECT)\s*\[\[([^\]|#]+)", re.IGNORECASE)
_WIKILINK = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]")
_SOURCE_KEYS = ("newspaper", "website", "work", "journal", "magazine", "publisher")


class WikipediaError(Exception):
    """本家の記事を取れない・読めないときの例外。

    Parameters
    ----------
    message : str
        理由の文。
    redirect_to : str | None
        転送のページなら、転送先の記事名。
    """

    def __init__(self, message: str, *, redirect_to: str | None = None) -> None:
        super().__init__(message)
        self.redirect_to = redirect_to


@dataclass(frozen=True, slots=True)
class Citation:
    """本家の記事の出典一つ。値は本家の書き方のまま（日付の形をそろえない）。"""

    section: str
    title: str
    source: str | None = None
    date: str | None = None
    url: str | None = None
    archive_url: str | None = None


@dataclass(frozen=True, slots=True)
class WikipediaArticle:
    """本家の記事から取り出したもの。

    ``sections`` は（段の深さ 2〜6, 見出し）の並び。
    ``related`` は「関連項目」の節の内部リンクの記事名。
    """

    title: str
    sections: tuple[tuple[int, str], ...]
    citations: tuple[Citation, ...]
    related: tuple[str, ...] = ()


def raw_url(title: str) -> str:
    """記事の生のウィキテキストの URL。"""
    name = urllib.parse.quote(title.strip().replace(" ", "_"), safe="")
    return f"https://{WIKIPEDIA_HOST}/w/index.php?title={name}&action=raw"


def fetch_raw(title: str, *, pacer: Pacer, timeout: float = 60.0) -> str:
    """記事の生のウィキテキストを 1 回取る。

    Raises
    ------
    WikipediaError
        記事が無い（404）、取れないとき。
    """
    pacer.wait(WIKIPEDIA_HOST)
    request = urllib.request.Request(raw_url(title), headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - 固定のホスト
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise WikipediaError(f"本家に記事「{title}」が無い") from error
        raise WikipediaError(f"本家の記事「{title}」を取れなかった（HTTP {error.code}）") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise WikipediaError(f"本家の記事「{title}」を取れなかった（{error}）") from error


def parse_article(title: str, raw: str) -> WikipediaArticle:
    """生のウィキテキストから、節の並びと出典の一覧を取り出す。

    出典は、``<ref>`` の中身（名前つきの再掲は一つと数える）と、``<ref>`` の外の Cite 系の
    テンプレート（参考文献の節など）。本文での現れる順に並べ、出典ごとに、そこを含む節の見出しを覚える。

    Raises
    ------
    WikipediaError
        転送のページのとき（``redirect_to`` に転送先）。
    """
    text = _COMMENT.sub("", raw)
    redirect = _REDIRECT.match(text)
    if redirect is not None:
        target = redirect.group(1).strip()
        raise WikipediaError(f"「{title}」は「{target}」への転送", redirect_to=target)

    headings = [(m.start(), len(m.group(1)), m.group(2).strip()) for m in _HEADING.finditer(text)]

    def section_at(pos: int) -> str:
        name = LEAD
        for start, _level, heading in headings:
            if start > pos:
                break
            name = heading
        return name

    found: list[tuple[int, Citation]] = []
    covered: list[tuple[int, int]] = []
    for match in _REF.finditer(text):
        covered.append((match.start(), match.end()))
        citation = _citation_from(match.group(1), section_at(match.start()))
        if citation is not None:
            found.append((match.start(), citation))
    for start, _end, body in _templates(text):
        if any(a <= start < b for a, b in covered):
            continue
        if not body.lstrip().lower().startswith("cite"):
            continue
        citation = _citation_from_template(body, section_at(start))
        if citation is not None:
            found.append((start, citation))
    found.sort(key=lambda item: item[0])
    return WikipediaArticle(
        title=title,
        sections=tuple((level, heading) for _start, level, heading in headings),
        citations=tuple(c for _pos, c in found),
        related=_related(text, headings),
    )


# --- 下請け -----------------------------------------------------------------------


def _related(text: str, headings: list[tuple[int, int, str]]) -> tuple[str, ...]:
    """「関連項目」の節（次の同じ深さ以上の見出しまで）の内部リンクの記事名。"""
    for index, (start, level, heading) in enumerate(headings):
        if heading != "関連項目":
            continue
        end = next((s for s, lv, _h in headings[index + 1 :] if lv <= level), len(text))
        names = re.findall(r"\[\[([^\]|#]+)", text[start:end])
        return tuple(dict.fromkeys(name.strip() for name in names if ":" not in name))
    return ()


def _citation_from(content: str, section: str) -> Citation | None:
    for _start, _end, body in _templates(content):
        if body.lstrip().lower().startswith("cite"):
            return _citation_from_template(body, section)
    link = _BRACKET_LINK.search(content)
    if link is not None:
        return Citation(section=section, title=link.group(2).strip(), url=link.group(1))
    bare = _BARE_URL.search(content)
    if bare is not None:
        return Citation(section=section, title=bare.group(0), url=bare.group(0))
    return None


def _citation_from_template(body: str, section: str) -> Citation | None:
    params = _params(body)
    title = params.get("title") or params.get("題名")
    url = params.get("url")
    if not title and not url:
        return None
    return Citation(
        section=section,
        title=title or url or "",
        source=next((params[k] for k in _SOURCE_KEYS if params.get(k)), None),
        date=params.get("date") or params.get("year"),
        url=url or None,
        archive_url=params.get("archive-url") or params.get("archiveurl") or None,
    )


def _params(body: str) -> dict[str, str]:
    """テンプレートの中身（``{{`` と ``}}`` を除いたもの）を、名前つきの引数に分ける。"""
    params: dict[str, str] = {}
    for part in _split_top(body)[1:]:
        name, sep, value = part.partition("=")
        if sep:
            params[name.strip().lower()] = _WIKILINK.sub(r"\1", value).strip()
    return params


def _split_top(body: str) -> list[str]:
    """``|`` で分ける。``{{…}}`` と ``[[…]]`` の中の ``|`` では分けない。"""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    i = 0
    while i < len(body):
        pair = body[i : i + 2]
        if pair in ("{{", "[["):
            depth += 1
            current.append(pair)
            i += 2
            continue
        if pair in ("}}", "]]"):
            depth = max(0, depth - 1)
            current.append(pair)
            i += 2
            continue
        if body[i] == "|" and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(body[i])
        i += 1
    parts.append("".join(current))
    return parts


def _templates(text: str) -> list[tuple[int, int, str]]:
    """一番外側の ``{{…}}`` を、（始まり, 終わり, 中身）で並べる。"""
    found: list[tuple[int, int, str]] = []
    depth = 0
    start = 0
    i = 0
    while i < len(text) - 1:
        pair = text[i : i + 2]
        if pair == "{{":
            if depth == 0:
                start = i
            depth += 1
            i += 2
            continue
        if pair == "}}" and depth > 0:
            depth -= 1
            i += 2
            if depth == 0:
                found.append((start, i, text[start + 2 : i - 2]))
            continue
        i += 1
    return found
