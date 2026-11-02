"""一枚の HTML に入れた通常の記事と噂込みの記事を切り替える部品（ボタン・CSS・スクリプト）。

雛形の差し込み口 ``{{VARIANT_STYLE}}``・``{{VARIANT_SWITCH}}``・``{{VARIANT_SCRIPT}}`` に入れる。
外部の資源は読まない。スクリプトが動かなければ、開いたときの通常の記事がそのまま読める。

版を表す要素には ``data-variant="normal"``・``data-variant="rumor"`` を付け、隠す版には ``hidden``
を付ける。ボタンは ``data-show`` に見せる版の名前を持ち、今の版のボタンが ``aria-pressed="true"``。
"""

from __future__ import annotations

from wikiskill.html_escape import escape

__all__ = [
    "NORMAL",
    "RUMOR",
    "RUMOR_NOTE",
    "RUMOR_PREFIX",
    "SWITCH_SCRIPT",
    "SWITCH_STYLE",
    "VARIANT_LABELS",
    "switch_html",
    "variant_attrs",
]

NORMAL = "normal"
"""通常の記事の版の名前。"""

RUMOR = "rumor"
"""噂込みの記事の版の名前。"""

RUMOR_PREFIX = "rumor-"
"""噂込みの版の id（見出し・脚注・戻りリンク・目次のリンク先）に付ける接頭辞。"""

VARIANT_LABELS: dict[str, str] = {NORMAL: "通常の記事", RUMOR: "噂込みの記事"}
"""切り替えのボタンの文字。"""

RUMOR_NOTE = "噂込みの記事には、確かめられていない噂や利用者の見方が含まれます。"
"""ボタンの横に置く断り書き。自作の文。"""

SWITCH_STYLE = """\
/* 通常の記事と噂込みの記事の切り替え */
[hidden]{display:none!important}
.variant-switch{display:flex;flex-wrap:wrap;align-items:center;gap:6px 12px;
  margin:10px 0 6px;font-size:14px;line-height:1.5}
.variant-buttons{display:inline-flex}
.variant-switch button{font:inherit;margin:0;padding:4px 12px;border:1px solid #a2a9b1;
  background:#f8f9fa;color:#202122;cursor:pointer}
.variant-switch button+button{margin-left:-1px}
.variant-switch button:first-child{border-radius:2px 0 0 2px}
.variant-switch button:last-child{border-radius:0 2px 2px 0}
.variant-switch button:hover{background:#fff}
.variant-switch button[aria-pressed="true"]{position:relative;z-index:1;background:#eaf3ff;
  border-color:#36c;color:#36c;font-weight:bold;box-shadow:inset 0 1px 2px rgba(0,0,0,.15);
  cursor:default}
.variant-note{color:#54595d;font-size:13px}"""
"""切り替えの部品の CSS。雛形の ``<style>`` の中に入れる。"""

SWITCH_SCRIPT = """\
<script>
/* 通常の記事と噂込みの記事を切り替える（動かなければ通常の記事のまま読める）。
   雛形の目次の強調は隠れた版の見出しも数えるので、見えている見出しだけで付け直す。 */
(function () {
  function all(selector) {
    return Array.prototype.slice.call(document.querySelectorAll(selector));
  }
  var buttons = all('.variant-switch button[data-show]');
  var parts = all('[data-variant]');
  var heads = all('.art h2[id],.art h3[id],.art h4[id]');
  var items = all('[data-toc="left"] li');
  var queued = false;
  function spy() {
    queued = false;
    var active = '';
    for (var i = 0; i < heads.length; i++) {
      if (heads[i].offsetParent === null) { continue; }
      if (120 >= heads[i].getBoundingClientRect().top) { active = heads[i].id; } else { break; }
    }
    var current = null;
    items.forEach(function (li) {
      var on = li.getAttribute('data-id') === active;
      li.classList.toggle('act', on);
      if (on) { current = li; }
    });
    items.forEach(function (li) {
      li.classList.toggle('exp', current !== null && li.contains(current));
    });
  }
  function show(name) {
    parts.forEach(function (el) { el.hidden = el.getAttribute('data-variant') !== name; });
    buttons.forEach(function (button) {
      var pressed = button.getAttribute('data-show') === name;
      button.setAttribute('aria-pressed', pressed ? 'true' : 'false');
    });
    spy();
  }
  buttons.forEach(function (button) {
    button.addEventListener('click', function () { show(button.getAttribute('data-show')); });
  });
  window.addEventListener('scroll', function () {
    if (!queued) { queued = true; window.requestAnimationFrame(spy); }
  }, { passive: true });
  spy();
})();
</script>"""
"""切り替えのスクリプト。雛形の目次のスクリプトの後に置く（後に置くので、同じ描画の中で
雛形の強調を上書きする）。"""


def switch_html() -> str:
    """記事名のすぐ下に置く、切り替えのボタンと断り書き。開いたときは通常の記事が押されている。"""
    buttons = "".join(
        f'<button type="button" data-show="{name}" aria-pressed="{str(name == NORMAL).lower()}">'
        f"{escape(label)}</button>"
        for name, label in VARIANT_LABELS.items()
    )
    return (
        '<div class="variant-switch">\n'
        f'<div class="variant-buttons" role="group" aria-label="記事の版">{buttons}</div>\n'
        f'<span class="variant-note">{escape(RUMOR_NOTE)}</span>\n'
        "</div>"
    )


def variant_attrs(name: str) -> str:
    """版を表す要素に付ける属性（先頭に空白を含む）。通常の版のほかは ``hidden`` で隠す。"""
    return f' data-variant="{name}"' + ("" if name == NORMAL else " hidden")
