"""原稿の冒頭にある TOML の設定欄を読み、型のついた :class:`~wikiskill.model.Settings` にする。

設定欄に書ける項目は次のとおり。

- ``title``（必須）・``type``（必須）・``reading``・``defaultsort``: 文字列
- ``categories``・``related``: 文字列の配列
- ``[infobox]``: 項目名 → 値（文字列）
- ``notices``: 警告の枠の種類（``観点``・``出典の明記``・``独自研究``）の配列
- ``[refs.キー]``: 出典。``kind``（web / book / news）と ``title`` が必須。任意の ``weak``
  （真偽値）は弱い出典であることを表す
- ``[notes.キー]``: 注釈。``text`` が必須で、本文と同じ文中の記法を使える
- ``[[external_links]]``: 外部リンク。``title`` と ``url`` が必須

書いていない項目や、印が指すキーが設定欄にあるかは、ここでは見ない（後の検査の仕事）。
"""

from __future__ import annotations

import re
import tomllib
from typing import cast

from wikiskill.errors import SettingsError
from wikiskill.inline import KEY_PATTERN, parse_inline
from wikiskill.model import (
    NOTICE_KINDS,
    REF_KINDS,
    ExternalLink,
    InfoboxField,
    Note,
    NoticeKind,
    Reference,
    Settings,
)

_Table = dict[str, object]

_TYPE_PATTERN = re.compile(r"[a-z]+(?:-[a-z]+)*")
_TOP_KEYS = (
    "title",
    "reading",
    "type",
    "defaultsort",
    "categories",
    "infobox",
    "refs",
    "notes",
    "related",
    "external_links",
    "notices",
)
_REF_OPTIONAL_KEYS = (
    "url",
    "author",
    "publisher",
    "work",
    "date",
    "access_date",
    "isbn",
    "pages",
    "note",
)

_NOTICES_BY_NAME: dict[str, NoticeKind] = {kind: kind for kind in NOTICE_KINDS}

_HEADER = re.compile(r"\s*(\[\[?)\s*(.+?)\s*\]\]?\s*(?:#.*)?")
_TOML_ERROR_LINE = re.compile(r"\(at line (\d+), column \d+\)")
_TOML_ERROR_SUFFIX = re.compile(r"\s*\(at (?:end of document|line \d+, column \d+)\)\s*$")


def parse_settings(config_text: str, first_line: int = 2) -> Settings:
    """設定欄の TOML を読んで、型のついた設定にする。

    Parameters
    ----------
    config_text : str
        設定欄の中身（冒頭と末尾の ``+++`` の行は含めない）。
    first_line : int
        ``config_text`` の先頭が原稿ファイルの何行目か。冒頭が ``+++`` の行なら 2。

    Returns
    -------
    Settings
        読み取った設定。``infobox``・``references``・``notes`` は書いた順。

    Raises
    ------
    SettingsError
        TOML として読めない、必須の項目がない、型や値が合わない、未知の項目があるとき。
        行番号は、その項目（なければその表の見出し、それもなければ冒頭の ``+++``）の行。
    MarkupError
        注釈の本文の文中の記法が壊れているとき。
    """
    return _SettingsReader(config_text, first_line).read()


class _Locator:
    """設定欄の項目が原稿の何行目にあるかを、書かれた文字列から探す。

    TOML の読み取り結果には行番号がないので、``[表]`` の見出しと ``キー =`` の行を探す。
    見つからなければ（ドット付きのキーや一行の表で書かれた場合など）冒頭の行を返す。
    """

    def __init__(self, text: str, first_line: int) -> None:
        self._lines = text.split("\n")
        self._first_line = first_line

    @property
    def opening_line(self) -> int:
        """設定欄を始める ``+++`` の行。"""
        return self._first_line - 1

    @property
    def last_line(self) -> int:
        """設定欄の最後の行。"""
        return self._first_line + len(self._lines) - 1

    def find(self, section: str | None, key: str | None = None, index: int = 0) -> int:
        """項目の行を返す。

        Parameters
        ----------
        section : str | None
            表の名前（``refs.a`` など）。None なら最初の見出しより前の部分。
        key : str | None
            表の中のキー。None なら表の見出しの行を探す。
        index : int
            同名の ``[[表]]`` が複数あるとき、何個目か（0 始まり）。
        """
        key_line = re.compile(rf"\s*[\"']?{re.escape(key)}[\"']?\s*=") if key is not None else None
        active = section is None
        occurrence = 0
        section_line: int | None = None
        for offset, line in enumerate(self._lines):
            number = self._first_line + offset
            header = _HEADER.fullmatch(line)
            if header is not None:
                name = re.sub(r"[\s\"']", "", header.group(2))
                if section is not None and name == section:
                    active = occurrence == index
                    if active:
                        section_line = number
                    occurrence += 1
                else:
                    active = False
            elif active and key_line is not None and key_line.match(line):
                return number
        return section_line if section_line is not None else self.opening_line


