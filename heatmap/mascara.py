"""Mascara "dentro do imovel" a partir do contorno real das paredes.

Dentro/fora e resolvido rasterizando as barreiras (paredes em poligono,
os trechos recortados pelas aberturas e as proprias aberturas, para uma
porta externa nao "vazar") num grid booleano e propagando um flood fill a
partir da borda da grade (BFS em stdlib). A rasterizacao usa
shapely.contains_xy, vetorizado sobre a grade inteira.
"""

from collections import deque

import numpy as np
import shapely
from shapely import LineString, Polygon
from shapely.ops import unary_union


def _barreiras(dados, raio):
    """Uniao de tudo que separa dentro de fora, engrossada por `raio`."""
    geoms = []
    for p in dados.get("paredes", []):
        if "vertices" in p:
            geoms.append(Polygon(p["vertices"], p.get("furos") or None).buffer(0))
        else:  # planta antiga, parede em segmento
            linha = LineString([(p["x1"], p["y1"]), (p["x2"], p["y2"])])
            geoms.append(linha.buffer(p.get("espessura", 0.1) / 2))
    for a in dados.get("aberturas", []):
        geoms += [Polygon(r["vertices"], r.get("furos") or None).buffer(0)
                  for r in a.get("recorte", [])]
        geoms.append(LineString([(a["x1"], a["y1"]), (a["x2"], a["y2"])]))
    return unary_union(geoms).buffer(raio)


def _rasterizar_paredes(dados, grid_x, grid_y):
    """Grade booleana: True nas celulas sobre alguma parede ou abertura."""
    paredes_grid = np.zeros(grid_x.shape, dtype=bool)
    if not dados.get("paredes"):
        return paredes_grid

    largura_celula = grid_x[0, 1] - grid_x[0, 0] if grid_x.shape[1] > 1 else 1.0
    altura_celula = grid_y[1, 0] - grid_y[0, 0] if grid_y.shape[0] > 1 else 1.0
    # pouco mais que meia diagonal de celula: parede fina nao deixa o
    # flood fill passar entre duas celulas vizinhas
    raio = 0.75 * max(abs(largura_celula), abs(altura_celula))
    return shapely.contains_xy(_barreiras(dados, raio), grid_x, grid_y)


def _preencher_exterior(paredes_grid):
    """Flood fill 4-conexo a partir da borda da grade, sem atravessar paredes."""
    linhas, colunas = paredes_grid.shape
    fora = np.zeros_like(paredes_grid, dtype=bool)
    fila = deque()

    def visitar(i, j):
        if 0 <= i < linhas and 0 <= j < colunas and not paredes_grid[i, j] and not fora[i, j]:
            fora[i, j] = True
            fila.append((i, j))

    for j in range(colunas):
        visitar(0, j)
        visitar(linhas - 1, j)
    for i in range(linhas):
        visitar(i, 0)
        visitar(i, colunas - 1)

    while fila:
        i, j = fila.popleft()
        visitar(i + 1, j)
        visitar(i - 1, j)
        visitar(i, j + 1)
        visitar(i, j - 1)

    return fora


def mascara_interior(dados, grid_x, grid_y):
    """True nas celulas dentro do contorno de paredes (a mostrar no heatmap).

    Inclui as proprias celulas de parede (o mapa de calor vai ate a linha da
    parede). Sem nenhuma parede na planta, retorna tudo True (nada a recortar).
    """
    if not dados.get("paredes"):
        return np.ones(grid_x.shape, dtype=bool)
    paredes_grid = _rasterizar_paredes(dados, grid_x, grid_y)
    return ~_preencher_exterior(paredes_grid)


# Alcance do mapa de calor: "dentro" recorta a grade pelo contorno real das
# paredes (mascara_interior); "expandido" mostra a grade completa, sem recorte.
MODOS_AREA = {
    "dentro": ("Dentro do imovel", True),
    "expandido": ("Expandido (fora)", False),
}
