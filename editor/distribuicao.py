"""Distribuidor automatico de pontos de medicao (numpy + shapely).

Cada metodo recebe a lista de `regioes` (uma por comodo alvo, ja com a
margem das paredes e dos moveis descontada), o `valor` digitado no painel
e um `ctx` com o resto (comodos crus, margem, access points, rng) e
devolve uma lista de (x, y). O registro MODOS_DISTRIBUICAO segue o mesmo
padrao de MODOS_INTERPOLACAO no heatmap.
"""

import math

import numpy as np
import shapely
from shapely import Point

from .poligonos import poligonos

MAX_AMOSTRAS = 40000


# ---------------------------------------------------------------------- #
# Utilitarios
# ---------------------------------------------------------------------- #
def _amostras(regiao, passo_min=0.05):
    """Pontos de uma grade densa dentro da regiao (para o k-means)."""
    xmin, ymin, xmax, ymax = regiao.bounds
    passo = max(passo_min, math.sqrt(max(regiao.area, 1e-9) / MAX_AMOSTRAS))
    xs = np.arange(xmin + passo / 2, xmax, passo)
    ys = np.arange(ymin + passo / 2, ymax, passo)
    if len(xs) == 0 or len(ys) == 0:
        return np.empty((0, 2))
    gx, gy = np.meshgrid(xs, ys)
    dentro = shapely.contains_xy(regiao, gx, gy)
    return np.column_stack([gx[dentro], gy[dentro]])


def _dist2(a, c):
    """Matriz (len(a), len(c)) de distancias ao quadrado, sem array 3D."""
    return np.maximum(
        (a ** 2).sum(axis=1)[:, None] - 2 * a @ c.T + (c ** 2).sum(axis=1)[None, :],
        0.0)


def _um_ponto(regiao):
    p = regiao.representative_point()
    return [(p.x, p.y)]


def _lloyd(amostras, pesos, n, rng, iteracoes=40):
    """k-means ponderado (Lloyd) com inicializacao k-means++.

    Os centros resultantes cobrem a regiao com densidade proporcional ao
    peso. Centros que caem fora (regiao concava) vao para a amostra mais
    proxima, entao todos ficam dentro da regiao.
    """
    n = min(int(n), len(amostras))
    if n <= 0:
        return np.empty((0, 2))
    prob = pesos / pesos.sum()
    centros = [amostras[rng.choice(len(amostras), p=prob)]]
    d2 = ((amostras - centros[0]) ** 2).sum(axis=1)
    for _ in range(1, n):
        p = d2 * pesos
        total = p.sum()
        idx = rng.choice(len(amostras), p=p / total) if total > 0 else \
            rng.choice(len(amostras))
        centros.append(amostras[idx])
        d2 = np.minimum(d2, ((amostras - amostras[idx]) ** 2).sum(axis=1))
    c = np.array(centros, dtype=float)

    for _ in range(iteracoes):
        dist = _dist2(amostras, c)
        rotulo = dist.argmin(axis=1)
        soma_p = np.bincount(rotulo, weights=pesos, minlength=n)
        soma_x = np.bincount(rotulo, weights=pesos * amostras[:, 0], minlength=n)
        soma_y = np.bincount(rotulo, weights=pesos * amostras[:, 1], minlength=n)
        ok = soma_p > 0
        novo = c.copy()
        novo[ok, 0] = soma_x[ok] / soma_p[ok]
        novo[ok, 1] = soma_y[ok] / soma_p[ok]
        if np.allclose(novo, c, atol=1e-4):
            c = novo
            break
        c = novo

    # centro fora da regiao (comodo em L, por ex.) -> amostra mais proxima
    dist = _dist2(amostras, c)
    mais_proxima = amostras[dist.argmin(axis=0)]
    return mais_proxima if len(mais_proxima) else c


