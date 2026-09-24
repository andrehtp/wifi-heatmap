"""Preparo das amostras e metodos de interpolacao espacial (numpy puro, sem scipy)."""

import numpy as np

from .constants import MARGEM_GRADE, RESOLUCAO_GRADE


def leituras_do_ponto(pt, leituras_por_id=None):
    """Leituras em dBm de um ponto: da tabela CSV (pelo id) ou, sem tabela,
    do campo leituras_dbm das plantas antigas."""
    if leituras_por_id is None:
        return pt.get("leituras_dbm") or []
    return leituras_por_id.get(pt["id"], [])


def preparar_amostras(dados, leituras_por_id=None):
    """Separa os pontos de medicao em amostras com dado e vazios.

    Retorna (coords, valores, vazios):
      coords: (N, 2) - x,y dos pontos com leitura
      valores: (N,)  - media das leituras de cada um
      vazios:  (M, 2) - x,y dos pontos de medicao ainda sem leitura

    Pontos access_point nunca entram como fonte de dado.
    """
    coords, valores, vazios = [], [], []
    for pt in dados.get("pontos_medicao", []):
        if pt.get("tipo", "medicao") != "medicao":
            continue
        leituras = leituras_do_ponto(pt, leituras_por_id)
        if leituras:
            coords.append((pt["x"], pt["y"]))
            valores.append(float(np.mean(leituras)))
        else:
            vazios.append((pt["x"], pt["y"]))
    return (np.array(coords).reshape(-1, 2), np.array(valores),
            np.array(vazios).reshape(-1, 2))


def extents(dados, margem=MARGEM_GRADE):
    """Bounding box (xmin, xmax, ymin, ymax) a partir de paredes/moveis/pontos."""
    xs, ys = [], []
    for p in dados.get("paredes", []):
        if "vertices" in p:
            xs += [v[0] for v in p["vertices"]]
            ys += [v[1] for v in p["vertices"]]
        else:  # planta antiga, parede em segmento
            xs += [p["x1"], p["x2"]]
            ys += [p["y1"], p["y2"]]
    for a in dados.get("aberturas", []):
        xs += [a["x1"], a["x2"]]
        ys += [a["y1"], a["y2"]]
    for m in dados.get("moveis", []):
        xs += [m["x"], m["x"] + m["largura"]]
        ys += [m["y"], m["y"] + m["profundidade"]]
    for pt in dados.get("pontos_medicao", []):
        xs.append(pt["x"])
        ys.append(pt["y"])
    if not xs:
        xs, ys = [0.0, 1.0], [0.0, 1.0]
    return min(xs) - margem, max(xs) + margem, min(ys) - margem, max(ys) + margem


def grade(dados, resolucao=RESOLUCAO_GRADE):
    """Malha (grid_x, grid_y) que cobre a planta, para as interpolacoes grid-based."""
    xmin, xmax, ymin, ymax = extents(dados)
    return np.meshgrid(np.linspace(xmin, xmax, resolucao),
                        np.linspace(ymin, ymax, resolucao))


def idw(grid_x, grid_y, coords, valores, potencia=2.0, epsilon=1e-6):
    """Inverse-distance weighting."""
    dx = grid_x[..., None] - coords[:, 0]
    dy = grid_y[..., None] - coords[:, 1]
    dist = np.sqrt(dx**2 + dy**2) + epsilon
    pesos = 1.0 / dist**potencia
    return np.sum(pesos * valores, axis=-1) / np.sum(pesos, axis=-1)


def gaussiana(grid_x, grid_y, coords, valores, sigma=2.0):
    """Media ponderada por um kernel gaussiano centrado em cada amostra."""
    dx = grid_x[..., None] - coords[:, 0]
    dy = grid_y[..., None] - coords[:, 1]
    dist2 = dx**2 + dy**2
    pesos = np.exp(-dist2 / (2 * sigma**2))
    return np.sum(pesos * valores, axis=-1) / (np.sum(pesos, axis=-1) + 1e-9)


def vizinho_mais_proximo(grid_x, grid_y, coords, valores):
    """Valor do ponto medido mais proximo (celulas de Voronoi), via argmin bruto."""
    dx = grid_x[..., None] - coords[:, 0]
    dy = grid_y[..., None] - coords[:, 1]
    dist2 = dx**2 + dy**2
    idx = np.argmin(dist2, axis=-1)
    return valores[idx]


MODOS_INTERPOLACAO = {
    "idw": ("IDW", idw),
    "gaussiana": ("Gaussiana", gaussiana),
    "vizinho": ("Vizinho mais proximo", vizinho_mais_proximo),
}
