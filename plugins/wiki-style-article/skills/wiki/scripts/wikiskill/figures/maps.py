"""地図の SVG を、データの色で塗り分けて描く。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from wikiskill.figures.assets import ASSETS_DIR
from wikiskill.figures.data import boolean, read_toml, reject_unknown, string
from wikiskill.figures.errors import FigureError
from wikiskill.figures.svg import escape, hex_color, legend, number

DEFAULT_SHAPE: Final = "us-states"
DEFAULT_FILL: Final = "#d9d9d9"
DEFAULT_BACKGROUND: Final = "#ffffff"
DEFAULT_LEGEND: Final = True
ROOT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"<svg\b(?P<attributes>[^>]*)>", re.IGNORECASE | re.DOTALL
)
ATTRIBUTE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"""([A-Za-z_:][\w:.-]*)\s*=\s*(?:"([^"]*)"|'([^']*)')"""
)
TAG_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"<(?!/|!)(?P<name>[A-Za-z][\w:.-]*)\b(?P<attributes>[^>]*)>", re.DOTALL
)
REGION_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_-]+$")
LENGTH_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*(?:px)?\s*$")
SKIP_TAGS: Final[frozenset[str]] = frozenset(
    {
        "clippath",
        "defs",
        "desc",
        "filter",
        "lineargradient",
        "marker",
        "mask",
        "metadata",
        "pattern",
        "radialgradient",
        "style",
        "svg",
        "symbol",
        "title",
    }
)


@dataclass(frozen=True, slots=True)
class MapData:
    """地図のデータ（TOML）を読んだ結果。"""

    title: str
    shape: str
    background: str | None
    show_legend: bool
    colors: dict[str, str]
    regions: dict[str, str]
    base_dir: Path


@dataclass(frozen=True, slots=True)
class Shape:
    """色を塗る元になる SVG。"""

    width: float
    height: float
    view_box: str
    inner: str
    regions: dict[str, tuple[str, ...]]
    namespaces: dict[str, str]


def render_map(data_path: Path, *, shape: str | None = None) -> str:
    """地図のデータを読み、塗り分けた SVG を返す。

    Parameters
    ----------
    data_path : Path
        地図のデータ（TOML）の道。
    shape : str | None
        同梱の形の名前か、SVG の道。省くとデータの shape。

    Returns
    -------
    str
        SVG の文字列。

    Raises
    ------
    FigureError
        データか形が正しくないとき。
    """
    data = _load_data(data_path)
    shape_path = _resolve_shape(shape if shape is not None else data.shape, data.base_dir)
    base = _read_shape(shape_path)
    assigned = _resolve_regions(data, base.regions)
    used = {color for _, color in assigned}
    items = [(name, color) for name, color in data.colors.items() if color in used]
    legend_markup, legend_height = legend(items, base.width) if data.show_legend else ("", 0.0)
    total_height = base.height + legend_height
    attributes = [
        'xmlns="http://www.w3.org/2000/svg"',
        f'width="{number(base.width)}"',
        f'height="{number(total_height)}"',
        f'viewBox="0 0 {number(base.width)} {number(total_height)}"',
        'role="img"',
    ]
    attributes.extend(f'{name}="{escape(value)}"' for name, value in base.namespaces.items())
    if data.title:
        attributes.append(f'aria-label="{escape(data.title)}"')
    parts = [f"<svg {' '.join(attributes)}>"]
    if data.title:
        parts.append(f"<title>{escape(data.title)}</title>")
    parts.append(
        f'<svg x="0" y="0" width="{number(base.width)}" height="{number(base.height)}" '
        f'viewBox="{base.view_box}">'
    )
    if data.background is not None:
        parts.append(
            f'<rect x="0" y="0" width="{number(base.width)}" height="{number(base.height)}" '
            f'fill="{data.background}"/>'
        )
    parts.append(base.inner)
    parts.append(f"<style>{_css(base.regions, assigned)}</style>")
    parts.append("</svg>")
    if legend_markup:
        parts.append(f'<g transform="translate(0,{number(base.height)})">{legend_markup}</g>')
    parts.append("</svg>")
    return "".join(parts)