def _grade(regiao, passo_x, passo_y, deslocar_linhas=False):
    """Grade centrada no retangulo envolvente da regiao."""
    xmin, ymin, xmax, ymax = regiao.bounds
    nx = int((xmax - xmin) // passo_x) + 1
    ny = int((ymax - ymin) // passo_y) + 1
    x0 = xmin + ((xmax - xmin) - (nx - 1) * passo_x) / 2
    y0 = ymin + ((ymax - ymin) - (ny - 1) * passo_y) / 2
    pontos = []
    for j in range(ny):
        y = y0 + j * passo_y
        desloc = passo_x / 2 if deslocar_linhas and j % 2 else 0.0
        for i in range(nx + (1 if desloc else 0)):
            x = x0 + i * passo_x - desloc
            pontos.append((x, y))
    if not pontos:
        return []
    arr = np.array(pontos)
    dentro = shapely.contains_xy(regiao, arr[:, 0], arr[:, 1])
    return [tuple(p) for p in arr[dentro]]


def _por_regiao(regioes, funcao):
    """Aplica `funcao(regiao)` em cada comodo; comodo vazio ganha 1 ponto."""
    pontos = []
    for regiao in regioes:
        achados = funcao(regiao)
        pontos += achados if achados else _um_ponto(regiao)
    return pontos


# ---------------------------------------------------------------------- #
# Metodos
# ---------------------------------------------------------------------- #
def grade_quadrada(regioes, valor, ctx):
    """Grade quadrada com `valor` pontos por m²."""
    passo = 1 / math.sqrt(valor)
    return _por_regiao(regioes, lambda r: _grade(r, passo, passo))


def grade_hexagonal(regioes, valor, ctx):
    """Grade hexagonal (triangular) com `valor` pontos por m².

    Cada ponto cobre um hexagono de area a²·√3/2, entao para a densidade
    pedida o lado e a = √(2 / (√3 · valor)).
    """
    a = math.sqrt(2 / (math.sqrt(3) * valor))
    return _por_regiao(
        regioes, lambda r: _grade(r, a, a * math.sqrt(3) / 2, True))


def quantidade_total(regioes, valor, ctx):
    """Exatamente `valor` pontos espalhados por todos os comodos alvo."""
    uniao = shapely.union_all(regioes)
    amostras = _amostras(uniao)
    pesos = np.ones(len(amostras))
    return [tuple(p) for p in _lloyd(amostras, pesos, valor, ctx["rng"])]


def por_comodo(regioes, valor, ctx):
    """`valor` pontos em cada comodo, qualquer que seja o tamanho dele."""
    pontos = []
    for regiao in regioes:
        amostras = _amostras(regiao)
        if len(amostras) == 0:
            pontos += _um_ponto(regiao)
            continue
        pontos += [tuple(p) for p in _lloyd(
            amostras, np.ones(len(amostras)), valor, ctx["rng"])]
    return pontos


def junto_paredes(regioes, valor, ctx):
    """Pontos a cada `valor` m ao longo das paredes + miolo mais esparso.

    O contorno fica afastado das paredes pela margem; o interior recebe uma
    grade com o dobro do espacamento, so onde ainda sobra espaco.
    """
    pontos = []
    for regiao, comodo in zip(regioes, ctx["comodos"]):
        faixa = comodo.buffer(-ctx["margem"], join_style="mitre")
        achados = []
        for pol in poligonos(faixa):
            for anel in [pol.exterior, *pol.interiors]:
                n = max(1, round(anel.length / valor))
                for i in range(n):
                    q = anel.interpolate(i * anel.length / n)
                    if regiao.buffer(1e-6).contains(q):
                        achados.append((q.x, q.y))
        miolo = comodo.buffer(-(ctx["margem"] + valor), join_style="mitre")
        miolo = miolo.intersection(regiao)
        if not miolo.is_empty:
            achados += _grade(miolo, 2 * valor, 2 * valor)
        pontos += achados if achados else _um_ponto(regiao)
    return pontos


def foco_access_point(regioes, valor, ctx):
    """`valor` pontos, mais densos perto dos access points.

    Perto do AP o sinal (em dBm) cai mais rapido com a distancia, entao e
    ali que a interpolacao mais precisa de amostras.
    """
    uniao = shapely.union_all(regioes)
    amostras = _amostras(uniao)
    aps = np.array(ctx["aps"]).reshape(-1, 2)
    if len(aps) == 0:
        print("Aviso: nenhum access point na planta; distribuindo uniforme.")
        pesos = np.ones(len(amostras))
    else:
        d = np.sqrt(_dist2(amostras, aps).min(axis=1))
        pesos = 1.0 / (1.0 + d) ** 2
    return [tuple(p) for p in _lloyd(amostras, pesos, valor, ctx["rng"])]


def aleatorio_poisson(regioes, valor, ctx):
    """Poisson-disk (Bridson): aleatorio, mas nunca a menos de `valor` m."""
    rng = ctx["rng"]
    r = valor
    pontos = []
    for regiao in regioes:
        achados = []
        # cada pedaco desconexo precisa da sua propria semente
        for pol in poligonos(regiao):
            achados += _bridson(pol, r, rng)
        pontos += achados if achados else _um_ponto(regiao)
    return pontos


def _bridson(pol, r, rng, k=30):
    amostras = _amostras(pol)
    if len(amostras) == 0:
        return []
    celula = r / math.sqrt(2)
    xmin, ymin, _, _ = pol.bounds
    grade = {}

    def chave(p):
        return (int((p[0] - xmin) // celula), int((p[1] - ymin) // celula))

    def livre(p):
        ci, cj = chave(p)
        for i in range(ci - 2, ci + 3):
            for j in range(cj - 2, cj + 3):
                q = grade.get((i, j))
                if q is not None and (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2 < r * r:
                    return False
        return True

    inicio = tuple(amostras[rng.integers(len(amostras))])
    grade[chave(inicio)] = inicio
    ativos, aceitos = [inicio], [inicio]
    while ativos:
        idx = rng.integers(len(ativos))
        base = ativos[idx]
        for _ in range(k):
            ang = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(r, 2 * r)
            p = (base[0] + dist * math.cos(ang), base[1] + dist * math.sin(ang))
            if livre(p) and pol.contains(Point(p)):
                grade[chave(p)] = p
                ativos.append(p)
                aceitos.append(p)
                break
        else:
            ativos.pop(idx)
    return aceitos


# chave -> (rotulo, rotulo do valor, valor padrao, funcao, valor inteiro?)
MODOS_DISTRIBUICAO = {
    "grade":      ("grade quadrada",    "pontos/m2", 0.5, grade_quadrada, False),
    "hexagonal":  ("grade hexagonal",   "pontos/m2", 0.5, grade_hexagonal, False),
    "quantidade": ("quantidade total",  "N pontos",  30, quantidade_total, True),
    "por_comodo": ("N por comodo",      "N/comodo",  3, por_comodo, True),
    "paredes":    ("junto as paredes",  "espac. m",  1.0, junto_paredes, False),
    "foco_ap":    ("foco no AP",        "N pontos",  30, foco_access_point, True),
    "aleatorio":  ("aleatorio (Poisson)", "dist. min m", 1.0, aleatorio_poisson, False),
}


# ---------------------------------------------------------------------- #
# Ordem de caminhada (ids em sequencia fisica)
# ---------------------------------------------------------------------- #
def _vizinho_mais_proximo(pontos, inicio):
    restantes = list(pontos)
    ordem = []
    atual = inicio
    while restantes:
        i = min(range(len(restantes)),
                key=lambda k: (restantes[k][0] - atual[0]) ** 2
                + (restantes[k][1] - atual[1]) ** 2)
        atual = restantes.pop(i)
        ordem.append(atual)
    return ordem


def ordenar_caminhada(pontos, comodos, inicio):
    """Ordena os pontos para uma caminhada: comodo a comodo, sempre indo
    para o mais proximo de onde se esta. Pontos fora de qualquer comodo
    vao para o fim, tambem em vizinho-mais-proximo."""
    grupos = [[] for _ in comodos]
    soltos = []
    for p in pontos:
        pt = Point(p)
        for i, comodo in enumerate(comodos):
            if comodo.buffer(1e-6).contains(pt):
                grupos[i].append(p)
                break
        else:
            soltos.append(p)

    ordem = []
    atual = inicio
    pendentes = [i for i, g in enumerate(grupos) if g]
    while pendentes:
        prox = min(pendentes, key=lambda i: comodos[i].distance(Point(atual)))
        pendentes.remove(prox)
        trecho = _vizinho_mais_proximo(grupos[prox], atual)
        ordem += trecho
        atual = trecho[-1]
    return ordem + _vizinho_mais_proximo(soltos, atual)
