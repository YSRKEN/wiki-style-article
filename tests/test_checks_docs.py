"""docs/checks.md の規則の一覧が、実装と食い違っていないかの試験。"""

import re
from pathlib import Path

from wikiskill.checks import Level, notation, wording

DOC = Path(__file__).parent.parent / "docs" / "checks.md"

# パターンの表に載らない（関数で検査する）規則と、そのレベル。
FUNCTION_RULES: dict[str, Level] = {
    "REF-UNDEFINED": Level.ERROR,
    "NOTE-UNDEFINED": Level.ERROR,
    "REF-UNUSED": Level.ERROR,
    "NOTE-UNUSED": Level.ERROR,
    "REF-WIKIPEDIA": Level.ERROR,
    "REF-WIKIPEDIA-NAME": Level.WARNING,
    "REF-URL": Level.ERROR,
    "LINK-URL": Level.ERROR,
    "REF-DATE": Level.ERROR,
    "REF-ACCESS-DATE": Level.ERROR,
    "REF-WEAK-UNMARKED": Level.ERROR,
    "EMPTY-SECTION": Level.ERROR,
    "SELF-LINK": Level.ERROR,
    "LEAD-NO-BOLD": Level.WARNING,
    "TRIVIA-SECTION": Level.WARNING,
    "TYPE-UNKNOWN": Level.ERROR,
    "INFOBOX-MISSING": Level.ERROR,
    "INFOBOX-UNKNOWN-FIELD": Level.WARNING,
}


def implemented() -> dict[str, Level]:
    rules = dict(FUNCTION_RULES)
    for item in (*notation.PATTERNS, *wording.PATTERNS):
        rules[item.rule] = item.level
    return rules


def documented() -> dict[str, str | None]:
    """表の行から、規則 ID と、その行に書かれたレベル（なければ None）を取り出す。"""
    found: dict[str, str | None] = {}
    for line in DOC.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        match = re.fullmatch(r"`([A-Z][A-Z-]+)`", cells[0]) if cells else None
        if match is None:
            continue
        level = cells[1] if len(cells) > 1 and cells[1] in ("エラー", "警告") else None
        found[match[1]] = level
    return found


def test_実装した規則はすべて文書にある() -> None:
    assert set(implemented()) == set(documented())


def test_文書のレベルは実装と一致する() -> None:
    rules = implemented()
    for rule, label in documented().items():
        if label is not None:
            assert label == rules[rule].label, rule


def test_言葉の選びの規則はすべて警告() -> None:
    assert {item.level for item in wording.PATTERNS} == {Level.WARNING}
