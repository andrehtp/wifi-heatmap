"""Preparo das amostras e metodos de interpolacao espacial (numpy puro, sem scipy).

Todo metodo tem a assinatura fn(grid_x, grid_y, coords, valores, ctx) -> grid,
onde grid_x/grid_y podem ter qualquer forma (a grade inteira ou um unico
ponto, no LOOCV) e ctx vem de montar_ctx: access points, barreiras
(paredes com material/tipo ja convertidos em perda), o parametro do
metodo, um cache compartilhado e as listas "avisos"/"ajuste", que o metodo
preenche para o titulo do grafico.
"""

import numpy as np
from matplotlib.tri import LinearTriInterpolator, Triangulation

from . import krigagem, propagacao
from .constants import (
    LIMITE_DISPERSAO_DB,
    MARGEM_GRADE,
    MAX_CELULAS,
    PARAMETROS_PADRAO,
    RESOLUCAO_M,
)


# --------------------------------------------------------------------------- #
# Agregacao das leituras de cada ponto
# --------------------------------------------------------------------------- #


def media_potencia(leituras):
    """Media em potencia: dBm -> mW, media, -> dBm (dBm e escala logaritmica)."""
    mw = 10.0 ** (np.asarray(leituras, dtype=float) / 10.0)
    return float(10.0 * np.log10(np.mean(mw)))


MODOS_AGREGACAO = {
    "potencia": ("Media em potencia (mW)", media_potencia),
    "dbm": ("Media aritmetica em dBm", lambda v: float(np.mean(v))),
    "mediana": ("Mediana", lambda v: float(np.median(v))),
}


def leituras_do_ponto(pt, leituras_por_id=None):
    """Leituras em dBm de um ponto: da tabela CSV (pelo id) ou, sem tabela,
    do campo leituras_dbm das plantas antigas."""
    if leituras_por_id is None:
        return pt.get("leituras_dbm") or []
    return leituras_por_id.get(pt["id"], [])


def preparar_amostras(dados, leituras_por_id=None, agregacao="potencia"):
    """Separa os pontos de medicao em amostras com dado e vazios.

    Retorna (coords, valores, vazios, ids):
      coords: (N, 2) - x,y dos pontos com leitura
      valores: (N,)  - leituras agregadas de cada um (MODOS_AGREGACAO)
      vazios:  (M, 2) - x,y dos pontos de medicao ainda sem leitura
      ids:     (N,)  - id de cada ponto com leitura

    Pontos access_point nunca entram como fonte de dado.
    """
    _, agregar = MODOS_AGREGACAO[agregacao]
    coords, valores, vazios, ids = [], [], [], []
    for pt in dados.get("pontos_medicao", []):
        if pt.get("tipo", "medicao") != "medicao":
            continue
        leituras = leituras_do_ponto(pt, leituras_por_id)
        if leituras:
            coords.append((pt["x"], pt["y"]))
            valores.append(agregar(leituras))
            ids.append(pt["id"])
        else:
            vazios.append((pt["x"], pt["y"]))
    return (np.array(coords, dtype=float).reshape(-1, 2), np.array(valores, dtype=float),
            np.array(vazios, dtype=float).reshape(-1, 2), ids)


def avisos_dispersao(dados, leituras_por_id=None, limite=LIMITE_DISPERSAO_DB):
    """Avisos dos pontos cujas leituras variam mais que `limite` dB (max - min)."""
    avisos = []
    for pt in dados.get("pontos_medicao", []):
        if pt.get("tipo", "medicao") != "medicao":
            continue
        leituras = leituras_do_ponto(pt, leituras_por_id)
        if len(leituras) > 1 and max(leituras) - min(leituras) > limite:
            texto = ", ".join(f"{v:g}" for v in leituras)
            avisos.append(f"id {pt['id']}: leituras [{texto}] variam "
                          f"{max(leituras) - min(leituras):.1f} dB (> {limite:g}), "
                          f"confira a medicao")
    return avisos


# --------------------------------------------------------------------------- #
# Grade e contexto
# --------------------------------------------------------------------------- #


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


def grade(dados, passo=RESOLUCAO_M, max_celulas=MAX_CELULAS):
    """Malha (grid_x, grid_y) de centros de celulas quadradas cobrindo a planta.

    O lado da celula e `passo` metros, aumentado so o necessario para nao
    passar de `max_celulas` em plantas grandes.
    """
    xmin, xmax, ymin, ymax = extents(dados)
    passo = max(passo, np.sqrt((xmax - xmin) * (ymax - ymin) / max_celulas))
    return np.meshgrid(np.arange(xmin + passo / 2, xmax, passo),
                       np.arange(ymin + passo / 2, ymax, passo))


