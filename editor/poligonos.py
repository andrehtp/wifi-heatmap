"""Geometria das paredes em poligono (shapely), sem estado do editor.

Uma parede e um dict {"tipo", "material", "vertices": [[x, y], ...],
"furos": [[[x, y], ...], ...]} ("furos" so existe quando a parede e um
anel fechado). As aberturas continuam segmentos; ao cair sobre uma parede
elas removem o trecho correspondente e guardam os pedacos removidos em
"recorte", o que permite devolver a parede se a abertura sair dali.
"""

import math

from shapely import GeometryCollection, LinearRing, LineString, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import nearest_points, unary_union

AREA_MINIMA = 1e-4    # m²; pedacos menores que isso sao descartados
PROF_CORTE = 0.5      # m para cada lado do segmento da abertura
CASAS = 4             # casas decimais gravadas no JSON
FECHAR = 2e-4         # buffer +/- que cola pedacos separados por arredondamento


# ---------------------------------------------------------------------- #
# Conversao dict <-> shapely
# ---------------------------------------------------------------------- #
def para_shapely(parede):
    return Polygon(parede["vertices"], parede.get("furos") or None)


def poligonos(geom):
    """Lista de Polygon contidos em qualquer geometria (Multi*, colecao)."""
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if hasattr(geom, "geoms"):
        return [p for g in geom.geoms for p in poligonos(g)]
    return []


def _coords(anel):
    return [[round(x, CASAS), round(y, CASAS)] for x, y in anel.coords[:-1]]


def de_shapely(geom, tipo, material):
    """Um dict de parede por poligono de `geom` (Multi* vira varios)."""
    dicts = []
    for pol in poligonos(geom):
        if pol.area < AREA_MINIMA:
            continue
        pol = orient(pol.simplify(1e-4, preserve_topology=True))
        parede = {"tipo": tipo, "material": material,
                  "vertices": _coords(pol.exterior)}
        furos = [_coords(anel) for anel in pol.interiors
                 if Polygon(anel).area >= AREA_MINIMA]
        if furos:
            parede["furos"] = furos
        dicts.append(parede)
    return dicts


def corrigir(geom):
    """Poligono valido a partir de um desenhado a mao (pode se cruzar)."""
    if geom.is_valid:
        return geom
    return geom.buffer(0)


def transladar(parede, dx, dy):
    novo = dict(parede)
    novo["vertices"] = [[round(x + dx, CASAS), round(y + dy, CASAS)]
                        for x, y in parede["vertices"]]
    if parede.get("furos"):
        novo["furos"] = [[[round(x + dx, CASAS), round(y + dy, CASAS)]
                          for x, y in anel] for anel in parede["furos"]]
    return novo


def espessura_aproximada(pol):
    """Lado menor do retangulo minimo que envolve o poligono (m)."""
    mrr = pol.minimum_rotated_rectangle
    if not isinstance(mrr, Polygon):
        return 0.0
    (ax, ay), (bx, by), (cx, cy) = list(mrr.exterior.coords)[:3]
    return min(math.hypot(bx - ax, by - ay), math.hypot(cx - bx, cy - by))


# ---------------------------------------------------------------------- #
# Criacao de paredes
# ---------------------------------------------------------------------- #
def _faixa_infinita(pol):
    """Faixa infinita ao longo do eixo maior da parede `pol`."""
    mrr = pol.minimum_rotated_rectangle
    if not isinstance(mrr, Polygon):
        return None
    (ax, ay), (bx, by), (cx, cy) = list(mrr.exterior.coords)[:3]
    l1, l2 = math.hypot(bx - ax, by - ay), math.hypot(cx - bx, cy - by)
    if l1 >= l2:
        ux, uy, meia = (bx - ax) / l1, (by - ay) / l1, l2 / 2
    else:
        ux, uy, meia = (cx - bx) / l2, (cy - by) / l2, l1 / 2
    centro = mrr.centroid
    eixo = LineString([(centro.x - ux * 1e3, centro.y - uy * 1e3),
                       (centro.x + ux * 1e3, centro.y + uy * 1e3)])
    return eixo.buffer(meia, cap_style="flat")


