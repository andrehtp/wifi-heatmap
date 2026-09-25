# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

An interactive floor-plan editor (`editor de planta baixa`) for a Wi-Fi
heatmap project, plus a downstream, independent command-line viewer that
consumes the JSON it produces:

1. **`editor/`** — the user draws walls (polygons with real thickness),
   openings (windows, doors, free passages) that cut the walls they sit
   on, furniture, and two kinds of points (signal measurement points and
   access points) with the mouse over a matplotlib canvas; it can also
   distribute measurement points automatically. Everything persists to a
   JSON file.
2. **`heatmap/`** — an interactive matplotlib viewer that reads a plan
   JSON plus a CSV table of dBm readings (keyed by point `id`),
   interpolates a Wi-Fi signal heatmap over the floor plan (9
   interpolation methods — geostatistical and propagation-model based —
   and 3 visual styles, switchable live, with leave-one-out validation),
   and exports the result to PNG or SVG.

The two are deliberately decoupled pipeline stages, each with its own
package and CLI entry script — `heatmap/` never imports from `editor/`,
it only reads the JSON contract the editor produces. Readings are **not**
stored in the plan JSON: measurement points are just `{id, x, y, tipo}`
and the heatmap joins them with the CSV by `id`. (There used to be a
`medicoes/` package that copied CSV readings into `leituras_dbm` in the
JSON; it was removed — its CSV reader lives on in `heatmap/tabela.py`.)

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

# only write the blank CSV readings table for the plan's measurement points
# (id + 3 empty reading columns), no window; refuses an existing CSV unless --forcar
python planta_editor.py --entrada planta_casa.json --gerar-tabela medicao.csv [--leituras 3] [--forcar]

# open the interactive heatmap viewer (CSV columns: id, leitura1, leitura2, ...)
# --agregacao {potencia,dbm,mediana}: how a point's readings are combined (default potencia)
python heatmap_gerador.py --entrada planta_casa.json --tabela medicao.csv
```

There is no build step, lint config, or test suite in this repo. When
verifying changes to `editor/` or `heatmap/`, there's no display
available in most agent environments — drive the classes/functions
headlessly instead of launching the real GUI:

```bash
MPLBACKEND=Agg python3 -c "
from editor.core import PlantaEditor
ed = PlantaEditor(largura=5, altura=5, output_path='/tmp/out.json')
ed._selecao['parede'] = 0                    # index into PALETAS['parede'][1]
ed._adicionar_parede('parede', [(0,0),(4,0),(4,3),(0,3)], fechada=True)
ed._adicionar_abertura('porta', 1.0, 0.0, 1.8, 0.0)   # cuts the wall
ed._selecao['distribuir'] = 2                # 'quantidade'
ed._valor_distribuicao['quantidade'] = 6
ed._distribuir()                             # whole plan; _distribuir(x, y) = one room
ed._salvar()
"

MPLBACKEND=Agg python3 -c "
from pathlib import Path
from heatmap.io import carregar_planta
from heatmap.core import HeatmapViewer
from heatmap.tabela import ler_csv_leituras, associar_leituras
dados = carregar_planta('/tmp/out.json')
leituras, _ = associar_leituras(dados, ler_csv_leituras('medicao.csv')[0])
v = HeatmapViewer(dados, saida_base=Path('/tmp/mapa'), leituras_por_id=leituras,
                  agregacao='potencia', validar=False)  # validar=True prints the LOOCV table