def montar_ctx(dados, parametro=None, cache=None):
    """Contexto dos metodos, no espirito do ctx de editor/distribuicao.py.

    As barreiras (paredes/janelas -> geometria + perda em dB) ficam no
    cache, que o chamador pode reaproveitar entre chamadas (o viewer
    guarda um so; o LOOCV reusa o mesmo em todas as rodadas).
    """
    cache = {} if cache is None else cache
    if "barreiras" not in cache:
        cache["barreiras"] = propagacao.barreiras(dados)
    aps = [(p["x"], p["y"]) for p in dados.get("pontos_medicao", [])
           if p.get("tipo") == "access_point"]
    return {
        "aps": np.array(aps, dtype=float).reshape(-1, 2),
        "barreiras": cache["barreiras"],
        "parametro": parametro,
        "cache": cache,
        "avisos": [],
        "ajuste": {},
    }


def _param(ctx, metodo):
    """Parametro do ctx, ou o padrao de constants.PARAMETROS_PADRAO."""
    if ctx.get("parametro") is not None:
        return ctx["parametro"]
    return PARAMETROS_PADRAO[metodo][1]


def _dist2(grid_x, grid_y, coords):
    """Distancia ao quadrado de cada celula a cada ponto: forma grade + (N,)."""
    dx = np.asarray(grid_x)[..., None] - coords[:, 0]
    dy = np.asarray(grid_y)[..., None] - coords[:, 1]
    return dx**2 + dy**2


# --------------------------------------------------------------------------- #
# Metodos
# --------------------------------------------------------------------------- #


def idw(grid_x, grid_y, coords, valores, ctx, epsilon=1e-6):
    """Inverse-distance weighting, potencia p = parametro."""
    dist = np.sqrt(_dist2(grid_x, grid_y, coords)) + epsilon
    pesos = 1.0 / dist ** _param(ctx, "idw")
    return np.sum(pesos * valores, axis=-1) / np.sum(pesos, axis=-1)


def gaussiana(grid_x, grid_y, coords, valores, ctx):
    """Media ponderada por um kernel gaussiano (sigma = parametro) em cada amostra."""
    sigma = _param(ctx, "gaussiana")
    pesos = np.exp(-_dist2(grid_x, grid_y, coords) / (2 * sigma**2))
    return np.sum(pesos * valores, axis=-1) / (np.sum(pesos, axis=-1) + 1e-300)


def vizinho_mais_proximo(grid_x, grid_y, coords, valores, ctx):
    """Valor do ponto medido mais proximo (celulas de Voronoi), via argmin bruto."""
    return valores[np.argmin(_dist2(grid_x, grid_y, coords), axis=-1)]


def linear(grid_x, grid_y, coords, valores, ctx):
    """Interpolacao linear na triangulacao de Delaunay dos pontos.

    Fora do fecho convexo dos pontos (NaN) usa o vizinho mais proximo,
    para o comodo nao ficar em branco.
    """
    try:
        if len(valores) < 3:
            raise ValueError("menos de 3 pontos")
        tri = Triangulation(coords[:, 0], coords[:, 1])
        z = LinearTriInterpolator(tri, valores)(grid_x, grid_y)
        z = np.ma.filled(z.astype(float), np.nan)
    except (RuntimeError, ValueError):
        ctx["avisos"].append("linear: pontos insuficientes/colineares, "
                             "usando vizinho mais proximo")
        return vizinho_mais_proximo(grid_x, grid_y, coords, valores, ctx)
    fora = np.isnan(z)
    if fora.any():
        z[fora] = vizinho_mais_proximo(np.asarray(grid_x)[fora], np.asarray(grid_y)[fora],
                                       coords, valores, ctx)
    return z


def _placa_fina(r2):
    """Kernel thin-plate spline r^2 log r = 0.5 r^2 log r^2 (0 em r = 0)."""
    out = np.zeros_like(r2)
    m = r2 > 0
    out[m] = 0.5 * r2[m] * np.log(r2[m])
    return out


def rbf(grid_x, grid_y, coords, valores, ctx):
    """Thin-plate spline + polinomio de grau 1, suavizacao lambda = parametro.

    Coordenadas centralizadas e escaladas pela extensao dos pontos, para o
    sistema ficar bem condicionado (e lambda ter a mesma escala em
    qualquer planta).
    """
    n = len(valores)
    if n < 3:
        ctx["avisos"].append("rbf: menos de 3 pontos, usando IDW")
        return idw(grid_x, grid_y, coords, valores, dict(ctx, parametro=None))
    centro = coords.mean(axis=0)
    escala = max(float(np.ptp(coords, axis=0).max()), 1e-6)
    c = (coords - centro) / escala

    A = np.zeros((n + 3, n + 3))
    A[:n, :n] = _placa_fina(_dist2(c[:, 0], c[:, 1], c)) + _param(ctx, "rbf") * np.eye(n)
    P = np.column_stack([np.ones(n), c])
    A[:n, n:] = P
    A[n:, :n] = P.T
    sol = krigagem.resolver_sistema(A, np.concatenate([valores, np.zeros(3)]))

    gx = (np.asarray(grid_x) - centro[0]) / escala
    gy = (np.asarray(grid_y) - centro[1]) / escala
    return (_placa_fina(_dist2(gx, gy, c)) @ sol[:n]
            + sol[n] + sol[n + 1] * gx + sol[n + 2] * gy)


