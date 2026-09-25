"""Desenho da planta (somente leitura) e dos estilos visuais do heatmap."""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import patheffects
from matplotlib.colors import Normalize
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path
import shapely
from shapely import Polygon
from shapely.geometry.polygon import orient

from .constants import (
    ALPHA_HEATMAP,
    COR_MATERIAL_PAREDE,
    COR_PAREDE_PADRAO,
    CORES_MATERIAL,
    COR_PADRAO,
    ESCALA_DBM,
    ESTILO_ABERTURA,
    ESTILO_PAREDE,
    ESTILO_PONTO,
    NIVEIS_DBM,
    RAIO_BLOB,
)

_HALO = [patheffects.withStroke(linewidth=2.5, foreground="white")]


def _caminho_poligono(pol):
    pol = orient(pol)
    return [Path(np.asarray(anel.coords), closed=True)
            for anel in (pol.exterior, *pol.interiors)]


def _caminho(dic):
    """Path do matplotlib para um poligono {"vertices", "furos"} do JSON."""
    return Path.make_compound_path(
        *_caminho_poligono(Polygon(dic["vertices"], dic.get("furos") or None)))


def caminho_geometria(geom):
    """Path do matplotlib para um Polygon/MultiPolygon do shapely (com furos)."""
    return Path.make_compound_path(*[
        anel for parte in shapely.get_parts(geom) if isinstance(parte, Polygon)
        for anel in _caminho_poligono(parte)])


def _formatar_dbm(valor):
    return f"{valor:.0f}".replace("-", "−")


def desenhar_planta_base(ax, dados, valores_por_id=None):
    """Reproducao somente-leitura de DrawingMixin._redesenhar (editor/rendering.py).

    valores_por_id: {id: leitura agregada em dBm} dos pontos com leitura;
    eles ganham o rotulo "id: valor", os demais pontos de medicao sao
    desenhados vazios.
    """
    valores_por_id = valores_por_id or {}
    for p in dados.get("paredes", []):
        estilo = ESTILO_PAREDE.get(p.get("tipo"), ESTILO_PAREDE["parede"])
        cor = COR_MATERIAL_PAREDE.get(p.get("material"), COR_PAREDE_PADRAO)
        if "vertices" in p:
            ax.add_patch(PathPatch(
                _caminho(p), facecolor=cor, edgecolor=cor,
                alpha=estilo["alpha"], hatch=estilo["hatch"],
                linewidth=0.6, zorder=3))
        else:  # planta antiga, parede em segmento
            ax.plot([p["x1"], p["x2"]], [p["y1"], p["y2"]], color="black",
                    linewidth=max(1.5, p.get("espessura", 0.1) * 20),
                    solid_capstyle="butt", zorder=3)

    for a in dados.get("aberturas", []):
        cor = ESTILO_ABERTURA.get(a.get("tipo"), ESTILO_ABERTURA["porta"])["cor"]
        for r in a.get("recorte", []):
            ax.add_patch(PathPatch(_caminho(r), facecolor=cor, edgecolor=cor,
                                   alpha=0.35, linewidth=0.8, zorder=4))
        ax.plot([a["x1"], a["x2"]], [a["y1"], a["y2"]], color=cor,
                linewidth=2.5, linestyle=":" if a.get("tipo") == "vao" else "-",
                solid_capstyle="butt", zorder=5)

    for m in dados.get("moveis", []):
        cor = CORES_MATERIAL.get(m["material"], COR_PADRAO)
        ax.add_patch(Rectangle(
            (m["x"], m["y"]), m["largura"], m["profundidade"],
            facecolor=cor, alpha=0.4, edgecolor=cor, zorder=3))

    for pt in dados.get("pontos_medicao", []):
        tipo = pt.get("tipo", "medicao")
        estilo = ESTILO_PONTO.get(tipo, ESTILO_PONTO["medicao"])
        valor = valores_por_id.get(pt["id"])
        if tipo == "medicao" and valor is None:
            ax.scatter([pt["x"]], [pt["y"]], facecolors="none",
                       edgecolors=estilo["cor"], marker=estilo["marcador"],
                       zorder=8, linewidths=1.5)
        else:
            ax.scatter([pt["x"]], [pt["y"]], color=estilo["cor"],
                       marker=estilo["marcador"], edgecolors="white",
                       linewidths=0.6, zorder=8)
        rotulo = str(pt["id"]) if valor is None else f"{pt['id']}: {_formatar_dbm(valor)}"
        ax.annotate(rotulo, (pt["x"], pt["y"]), textcoords="offset points",
                    xytext=(4, 4), fontsize=7, color=estilo["cor"],
                    path_effects=_HALO, zorder=9)


# ---------------------------------------------------------------------- #
# Escala de cor (uma so norma para todos os estilos)
# ---------------------------------------------------------------------- #


