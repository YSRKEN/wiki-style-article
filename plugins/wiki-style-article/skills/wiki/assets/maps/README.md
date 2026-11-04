# 同梱の地図の形

`figure map` の `shape` に名前で渡せる地図の形（SVG）を置く。

## us-states.svg

- 題: Blank US Map (states only)
- 出典: <https://commons.wikimedia.org/wiki/File:Blank_US_Map_(states_only).svg>
- 作者: Heitordp（Wikimedia Commons）
- 許諾: CC0 1.0（パブリックドメインへの献呈）
- 寸法: 959 × 593（Albers 投影）
- 改変: 無し。ファイルはそのまま同梱し、色は描くときに CSS を重ねて付ける（元のファイルは書き換えない）。

### 地域の名前

州の `<path>` の `class` が 2 文字の州のコード（`al`、`ak`、…）。District of Columbia は
`class="dc"` の `circle`。原稿のデータでは大文字（`AL`、`DC`）で書けばよい
（大文字小文字だけ違うときは形の側に合わせる）。