def _sem_ap(nome, grid_x, grid_y, coords, valores, ctx):
    ctx["avisos"].append(f"{nome}: sem access point na planta, usando IDW")
    return idw(grid_x, grid_y, coords, valores, dict(ctx, parametro=None))


def path_loss(grid_x, grid_y, coords, valores, ctx):
    """Log-distancia P0 - 10 n log10(d), P0 e n ajustados; max entre os APs."""
    if len(ctx["aps"]) == 0:
        return _sem_ap("path loss", grid_x, grid_y, coords, valores, ctx)
    return propagacao.modelo_log_distancia(grid_x, grid_y, coords, valores, ctx)[0]


def multi_wall(grid_x, grid_y, coords, valores, ctx):
    """Log-distancia menos a perda de cada parede cruzada (Motley-Keenan).

    Parametro = escala aplicada a todas as perdas da tabela de materiais.
    """
    if len(ctx["aps"]) == 0:
        return _sem_ap("multi-wall", grid_x, grid_y, coords, valores, ctx)
    return propagacao.modelo_log_distancia(
        grid_x, grid_y, coords, valores, ctx, _param(ctx, "multi_wall"))[0]


def hibrido(grid_x, grid_y, coords, valores, ctx):
    """Multi-wall + residuos (medido - modelo) interpolados por kriging.

    Com o variograma dos residuos em fallback (poucos pontos/instavel), os
    residuos vao por IDW. Sem AP, vira kriging puro.
    """
    if len(ctx["aps"]) == 0:
        ctx["avisos"].append("hibrido: sem access point na planta, usando kriging")
        return krigagem.kriging(grid_x, grid_y, coords, valores, dict(ctx, parametro=None))
    modelo_grid, modelo_obs = propagacao.modelo_log_distancia(
        grid_x, grid_y, coords, valores, ctx, _param(ctx, "hibrido"))
    residuos = valores - modelo_obs
    vg = krigagem.ajustar_variograma(coords, residuos)
    if vg["fallback"]:
        ctx["ajuste"]["residuos"] = "IDW"
        corr = idw(grid_x, grid_y, coords, residuos, dict(ctx, parametro=None))
    else:
        ctx["ajuste"]["residuos"] = "kriging"
        ctx["ajuste"]["variograma"] = vg
        corr = krigagem.krigar(grid_x, grid_y, coords, residuos, vg)
    return modelo_grid + corr


# chave: (rotulo, funcao, parametro) - parametro = (rotulo, padrao, (min, max))
# ou None, de constants.PARAMETROS_PADRAO (editavel no painel).
_METODOS = {
    "idw": ("IDW", idw),
    "gaussiana": ("Gaussiana", gaussiana),
    "vizinho": ("Vizinho mais proximo", vizinho_mais_proximo),
    "linear": ("Linear (Delaunay)", linear),
    "rbf": ("RBF thin-plate", rbf),
    "kriging": ("Kriging ordinario", krigagem.kriging),
    "path_loss": ("Path loss (log-dist.)", path_loss),
    "multi_wall": ("Multi-wall", multi_wall),
    "hibrido": ("Hibrido (MW + kriging)", hibrido),
}
MODOS_INTERPOLACAO = {chave: (rotulo, fn, PARAMETROS_PADRAO[chave])
                      for chave, (rotulo, fn) in _METODOS.items()}


def descrever_ajuste(ajuste):
    """Texto curto do que o metodo ajustou (P0/n, variograma), para o titulo."""
    partes = []
    if "P0" in ajuste:
        obs = f" ({ajuste['obs']})" if ajuste.get("obs") else ""
        partes.append(f"P0 {ajuste['P0']:.1f} dBm, n {ajuste['n']:.2f}{obs}")
    if "residuos" in ajuste:
        partes.append(f"residuos: {ajuste['residuos']}")
    vg = ajuste.get("variograma")
    if vg:
        partes.append(f"variograma {vg['modelo'][:3]}. alcance {vg['alcance']:.1f} m, "
                      f"nugget {vg['nugget']:.1f}, patamar {vg['patamar']:.1f}")
    return " | ".join(partes)