def _faixa_da_linha(linha, espessura, alinhamento):
    if alinhamento == "centro":
        return linha.buffer(espessura / 2, cap_style="flat",
                            join_style="mitre")
    lado = espessura if alinhamento == "esquerda" else -espessura
    return linha.buffer(lado, single_sided=True, join_style="mitre")


def _completar_canto(ponta, vizinho, espessura, alinhamento, existentes):
    """Prolonga a ponta que encosta numa parede existente, fechando o canto.

    O prolongamento so e mantido dentro da faixa da parede tocada, entao
    ele preenche o "dente" de um canto em L sem sobrar para fora dela.
    """
    tocadas = [p for p in existentes if p.distance(Point(ponta)) <= 1e-6]
    if not tocadas:
        return None
    dx, dy = ponta[0] - vizinho[0], ponta[1] - vizinho[1]
    comp = math.hypot(dx, dy)
    if comp == 0:
        return None
    ext = espessura / 2 if alinhamento == "centro" else espessura
    alem = (ponta[0] + dx / comp * ext, ponta[1] + dy / comp * ext)
    # mesma orientacao do trecho original, para o lado do buffer bater
    pedaco = _faixa_da_linha(LineString([ponta, alem]), espessura, alinhamento)
    faixas = [f for f in (_faixa_infinita(p) for p in tocadas) if f is not None]
    if not faixas:
        return None
    return pedaco.intersection(unary_union(faixas))


def parede_de_polilinha(pontos, espessura, alinhamento, fechada=False,
                        existentes=()):
    """Poligono de uma parede desenhada pelo eixo (ou por uma face).

    `alinhamento` diz de que lado da linha clicada fica a espessura:
    "centro", "esquerda" ou "direita" em relacao ao sentido do desenho.
    Pontas livres sao retas (o comprimento e exatamente o clicado); pontas
    que encostam numa parede existente sao prolongadas para fechar o canto.
    """
    if fechada:
        anel = Polygon(pontos)
        if not anel.is_valid or anel.area == 0:
            return GeometryCollection()
        # sentido anti-horario: a esquerda de quem desenha e o lado de dentro
        antihorario = LinearRing(pontos).is_ccw
        if alinhamento == "centro":
            fora = anel.buffer(espessura / 2, join_style="mitre")
            dentro = anel.buffer(-espessura / 2, join_style="mitre")
        elif (alinhamento == "esquerda") == antihorario:
            fora, dentro = anel, anel.buffer(-espessura, join_style="mitre")
        else:
            fora, dentro = anel.buffer(espessura, join_style="mitre"), anel
        return fora.difference(dentro)

    linha = LineString(pontos)
    if linha.length == 0:
        return GeometryCollection()
    partes = [_faixa_da_linha(linha, espessura, alinhamento)]
    existentes = list(existentes)
    if existentes:
        cantos = (
            (pontos[0], pontos[1], True),
            (pontos[-1], pontos[-2], False),
        )
        for ponta, vizinho, inicio in cantos:
            extra = _completar_canto(ponta, vizinho, espessura,
                                     alinhamento if not inicio
                                     else _inverter(alinhamento),
                                     existentes)
            if extra is not None and not extra.is_empty:
                partes.append(extra)
    return _colar(unary_union(partes))


def _colar(geom):
    """Funde pedacos que so se tocam por diferenca de ponto flutuante."""
    return geom.buffer(FECHAR, join_style="mitre").buffer(
        -FECHAR, join_style="mitre")


def _inverter(alinhamento):
    """No inicio da linha o prolongamento anda para tras: troca os lados."""
    return {"esquerda": "direita", "direita": "esquerda"}.get(
        alinhamento, alinhamento)


