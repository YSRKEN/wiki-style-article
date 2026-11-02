"""プラグインとマーケットプレイスのマニフェスト・LICENSE が互いに食い違わないかを見る。"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
MARKETPLACE = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
ENTRY = MARKETPLACE["plugins"][0]
PLUGIN_DIR = (ROOT / ENTRY["source"]).resolve()
PLUGIN = json.loads((PLUGIN_DIR / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))


def test_マーケットプレイスの項目はプラグインの名前と一致する() -> None:
    # 違うと、利用者が plugin.json の名前で入れようとして not found になる
    assert len(MARKETPLACE["plugins"]) == 1
    assert ENTRY["name"] == PLUGIN["name"] == MARKETPLACE["name"]


def test_マーケットプレイスの_source_はスキルと担当を持つフォルダを指す() -> None:
    assert ENTRY["source"].startswith("./")
    assert (PLUGIN_DIR / "skills" / "wiki" / "SKILL.md").is_file()
    assert (PLUGIN_DIR / "agents" / "researcher.md").is_file()


def test_版は_x_y_z_の形() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", PLUGIN["version"])


def test_入れた人に写る_LICENSE_は根の_LICENSE_と同じ() -> None:
    # 入れた人の手元に写るのはプラグインのフォルダだけなので、そこにも同じ LICENSE を置く
    root = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert (PLUGIN_DIR / "LICENSE").read_text(encoding="utf-8") == root


def test_参照の文書の_CC_BY_SA_の表示がある() -> None:
    notice = PLUGIN_DIR / "skills" / "wiki" / "references" / "LICENSE.md"
    assert "CC BY-SA 4.0" in notice.read_text(encoding="utf-8")
    assert "references/" in (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert PLUGIN["license"] == "MIT AND CC-BY-SA-4.0"
