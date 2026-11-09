"""ja.wikipedia の TemplateData（テンプレートの引数定義）を読み、項目名を引数名に解決する。

原稿の `[infobox]` に `_template` を書くと、本家のテンプレートをそのまま呼べる。
このとき原稿の項目名を、そのまま本家の引数名として扱う。ただし本家の TemplateData には
引数名（`image`）と日本語のラベル（`画像`）の両方があり、どちらで書かれても受け付けたい。
そこでこのモジュールが、同梱の TemplateData を使って次のことを決める。

- 原稿の項目名を引数名に解決する（引数名の完全一致 → 別名 → 日本語のラベル → 見つからない）
- 解決できない項目名と、必須の引数の欠けを検査に渡す
- 画像の引数（`type` が `wiki-file-name`）を、ファイル名だけを渡す書式にする

同梱のデータは `assets/templatedata.toml`。中身は ja.wikipedia の MediaWiki API
（`action=templatedata`）から取ったもので、ネットワークが無くても動くようにしてある。
取り直しは `wikiskill templatedata --fetch`（:func:`fetch_template_data`）。

同梱に無いテンプレートは、定義が分からないので何も言わない（従来どおり、項目名をそのまま
引数名にする）。データの誤りは :class:`TemplateDataError` の仲間の例外にする。

使い方::

    from wikiskill.templatedata import load_default_templatedata

    registry = load_default_templatedata()
    template = registry.find("Infobox 人物")
    if template is not None:
        print(template.resolve_name("画像"))
"""

from __future__ import annotations

import json
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import cast

from wikiskill.fetch import Pacer
from wikiskill.types import TypeRegistry

__all__ = [
    "DEFAULT_TEMPLATEDATA_PATH",
    "USER_AGENT",
    "DuplicateTemplateError",
    "TemplateData",
    "TemplateDataError",
    "TemplateDataFetchError",
    "TemplateDataRegistry",
    "TemplateDataSchemaError",
    "TemplateParam",
    "fetch_template_data",
    "format_templatedata",
    "load_default_templatedata",
    "normalize_template_name",
    "parse_templatedata",
    "read_templatedata_file",
    "template_data_from_page",
    "template_names_from_types",
    "write_templatedata_file",
]

DEFAULT_TEMPLATEDATA_PATH = Path(__file__).resolve().parents[2] / "assets" / "templatedata.toml"
"""同梱の TemplateData（`plugins/wiki-style-article/skills/wiki/assets/templatedata.toml`）。"""

TEMPLATEDATA_HOST = "ja.wikipedia.org"
"""TemplateData を取るホスト。"""

API_URL = f"https://{TEMPLATEDATA_HOST}/w/api.php"
"""MediaWiki API の URL。"""

USER_AGENT = "wsa-template-audit/1.0 (https://github.com/YSRKEN/wiki-style-article; template audit)"
"""取得のときに名乗る UA。本家の案内に従い、何の道具かを書く。"""

BATCH_SIZE = 40
"""一度に聞くテンプレートの数。`titles=` は 50 件までなので、余裕を見て 40 にする。"""

_EXTRA_INTERVAL = 1.0
"""同じホストへ続けて聞くとき、間をどれだけ余分に空けるか（秒）。"""

_RETRY_STATUSES = frozenset({429, 503})
_MAX_ATTEMPTS = 4
_RETRY_DELAY = 5.0
_MAX_RETRY_DELAY = 60.0

_TOP_KEYS = ("template",)
_TEMPLATE_KEYS = ("name", "description", "params")
_PARAM_KEYS = ("name", "label", "required", "image", "aliases", "description")
_NAMESPACE_PREFIXES = ("template:", "テンプレート:")

_Table = dict[str, object]


# --- 例外 -------------------------------------------------------------------------


class TemplateDataError(Exception):
    """TemplateData の誤りや、取得に失敗したときの基底の例外。"""


class TemplateDataSchemaError(TemplateDataError):
    """TOML として読めない、キーが足りない・未知、値の型や書式が合わない。"""


class DuplicateTemplateError(TemplateDataError):
    """同じ名前のテンプレートが二つ以上ある。"""