# ---------------------------------------------------------------------- #
# Aberturas: recorte e restauracao
# ---------------------------------------------------------------------- #
def cortar(paredes, x1, y1, x2, y2, prof=PROF_CORTE):
    """Remove das paredes o trecho sob o segmento da abertura.

    So entram as paredes que acompanham o segmento (sobreposicao de pelo
    menos 0,2 m ou metade dele); uma parede perpendicular que so encosta na
    ponta da abertura fica intacta, assim como as paralelas vizinhas.
    Retorna (paredes_novas, recorte).
    """
    seg = LineString([(x1, y1), (x2, y2)])
    if seg.length < 1e-9:
        return list(paredes), []
    faixa = seg.buffer(prof, cap_style="flat")
    minimo = min(0.2, 0.5 * seg.length)
    novas, recorte = [], []
    for p in paredes:
        pol = para_shapely(p)
        if pol.distance(seg) > 0.02 or \
                seg.intersection(pol.buffer(0.02)).length < minimo:
            novas.append(p)
            continue
        removido = pol.intersection(faixa)
        if removido.area < AREA_MINIMA:
            novas.append(p)
            continue
        novas += de_shapely(pol.difference(faixa), p["tipo"], p["material"])
        recorte += de_shapely(removido, p["tipo"], p["material"])
    return novas, recorte


def restaurar(paredes, recorte):
    """Devolve os pedacos de `recorte` e os funde com as paredes vizinhas
    de mesmo tipo e material (a parede volta a ser uma peca so)."""
    novas = list(paredes)
    for pedaco in recorte:
        pol = para_shapely(pedaco)
        tocando = [p for p in novas
                   if p["tipo"] == pedaco["tipo"]
                   and p["material"] == pedaco["material"]
                   and para_shapely(p).distance(pol) <= 1e-3]
        ids = {id(p) for p in tocando}
        uniao = unary_union([pol] + [para_shapely(p) for p in tocando])
        uniao = _colar(uniao)
        novas = [p for p in novas if id(p) not in ids]
        novas += de_shapely(uniao, pedaco["tipo"], pedaco["material"])
    return novas


# ---------------------------------------------------------------------- #
# Comodos (espacos fechados por paredes e aberturas)
# ---------------------------------------------------------------------- #
def barreiras(paredes, aberturas):
    """Uniao de tudo que separa comodos: paredes, vaos das aberturas."""
    geoms = [corrigir(para_shapely(p)) for p in paredes]
    for a in aberturas:
        geoms += [para_shapely(r) for r in a.get("recorte", [])]
        geoms.append(LineString([(a["x1"], a["y1"]), (a["x2"], a["y2"])])
                     .buffer(0.02, cap_style="flat"))
    if not geoms:
        return GeometryCollection()
    uniao = unary_union(geoms)
    return uniao.buffer(1e-3, join_style="mitre").buffer(
        -1e-3, join_style="mitre")


def comodos(paredes, aberturas, area_minima=0.1):
    """(lista de Polygon dos comodos, fechado?).

    Os comodos sao os buracos da uniao das barreiras. Se nenhum contorno
    estiver fechado, devolve o envoltorio convexo menos as paredes, com
    fechado=False (o chamador avisa o usuario).
    """
    uniao = barreiras(paredes, aberturas)
    if uniao.is_empty:
        return [], False
    salas = []
    for pol in poligonos(uniao):
        for anel in pol.interiors:
            sala = Polygon(anel).difference(uniao)
            salas += [s for s in poligonos(sala) if s.area >= area_minima]
    if salas:
        return salas, True
    resto = uniao.convex_hull.difference(uniao)
    return [s for s in poligonos(resto) if s.area >= area_minima], False


# ---------------------------------------------------------------------- #
# Snap em aresta
# ---------------------------------------------------------------------- #
def bordas(paredes, guias):
    """Colecao com os contornos das paredes e as guias (para o snap)."""
    linhas = []
    for p in paredes:
        pol = para_shapely(p)
        linhas.append(pol.exterior)
        linhas += list(pol.interiors)
    for g in guias:
        linhas.append(LineString([(g["x1"], g["y1"]), (g["x2"], g["y2"])]))
    return GeometryCollection(linhas)


def ponto_em_aresta(x, y, geom_bordas, tolerancia):
    """Projecao de (x, y) na aresta mais proxima, ou None se estiver longe."""
    if geom_bordas is None or geom_bordas.is_empty:
        return None
    p = Point(x, y)
    if geom_bordas.distance(p) > tolerancia:
        return None
    q = nearest_points(geom_bordas, p)[0]
    return q.x, q.y
