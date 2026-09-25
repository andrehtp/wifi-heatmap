"""Recorte "dentro do imovel" a partir do contorno real das paredes.

Caminho principal (vetorial, `contorno_interior`): a uniao das barreiras
(paredes, trechos recortados pelas aberturas e as proprias aberturas) tem
cada componente preenchido pelo seu anel externo - isso fecha os comodos.
O resultado vira um clip path do matplotlib, com borda exata (sem degraus
de celula). Se o contorno nao fecha (quase nenhuma area de comodo, ou
pontos da planta caindo fora dos comodos fechados), cai para o fecho
convexo das paredes e pontos, com fechado=False.

Fallback raster (`mascara_interior`, usado so se o vetorial falhar):
dentro/fora e resolvido rasterizando as barreiras (paredes em poligono,
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

# Com area de comodos fechados menor que esta fracao da area livre do fecho
# convexo das paredes, o contorno e considerado aberto (-> fecho convexo).
FRACAO_MIN_COMODOS = 0.25
# Mais que esta fracao dos pontos da planta fora do interior fechado tambem
# indica contorno aberto (ex.: so alguns comodos fecham).
FRACAO_MAX_PONTOS_FORA = 0.10
# Mascara raster com menos que esta fracao de celulas "dentro" = vazia.
FRACAO_MIN_MASCARA = 0.05


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


def _fecho_convexo(dados, barreiras):
    """Fecho convexo das paredes e de todos os pontos da planta."""
    pontos = [shapely.Point(p["x"], p["y"]) for p in dados.get("pontos_medicao", [])]
    return unary_union([barreiras, *pontos]).convex_hull


def _fracao_pontos_fora(dados, dentro):
    """Fracao dos pontos da planta (medicao + AP) em que dentro(xs, ys) e False.

    Pontos caidos fora do interior = parte da casa sem contorno fechado.
    """
    pontos = [(p["x"], p["y"]) for p in dados.get("pontos_medicao", [])]
    if not pontos:
        return 0.0
    xs, ys = np.array(pontos, dtype=float).T
    return float(np.mean(~np.asarray(dentro(xs, ys), dtype=bool)))


def contorno_interior(dados):
    """(geometria do interior, fechado) - None sem paredes (nada a recortar).

    Interior = cada componente da uniao das barreiras preenchido pelo anel
    externo (inclui as paredes). fechado=False quando o contorno nao fecha
    e o recorte vira o fecho convexo das paredes e dos pontos.
    """
    if not dados.get("paredes"):
        return None, True
    barreiras = _barreiras(dados, 0.01)  # 1 cm fecha frestas de desenho
    preenchido = unary_union([Polygon(parte.exterior)
                              for parte in shapely.get_parts(barreiras)
                              if isinstance(parte, Polygon) and not parte.is_empty])
    casco = _fecho_convexo(dados, barreiras)
    area_livre = casco.area - barreiras.area
    comodos = preenchido.difference(barreiras).area
    interior = preenchido.buffer(0.05)
    if (area_livre > 0 and comodos < FRACAO_MIN_COMODOS * area_livre) \
            or _fracao_pontos_fora(dados, lambda xs, ys: shapely.contains_xy(interior, xs, ys)) \
            > FRACAO_MAX_PONTOS_FORA:
        return casco, False
    return preenchido, True


def mascara_interior(dados, grid_x, grid_y):
    """(mascara, fechado): True nas celulas dentro do contorno de paredes.

    Inclui as proprias celulas de parede (o mapa de calor vai ate a linha da
    parede). Sem nenhuma parede na planta, retorna tudo True (nada a recortar).
    Se o flood fill vazar (contorno aberto: quase nada sobra dentro, ou os
    pontos da planta caem fora), usa o fecho convexo das paredes e pontos,
    com fechado=False.
    """
    if not dados.get("paredes"):
        return np.ones(grid_x.shape, dtype=bool), True
    paredes_grid = _rasterizar_paredes(dados, grid_x, grid_y)
    dentro = ~_preencher_exterior(paredes_grid)

    def na_mascara(xs, ys):
        i = np.abs(grid_y[:, :1] - ys).argmin(axis=0)
        j = np.abs(grid_x[:1, :].T - xs).argmin(axis=0)
        return dentro[i, j]

    if dentro.mean() - paredes_grid.mean() < FRACAO_MIN_MASCARA \
            or _fracao_pontos_fora(dados, na_mascara) > FRACAO_MAX_PONTOS_FORA:
        casco = _fecho_convexo(dados, _barreiras(dados, 0.0))
        return shapely.contains_xy(casco, grid_x, grid_y), False
    return dentro, True


# Alcance do mapa de calor: "dentro" recorta pelo contorno real das paredes
# (contorno_interior, com mascara_interior de fallback); "expandido" mostra a
# grade completa, sem recorte.
MODOS_AREA = {
    "dentro": ("Dentro do imovel", True),
    "expandido": ("Expandido (fora)", False),
}
