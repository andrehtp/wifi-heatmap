"""Kriging ordinario em numpy puro: variograma empirico, ajuste e sistema.

Com N pontos medidos (dezenas), o sistema e (N+1)x(N+1): np.linalg.solve
basta, sem scipy/pykrige.

Ajuste do variograma (simplificado de proposito): semivariancia empirica
em N_FAIXAS faixas de distancia ate metade da maior distancia entre
pontos; para cada modelo (exponencial, esferico) e cada alcance de uma
busca em grade, o modelo e linear em (nugget, patamar parcial) e sai por
minimos quadrados ponderados pelo numero de pares da faixa. Fica o de
menor erro.

Fallback documentado: com menos de MIN_PONTOS pontos, menos de 3 faixas
validas ou nenhum ajuste com patamar positivo, usa-se um modelo
exponencial sem nugget, patamar = variancia amostral e alcance = 1/3 da
diagonal dos pontos. O resultado vem marcado com fallback=True.
"""

import numpy as np

N_FAIXAS = 8        # faixas de distancia do variograma empirico
MIN_PARES = 3       # pares minimos para uma faixa contar
MIN_PONTOS = 6      # abaixo disso o ajuste e instavel demais: fallback
N_ALCANCES = 40     # busca em grade do alcance
ALCANCE_MIN = 0.3   # metros


def _exponencial(h, a):
    # alcance "pratico": atinge 95% do patamar em h = a
    return 1.0 - np.exp(-3.0 * h / a)


def _esferico(h, a):
    r = np.minimum(h / a, 1.0)
    return 1.5 * r - 0.5 * r**3


MODELOS_VARIOGRAMA = {"exponencial": _exponencial, "esferico": _esferico}


def distancias(a, b):
    """Matriz de distancias euclidianas entre (Na, 2) e (Nb, 2)."""
    return np.hypot(a[:, None, 0] - b[None, :, 0], a[:, None, 1] - b[None, :, 1])


def resolver_sistema(A, b):
    """np.linalg.solve, caindo para minimos quadrados se A for singular."""
    try:
        return np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        return np.linalg.lstsq(A, b, rcond=None)[0]


def variograma_empirico(coords, valores, n_faixas=N_FAIXAS):
    """(h medio, semivariancia media, n pares) das faixas com pares suficientes."""
    i, j = np.triu_indices(len(valores), k=1)
    h = distancias(coords, coords)[i, j]
    g = 0.5 * (valores[i] - valores[j]) ** 2
    if len(h) == 0 or h.max() <= 0:
        return np.array([]), np.array([]), np.array([])
    faixa = np.digitize(h, np.linspace(0.0, h.max() / 2, n_faixas + 1)) - 1
    hs, gs, ns = [], [], []
    for k in range(n_faixas):
        m = faixa == k
        if m.sum() >= MIN_PARES:
            hs.append(h[m].mean())
            gs.append(g[m].mean())
            ns.append(m.sum())
    return np.array(hs), np.array(gs), np.array(ns, dtype=float)


def ajustar_variograma(coords, valores, nugget_rel=None):
    """Ajusta o variograma; nugget_rel (0-1) fixa o nugget como fracao do patamar total.

    Retorna {"modelo", "nugget", "patamar" (parcial), "alcance", "fallback"}.
    """
    n = len(valores)
    var = float(np.var(valores)) if n > 1 else 0.0
    diag = float(np.hypot(*np.ptp(coords, axis=0))) if n > 1 else 1.0
    diag = max(diag, 1e-3)
    nugget_padrao = (nugget_rel or 0.0) * var
    padrao = {"modelo": "exponencial", "nugget": nugget_padrao,
              "patamar": max(var - nugget_padrao, 1e-6),
              "alcance": diag / 3, "fallback": True}
    if n < MIN_PONTOS:
        return padrao
    hs, gs, ns = variograma_empirico(coords, valores)
    if len(hs) < 3:
        return padrao

    w2 = ns  # peso (ao quadrado) de cada faixa = numero de pares
    melhor_sse, melhor = np.inf, None
    for nome, f in MODELOS_VARIOGRAMA.items():
        for a in np.geomspace(min(ALCANCE_MIN, diag / 10), diag, N_ALCANCES):
            fh = f(hs, a)
            if nugget_rel is None:
                X = np.column_stack([np.ones_like(fh), fh]) * np.sqrt(w2)[:, None]
                nugget, patamar = np.linalg.lstsq(X, gs * np.sqrt(w2), rcond=None)[0]
                if nugget < 0:
                    nugget = 0.0
                    patamar = np.sum(w2 * fh * gs) / max(np.sum(w2 * fh * fh), 1e-12)
            else:
                base = nugget_rel + (1 - nugget_rel) * fh
                s = np.sum(w2 * base * gs) / max(np.sum(w2 * base * base), 1e-12)
                nugget, patamar = nugget_rel * s, (1 - nugget_rel) * s
            if patamar <= 1e-9:
                continue
            sse = np.sum(w2 * (nugget + patamar * fh - gs) ** 2)
            if sse < melhor_sse:
                melhor_sse = sse
                melhor = {"modelo": nome, "nugget": float(nugget),
                          "patamar": float(patamar), "alcance": float(a),
                          "fallback": False}
    return melhor or padrao


def semivariancia(h, vg):
    """gamma(h) do modelo ajustado, com o nugget incluso (tambem em h = 0)."""
    f = MODELOS_VARIOGRAMA[vg["modelo"]]
    return vg["nugget"] + vg["patamar"] * f(h, vg["alcance"])


def krigar(grid_x, grid_y, coords, valores, vg):
    """Kriging ordinario na forma dual: resolve o sistema com o multiplicador
    de Lagrange uma unica vez e avalia gamma(celula, pontos) . pesos.

    No sistema, gamma(0) = 0 na diagonal; na predicao o nugget entra mesmo
    em h = 0 ("kriging filtrado"): o nugget e tratado como ruido de medicao,
    e o mapa nao tem picos isolados exatamente sobre os pontos.
    """
    n = len(valores)
    if n == 1:
        return np.full(np.shape(grid_x), float(valores[0]))
    A = np.ones((n + 1, n + 1))
    A[n, n] = 0.0
    gamma = semivariancia(distancias(coords, coords), vg)
    # jitter minimo na diagonal (equivale a C(0) + eps) contra pontos repetidos
    np.fill_diagonal(gamma, -1e-8 * max(vg["nugget"] + vg["patamar"], 1e-6))
    A[:n, :n] = gamma
    pesos = resolver_sistema(A, np.append(valores, 0.0))

    pts = np.column_stack([np.ravel(grid_x), np.ravel(grid_y)])
    g0 = semivariancia(distancias(pts, coords), vg)
    return (g0 @ pesos[:n] + pesos[n]).reshape(np.shape(grid_x))


def kriging(grid_x, grid_y, coords, valores, ctx):
    """Metodo do registro: ajusta o variograma e interpola por kriging ordinario."""
    vg = ajustar_variograma(coords, valores, ctx.get("parametro"))
    if vg["fallback"]:
        ctx["avisos"].append("kriging: poucos pontos/variograma instavel, "
                             "modelo exponencial padrao")
    ctx["ajuste"]["variograma"] = vg
    return krigar(grid_x, grid_y, coords, valores, vg)