class TemplateDataFetchError(TemplateDataError):
    """MediaWiki API から TemplateData を取れない。"""


# --- データ型 ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TemplateParam:
    """テンプレートの引数一つ。

    Parameters
    ----------
    name : str
        本家での引数名。ウィキテキストに書き出すときはこの名前を使う。
    label : str | None
        日本語のラベル（TemplateData の `label`）。無ければ None。
    required : bool
        TemplateData で必須になっているか。
    image : bool
        画像の引数か（TemplateData の `type` が `wiki-file-name`）。本家が `[[File:]]` を包むので、
        原稿はファイル名だけを渡す。
    aliases : tuple[str, ...]
        別名（TemplateData の `aliases`）。英語名がここに入ることが多い。
    description : str | None
        引数の説明（日本語）。無ければ None。
    """

    name: str
    label: str | None = None
    required: bool = False
    image: bool = False
    aliases: tuple[str, ...] = ()
    description: str | None = None

    @property
    def heading(self) -> str:
        """表の見出しに使う名前。ラベルがあればラベル、無ければ引数名。"""
        return self.label or self.name


@dataclass(frozen=True, slots=True)
class TemplateData:
    """テンプレート一つの引数定義。

    Parameters
    ----------
    name : str
        テンプレート名（`Template:` は付けない）。
    params : tuple[TemplateParam, ...]
        引数の並び。TemplateData での宣言順。
    description : str | None
        テンプレートの説明（日本語）。無ければ None。
    """

    name: str
    params: tuple[TemplateParam, ...] = ()
    description: str | None = None

    def resolve(self, key: str) -> TemplateParam | None:
        """原稿の項目名を引数に解決する。

        引数名の完全一致をいちばんに採る。無ければ別名と日本語のラベルを合わせて探し、
        候補がちょうど一つのときだけ採る。候補が無い、または複数ある（曖昧）なら None。

        Parameters
        ----------
        key : str
            原稿の `[infobox]` に書かれた項目名。

        Returns
        -------
        TemplateParam | None
            解決した引数。決められなければ None。
        """
        wanted = key.strip()
        for param in self.params:
            if param.name == wanted:
                return param
        found: dict[str, TemplateParam] = {}
        for param in self.params:
            if wanted in param.aliases or param.label == wanted:
                found.setdefault(param.name, param)
        if len(found) == 1:
            return next(iter(found.values()))
        return None

    def resolve_name(self, key: str) -> str | None:
        """原稿の項目名を引数名に解決する。決められなければ None。

        Parameters
        ----------
        key : str
            原稿の `[infobox]` に書かれた項目名。

        Returns
        -------
        str | None
            引数名。:meth:`resolve` が None を返すときは None。
        """
        param = self.resolve(key)
        return None if param is None else param.name

    def image_params(self, keys: Iterable[str]) -> tuple[str, ...]:
        """画像の引数（`wiki-file-name`）に解決できた引数名を返す。

        Parameters
        ----------
        keys : Iterable[str]
            原稿の項目名（引数名でもラベルでもよい）。

        Returns
        -------
        tuple[str, ...]
            画像の引数の引数名。重複は除き、`keys` の順。
        """
        names: dict[str, None] = {}
        for key in keys:
            param = self.resolve(key)
            if param is not None and param.image:
                names.setdefault(param.name, None)
        return tuple(names)

    def missing_required(self, keys: Iterable[str]) -> tuple[TemplateParam, ...]:
        """原稿に無い必須の引数を返す。

        Parameters
        ----------
        keys : Iterable[str]
            原稿の項目名（引数名でもラベルでもよい）。

        Returns
        -------
        tuple[TemplateParam, ...]
            必須なのに、どの項目名からも解決できなかった引数。宣言順。
        """
        written = {param.name for key in keys if (param := self.resolve(key)) is not None}
        return tuple(param for param in self.params if param.required and param.name not in written)


