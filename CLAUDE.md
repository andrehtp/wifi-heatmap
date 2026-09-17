# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

An interactive floor-plan editor (`editor de planta baixa`) for a Wi-Fi
heatmap project, plus two downstream, independent command-line tools that
consume the JSON it produces:

1. **`editor/`** — the user draws walls, windows, doors, furniture, and
   two kinds of points (signal measurement points and access points) with
   the mouse over a matplotlib canvas; persists everything to a JSON file.
2. **`medicoes/`** — imports dBm signal readings from a CSV table
   (keyed by point `id`) into the `leituras_dbm` field of the plan's
   measurement points.
3. **`heatmap/`** — an interactive matplotlib viewer that reads a plan
   JSON with populated `leituras_dbm`, interpolates a Wi-Fi signal
   heatmap over the floor plan (multiple interpolation methods and visual
   styles, switchable live), and exports the result to PNG or SVG.

These three are deliberately decoupled pipeline stages, each with its own
package and CLI entry script — `heatmap/` and `medicoes/` never import
from `editor/`, they only read the JSON contract it produces.

## Commands

```bash
# setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# run the editor (creates a new plan)
python planta_editor.py --largura 8 --altura 6 --saida planta_casa.json

# continue editing an existing plan (overwrite in place)
python planta_editor.py --entrada planta_casa.json --saida planta_casa.json

# custom snap grid step (default 0.25 m)
python planta_editor.py --passo 0.5

# import dBm readings from a CSV (columns: id, leitura1, leitura2, ...)
python importar_medicoes.py --planta planta_casa.json --tabela medicoes.csv

# open the interactive heatmap viewer for a plan with readings
python heatmap_gerador.py --entrada planta_casa.json
```

There is no build step, lint config, or test suite in this repo. When
verifying changes to any of `editor/`, `medicoes/`, `heatmap/`, there's no
display available in most agent environments — drive the classes/functions
headlessly instead of launching the real GUI:

```bash
MPLBACKEND=Agg python3 -c "
from editor.core import PlantaEditor
ed = PlantaEditor(largura=5, altura=5, output_path='/tmp/out.json')
ed._selecao['ponto'] = 0          # index into PALETAS['ponto'][1]
ed._adicionar_ponto(1.0, 1.0)     # call the same methods events.py calls
ed._salvar()
"

MPLBACKEND=Agg python3 -c "
from pathlib import Path
from heatmap.io import carregar_planta
from heatmap.core import HeatmapViewer
dados = carregar_planta('planta_trabalho.json')
v = HeatmapViewer(dados, saida_base=Path('/tmp/mapa'))
v.metodo, v.estilo = 'idw', 'campo_continuo'  # or any key in MODOS_INTERPOLACAO/MODOS_RENDER
v._redesenhar()
v._exportar('png')   # writes /tmp/mapa.png
"
```
`matplotlib` is pinned to `3.10.9` in `requirements.txt` — 3.11.0/3.11.1
have a known bug (matplotlib#32222) that breaks `TextBox` on window
resize. Only bump past 3.10.9 once 3.11.2+ is released. No other
third-party dependency was added for `medicoes/`/`heatmap/` — CSV parsing
uses the stdlib `csv` module and interpolation is plain `numpy` (already a
transitive matplotlib dependency), no `scipy`/`pandas`.

## Architecture

Entry point: `planta_editor.py` → `editor.cli:main` → parses `argparse`
flags and instantiates `editor.core.PlantaEditor`.

`PlantaEditor` (`editor/core.py`) is a single class assembled from mixins,
each in its own file under `editor/`:

| Module | Mixin | Responsibility |
|---|---|---|
| `elements.py` | `ElementsMixin` | Creating walls/furniture/points, undo snapshots, JSON load/save |
| `events.py` | `EventsMixin` | Keyboard/mouse dispatch, mode switching, click accumulation |
| `edit_panel.py` | `EditPanelMixin` | Right-click "edit an existing object" form |
| `hit_testing.py` | `HitTestingMixin` | Finding which object is under the cursor, category → list lookup |
| `rendering.py` | `DrawingMixin`, `HudMixin` | Full canvas redraw + live cursor HUD (crosshair, snap, tooltip via blitting) |
| `navigation.py` | `NavigationMixin` | Pan (space+drag / middle button), scroll-zoom, "fit view" |
| `widgets.py` | `WidgetsMixin` | matplotlib `Button`/`TextBox` side-panel widgets, mode-palette selection |
| `constants.py` | — | All static config: `USAGE` help text, keybindings, palettes, styles |
| `geometry.py` | — | Pure geometry helpers (point-to-segment/rectangle distance, number formatting) |

There is no ORM/DB — all state is plain Python lists of dicts on the
`PlantaEditor` instance (`self.paredes`, `self.moveis`,
`self.pontos_medicao`), serialized as-is to JSON.

### State model

Elements are plain dicts, not dataclasses, appended straight into one of
three lists. Any key added to a dict flows through to the saved JSON with
no changes needed in `_salvar`.

- **Walls** (`self.paredes`): `{"tipo", "x1","y1","x2","y2", "espessura", "material"}`. `tipo` is one of `MODOS_SEGMENTO` (`parede`, `meia_parede`, `janela`, `porta`).
- **Furniture** (`self.moveis`): `{"tipo", "material", "x","y","largura","profundidade"}`.
- **Points** (`self.pontos_medicao`): `{"id", "x", "y", "tipo"}` where `tipo` is `"medicao"` or `"access_point"`. Points with `tipo == "medicao"` also carry `"leituras_dbm": []` — created empty; a future measurement stage is expected to fill it with up to 5 dBm readings taken over a ~25–30s window. `access_point` points intentionally do **not** get `leituras_dbm`.

JSON shape written by `_salvar` (`editor/elements.py`):
```json
{"paredes": [...], "moveis": [...], "pontos_medicao": [...]}
```
`_carregar` (`editor/elements.py`) migrates old JSON files on load via
`setdefault` (e.g. old walls without `"tipo"` → `"parede"`; old points
without `"tipo"`/`"leituras_dbm"` → `"medicao"` + `[]`). When adding a new
field to any element type, follow this same load-time migration pattern
rather than rewriting existing `.json` files by hand.

### The mode/palette pattern (central to how the editor is extended)

This is the mechanism every drawing mode is built on, and the one to reuse
for any new per-mode "pick a sub-option" UI:

1. `TECLAS_MODO` (`constants.py`) maps a keypress to a mode string
   (`self.modo`), handled in `EventsMixin._on_key`.
2. `PALETAS` (`constants.py`) maps a mode string to `(rotulo, [opções])` —
   e.g. `"parede": ("material", ["concreto", "tijolo", ...])`,
   `"ponto": ("tipo", ["medicao", "access_point"])`. Digit keys `1`-`9`
   (`_on_key` → `_selecionar_opcao`) cycle through whatever `PALETAS[modo]`
   contains; `self._selecao` (dict, one index per mode, initialized from
   `PALETAS` in `PlantaEditor.__init__`) remembers the last choice per
   mode.
3. `WidgetsMixin._opcao_atual(modo)` reads the currently selected option;
   the `_adicionar_*` methods in `elements.py` call it to decide what to
   stamp onto the new element (no terminal prompts anywhere — the side
   panel, built generically from `PALETAS` in
   `DrawingMixin._atualizar_painel`, always reflects the live selection).
4. Click counting: `DrawingMixin._cliques_necessarios()` returns how many
   clicks the current mode needs (1 for `"ponto"`, 2 for segment/furniture
   modes); `EventsMixin._on_click` accumulates clicks and dispatches to
   the right `_adicionar_*` once enough are collected.

Adding a new mode or a new per-mode option (e.g. a new point type) means
touching `TECLAS_MODO`/`PALETAS` in `constants.py` plus the relevant
`_adicionar_*`/rendering/edit-panel branches — not inventing new
menu/dialog plumbing.

### Editing existing objects

Right-click → `EditPanelMixin._clique_direito` → `_objeto_sob` (hit test)
→ `_abrir_edicao(categoria, indice)`, which populates the side-panel form
from a *working copy* (`self._edicao`) of the object; nothing mutates the
real list until "aplicar" (`_aplicar_edicao`). The "tipo"/"material"
buttons in this form call `_ciclar("tipo"|"material")`, which cycles
`self._edicao["tipo"]`/`["material"]` through the relevant `PALETAS`
entry per category (`parede`, `movel`, `ponto`) — each category has its
own branch in `_ciclar` since the fields and constraints differ (e.g.
switching a point's `tipo` also adds/removes `leituras_dbm`; switching a
wall's `tipo` recomputes `espessura` from its material).

### Rendering

`DrawingMixin._redesenhar` fully clears and redraws the `Axes` (walls,
furniture, points, selection outline, pending clicks) on every mutation —
there's no incremental diffing for the main drawing. The live cursor HUD
(crosshair, snap preview, hover tooltip) is separate and uses matplotlib
blitting (`HudMixin`) for performance, since it redraws on every mouse-move
event. Styling per element type lives in `constants.py`
(`ESTILO_SEGMENTO` for walls, `ESTILO_PONTO` for points — color/marker per
`tipo`); `rendering.py` builds the legend from whatever types are actually
present in the current plan.

## `medicoes/` — CSV measurement importer

Entry point: `importar_medicoes.py` → `medicoes.cli:main`. Pure functions
in `medicoes/core.py`, no class/GUI state:
`carregar_planta`/`salvar_planta` (plain `json.load`/`json.dump`),
`ler_csv_leituras` (parses any CSV with an `id` column plus any number of
reading columns via `csv.DictReader`, blank cells skipped, bad cells
warned-and-skipped), `aplicar_leituras` (matches by `id` against
`dados["pontos_medicao"]`, **replaces** — does not append to —
`leituras_dbm`, truncates at `MAX_LEITURAS = 5`, warns and skips unknown
ids or `access_point` ids). Never raises on bad data rows, only on a CSV
missing the `id` column.

## `heatmap/` — interactive heatmap viewer

Entry point: `heatmap_gerador.py` → `heatmap.cli:main` → builds
`heatmap.core.HeatmapViewer` (mixes in `heatmap.widgets.WidgetsMixin`,
analogous in spirit to `PlantaEditor` but read-only, no editing/navigation
mixins). `heatmap/constants.py` duplicates the handful of style dicts it
needs from `editor/constants.py` rather than importing it, to keep the
two packages decoupled.

- `heatmap/interpolation.py`: `preparar_amostras(dados)` splits
  `tipo=="medicao"` points into ones with data (mean of `leituras_dbm`
  used as the scalar value) and empty ones (drawn hollow, excluded from
  interpolation); `access_point` points are never a data source. Three
  numpy-only grid functions sharing the signature
  `(grid_x, grid_y, coords, valores) -> grid`: `idw`, `gaussiana`,
  `vizinho_mais_proximo` (nearest-neighbor via `np.argmin`, no
  `scipy.spatial`), registered in `MODOS_INTERPOLACAO`.
- `heatmap/rendering.py`: `desenhar_planta_base` is a read-only
  reimplementation of the relevant slice of `DrawingMixin._redesenhar`.
  Three overlay styles registered in `MODOS_RENDER`, each tagged
  `"grade"` (consumes the interpolated grid — `campo_continuo` via
  `pcolormesh`, `bandas_contorno` via `contourf`) or `"pontos"` (consumes
  raw samples directly — `blobs`, concentric translucent circles per
  point, no grid); `HeatmapViewer._redesenhar` dispatches on that tag.
- `heatmap/widgets.py` introduces `matplotlib.widgets.RadioButtons` (not
  used anywhere in `editor/`, which relies on digit-key palettes instead)
  to pick the method/style live, plus a `TextBox` + two `Button`s wired to
  `HeatmapViewer._exportar("png"|"svg")` (`fig.savefig`, path taken from
  the `TextBox`, default derived from `--entrada`/`--saida`).

Extending either package (a new interpolation method, a new render style,
a new CSV column convention) follows the same registry pattern —
`MODOS_INTERPOLACAO`/`MODOS_RENDER` dicts, not new dispatch plumbing.