v.metodo, v.estilo = 'hibrido', 'campo_continuo'  # any key in MODOS_INTERPOLACAO/MODOS_RENDER
v.area, v.escala = 'dentro', 'fixa'               # MODOS_AREA / MODOS_ESCALA
v._redesenhar()
v.fig.savefig('/tmp/mapa.png')  # _exportar reads the path from the TextBox
"
```
Setting `v.metodo` directly doesn't move the radio buttons (the image is
right, the panel isn't); to drive the real callbacks use
`v._radio_metodo.set_active(i)` (same for `_radio_estilo`, `_radio_area`,
`_radio_escala`). The parameter box is `v._tb_param` (`set_val("2")` +
`_redesenhar()`). Methods can also be called standalone:
`fn(grid_x, grid_y, coords, valores, montar_ctx(dados, parametro))`, and
`heatmap.validacao.tabela_loocv(dados, coords, valores)` prints the
comparison table.
To exercise the real event handlers (click accumulation, enter, dragging)
pass fake events: `ed._on_click(SimpleNamespace(inaxes=ed.ax, xdata=x,
ydata=y, button=1, x=0, y=0))`, `ed._on_key(SimpleNamespace(key="enter"))`,
`ed._on_motion(...)`/`ed._on_release(...)`.

`matplotlib` is pinned to `3.10.9` in `requirements.txt` — 3.11.0/3.11.1
have a known bug (matplotlib#32222) that breaks `TextBox` on window
resize. Only bump past 3.10.9 once 3.11.2+ is released. The only other
third-party dependency is `shapely` (polygon walls: buffering, cutting,
unions, room detection, point-in-polygon, and the vectorised wall-crossing
count of the multi-wall model). CSV parsing uses the stdlib `csv` module
and interpolation/k-means are plain `numpy` (kriging and RBF are small
N×N systems via `np.linalg.solve`; Delaunay comes from
`matplotlib.tri`), no `scipy`/`pandas`/`pykrige`/`sklearn`.

## Architecture

Entry point: `planta_editor.py` → `editor.cli:main` → parses `argparse`
flags and instantiates `editor.core.PlantaEditor`.

`PlantaEditor` (`editor/core.py`) is a single class assembled from mixins,
each in its own file under `editor/`:

| Module | Mixin | Responsibility |
|---|---|---|
| `elements.py` | `ElementsMixin` | Creating walls/openings/furniture/points, the point distributor entry, undo snapshots, JSON load/save + migration |
| `events.py` | `EventsMixin` | Keyboard/mouse dispatch, mode switching, click accumulation, dragging the selected object |
| `edit_panel.py` | `EditPanelMixin` | Right-click "edit an existing object" form |
| `hit_testing.py` | `HitTestingMixin` | Finding which object is under the cursor, category → list lookup |
| `rendering.py` | `DrawingMixin`, `HudMixin` | Full canvas redraw, snapping + live cursor HUD (crosshair, rubber band, tooltip via blitting) |
| `navigation.py` | `NavigationMixin` | Pan (space+drag / middle button), scroll-zoom, "fit view" |
| `widgets.py` | `WidgetsMixin` | matplotlib `Button`/`TextBox` side-panel widgets, mode-palette selection, per-mode parameter boxes |
| `poligonos.py` | — | Stateless shapely helpers: dict ↔ `Polygon`, wall from polyline, cut/restore by openings, rooms, edge snap |
| `tabela.py` | — | `escrever_tabela`: blank CSV (`id,leitura_1..N`) of the measurement points, the format `heatmap/tabela.py` reads. Used by `--gerar-tabela` (reads the JSON directly, never builds `PlantaEditor`) and by `ElementsMixin._gerar_tabela` (key `t` / button in `ponto` mode's parameter area; saves the JSON first; an existing CSV is only overwritten on a second consecutive request, tracked in `self._confirmar_tabela`) |
| `distribuicao.py` | — | Point distribution methods (`MODOS_DISTRIBUICAO` registry) + walking-order sort |
| `constants.py` | — | All static config: `USAGE` help text, keybindings, palettes, styles |
| `geometry.py` | — | Pure geometry helpers (point-to-segment/rectangle distance, number formatting) |

There is no ORM/DB — all state is plain Python lists of dicts on the
`PlantaEditor` instance (`self.paredes`, `self.aberturas`, `self.moveis`,
`self.pontos_medicao`, `self.guias`), serialized as-is to JSON.
Derived shapely geometry (wall polygons, rooms, snap edges) is cached in
`self._cache_geo`, which `_redesenhar` clears — every mutation redraws, so
the cache never outlives a change.

### State model

Elements are plain dicts, not dataclasses. Any key added to a dict flows
through to the saved JSON with no changes needed in `_salvar`.

- **Walls** (`self.paredes`): `{"tipo", "material", "vertices": [[x,y],...], "furos": [[[x,y],...]]}`. `tipo` is `parede` or `meia_parede`; `furos` (holes) only exists for a wall drawn as a closed ring. Default material is `alvenaria`. There is no stored thickness — the polygon *is* the wall.
- **Openings** (`self.aberturas`): `{"tipo", "material", "x1","y1","x2","y2", "recorte": [wall dicts]}`. `tipo` is one of `MODOS_ABERTURA` (`janela`, `porta`, `vao`). `recorte` holds the wall pieces the opening removed; it's where the opening is drawn and what gets given back when the opening is deleted or moved.
- **Furniture** (`self.moveis`): `{"tipo", "nome", "material", "x","y","largura","profundidade"}`. `tipo` is one of `TIPOS_MOVEL` (six fixed kinds + `personalizado`, whose `nome`/`material` come from the side-panel boxes).
- **Points** (`self.pontos_medicao`): `{"id", "x", "y", "tipo"}` where `tipo` is `"medicao"` or `"access_point"`. No readings — those live in the CSV.
- **Guides** (`self.guias`): `{"x1","y1","x2","y2"}` — walls of old line-based plans, kept only as a drawing/snap reference for redrawing; never read by the heatmap. `h` hides them.

JSON shape written by `_salvar` (`editor/elements.py`):
```json
{"paredes": [...], "aberturas": [...], "moveis": [...], "pontos_medicao": [...], "guias": [...]}
```
`_carregar` (`editor/elements.py`) migrates old JSON files on load:
line walls (`x1..y2`, no `vertices`) → `guias`, old `janela`/`porta`
segments → `aberturas` with `recorte: []`, `leituras_dbm` dropped from
points, old furniture types → new ones via `MIGRACAO_MOVEL` (old `tipo`
kept as `nome`), plus `setdefault`s. If the loaded file was in the old
format and the editor saves over it, the first save copies the original
to `<name>.antigo.json` (the `*.json` files are gitignored, so that copy
is the only way back). When adding a new field to any element type,
follow this same load-time migration pattern rather than rewriting
existing `.json` files by hand.

### Walls and openings (`poligonos.py`)

- `parede_de_polilinha(pontos, espessura, alinhamento, fechada, existentes)`
  buffers the clicked polyline (`join_style="mitre"`). `alinhamento` is
  which side of the clicked line the thickness goes to (`centro`,
  `esquerda`, `direita`, relative to drawing direction; for a closed ring
  it's resolved against the ring's orientation). Free ends are flat (the
  wall is exactly as long as clicked); an end touching an existing wall is
  extended to fill the L-corner notch, clipped to the touched wall's
  infinite strip so it never sticks out.
- `cortar(paredes, x1,y1,x2,y2)` subtracts a `PROF_CORTE`-deep band around
  the opening segment, **only** from walls that run along the segment
  (overlap ≥ min(0.2 m, half the segment)) — a perpendicular wall merely
  touching the opening's end, or a parallel wall nearby, is untouched.
  A new wall is also cut by every existing opening it crosses, so drawing
  order doesn't matter.
- `restaurar(paredes, recorte)` gives the pieces back and unions them with
  touching walls of the same tipo/material.
- `comodos(paredes, aberturas)` = holes of the union of walls + opening
  footprints (openings count as room boundaries). If no contour is
  closed it falls back to `convex_hull - walls` with `fechado=False`.

### The mode/palette pattern (central to how the editor is extended)

This is the mechanism every drawing mode is built on, and the one to reuse
for any new per-mode "pick a sub-option" UI:

1. `TECLAS_MODO` (`constants.py`) maps a keypress to a mode string
   (`self.modo`), handled in `EventsMixin._on_key`.
2. `PALETAS` (`constants.py`) maps a mode string to `(rotulo, [opções])` —
   e.g. `"parede": ("material", ["alvenaria", "concreto", ...])`,
   `"distribuir": ("metodo", [keys of MODOS_DISTRIBUICAO])`. Digit keys
   `1`-`9` (`_on_key` → `_selecionar_opcao`) cycle through whatever
   `PALETAS[modo]` contains; `self._selecao` (dict, one index per mode,
   initialized from `PALETAS` in `PlantaEditor.__init__`) remembers the
   last choice per mode.
3. `WidgetsMixin._opcao_atual(modo)` reads the currently selected option;
   the `_adicionar_*` methods in `elements.py` call it to decide what to
   stamp onto the new element (no terminal prompts anywhere — the side
   panel, built generically from `PALETAS` in
   `DrawingMixin._atualizar_painel`, always reflects the live selection).
4. Free-form per-mode parameters (wall thickness/alignment, custom
   furniture name/material, distribution value/margin) go through the
   parameter area: `WidgetsMixin._config_parametros()` declares, per
   mode, a title + up to two `TextBox`es + one `Button`;
   `_ler_parametros()` parses them (returns `False` on invalid input, and
   callers abort the action) and `_acao_parametro()` handles the button.
5. Click counting: `DrawingMixin._cliques_necessarios()` returns how many
   clicks the current mode needs (1 for `ponto`/`distribuir`, 2 for
   openings/furniture, `None` = open-ended for wall modes, finished with
   enter, by clicking the last vertex again, or closed by clicking the
   first one); `EventsMixin._on_click` accumulates clicks and dispatches to
   the right `_adicionar_*`.

Adding a new mode or a new per-mode option (e.g. a new point type) means
touching `TECLAS_MODO`/`PALETAS` in `constants.py` plus the relevant
`_adicionar_*`/rendering/edit-panel branches — not inventing new
menu/dialog plumbing.

### Point distributor (`distribuicao.py`)

`MODOS_DISTRIBUICAO = {key: (label, value label, default, fn, int?)}`,
every `fn(regioes, valor, ctx) -> [(x, y)]`, where `regioes` are the
target rooms already shrunk by the wall margin and minus furniture, and
`ctx` carries the raw rooms, margin, AP coordinates and a fixed-seed
`rng` (results are reproducible). Methods: square/hex grid by density,
exact-N weighted Lloyd/k-means (uniform, per room, or AP-weighted),
wall-following ring + sparse core, Poisson-disk. `ElementsMixin._distribuir`
replaces the measurement points of the target (whole plan, or the room
clicked) and renumbers **all** measurement points 1..N in walking order
(`ordenar_caminhada`: room by room, nearest-neighbor, starting at the AP);
access points get the ids after that.

### Editing existing objects

Right-click → `EditPanelMixin._clique_direito` → `_objeto_sob` (hit test)
→ `_abrir_edicao(categoria, indice)`, which populates the side-panel form
(`CAMPOS[categoria]` in `edit_panel.py`) from a *working copy*
(`self._edicao`); nothing mutates the real list until "aplicar"
(`_aplicar_edicao`). The "tipo"/"material" buttons call
`_ciclar("tipo"|"material")`, with one branch per category. Walls expose
`dx`/`dy` boxes (translate on apply) rather than editable vertices;
moving an opening (by boxes or by dragging) restores the wall at the old
spot and re-cuts at the new one (`_reposicionar_abertura`). While an
object is open in the panel, left-dragging it moves it
(`EventsMixin._iniciar_arraste`/`_mover_arraste`/`_encerrar_arraste`): a
wall vertex under the cursor moves just that vertex, otherwise the whole
object moves. The snapshot is taken on press and dropped again if nothing
moved.

### Rendering and snapping

`DrawingMixin._redesenhar` fully clears and redraws the `Axes` on every
mutation — there's no incremental diffing for the main drawing. Walls are
`PathPatch`es (holes supported); openings are drawn over their `recorte`
footprint. Pending wall clicks are previewed as the polygon they'll become.
The live cursor HUD (crosshair, snap marker, rubber band from the last
click, hover tooltip incl. room area) is separate and uses matplotlib
blitting (`HudMixin`) since it redraws on every mouse-move.
`_encaixar` snaps with priority vertex → wall/guide edge (preferring a
point that is also on the grid) → grid. Styling lives in `constants.py`
(`ESTILO_PAREDE` + `COR_MATERIAL_PAREDE`, `ESTILO_ABERTURA`, `ESTILO_GUIA`,
`ESTILO_PONTO`); the legend is built from what's actually in the plan.

## `heatmap/` — interactive heatmap viewer

Entry point: `heatmap_gerador.py` → `heatmap.cli:main` → builds
`heatmap.core.HeatmapViewer` (mixes in `heatmap.widgets.WidgetsMixin`,
analogous in spirit to `PlantaEditor` but read-only, no editing/navigation
mixins). `heatmap/constants.py` duplicates the handful of style dicts it
needs from `editor/constants.py` rather than importing it, to keep the
two packages decoupled; it also holds every tunable default (dBm color
scale and band levels, grid resolution in metres + cell cap, per-material
wall attenuation with sources, log-distance defaults/limits, and
`PARAMETROS_PADRAO` = each method's main parameter `(label, default,
(min, max))`).

- `heatmap/tabela.py`: `ler_csv_leituras` (any CSV with an `id` column
  plus any number of reading columns via `csv.DictReader`; blank cells
  skipped, bad cells warned-and-skipped; only a missing `id` column
  raises) and `associar_leituras` (keeps readings of ids that are
  measurement points in the plan, warns about unknown/AP ids and points
  with no reading). It returns raw `{id: [floats]}` — aggregation happens
  in `interpolation.py`. `--tabela` is optional: without it
  `leituras_do_ponto` falls back to `leituras_dbm` inside old JSONs.
- `heatmap/interpolation.py`:
  - `MODOS_AGREGACAO` (`potencia` = mean in mW, the default; `dbm`;
    `mediana`) used by `preparar_amostras(dados, leituras_por_id,
    agregacao)` → `(coords, valores, vazios, ids)`: `tipo=="medicao"`
    points with data vs. empty ones (drawn hollow, excluded); access
    points are never a data source. `avisos_dispersao` flags points whose
    readings spread more than `LIMITE_DISPERSAO_DB` (printed once by the
    CLI).
  - `grade(dados)`: square cells of `RESOLUCAO_M`, enlarged only to stay
    under `MAX_CELULAS`.
  - Every method has the signature `(grid_x, grid_y, coords, valores, ctx)
    -> grid`, with grid_x/grid_y of any shape (the full grid, or a single
    point in LOOCV). `montar_ctx(dados, parametro, cache)` builds `ctx`:
    `aps` (K,2), `barreiras` (wall/window geometry + dB loss, from
    `propagacao.barreiras`), `parametro` (None = default), a shared
    `cache`, and the `avisos` list / `ajuste` dict the method fills
    (fallback warnings, fitted P0/n/variogram) for the plot title.
  - `MODOS_INTERPOLACAO = {key: (label, fn, PARAMETROS_PADRAO[key])}`,
    9 methods: `idw`, `gaussiana`, `vizinho`, `linear` (Delaunay via
    `matplotlib.tri`, NaN outside the hull filled by nearest neighbour),
    `rbf` (thin-plate spline + degree-1 polynomial, normalised coords,
    smoothing λ), `kriging`, `path_loss`, `multi_wall`, `hibrido`
    (multi-wall + kriged residuals, IDW if the residual variogram falls
    back). Methods that can't run degrade instead of raising (no AP →
    IDW/kriging, <3 points → nearest/IDW) and say so in `ctx["avisos"]`.
- `heatmap/krigagem.py`: empirical semivariogram in distance bins, fit of
  exponential/spherical + nugget (grid search on range, weighted least
  squares on nugget/sill), documented fallback model for few points,
  ordinary kriging solved once in dual form (`np.linalg.solve`, lstsq if
  singular). The nugget is treated as measurement noise at prediction
  time (no spikes on the points).
- `heatmap/propagacao.py`: log-distance `P0 − 10 n log10(d/1 m)` (d ≥
  0.5 m) with P0/n fitted by least squares (n clamped to `LIMITES_N`,
  multiple APs → strongest AP per point), and the multi-wall loss:
  touching wall pieces of the same tipo/material are unioned, then all
  AP→target segments are tested at once with `STRtree.query(predicate=
  "intersects")` + vectorised `shapely.intersection` (a wall crossed in k
  pieces counts k times; walls containing the AP are ignored). Losses are
  cached in `ctx["cache"]` per AP + point set (~0.4 s for the full grid).
- `heatmap/validacao.py`: `loocv` (drop one point, predict only at it,
  RMSE/MAE/bias) and `tabela_loocv` (all methods, printed when the viewer
  opens; the title shows the active method's RMSE).
- `heatmap/mascara.py`: `contorno_interior` (vector, primary) fills each
  component of the union of walls + opening footprints/segments by its
  exterior ring, which becomes a matplotlib clip path (exact edge). If
  the contour doesn't close — little room area, or >10% of the plan's
  points outside the closed rooms — it returns the convex hull of walls +
  points with `fechado=False` (warning in the title). `mascara_interior`
  (raster flood fill, same open-contour fallback) is only used if the
  vector path raises. `MODOS_AREA` switches between clipped and full grid.
- `heatmap/rendering.py`: `desenhar_planta_base` is a read-only
  reimplementation of the relevant slice of `DrawingMixin._redesenhar`
  (it still draws old line walls, for old JSONs; points with data are
  labelled `id: dBm`). `MODOS_ESCALA` (`fixa` = `ESCALA_DBM`, `auto` =
  min/max of the *measured* values) produces the one `Normalize` shared
  by every style. Styles in `MODOS_RENDER` have the signature
  `fn(ax, grid_x, grid_y, entrada, norm, cmap, mascara=None) -> (artists
  to clip, colorbar mappable)` and are tagged `"grade"` (`entrada` = the
  interpolated grid — `campo_continuo` via `pcolormesh`,
  `bandas_contorno` via `contourf` on `NIVEIS_DBM`) or `"pontos"`
  (`entrada` = `(coords, valores)` — `blobs`, one RGBA image with a
  compact radial kernel, opacity = max kernel so alphas never stack);
  `HeatmapViewer._redesenhar` dispatches on that tag and clips.
- `heatmap/core.py`: samples, grid and contour are computed once in
  `__init__`; interpolated grids and LOOCV results are cached per
  `(method, parameter)`, so switching style/area/scale doesn't
  recompute. The colorbar's `cax` comes from an axes divider, and its
  original locator is restored before every `fig.colorbar` (a colorbar
  with `extend` wraps the locator and would shrink the cax on every
  redraw).
- `heatmap/widgets.py` introduces `matplotlib.widgets.RadioButtons` (not
  used anywhere in `editor/`, which relies on digit-key palettes instead)
  for method/style/area/scale. The right column is laid out top-down
  from the registries' sizes (a new method needs no coordinates). There's
  a `TextBox` for the active method's parameter (read on every redraw,
  invalid → keeps the old value + title warning), fonts scaled to the
  window height, and the export `TextBox` + two `Button`s wired to
  `HeatmapViewer._exportar("png"|"svg")`.

Extending either package (a new interpolation method, a new render style,
a new distribution method, a new CSV column convention) follows the same
registry pattern — `MODOS_INTERPOLACAO`/`MODOS_RENDER`/`MODOS_AREA`/
`MODOS_ESCALA`/`MODOS_AGREGACAO`/`MODOS_DISTRIBUICAO` dicts, not new
dispatch plumbing. A new interpolation method also needs its entry in
`PARAMETROS_PADRAO`.