@dataclass(frozen=True, slots=True)
class TemplateDataRegistry:
    """テンプレート名から :class:`TemplateData` を引く登録簿。

    Parameters
    ----------
    templates : tuple[TemplateData, ...]
        テンプレートの並び。
    """

    templates: tuple[TemplateData, ...] = ()

    def find(self, name: str) -> TemplateData | None:
        """テンプレート名で引く。無ければ None。

        Parameters
        ----------
        name : str
            テンプレート名。`Template:` や `テンプレート:` の接頭辞、`_` は落として比べる。

        Returns
        -------
        TemplateData | None
            見つかった定義。無ければ None。
        """
        wanted = normalize_template_name(name)
        for template in self.templates:
            if template.name == wanted:
                return template
        return None

    def __contains__(self, name: object) -> bool:
        """テンプレート名が登録簿にあるか。"""
        return isinstance(name, str) and self.find(name) is not None

    def __len__(self) -> int:
        """登録簿のテンプレートの数。"""
        return len(self.templates)

    def __iter__(self) -> Iterator[TemplateData]:
        """テンプレートを並びの順に返す。"""
        return iter(self.templates)


def normalize_template_name(name: str) -> str:
    """テンプレート名を比べられる形にそろえる。

    `Template:`・`テンプレート:` の接頭辞を落とし、`_` を空白にし、続く空白を一つにする。

    Parameters
    ----------
    name : str
        テンプレート名。

    Returns
    -------
    str
        そろえたテンプレート名。
    """
    text = name.strip()
    lowered = text.casefold()
    for prefix in _NAMESPACE_PREFIXES:
        if lowered.startswith(prefix):
            text = text[len(prefix) :]
            break
    return " ".join(text.replace("_", " ").split())


# --- 読み込み ---------------------------------------------------------------------


def parse_templatedata(text: str) -> TemplateDataRegistry:
    """TemplateData の TOML を読み、登録簿にする。

    Parameters
    ----------
    text : str
        TOML の文字列。

    Returns
    -------
    TemplateDataRegistry
        読んだ登録簿。

    Raises
    ------
    TemplateDataSchemaError
        TOML として読めない、キーが足りない・未知、値の型や書式が合わないとき。
    DuplicateTemplateError
        同じ名前のテンプレートが二つ以上あるとき。
    """
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise TemplateDataSchemaError(f"TOML として読めない: {exc}") from exc
    table = cast("_Table", data)
    _reject_unknown(table, _TOP_KEYS, "定義の最上位")
    raw_templates = table.get("template", [])
    if not isinstance(raw_templates, list):
        raise TemplateDataSchemaError("[[template]] は配列で書く")
    templates: list[TemplateData] = []
    seen: set[str] = set()
    for index, raw in enumerate(cast("list[object]", raw_templates), start=1):
        template = _read_template(raw, index)
        if template.name in seen:
            raise DuplicateTemplateError(f"テンプレート {template.name!r} が重複している")
        seen.add(template.name)
        templates.append(template)
    return TemplateDataRegistry(templates=tuple(templates))


def read_templatedata_file(path: Path | str) -> TemplateDataRegistry:
    """TemplateData の TOML のファイルを読む。

    Parameters
    ----------
    path : Path | str
        読むファイル。

    Returns
    -------
    TemplateDataRegistry
        読んだ登録簿。
    """
    return parse_templatedata(Path(path).read_text(encoding="utf-8"))


@cache
def load_default_templatedata() -> TemplateDataRegistry:
    """同梱の TemplateData を読む。ファイルが無ければ空の登録簿を返す。

    Returns
    -------
    TemplateDataRegistry
        同梱の登録簿。ファイルが無ければ空のもの。
    """
    if not DEFAULT_TEMPLATEDATA_PATH.is_file():
        return TemplateDataRegistry()
    return read_templatedata_file(DEFAULT_TEMPLATEDATA_PATH)


# --- 書き出し ---------------------------------------------------------------------