def _load_data(path: Path) -> MapData:
    raw = read_toml(path)
    where = "地図のデータ"
    reject_unknown(
        raw, frozenset({"title", "shape", "background", "legend", "colors", "regions"}), where
    )
    title = string(raw, "title", "", where)
    shape = string(raw, "shape", DEFAULT_SHAPE, where)
    background_raw = string(raw, "background", DEFAULT_BACKGROUND, where)
    background = (
        None
        if background_raw.lower() in {"none", "transparent"}
        else hex_color(background_raw, where=f"{where} の background")
    )
    show_legend = boolean(raw, "legend", DEFAULT_LEGEND, where)
    colors = _read_colors(raw, where)
    regions = _read_regions(raw, where)
    for name, color in regions.items():
        if color not in colors:
            raise FigureError(f"{where} の regions の {name} の色 {color!r} が colors に無い")
    return MapData(
        title=title,
        shape=shape,
        background=background,
        show_legend=show_legend,
        colors=colors,
        regions=regions,
        base_dir=path.parent,
    )


def _read_colors(raw: dict[str, object], where: str) -> dict[str, str]:
    value = raw.get("colors")
    if not isinstance(value, dict):
        raise FigureError(f"{where} の colors は表で書く")
    table = cast(dict[str, object], value)
    if not table:
        raise FigureError(f"{where} の colors が空")
    colors: dict[str, str] = {}
    for name, color in table.items():
        if not name.strip():
            raise FigureError(f"{where} の colors に名前の無い色がある")
        colors[name] = hex_color(color, where=f"{where} の colors の {name}")
    return colors


def _read_regions(raw: dict[str, object], where: str) -> dict[str, str]:
    value = raw.get("regions")
    if not isinstance(value, dict):
        raise FigureError(f"{where} の regions は表で書く")
    table = cast(dict[str, object], value)
    if not table:
        raise FigureError(f"{where} の regions が空")
    regions: dict[str, str] = {}
    for name, color in table.items():
        if not isinstance(color, str):
            raise FigureError(f"{where} の regions の {name} は色の名前で書く")
        regions[name] = color
    return regions


def _resolve_shape(name: str, base_dir: Path) -> Path:
    if not name.strip():
        raise FigureError("地図の形の名前が空")
    for candidate in (ASSETS_DIR / name, ASSETS_DIR / f"{name}.svg"):
        if candidate.is_file():
            return candidate
    path = Path(name)
    if not path.is_absolute():
        path = base_dir / path
    if not path.is_file():
        bundled = ", ".join(sorted(item.stem for item in ASSETS_DIR.glob("*.svg")))
        raise FigureError(f"地図の形が見つからない: {name}（同梱の形: {bundled or 'なし'}）")
    return path


def _attributes(text: str) -> dict[str, str]:
    attributes: dict[str, str] = {}
    for match in ATTRIBUTE_PATTERN.finditer(text):
        value = match.group(2) if match.group(2) is not None else match.group(3)
        attributes[match.group(1).lower()] = value or ""
    return attributes


def _read_shape(path: Path) -> Shape:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        raise FigureError(f"形の SVG を読めない: {path}（{error}）") from error
    root = ROOT_PATTERN.search(text)
    if root is None:
        raise FigureError(f"形の SVG に <svg> が無い: {path.name}")
    end = text.lower().rfind("</svg>")
    if end < root.end():
        raise FigureError(f"形の SVG の </svg> が無い: {path.name}")
    attributes = _attributes(root.group("attributes"))
    view_box, width, height = _geometry(attributes, path)
    inner = text[root.end() : end]
    regions = _find_regions(inner)
    namespaces = {
        name: value for name, value in attributes.items() if name.startswith("xmlns:") and value
    }
    return Shape(
        width=width,
        height=height,
        view_box=view_box,
        inner=inner,
        regions=regions,
        namespaces=namespaces,
    )


