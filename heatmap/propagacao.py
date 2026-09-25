"""Modelos de propagacao: log-distancia e multi-wall (Motley-Keenan / COST 231).

    P(d) = P0 - 10 n log10(d / d0) - sum(perdas das paredes atravessadas)

com d0 = 1 m e d >= D_MIN. P0 e n sao ajustados as medicoes por minimos
quadrados (com a perda das paredes ja descontada, no multi-wall); com
varios APs, cada celula recebe o AP mais forte.

As paredes vem ja cortadas pelas aberturas (e o que o editor grava), entao
um segmento AP->celula que passa por uma porta ou vao nao cruza parede
nenhuma ali. A contagem e vetorizada: todos os segmentos AP->alvo de uma
vez, STRtree.query(predicate="intersects") para os pares candidatos e
shapely.intersection nos pares, sem loop Python por celula.
"""

import numpy as np
import shapely
from shapely import LineString, Polygon
from shapely.ops import unary_union

from .constants import (
    ATENUACAO_ABERTURA,
    ATENUACAO_MATERIAL,
    ATENUACAO_PADRAO,
    D0,
    D_MIN,
    FATOR_MEIA_PAREDE,
    LIMITES_N,
    LOG_DIST_PADRAO,
)


def barreiras(dados):
    """(geometrias, perda em dB) de tudo que atenua: paredes e janelas.

    Pedacos de parede que se tocam, com o mesmo tipo e material, sao unidos
    antes: senao um segmento que passa na emenda de dois pedacos colineares
    contaria duas paredes.
    """
    grupos = {}
    for p in dados.get("paredes", []):
        if "vertices" in p:
            geom = Polygon(p["vertices"], p.get("furos") or None).buffer(0)
        else:  # planta antiga, parede em segmento
            geom = LineString([(p["x1"], p["y1"]), (p["x2"], p["y2"])]).buffer(
                p.get("espessura", 0.1) / 2)
        grupos.setdefault((p.get("tipo"), p.get("material")), []).append(geom)

    geoms, perdas = [], []
    for (tipo, material), lista in grupos.items():
        perda = ATENUACAO_MATERIAL.get(material, ATENUACAO_PADRAO)
        if tipo == "meia_parede":
            perda *= FATOR_MEIA_PAREDE
        for geom in shapely.get_parts(unary_union(lista)):
            if not geom.is_empty:
                geoms.append(geom)
                perdas.append(perda)
    for a in dados.get("aberturas", []):
        perda = ATENUACAO_ABERTURA.get(a.get("tipo"), 0.0)
        if perda > 0:
            geoms.append(LineString([(a["x1"], a["y1"]), (a["x2"], a["y2"])]))
            perdas.append(perda)
    arr = np.empty(len(geoms), dtype=object)
    arr[:] = geoms
    return arr, np.array(perdas, dtype=float)


def perda_paredes(xs, ys, ap, ctx):
    """Soma das perdas (dB) das barreiras cruzadas pelo segmento ap -> (x, y).

    Uma parede atravessada em k trechos (ex.: os dois bracos de um L) conta
    k vezes; uma parede que contem o proprio AP e ignorada. Resultado em
    cache no ctx (chave: AP + pontos), ja que a grade nao muda.
    """
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    cache = ctx["cache"]
    chave = ("perda", float(ap[0]), float(ap[1]), xs.shape,
             hash(xs.tobytes()), hash(ys.tobytes()))
    if chave in cache:
        return cache[chave]

    geoms, atenuacao = ctx["barreiras"]
    perda = np.zeros(xs.size)
    if len(geoms):
        if "arvore" not in cache:
            cache["arvore"] = shapely.STRtree(geoms)
        contem_ap = shapely.contains_xy(geoms, ap[0], ap[1])
        segmentos = np.empty((xs.size, 2, 2))
        segmentos[:, 0] = ap
        segmentos[:, 1, 0] = xs.ravel()
        segmentos[:, 1, 1] = ys.ravel()
        linhas = shapely.linestrings(segmentos)
        i_linha, i_geom = cache["arvore"].query(linhas, predicate="intersects")
        manter = ~contem_ap[i_geom]
        i_linha, i_geom = i_linha[manter], i_geom[manter]
        trechos = shapely.get_num_geometries(
            shapely.intersection(linhas[i_linha], geoms[i_geom]))
        np.add.at(perda, i_linha, trechos * atenuacao[i_geom])
    perda = perda.reshape(xs.shape)
    cache[chave] = perda
    return perda


def _termo_distancia(xs, ys, ap):
    """10 log10(d / d0), com d >= D_MIN."""
    d = np.maximum(np.hypot(np.asarray(xs) - ap[0], np.asarray(ys) - ap[1]), D_MIN)
    return 10.0 * np.log10(d / D0)


def ajustar_log_distancia(termos, perdas, valores):
    """Ajusta P0 e n por minimos quadrados lineares.

    termos, perdas: (K APs, N pontos). Cada ponto e atribuido ao AP que o
    modelo preve como mais forte; reatribui e reajusta ate estabilizar.
    n fora de LIMITES_N e travado no limite (e P0 reajustado); sem
    variacao de distancia para ajustar n, usa o n padrao.
    """
    p0_padrao, n_padrao = LOG_DIST_PADRAO
    idx = np.arange(len(valores))
    atrib = np.argmin(n_padrao * termos + perdas, axis=0)
    for _ in range(5):
        t = termos[atrib, idx]
        y = valores + perdas[atrib, idx]
        obs = ""
        if len(valores) >= 2 and np.ptp(t) > 1e-6:
            A = np.column_stack([np.ones_like(t), -t])
            p0, n = np.linalg.lstsq(A, y, rcond=None)[0]
            if not LIMITES_N[0] <= n <= LIMITES_N[1]:
                n = float(np.clip(n, *LIMITES_N))
                p0 = float(np.mean(y + n * t))
                obs = "n no limite"
        elif len(valores):
            n, obs = n_padrao, "n padrao"
            p0 = float(np.mean(y + n * t))
        else:
            p0, n, obs = p0_padrao, n_padrao, "padrao"
        nova = np.argmin(n * termos + perdas, axis=0)
        if np.array_equal(nova, atrib):
            break
        atrib = nova
    return {"P0": float(p0), "n": float(n), "obs": obs}


def modelo_log_distancia(grid_x, grid_y, coords, valores, ctx, escala_paredes=0.0):
    """Ajusta e avalia o modelo; escala_paredes = 0 e o log-distancia puro.

    Retorna (previsto na grade, previsto nos pontos medidos). Exige ao
    menos um AP em ctx["aps"] (quem chama cuida do fallback).
    """
    aps = ctx["aps"]

    def avaliar(xs, ys):
        termos = np.stack([_termo_distancia(xs, ys, ap) for ap in aps])
        if escala_paredes > 0:
            perdas = np.stack([escala_paredes * perda_paredes(xs, ys, ap, ctx)
                               for ap in aps])
        else:
            perdas = np.zeros_like(termos)
        return termos, perdas

    termos_obs, perdas_obs = avaliar(coords[:, 0], coords[:, 1])
    ajuste = ajustar_log_distancia(termos_obs, perdas_obs, valores)
    ctx["ajuste"].update(ajuste)

    def prever(termos, perdas):
        return np.max(ajuste["P0"] - ajuste["n"] * termos - perdas, axis=0)

    return prever(*avaliar(grid_x, grid_y)), prever(termos_obs, perdas_obs)
