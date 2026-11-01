"""原稿を読み取った結果を表す、変更できないデータ型。

記事 → 導入部と節の木 → 段落・箇条書き → 文中の部品、の順に入れ子になる。
設定欄の中身（Infobox・出典・注釈など）は :class:`Settings` に型つきで入る。

段落・箇条書き・節・Infobox の項目・出典・注釈・外部リンクは、原稿ファイル全体での行番号
（1 始まり）を ``line`` に持つ。検査の結果に行を載せるためのもので、等しさの比較には使わない
（``compare=False``）。段落と箇条書きの項目の行は、その先頭の行。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypeAlias

RefKind = Literal["web", "book", "news"]
"""出典の種類。"""

REF_KINDS: tuple[RefKind, ...] = ("web", "book", "news")
"""出典の種類として使える値。"""


# --- 文中の部品 -------------------------------------------------------------


@dataclass(frozen=True)
class Text:
    """記法を含まない、そのままの文字。"""

    text: str


@dataclass(frozen=True)
class RefMark:
    """出典への脚注の印 ``[^キー]``。"""

    key: str


@dataclass(frozen=True)
class NoteMark:
    """注釈への印 ``[^n:キー]``。"""

    key: str


@dataclass(frozen=True)
class InternalLink:
    """内部リンク ``[[記事名]]`` または ``[[記事名|表示]]``。"""

    target: str
    label: str | None

    @property
    def display(self) -> str:
        """画面に出す文字（表示の指定がなければ記事名）。"""
        return self.target if self.label is None else self.label


@dataclass(frozen=True)
class Bold:
    """太字 ``'''…'''``。中に内部リンクや脚注の印を入れられる。"""

    children: tuple[Text | RefMark | NoteMark | InternalLink, ...]


Inline: TypeAlias = Text | RefMark | NoteMark | InternalLink | Bold
"""文中の部品のいずれか。"""


# --- 本文のまとまり -----------------------------------------------------------


@dataclass(frozen=True)
class Paragraph:
    """段落。"""

    content: tuple[Inline, ...]
    line: int = field(default=0, compare=False)


@dataclass(frozen=True)
class BulletList:
    """箇条書き（入れ子なし）。``items`` の各要素が一項目の中身。

    ``line`` は最初の項目の行、``item_lines`` は各項目の先頭の行。
    """

    items: tuple[tuple[Inline, ...], ...]
    line: int = field(default=0, compare=False)
    item_lines: tuple[int, ...] = field(default=(), compare=False)


Block: TypeAlias = Paragraph | BulletList
"""節や導入部の直下に置けるまとまり。"""


@dataclass(frozen=True)
class Section:
    """節。``blocks`` は見出しの直後から最初の子の節の前まで、``children`` は一段下の節。"""

    level: int
    title: str
    blocks: tuple[Block, ...]
    children: tuple[Section, ...]
    line: int = field(default=0, compare=False)


# --- 設定欄 ----------------------------------------------------------------


@dataclass(frozen=True)
class InfoboxField:
    """Infobox の一項目（項目名と値）。"""

    name: str
    value: str
    line: int = field(default=0, compare=False)


@dataclass(frozen=True)
class Reference:
    """出典 ``[refs.キー]``。"""

    key: str
    kind: RefKind
    title: str
    url: str | None = None
    author: str | None = None
    publisher: str | None = None
    work: str | None = None
    date: str | None = None
    access_date: str | None = None
    isbn: str | None = None
    pages: str | None = None
    note: str | None = None
    line: int = field(default=0, compare=False)
    field_lines: tuple[tuple[str, int], ...] = field(default=(), compare=False)

    def line_of(self, name: str) -> int:
        """項目 ``name``（``url`` など）が書かれた行。書かれていなければ表の見出しの行。"""
        return dict(self.field_lines).get(name, self.line)


@dataclass(frozen=True)
class Note:
    """注釈 ``[notes.キー]``。本文は文中の部品に分けてある。"""

    key: str
    text: tuple[Inline, ...]
    line: int = field(default=0, compare=False)


@dataclass(frozen=True)
class ExternalLink:
    """外部リンク ``[[external_links]]``。"""

    title: str
    url: str
    line: int = field(default=0, compare=False)


@dataclass(frozen=True)
class Settings:
    """冒頭の TOML の設定欄の中身。

    ``infobox``・``references``・``notes`` は原稿に書いた順を保つ。
    """

    title: str
    type_id: str
    reading: str | None = None
    defaultsort: str | None = None
    categories: tuple[str, ...] = ()
    infobox: tuple[InfoboxField, ...] = ()
    references: tuple[Reference, ...] = ()
    notes: tuple[Note, ...] = ()
    related: tuple[str, ...] = ()
    external_links: tuple[ExternalLink, ...] = ()


# --- 記事 ------------------------------------------------------------------


@dataclass(frozen=True)
class Article:
    """原稿を読み取った記事全体。

    ``lead`` は最初の ``## `` 見出しより前の導入部、``sections`` は ``## `` の節（一段目）の並び。
    """

    settings: Settings
    lead: tuple[Block, ...]
    sections: tuple[Section, ...]
