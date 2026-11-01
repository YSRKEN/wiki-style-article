"""記事の類型の定義（``assets/types.toml``）を読み、変更できないデータにする。

類型は二層ある。

- **基本型**: 記事の節の並びや書き方が決まる型（人物・漫画・出来事など）。``parents`` を持たない。
- **細かい種類**: 基本型の一つ以上に「寄せる」型（声優・バンド・鉄道車両など）。
  節の並びは寄せ先に従い、Infobox だけを自分のものに差し替える。

どちらも :class:`ArticleType` で、``id`` が原稿の ``type`` に書く値になる。
Infobox は :class:`InfoboxPart` の並びで、漫画の Header・本体・Footer のように
複数の部品を重ねる型も表せる。部品の中は :class:`InfoboxField`（日本語の項目名、
テンプレートの引数名、必須か、未確認か）の並び。

定義の書き方は ``docs/types.md``。定義の誤りは :class:`TypeRegistryError` の仲間の例外にする。
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal, cast

Placement = Literal["top", "lead"]
"""テンプレートを置く場所。``top`` は記事の最上部（導入部の前）、``lead`` は導入部の中。"""

PLACEMENTS: tuple[Placement, ...] = ("top", "lead")
"""``placement`` に書ける値。"""

DEFAULT_TYPES_PATH = Path(__file__).resolve().parents[2] / "assets" / "types.toml"
"""同梱の定義ファイル（``skills/wiki/assets/types.toml``）。"""

_ID_PATTERN = re.compile(r"[a-z]+(?:-[a-z]+)*")
_TOP_KEYS = ("type",)
_TYPE_KEYS = ("id", "name", "parents", "no_infobox", "infobox")
_PART_KEYS = ("template", "placement", "title_field", "required", "unverified", "fields")

_Table = dict[str, object]


# --- 例外 -------------------------------------------------------------------------


class TypeRegistryError(Exception):
    """類型の定義の誤りや、定義にない型を引いたときの基底の例外。"""


class TypeSchemaError(TypeRegistryError):
    """TOML として読めない、キーが足りない・未知、値の型や書式が合わない。"""


class DuplicateTypeError(TypeRegistryError):
    """同じ ``id`` の型が二つ以上ある。"""


class UnknownParentError(TypeRegistryError):
    """``parents`` に書いた型が定義の中にない。"""


class ParentNotBaseError(TypeRegistryError):
    """``parents`` に書いた型が、基本型ではなく細かい種類（または自分自身）である。"""


class InfoboxError(TypeRegistryError):
    """Infobox の定義が矛盾している（必須の項目が並びにない、項目名の重複、有無が不明など）。"""


class UnknownTypeError(TypeRegistryError):
    """定義にない型の ``id`` を引いた。"""


# --- データ型 ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class InfoboxField:
    """Infobox の一つの項目。

    Parameters
    ----------
    label : str
        原稿の ``[infobox]`` に書く日本語の項目名。
    param : str
        本家のテンプレートでの引数名。書き出しはこの名前で出す。
    required : bool
        原稿に必ず書くか。書かれていなければ検査で指摘する。
    unverified : bool
        引数名を本家のテンプレートで確かめられていないか。
    """

    label: str
    param: str
    required: bool
    unverified: bool


@dataclass(frozen=True, slots=True)
class InfoboxPart:
    """Infobox を作るテンプレートの一つ。漫画の Header・本体・Footer のように重ねて使う。

    Parameters
    ----------
    template : str
        本家のテンプレート名（``Template:`` は付けない）。
    placement : Placement
        テンプレートを置く場所。
    title_field : str | None
        記事名を既定値にする項目の項目名。原稿に書かれていなければ、書き出しは記事名を入れる。
        そのため必須にはしない。なければ None。
    fields : tuple[InfoboxField, ...]
        項目の並び。表示の順でもある。
    """

    template: str
    placement: Placement
    title_field: str | None
    fields: tuple[InfoboxField, ...]


@dataclass(frozen=True, slots=True)
class ArticleType:
    """記事の類型（基本型または細かい種類）。

    Parameters
    ----------
    id : str
        原稿の ``type`` に書く値。英小文字とハイフン。
    name : str
        日本語名。
    parents : tuple[str, ...]
        寄せ先の基本型の ``id``。基本型は空。
    infobox : tuple[InfoboxPart, ...]
        Infobox の部品の並び。Infobox を持たない型は空。
    """

    id: str
    name: str
    parents: tuple[str, ...]
    infobox: tuple[InfoboxPart, ...]

    @property
    def is_base(self) -> bool:
        """基本型か（寄せ先を持たないか）。"""
        return not self.parents

    @property
    def has_infobox(self) -> bool:
        """Infobox を持つか。"""
        return bool(self.infobox)

    @property
    def fields(self) -> tuple[InfoboxField, ...]:
        """全部品の項目を、部品の順・書いた順に並べたもの。"""
        return tuple(f for part in self.infobox for f in part.fields)

    @property
    def required_fields(self) -> tuple[InfoboxField, ...]:
        """必須の項目だけ。"""
        return tuple(f for f in self.fields if f.required)

    def find_field(self, label: str) -> InfoboxField | None:
        """日本語の項目名から項目を探す。

        Parameters
        ----------
        label : str
            日本語の項目名。

        Returns
        -------
        InfoboxField | None
            見つかった項目。なければ None。
        """
        return next((f for f in self.fields if f.label == label), None)


@dataclass(frozen=True, slots=True)
class TypeRegistry:
    """類型の一覧。定義ファイルに書いた順を保つ。

    :func:`parse_registry` が検査して作る。直接作ると検査は通らない。

    Parameters
    ----------
    types : tuple[ArticleType, ...]
        全部の型。
    """

    types: tuple[ArticleType, ...]

    def __iter__(self) -> Iterator[ArticleType]:
        """全部の型を順に返す。"""
        return iter(self.types)

    def __len__(self) -> int:
        """型の数。"""
        return len(self.types)

    def __contains__(self, type_id: object) -> bool:
        """``id`` の型があるか。"""
        return any(t.id == type_id for t in self.types)

    def __getitem__(self, type_id: str) -> ArticleType:
        """``id`` から型を引く。

        Raises
        ------
        UnknownTypeError
            その ``id`` の型がないとき。
        """
        found = self.find(type_id)
        if found is None:
            raise UnknownTypeError(f"型 {type_id!r} は定義にない")
        return found

    def find(self, type_id: str) -> ArticleType | None:
        """``id`` から型を探す。なければ None。"""
        return next((t for t in self.types if t.id == type_id), None)

    def kinds_of(self, base_id: str) -> tuple[ArticleType, ...]:
        """基本型に寄せている細かい種類を、定義の順に返す。"""
        return tuple(t for t in self.types if base_id in t.parents)


# --- 読み込み ---------------------------------------------------------------------


def parse_registry(text: str) -> TypeRegistry:
    """定義の TOML を読み、検査して :class:`TypeRegistry` にする。

    Parameters
    ----------
    text : str
        ``types.toml`` の中身。

    Returns
    -------
    TypeRegistry
        読み取った型の一覧。定義ファイルに書いた順。

    Raises
    ------
    TypeSchemaError
        TOML として読めない、キーが足りない・未知、値の型や書式が合わないとき。
    DuplicateTypeError
        ``id`` が重複しているとき。
    UnknownParentError
        寄せ先の型がないとき。
    ParentNotBaseError
        寄せ先が基本型でないとき。
    InfoboxError
        Infobox の定義が矛盾しているとき。
    """
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise TypeSchemaError(f"TOML として読めない: {exc}") from exc
    _reject_unknown(cast("_Table", data), _TOP_KEYS, "定義の最上位")
    raw_types = data.get("type")
    if not isinstance(raw_types, list) or not raw_types:
        raise TypeSchemaError("[[type]] が一つもない")
    types: list[ArticleType] = []
    seen: set[str] = set()
    for index, raw in enumerate(cast("list[object]", raw_types), start=1):
        article_type = _read_type(raw, index)
        if article_type.id in seen:
            raise DuplicateTypeError(f"型 {article_type.id!r} が重複している")
        seen.add(article_type.id)
        types.append(article_type)
    _check_parents(types)
    return TypeRegistry(types=tuple(types))


def read_registry_file(path: Path | str) -> TypeRegistry:
    """定義ファイル（UTF-8 の TOML）を読む。

    Parameters
    ----------
    path : Path | str
        ``types.toml`` のパス。

    Returns
    -------
    TypeRegistry
        読み取った型の一覧。
    """
    return parse_registry(Path(path).read_text(encoding="utf-8"))


@cache
def load_default_registry() -> TypeRegistry:
    """同梱の定義（``skills/wiki/assets/types.toml``）を読む。結果は使い回す。"""
    return read_registry_file(DEFAULT_TYPES_PATH)


# --- 検査つきの組み立て -----------------------------------------------------------


def _read_type(raw: object, index: int) -> ArticleType:
    table = _table(raw, f"{index} 個目の [[type]]")
    type_id = _str(table, "id", f"{index} 個目の [[type]]")
    where = f"型 {type_id!r}"
    if not _ID_PATTERN.fullmatch(type_id):
        raise TypeSchemaError(
            f"{index} 個目の [[type]] の id {type_id!r} は使えない"
            "（英小文字とハイフンだけ。例: person-living）"
        )
    _reject_unknown(table, _TYPE_KEYS, where)
    name = _str(table, "name", where)
    parents = _parents(table, where)
    no_infobox = table.get("no_infobox", False)
    if not isinstance(no_infobox, bool):
        raise TypeSchemaError(f"{where}: no_infobox は true か false")
    raw_parts = table.get("infobox", [])
    if not isinstance(raw_parts, list):
        raise TypeSchemaError(f"{where}: infobox は [[type.infobox]] の並びで書く")
    parts = tuple(
        _read_part(p, where, i) for i, p in enumerate(cast("list[object]", raw_parts), start=1)
    )
    if no_infobox and parts:
        raise InfoboxError(f"{where}: no_infobox = true と [[type.infobox]] は同時に書けない")
    if not no_infobox and not parts:
        raise InfoboxError(
            f"{where}: Infobox を持たない型は no_infobox = true と明示する"
            "（持つ型は [[type.infobox]] を書く）"
        )
    _check_labels_unique(parts, where)
    return ArticleType(id=type_id, name=name, parents=parents, infobox=parts)


def _read_part(raw: object, type_where: str, index: int) -> InfoboxPart:
    where = f"{type_where} の {index} 個目の [[type.infobox]]"
    table = _table(raw, where)
    template = _str(table, "template", where)
    where = f"{type_where} の Infobox {template!r}"
    _reject_unknown(table, _PART_KEYS, where)
    placement = table.get("placement", "top")
    if placement not in PLACEMENTS:
        raise TypeSchemaError(f"{where}: placement は {' か '.join(PLACEMENTS)} のどちらか")
    if "fields" not in table:
        raise TypeSchemaError(f"{where}: fields がない")
    raw_fields = _table(table["fields"], f"{where} の fields")
    if not raw_fields:
        raise InfoboxError(f"{where}: fields が空（項目を一つ以上書く）")
    mapping: dict[str, str] = {}
    for label, value in raw_fields.items():
        if not label:
            raise TypeSchemaError(f"{where}: 空の項目名がある")
        if not isinstance(value, str) or not value:
            raise TypeSchemaError(f"{where}: 項目 {label!r} の引数名は空でない文字列で書く")
        mapping[label] = value
    required = _label_list(table, "required", where, mapping)
    unverified = _label_list(table, "unverified", where, mapping)
    title_field = _title_field(table, where, mapping, required)
    params: dict[str, str] = {}
    for label, param in mapping.items():
        if param in params:
            raise InfoboxError(
                f"{where}: 引数名 {param!r} が項目 {params[param]!r} と {label!r} で重複している"
            )
        params[param] = label
    fields = tuple(
        InfoboxField(
            label=label,
            param=param,
            required=label in required,
            unverified=label in unverified,
        )
        for label, param in mapping.items()
    )
    return InfoboxPart(
        template=template,
        placement=placement,
        title_field=title_field,
        fields=fields,
    )


def _title_field(
    table: _Table, where: str, mapping: dict[str, str], required: frozenset[str]
) -> str | None:
    """``title_field`` を読み、fields にあり必須でないことを確かめる。"""
    if "title_field" not in table:
        return None
    label = _str(table, "title_field", where)
    if label not in mapping:
        raise InfoboxError(f"{where}: title_field の {label!r} が fields の並びにない")
    if label in required:
        raise InfoboxError(
            f"{where}: title_field の {label!r} は記事名で埋まるので required にしない"
        )
    return label


def _label_list(table: _Table, key: str, where: str, mapping: dict[str, str]) -> frozenset[str]:
    """項目名の配列（``required`` など）を読み、fields にあることを確かめる。"""
    labels = _str_list(table.get(key, []))
    if labels is None:
        raise TypeSchemaError(f"{where}: {key} は項目名（文字列）の配列")
    seen: set[str] = set()
    for label in labels:
        if label in seen:
            raise InfoboxError(f"{where}: {key} に {label!r} が重複している")
        seen.add(label)
        if label not in mapping:
            raise InfoboxError(f"{where}: {key} の {label!r} が fields の並びにない")
    return frozenset(labels)


def _check_labels_unique(parts: tuple[InfoboxPart, ...], where: str) -> None:
    """型の Infobox 全体で、日本語の項目名が重ならないことを確かめる。"""
    owner: dict[str, str] = {}
    for part in parts:
        for field in part.fields:
            if field.label in owner:
                raise InfoboxError(
                    f"{where}: 項目名 {field.label!r} が {owner[field.label]!r} と"
                    f" {part.template!r} の両方にある（原稿の項目名は型の中で一意）"
                )
            owner[field.label] = part.template


def _parents(table: _Table, where: str) -> tuple[str, ...]:
    if "parents" not in table:
        return ()
    parents = _str_list(table["parents"])
    if not parents:
        raise TypeSchemaError(f"{where}: parents は型の id の空でない配列")
    if len(set(parents)) != len(parents):
        raise TypeSchemaError(f"{where}: parents に同じ id が重複している")
    return tuple(parents)


def _check_parents(types: list[ArticleType]) -> None:
    """寄せ先が定義にあり、基本型であることを確かめる。"""
    by_id = {t.id: t for t in types}
    for article_type in types:
        for parent_id in article_type.parents:
            parent = by_id.get(parent_id)
            if parent is None:
                raise UnknownParentError(
                    f"型 {article_type.id!r} の寄せ先 {parent_id!r} が定義にない"
                )
            if parent_id == article_type.id or not parent.is_base:
                raise ParentNotBaseError(
                    f"型 {article_type.id!r} の寄せ先 {parent_id!r} は基本型ではない"
                    "（寄せ先にできるのは parents を持たない型だけ）"
                )


# --- 小さな部品 -------------------------------------------------------------------


def _table(value: object, where: str) -> _Table:
    if not isinstance(value, dict):
        raise TypeSchemaError(f"{where} は表で書く")
    return cast("_Table", value)


def _str_list(value: object) -> list[str] | None:
    """文字列だけの配列ならそのリストを、そうでなければ None を返す。"""
    if not isinstance(value, list):
        return None
    items = cast("list[object]", value)
    if not all(isinstance(item, str) for item in items):
        return None
    return cast("list[str]", items)


def _str(table: _Table, key: str, where: str) -> str:
    if key not in table:
        raise TypeSchemaError(f"{where}: {key} がない")
    value = table[key]
    if not isinstance(value, str) or not value:
        raise TypeSchemaError(f"{where}: {key} は空でない文字列で書く")
    return value


def _reject_unknown(table: _Table, allowed: tuple[str, ...], where: str) -> None:
    """書き間違いを見つけるため、決まったキー以外はエラーにする。"""
    for key in table:
        if key not in allowed:
            raise TypeSchemaError(f"{where}: 未知のキー {key!r}（使えるのは {', '.join(allowed)}）")