def _norma_fixa(valores):
    return Normalize(*ESCALA_DBM)


def _norma_auto(valores):
    """Min/max das amostras medidas (nao da grade interpolada): trocar de
    metodo nao muda as cores."""
    vmin, vmax = float(np.min(valores)), float(np.max(valores))
    if vmax - vmin < 1.0:
        vmin, vmax = vmin - 0.5, vmax + 0.5
    return Normalize(vmin, vmax)


# chave: (rotulo, funcao(valores medidos) -> Normalize)
MODOS_ESCALA = {
    "fixa": (f"Fixa ({ESCALA_DBM[0]:.0f} a {ESCALA_DBM[1]:.0f} dBm)", _norma_fixa),
    "auto": ("Auto (min/max medidos)", _norma_auto),
}


def niveis_na_escala(norm):
    """Limiares de NIVEIS_DBM dentro da norma, mais os extremos dela."""
    internos = [n for n in NIVEIS_DBM if norm.vmin < n < norm.vmax]
    return [norm.vmin, *internos, norm.vmax]


# ---------------------------------------------------------------------- #
# Estilos visuais do overlay de heatmap
#
# fn(ax, grid_x, grid_y, entrada, norm, cmap, mascara=None)
#   -> ([artistas a recortar], mappable da colorbar)
# entrada = grade interpolada (tipo "grade") ou (coords, valores) ("pontos").
# mascara = grade booleana (so no fallback raster) ou None.
# ---------------------------------------------------------------------- #


def _mascarar(valores_grid, mascara):
    return valores_grid if mascara is None else np.where(mascara, valores_grid, np.nan)


def campo_continuo(ax, grid_x, grid_y, valores_grid, norm, cmap, mascara=None):
    malha = ax.pcolormesh(grid_x, grid_y, _mascarar(valores_grid, mascara),
                          cmap=cmap, norm=norm, shading="nearest",
                          alpha=ALPHA_HEATMAP, zorder=1, rasterized=True)
    return [malha], malha


def bandas_contorno(ax, grid_x, grid_y, valores_grid, norm, cmap, mascara=None):
    """Bandas com limites fixos em dBm (limiares de qualidade Wi-Fi)."""
    bandas = ax.contourf(grid_x, grid_y, _mascarar(valores_grid, mascara),
                         levels=niveis_na_escala(norm), cmap=cmap, norm=norm,
                         extend="both", alpha=ALPHA_HEATMAP, zorder=1)
    linhas = ax.contour(grid_x, grid_y, _mascarar(valores_grid, mascara),
                        levels=bandas.levels, colors="white", linewidths=0.5,
                        alpha=0.6, zorder=2)
    return [bandas, linhas], bandas


def blobs(ax, grid_x, grid_y, entrada, norm, cmap, mascara=None, raio=RAIO_BLOB):
    """Manchas radiais em volta de cada ponto medido, numa camada RGBA unica.

    Cor = media dos valores ponderada pelo kernel de cada ponto; opacidade =
    o maior kernel (sem somar alphas de circulos empilhados, que deixava as
    cores barrentas). Mesma norma e mesmo recorte dos outros estilos.
    """
    coords, valores = entrada
    d2 = (grid_x[..., None] - coords[:, 0]) ** 2 + (grid_y[..., None] - coords[:, 1]) ** 2
    kernel = np.clip(1.0 - d2 / raio**2, 0.0, None) ** 2  # 1 no ponto, 0 no raio
    soma = kernel.sum(axis=-1)
    valor = np.sum(kernel * valores, axis=-1) / np.where(soma > 0, soma, 1.0)
    rgba = cmap(norm(valor))
    rgba[..., 3] = ALPHA_HEATMAP * kernel.max(axis=-1)
    if mascara is not None:
        rgba[..., 3] = np.where(mascara, rgba[..., 3], 0.0)
    passo_x = grid_x[0, 1] - grid_x[0, 0] if grid_x.shape[1] > 1 else 1.0
    passo_y = grid_y[1, 0] - grid_y[0, 0] if grid_y.shape[0] > 1 else 1.0
    imagem = ax.imshow(rgba, origin="lower", interpolation="bilinear", zorder=1,
                       extent=(grid_x[0, 0] - passo_x / 2, grid_x[0, -1] + passo_x / 2,
                               grid_y[0, 0] - passo_y / 2, grid_y[-1, 0] + passo_y / 2))
    return [imagem], plt.cm.ScalarMappable(norm=norm, cmap=cmap)


MODOS_RENDER = {
    "campo_continuo": ("Campo continuo", campo_continuo, "grade"),
    "bandas_contorno": ("Bandas (limiares dBm)", bandas_contorno, "grade"),
    "blobs": ("Blobs por ponto", blobs, "pontos"),
}
