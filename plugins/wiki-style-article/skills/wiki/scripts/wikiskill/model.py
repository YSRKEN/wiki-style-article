"""原稿を読み取った結果を表す、変更できないデータ型。

記事 → 導入部と節の木 → 段落・箇条書き → 文中の部品、の順に入れ子になる。
設定欄の中身（Infobox・出典・注釈など）は :class:`Settings` に型つきで入る。

段落・箇条書き・節・Infobox の項目・出典・注釈・外部リンクは、原稿ファイル全体での行番号
（1 始まり）を ``line`` に持つ。検査の結果に行を載せるためのもので、等しさの比較には使わない
（``compare=False``）。段落と箇条書きの項目の行は、その先頭の行。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TypeAlias

RefKind = Literal["web", "book", "news"]
"""出典の種類。"""

REF_KINDS: tuple[RefKind, ...] = ("web", "book", "news")
"""出典の種類として使える値。"""

FixMarkKind = Literal["要出典", "信頼性要検証"]
"""点の印（文の直後に付ける印）の種類。"""

FIX_MARK_KINDS: tuple[FixMarkKind, ...] = ("要出典", "信頼性要検証")
"""点の印の種類として使える値。"""

FixRangeKind = Literal["要出典範囲", "独自研究範囲"]
"""範囲の印（範囲の文を包む印）の種類。"""

FIX_RANGE_KINDS: tuple[FixRangeKind, ...] = ("要出典範囲", "独自研究範囲")
"""範囲の印の種類として使える値。"""

FIX_RANGE_LABELS: dict[FixRangeKind, str] = {"要出典範囲": "要出典", "独自研究範囲": "独自研究?"}
"""範囲の印の後ろに付ける文字（``[要出典]``・``[独自研究?]``）。本家の表示と同じ。"""

NoticeKind = Literal["出典の明記", "独自研究", "観点"]
"""記事の冒頭に貼る警告の枠の種類。"""

NOTICE_KINDS: tuple[NoticeKind, ...] = ("出典の明記", "独自研究", "観点")
"""警告の枠の種類として使える値。並びは枠に載せる順。"""

NoticeRule = Literal["多いときだけ", "付けない", "付ける"]
"""印から決まる警告の枠の出し方。生成の前に利用者に聞いて決める。"""

NOTICE_RULES: tuple[NoticeRule, ...] = ("多いときだけ", "付けない", "付ける")
"""枠の出し方として使える値。先頭が既定。"""


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
class FixMark:
    """点の印 ``[!要出典]``・``[!信頼性要検証]``。直前の文の出典に問題があることを示す。"""

    kind: FixMarkKind


@dataclass(frozen=True)
class FixRange:
    """範囲の印 ``[!要出典範囲|範囲の文]``・``[!独自研究範囲|範囲の文]``。

    範囲の文には、文字・内部リンク・出典の印・注釈の印を入れられる（太字と印は入れない）。
    """

    kind: FixRangeKind
    children: tuple[Text | RefMark | NoteMark | InternalLink, ...]


@dataclass(frozen=True)
class Original:
    """外国語の原文 ``[!原文|言語タグ|文]``。訳文に添える原文で、和文用の検査にはかけない。

    ``lang`` は BCP 47 の形の言語タグ（``en``・``zh-Hans`` など）、``text`` は原文の文字
    （記法は含まない）。
    """

    lang: str
    text: str


@dataclass(frozen=True)
class InterlanguageLink:
    """仮リンク ``[!仮リンク|言語タグ|本家の記事名|表示]``。

    ``target`` は本家（``lang`` の言語版）の記事名、``label`` はこの記事での表示。
    HTML では赤字の内部リンクと、本家の記事への外部リンクを並べて出す。
    """

    lang: str
    target: str
    label: str


@dataclass(frozen=True)
class LanguageName:
    """言語名 ``[!言語|言語タグ]``。

    HTML では日本語の言語名に、ウィキテキストでは ``{{ISO639言語名|言語タグ}}`` になる。
    """

    lang: str


@dataclass(frozen=True)
class Bold:
    """太字 ``'''…'''``。中に内部リンク・仮リンク・言語名・脚注の印・点の印を入れられる。"""

    children: tuple[
        Text | RefMark | NoteMark | InternalLink | InterlanguageLink | LanguageName | FixMark, ...
    ]


@dataclass(frozen=True)
class RumorRange:
    """噂の範囲 ``[!噂|範囲の文]``。通常の記事では取り除き、噂込みの記事では中身にほどく。

    範囲の文には、文字・内部リンク・仮リンク・言語名・太字・出典の印・注釈の印・点の印・
    範囲の印を入れられる・原文（噂の範囲の入れ子は入れない）。二つの版への分け方は
    :mod:`wikiskill.variants`。
    """

    children: tuple[
        Text
        | RefMark
        | NoteMark
        | InternalLink
        | InterlanguageLink
        | LanguageName
        | FixMark
        | FixRange
        | Bold
        | Original,
        ...,
    ]


Inline: TypeAlias = (
    Text
    | RefMark
    | NoteMark
    | InternalLink
    | InterlanguageLink
    | LanguageName
    | FixMark
    | FixRange
    | Bold
    | RumorRange
    | Original
)
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


@dataclass(frozen=True)
class Figure:
    """画像。`source` は原稿からの相対の道、`caption` は図の説明。

    画像そのものは HTML を書き出すときに読み、`data:` の URI として埋め込む。
    ウィキテキストにはファイルの名前だけを書く。`line` は `![...](...)` を置いた行。
    """

    caption: str
    source: str
    line: int = field(default=0, compare=False)


@dataclass(frozen=True)
class SectionStub:
    """節スタブ ``[!節スタブ]``。行に単独で置く（段落の中には書けない）。"""

    line: int = field(default=0, compare=False)


Block: TypeAlias = Paragraph | BulletList | Figure | SectionStub
"""節や導入部の直下に置けるまとまり。"""


@dataclass(frozen=True)
class Section:
    """節。``blocks`` は見出しの直後から最初の子の節の前まで、``children`` は一段下の節。

    ``rumor`` は見出しの末尾に ``[!噂]`` を付けた節（子の節を含めて噂として扱う）であること。
    """

    level: int
    title: str
    blocks: tuple[Block, ...]
    children: tuple[Section, ...]
    line: int = field(default=0, compare=False)
    rumor: bool = False


# --- 設定欄 ----------------------------------------------------------------


@dataclass(frozen=True)
class InfoboxField:
    """Infobox の一項目（項目名と値）。"""

    name: str
    value: str
    line: int = field(default=0, compare=False)


@dataclass(frozen=True)
class Reference:
    """出典 ``[refs.キー]``。

    ``weak`` は弱い出典（攻略 Wiki・個人のブログ・SNS・まとめなど、本家が出典として認めない
    出どころ）であることを表す。弱い出典を指す印の直後には ``[!信頼性要検証]`` を付ける。
    """

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
    weak: bool = False
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
class Coordinate:
    """座標 ``[coord]``。

    ``lat``・``lon`` は十進の度、``type`` は本家の ``{{Coord}}`` の type（``city`` など）、
    ``display`` は表示の仕方（``title`` なら記事名の横に出す）。
    """

    lat: float
    lon: float
    type: str | None = None
    display: str = "title"
    line: int = field(default=0, compare=False)


@dataclass(frozen=True)
class Navbox:
    """Navbox ``[[navbox]]``。

    ``name`` は本家でのテンプレート名、``state`` は畳み方（``collapsed`` など）、
    ``items`` は並べる項目（順に list1, list2, … に入る）。
    """

    title: str
    name: str | None = None
    state: str | None = None
    items: tuple[str, ...] = ()
    line: int = field(default=0, compare=False)


@dataclass(frozen=True)
class Settings:
    """冒頭の TOML の設定欄の中身。

    ``infobox``・``references``・``notes`` は原稿に書いた順を保つ。
    ``notices`` は、印から決まる枠に足して貼る警告の枠（``観点`` など）。書いた順を保つ。
    ``notice_rule`` は、印から決まる枠の出し方（:data:`NOTICE_RULES`）。
    ``infobox_template`` は ``[infobox]`` の ``_template``（本家のテンプレートをそのまま使う
    ときの名前。項目名はそのまま本家の引数名として扱う）。
    ``infobox_images`` は ``[infobox]`` の ``_image_fields``（そのうち、本家がファイル名だけを
    受け取る引数の名前）。``_template`` を使うときにだけ意味を持つ。
    ``coord`` は ``[coord]`` の座標、``navboxes`` は ``[[navbox]]`` の並び、
    ``stub`` は ``[stub]`` で貼る記事スタブの本家のテンプレート名。
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
    notices: tuple[NoticeKind, ...] = ()
    notice_rule: NoticeRule = "多いときだけ"
    infobox_template: str | None = None
    infobox_images: tuple[str, ...] = ()
    coord: Coordinate | None = None
    navboxes: tuple[Navbox, ...] = ()
    stub: str | None = None


# --- 記事 ------------------------------------------------------------------


@dataclass(frozen=True)
class Article:
    """原稿を読み取った記事全体。

    ``lead`` は最初の ``## `` 見出しより前の導入部、``sections`` は ``## `` の節（一段目）の並び。
    """

    settings: Settings
    lead: tuple[Block, ...]
    sections: tuple[Section, ...]
    # 原稿ファイルの置き場。画像の道を解決するのに使う（文字列から読んだときは None）。
    base_dir: Path | None = field(default=None, compare=False, repr=False)