class _SettingsReader:
    """TOML を読み、項目ごとに検査しながら :class:`Settings` を組み立てる。"""

    def __init__(self, text: str, first_line: int) -> None:
        self._text = text
        self._locator = _Locator(text, first_line)

    def read(self) -> Settings:
        """設定欄全体を読む。"""
        data = self._load()
        self._reject_unknown(data, _TOP_KEYS, None)
        type_id = self._str(data, "type", None, required=True)
        if type_id is not None and not _TYPE_PATTERN.fullmatch(type_id):
            raise self._error(
                f"type {type_id!r} は使えない（英小文字とハイフンだけ。例: person, manga）",
                None,
                "type",
            )
        return Settings(
            title=self._str(data, "title", None, required=True) or "",
            type_id=type_id or "",
            reading=self._str(data, "reading", None),
            defaultsort=self._str(data, "defaultsort", None),
            categories=self._str_list(data, "categories"),
            infobox=self._infobox(data),
            references=self._references(data),
            notes=self._notes(data),
            related=self._str_list(data, "related"),
            external_links=self._external_links(data),
            notices=self._notices(data),
        )

    # --- 読み込みと、エラーの作り方 -------------------------------------------

    def _load(self) -> _Table:
        try:
            return tomllib.loads(self._text)
        except tomllib.TOMLDecodeError as exc:
            lineno = getattr(exc, "lineno", None)
            if not isinstance(lineno, int):
                found = _TOML_ERROR_LINE.search(str(exc))
                lineno = int(found.group(1)) if found else None
            line = (
                self._locator.opening_line + lineno
                if lineno is not None
                else self._locator.last_line
            )
            reason = _TOML_ERROR_SUFFIX.sub("", str(exc))
            raise SettingsError(
                f"設定欄の TOML が読めない: {reason}{self._hint(lineno)}", line
            ) from exc

    def _hint(self, lineno: int | None) -> str:
        """引用符のない日本語の項目名が原因らしいときの、直し方の補足。"""
        if lineno is None:
            return ""
        lines = self._text.split("\n")
        if not 1 <= lineno <= len(lines):
            return ""
        before_equal = lines[lineno - 1].partition("=")[0].strip()
        if before_equal and not before_equal.isascii() and not before_equal.startswith(('"', "'")):
            return f'（日本語の項目名は "{before_equal}" = "…" のように引用符で囲む）'
        return ""

    def _error(
        self,
        message: str,
        section: str | None,
        key: str | None = None,
        index: int = 0,
    ) -> SettingsError:
        return SettingsError(message, self._locator.find(section, key, index))

    @staticmethod
    def _label(section: str | None, key: str) -> str:
        return key if section is None else f"[{section}] の {key}"

    # --- 型ごとの取り出し ---------------------------------------------------

    def _reject_unknown(
        self,
        table: _Table,
        allowed: tuple[str, ...],
        section: str | None,
        index: int = 0,
    ) -> None:
        for key in table:
            if key not in allowed:
                where = "" if section is None else f"[{section}] に"
                raise self._error(
                    f"{where}未知の項目 {key!r} がある（使える項目: {', '.join(allowed)}）",
                    section,
                    key,
                    index,
                )

    def _str(
        self,
        table: _Table,
        key: str,
        section: str | None,
        *,
        required: bool = False,
        index: int = 0,
    ) -> str | None:
        label = self._label(section, key)
        if key not in table:
            if required:
                raise self._error(f"{label} がない", section, None, index)
            return None
        value = table[key]
        if not isinstance(value, str):
            raise self._error(f"{label} は文字列で書く（引用符で囲む）", section, key, index)
        if required and not value.strip():
            raise self._error(f"{label} が空", section, key, index)
        return value

    def _str_list(self, table: _Table, key: str) -> tuple[str, ...]:
        if key not in table:
            return ()
        value = table[key]
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in cast("list[object]", value)
        ):
            raise self._error(f"{key} は文字列の配列で書く", None, key)
        return tuple(cast("list[str]", value))

    def _table(self, table: _Table, key: str) -> _Table:
        value = table.get(key)
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise self._error(f"{key} は表（[{key}] の形）で書く", None, key)
        return cast("_Table", value)

    def _sub_table(self, table: _Table, parent: str, key: str) -> _Table:
        value = table[key]
        if not isinstance(value, dict):
            raise self._error(
                f"[{parent}.{key}] の形の表で書く（{key} の値が表になっていない）",
                parent,
                key,
            )
        return cast("_Table", value)

    # --- 各項目 -----------------------------------------------------------

    def _infobox(self, data: _Table) -> tuple[InfoboxField, ...]:
        fields: list[InfoboxField] = []
        for name, value in self._table(data, "infobox").items():
            if not isinstance(value, str):
                raise self._error(
                    f"[infobox] の {name} は文字列で書く（数値も引用符で囲む）",
                    "infobox",
                    name,
                )
            fields.append(InfoboxField(name, value, self._locator.find("infobox", name)))
        return tuple(fields)

    def _references(self, data: _Table) -> tuple[Reference, ...]:
        refs = self._table(data, "refs")
        result: list[Reference] = []
        for key in refs:
            section = f"refs.{key}"
            if not KEY_PATTERN.fullmatch(key):
                raise self._error(
                    f"出典のキー {key!r} は使えない（英数字・ハイフン・下線だけ）",
                    section,
                )
            table = self._sub_table(refs, "refs", key)
            self._reject_unknown(table, ("kind", "title", *_REF_OPTIONAL_KEYS, "weak"), section)
            kind = self._str(table, "kind", section, required=True)
            if kind not in REF_KINDS:
                kinds = " / ".join(REF_KINDS)
                raise self._error(
                    f"[{section}] の kind は {kinds} のどれか（{kind!r} は使えない）",
                    section,
                    "kind",
                )
            optional = {name: self._str(table, name, section) for name in _REF_OPTIONAL_KEYS}
            result.append(
                Reference(
                    key=key,
                    kind=kind,
                    title=self._str(table, "title", section, required=True) or "",
                    weak=self._weak(table, section),
                    line=self._locator.find(section),
                    field_lines=tuple((name, self._locator.find(section, name)) for name in table),
                    **optional,
                )
            )
        return tuple(result)

    def _weak(self, table: _Table, section: str) -> bool:
        value = table.get("weak", False)
        if not isinstance(value, bool):
            raise self._error(
                f"[{section}] の weak は true か false で書く（引用符で囲まない）", section, "weak"
            )
        return value

    def _notices(self, data: _Table) -> tuple[NoticeKind, ...]:
        result: list[NoticeKind] = []
        for value in self._str_list(data, "notices"):
            kind = _NOTICES_BY_NAME.get(value)
            if kind is None:
                raise self._error(
                    f"notices の {value!r} は使えない（使える値: {'、'.join(NOTICE_KINDS)}）",
                    None,
                    "notices",
                )
            result.append(kind)
        return tuple(result)

    def _notes(self, data: _Table) -> tuple[Note, ...]:
        notes = self._table(data, "notes")
        result: list[Note] = []
        for key in notes:
            section = f"notes.{key}"
            if not KEY_PATTERN.fullmatch(key):
                raise self._error(
                    f"注釈のキー {key!r} は使えない（英数字・ハイフン・下線だけ）",
                    section,
                )
            table = self._sub_table(notes, "notes", key)
            self._reject_unknown(table, ("text",), section)
            text = self._str(table, "text", section, required=True) or ""
            line = self._locator.find(section, "text")
            result.append(Note(key, parse_inline(text, line), line))
        return tuple(result)

    def _external_links(self, data: _Table) -> tuple[ExternalLink, ...]:
        if "external_links" not in data:
            return ()
        value = data["external_links"]
        if not isinstance(value, list):
            raise self._error(
                "external_links は [[external_links]] の形で書く", None, "external_links"
            )
        result: list[ExternalLink] = []
        for index, item in enumerate(cast("list[object]", value)):
            if not isinstance(item, dict):
                raise self._error(
                    "external_links は [[external_links]] の形で書く", "external_links", None, index
                )
            table = cast("_Table", item)
            self._reject_unknown(table, ("title", "url"), "external_links", index)
            result.append(
                ExternalLink(
                    title=self._str(table, "title", "external_links", required=True, index=index)
                    or "",
                    url=self._str(table, "url", "external_links", required=True, index=index) or "",
                    line=self._locator.find("external_links", None, index),
                )
            )
        return tuple(result)