def _geometry(attributes: dict[str, str], path: Path) -> tuple[str, float, float]:
    raw_box = attributes.get("viewbox")
    if raw_box is not None and raw_box.strip() and raw_box.strip().lower() != "none":
        parts = [part for part in re.split(r"[\s,]+", raw_box.strip()) if part]
        if len(parts) != 4:
            raise FigureError(f"形の SVG の viewBox が 4 つの数でない: {path.name}")
        try:
            values = [float(part) for part in parts]
        except ValueError as error:
            raise FigureError(f"形の SVG の viewBox に数でないものがある: {path.name}") from error
        if values[2] <= 0 or values[3] <= 0:
            raise FigureError(f"形の SVG の viewBox の幅か高さが 0 以下: {path.name}")
        return " ".join(number(value) for value in values), values[2], values[3]
    width = _length(attributes.get("width"))
    height = _length(attributes.get("height"))
    if width is None or height is None:
        raise FigureError(f"形の SVG に幅と高さ（viewBox か width/height）が無い: {path.name}")
    return f"0 0 {number(width)} {number(height)}", width, height


def _length(value: str | None) -> float | None:
    if value is None:
        return None
    match = LENGTH_PATTERN.fullmatch(value)
    if match is None:
        return None
    length = float(match.group(1))
    return length if length > 0 else None


def _find_regions(inner: str) -> dict[str, tuple[str, ...]]:
    selectors: dict[str, list[str]] = {}
    for match in TAG_PATTERN.finditer(inner):
        if match.group("name").lower() in SKIP_TAGS:
            continue
        attributes = _attributes(match.group("attributes"))
        pairs: list[tuple[str, str]] = []
        for token in attributes.get("data-region", "").split():
            _check_region_name(token)
            pairs.append((token, f'[data-region="{token}"]'))
        for token in attributes.get("class", "").split():
            if token.startswith("region-"):
                key = token[len("region-") :]
                _check_region_name(key)
                pairs.append((key, f".{token}"))
            elif len(token) <= 3 and REGION_NAME_PATTERN.fullmatch(token) is not None:
                pairs.append((token, f".{token}"))
        for key, selector in pairs:
            found = selectors.setdefault(key, [])
            if selector not in found:
                found.append(selector)
    if not selectors:
        raise FigureError("形の SVG に色を塗れる地域が無い（class か data-region を付ける）")
    return {key: tuple(value) for key, value in selectors.items()}


def _check_region_name(name: str) -> None:
    if REGION_NAME_PATTERN.fullmatch(name) is None:
        raise FigureError(f"地域の名前に使えない文字がある: {name!r}")


def _resolve_regions(data: MapData, shape: dict[str, tuple[str, ...]]) -> list[tuple[str, str]]:
    by_lower: dict[str, list[str]] = {}
    for key in shape:
        by_lower.setdefault(key.lower(), []).append(key)
    assigned: list[tuple[str, str]] = []
    for name, color in data.regions.items():
        if name in shape:
            key = name
        else:
            candidates = by_lower.get(name.lower(), [])
            if not candidates:
                raise FigureError(f"地図のデータの地域 {name!r} が形に無い")
            if len(candidates) > 1:
                names = "、".join(candidates)
                raise FigureError(
                    f"地図のデータの地域 {name!r} は大文字小文字だけ違う地域が複数ある: {names}"
                )
            key = candidates[0]
        assigned.append((key, data.colors[color]))
    return assigned


def _css(shape: dict[str, tuple[str, ...]], assigned: list[tuple[str, str]]) -> str:
    defaults = ", ".join(selector for selectors in shape.values() for selector in selectors)
    rules = [f"{defaults} {{ fill: {DEFAULT_FILL} !important; }}"]
    for key, color in assigned:
        selectors = ", ".join(shape[key])
        rules.append(f"{selectors} {{ fill: {color} !important; }}")
    return "\n".join(rules)
