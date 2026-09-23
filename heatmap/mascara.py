"""Mascara "dentro do imovel" a partir do contorno real das paredes.

As paredes sao so uma lista de segmentos soltos (sem nocao de poligono
fechado no modelo de dados), entao dentro/fora e resolvido rasterizando as
paredes num grid booleano e propagando um flood fill a partir da borda da
grade (numpy puro + BFS em stdlib, sem scipy/shapely - mesma filosofia do
resto do pacote, que ja evita scipy.spatial ate pro vizinho-mais-proximo).
"""

from collections import deque

import numpy as np


def _rasterizar_paredes(dados, grid_x, grid_y):
    """Grade booleana: True nas celulas sobre alguma parede (qualquer tipo)."""
    paredes = dados.get("paredes", [])
    paredes_grid = np.zeros(grid_x.shape, dtype=bool)
    if not paredes:
        return paredes_grid

    largura_celula = grid_x[0, 1] - grid_x[0, 0] if grid_x.shape[1] > 1 else 1.0
    altura_celula = grid_y[1, 0] - grid_y[0, 0] if grid_y.shape[0] > 1 else 1.0
    raio_minimo = 1.5 * max(abs(largura_celula), abs(altura_celula))

    for p in paredes:
        x1, y1, x2, y2 = p["x1"], p["y1"], p["x2"], p["y2"]
        raio = max(p.get("espessura", 0.1) / 2, raio_minimo)

        seg_x, seg_y = x2 - x1, y2 - y1
        comprimento2 = seg_x**2 + seg_y**2
        if comprimento2 < 1e-12:
            dist = np.hypot(grid_x - x1, grid_y - y1)
        else:
            t = ((grid_x - x1) * seg_x + (grid_y - y1) * seg_y) / comprimento2
            t = np.clip(t, 0.0, 1.0)
            proj_x = x1 + t * seg_x
            proj_y = y1 + t * seg_y
            dist = np.hypot(grid_x - proj_x, grid_y - proj_y)

        paredes_grid |= dist <= raio

    return paredes_grid


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