def format_templatedata(registry: TemplateDataRegistry, *, fetched: str | None = None) -> str:
    """登録簿を TOML の文字列にする。並びは名前順で、引数は宣言順に固定する。

    Parameters
    ----------
    registry : TemplateDataRegistry
        書き出す登録簿。
    fetched : str | None
        取得日（`2026-11-05` の形）。省くと日付を書かない。

    Returns
    -------
    str
        TOML の文字列。日本語はそのまま（UTF-8）で書く。
    """
    lines = [
        "# ja.wikipedia の TemplateData（テンプレートの引数定義）。",
        "# 原稿の [infobox] に _template を書いたとき、項目名を本家の引数名に解決し、",
        "# 未知の項目名と必須の引数の欠けを検査するために使う。",
        "# 生成: wikiskill templatedata --fetch（wikiskill.templatedata の fetch_template_data）",
        "# 出典: 日本語版ウィキペディアのテンプレートの TemplateData（そのページか /doc に",
        "# 書かれている）。説明文（description）と表示名（label）は日本語版ウィキペディアの文で、",
        "# サイトの許諾 CC BY-SA 4.0（https://creativecommons.org/licenses/by-sa/4.0/）に従って扱う。",
        "# このファイルはリポジトリの MIT License の対象外で、CC BY-SA 4.0 で配る。",
    ]
    if fetched is not None:
        lines.append(f"# 取得日: {fetched}")
    lines.append("")
    for template in sorted(registry.templates, key=lambda item: item.name):
        lines.append("[[template]]")
        lines.append(f"name = {_quote(template.name)}")
        if template.description:
            lines.append(f"description = {_quote(template.description)}")
        if template.params:
            lines.append("params = [")
            lines.extend(f"  {_param_inline(param)}," for param in template.params)
            lines.append("]")
        else:
            lines.append("params = []")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def write_templatedata_file(
    registry: TemplateDataRegistry, path: Path | str, *, fetched: str | None = None
) -> None:
    """登録簿を TOML のファイルに書く。途中のディレクトリは作る。

    Parameters
    ----------
    registry : TemplateDataRegistry
        書き出す登録簿。
    path : Path | str
        書き出すファイル。
    fetched : str | None
        取得日（`2026-11-05` の形）。省くと日付を書かない。
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(format_templatedata(registry, fetched=fetched), encoding="utf-8")


# --- 取得 -------------------------------------------------------------------------


def template_data_from_page(page: Mapping[str, object]) -> TemplateData | None:
    """応答の `pages` の一つを :class:`TemplateData` にする。

    Parameters
    ----------
    page : Mapping[str, object]
        `action=templatedata` の応答の `pages` の値。

    Returns
    -------
    TemplateData | None
        引数定義。ページが無い、または TemplateData が無ければ None。TemplateData があって
        引数が 0 件なら、引数 0 件の :class:`TemplateData` を返す。
    """
    title = page.get("title")
    if not isinstance(title, str) or page.get("missing") is True:
        return None
    raw_params = page.get("params")
    if not isinstance(raw_params, dict):
        return None
    params: list[TemplateParam] = []
    for name, raw in cast("dict[str, object]", raw_params).items():
        if not isinstance(raw, dict):
            raise TemplateDataFetchError(f"テンプレート {title!r} の引数 {name!r} が表でない")
        table = cast("_Table", raw)
        params.append(
            TemplateParam(
                name=name,
                label=_localized(table.get("label")),
                required=table.get("required") is True,
                image=table.get("type") == "wiki-file-name",
                aliases=_alias_list(table.get("aliases")),
                description=_localized(table.get("description")),
            )
        )
    return TemplateData(
        name=normalize_template_name(title),
        params=tuple(params),
        description=_localized(page.get("description")),
    )


def template_names_from_types(registry: TypeRegistry) -> tuple[str, ...]:
    """型の定義が参照するテンプレートの名前を集める。

    Parameters
    ----------
    registry : TypeRegistry
        型の定義。

    Returns
    -------
    tuple[str, ...]
        テンプレート名。重複は除き、定義に現れた順。
    """
    names: dict[str, None] = {}
    for article_type in registry:
        for part in article_type.infobox:
            names.setdefault(normalize_template_name(part.template), None)
    return tuple(names)


def fetch_template_data(
    names: Iterable[str], *, pacer: Pacer, timeout: float = 60.0
) -> tuple[TemplateData, ...]:
    """MediaWiki API から TemplateData を取る。

    一度に :data:`BATCH_SIZE` 件までまとめて聞き、429 と maxlag は間を空けて取り直す。
    テンプレートが無い、または TemplateData が無いものは結果に含めない。

    Parameters
    ----------
    names : Iterable[str]
        テンプレート名。`Template:` の接頭辞や `_` は落として扱う。
    pacer : Pacer
        同じホストへの間を空ける仕組み。状態の置き場を決める。
    timeout : float
        一回の取得の制限時間（秒）。

    Returns
    -------
    tuple[TemplateData, ...]
        取れた定義。`names` の順（重複は除く）。

    Raises
    ------
    TemplateDataFetchError
        通信に失敗した、応答が読めない、試行の上限を超えたとき。
    """
    ordered: list[str] = []
    seen: set[str] = set()
    for name in names:
        normalized = normalize_template_name(name)
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    found: dict[str, TemplateData] = {}
    for start in range(0, len(ordered), BATCH_SIZE):
        batch = ordered[start : start + BATCH_SIZE]
        for page in _query_pages(batch, pacer=pacer, timeout=timeout):
            data = template_data_from_page(page)
            if data is not None:
                found[data.name] = data
    return tuple(found[name] for name in ordered if name in found)


def _query_pages(
    names: Sequence[str], *, pacer: Pacer, timeout: float
) -> list[Mapping[str, object]]:
    """テンプレートの一群の TemplateData を聞き、`pages` の値を返す。"""
    query = urllib.parse.urlencode(
        {
            "action": "templatedata",
            "format": "json",
            "formatversion": "2",
            "maxlag": "5",
            "titles": "|".join(f"Template:{name}" for name in names),
        }
    )
    url = f"{API_URL}?{query}"
    for attempt in range(_MAX_ATTEMPTS):
        pacer.wait(TEMPLATEDATA_HOST, extra=_EXTRA_INTERVAL)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload: object = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code in _RETRY_STATUSES and attempt + 1 < _MAX_ATTEMPTS:
                time.sleep(_retry_delay(error, attempt))
                continue
            raise TemplateDataFetchError(f"TemplateData を取れない（HTTP {error.code}）") from error
        except urllib.error.URLError as error:
            raise TemplateDataFetchError(f"TemplateData を取れない（{error.reason}）") from error
        if not isinstance(payload, dict):
            raise TemplateDataFetchError("TemplateData の応答が表でない")
        table = cast("_Table", payload)
        error_body = table.get("error")
        if isinstance(error_body, dict):
            code = cast("_Table", error_body).get("code")
            if code == "maxlag" and attempt + 1 < _MAX_ATTEMPTS:
                time.sleep(_RETRY_DELAY * (attempt + 1))
                continue
            raise TemplateDataFetchError(f"TemplateData を取れない（{code!r}）")
        pages = table.get("pages")
        if not isinstance(pages, dict):
            return []
        return [
            cast("Mapping[str, object]", page) for page in cast("dict[str, object]", pages).values()
        ]
    raise TemplateDataFetchError("TemplateData を取れない（試行の上限）")


def _retry_delay(error: urllib.error.HTTPError, attempt: int) -> float:
    """取り直すまでの待ち（秒）。Retry-After があればそれに従う。"""
    header = error.headers.get("Retry-After")
    if header is not None:
        try:
            return min(float(header), _MAX_RETRY_DELAY)
        except ValueError:
            pass
    return min(_RETRY_DELAY * (attempt + 1), _MAX_RETRY_DELAY)


# --- 読み込みの補助 ---------------------------------------------------------------


def _read_template(raw: object, index: int) -> TemplateData:
    """`[[template]]` の一つを読む。"""
    where = f"{index} 個目の [[template]]"
    table = _table(raw, where)
    _reject_unknown(table, _TEMPLATE_KEYS, where)
    name = _str(table, "name", where)
    description = _optional_str(table, "description", where)
    raw_params = table.get("params", [])
    if not isinstance(raw_params, list):
        raise TemplateDataSchemaError(f"{where}: params は配列で書く")
    params: list[TemplateParam] = []
    seen: set[str] = set()
    for param_index, raw_param in enumerate(cast("list[object]", raw_params), start=1):
        param = _read_param(raw_param, f"{where} の {param_index} 個目の引数")
        if param.name in seen:
            raise TemplateDataSchemaError(f"{where}: 引数 {param.name!r} が重複している")
        seen.add(param.name)
        params.append(param)
    return TemplateData(
        name=normalize_template_name(name), params=tuple(params), description=description
    )


def _read_param(raw: object, where: str) -> TemplateParam:
    """引数の一つを読む。"""
    table = _table(raw, where)
    _reject_unknown(table, _PARAM_KEYS, where)
    return TemplateParam(
        name=_str(table, "name", where),
        label=_optional_str(table, "label", where),
        required=_bool(table, "required", where),
        image=_bool(table, "image", where),
        aliases=_str_list(table, "aliases", where),
        description=_optional_str(table, "description", where),
    )


def _param_inline(param: TemplateParam) -> str:
    """引数を TOML のインライン表にする。既定の値（偽・空）は書かない。"""
    parts = [f"name = {_quote(param.name)}"]
    if param.label and param.label != param.name:
        parts.append(f"label = {_quote(param.label)}")
    if param.required:
        parts.append("required = true")
    if param.image:
        parts.append("image = true")
    if param.aliases:
        aliases = ", ".join(_quote(alias) for alias in param.aliases)
        parts.append(f"aliases = [{aliases}]")
    if param.description:
        parts.append(f"description = {_quote(param.description)}")
    return "{ " + ", ".join(parts) + " }"


def _quote(text: str) -> str:
    """TOML の基本文字列にする（日本語はそのまま）。"""
    return json.dumps(text, ensure_ascii=False)


def _localized(value: object) -> str | None:
    """`{ja: …}` の形の説明から日本語を取る。文字列ならそのまま。"""
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        table = cast("_Table", value)
        for key in ("ja", "*"):
            text = table.get(key)
            if isinstance(text, str) and text:
                return text
    return None


def _alias_list(value: object) -> tuple[str, ...]:
    """`aliases` の配列を文字列の並びにする。"""
    if not isinstance(value, list):
        return ()
    return tuple(item for item in cast("list[object]", value) if isinstance(item, str) and item)


def _table(value: object, where: str) -> _Table:
    """値が表であることを確かめる。"""
    if not isinstance(value, dict):
        raise TemplateDataSchemaError(f"{where} は表で書く")
    return cast("_Table", value)


def _str(table: _Table, key: str, where: str) -> str:
    """表から空でない文字列を取る。"""
    value = table.get(key)
    if value is None:
        raise TemplateDataSchemaError(f"{where}: {key} がない")
    if not isinstance(value, str) or not value.strip():
        raise TemplateDataSchemaError(f"{where}: {key} は空でない文字列で書く")
    return value


def _optional_str(table: _Table, key: str, where: str) -> str | None:
    """表から文字列を取る。無ければ None。"""
    value = table.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TemplateDataSchemaError(f"{where}: {key} は文字列で書く")
    return value or None


def _bool(table: _Table, key: str, where: str) -> bool:
    """表から真偽を取る。無ければ偽。"""
    value = table.get(key, False)
    if not isinstance(value, bool):
        raise TemplateDataSchemaError(f"{where}: {key} は真偽で書く")
    return value


def _str_list(table: _Table, key: str, where: str) -> tuple[str, ...]:
    """表から文字列の配列を取る。無ければ空。"""
    value = table.get(key, [])
    if not isinstance(value, list):
        raise TemplateDataSchemaError(f"{where}: {key} は配列で書く")
    items: list[str] = []
    for item in cast("list[object]", value):
        if not isinstance(item, str) or not item:
            raise TemplateDataSchemaError(f"{where}: {key} は空でない文字列の配列で書く")
        items.append(item)
    return tuple(items)


def _reject_unknown(table: _Table, allowed: tuple[str, ...], where: str) -> None:
    """知らないキーがあれば例外にする。"""
    for key in table:
        if key not in allowed:
            raise TemplateDataSchemaError(
                f"{where}: 未知のキー {key!r}（使えるのは {', '.join(allowed)}）"
            )
