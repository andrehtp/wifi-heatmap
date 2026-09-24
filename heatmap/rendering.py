"""Desenho da planta (somente leitura) e dos estilos visuais do heatmap."""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path
from shapely import Polygon
from shapely.geometry.polygon import orient

from .constants import (
    COR_MATERIAL_PAREDE,
    COR_PAREDE_PADRAO,
    CORES_MATERIAL,
    COR_PADRAO,
    ESTILO_ABERTURA,
    ESTILO_PAREDE,
    ESTILO_PONTO,
)
from .interpolation import leituras_do_ponto


def _caminho(dic):
    """Path do matplotlib para um poligono {"vertices", "furos"} do JSON."""
    pol = orient(Polygon(dic["vertices"], dic.get("furos") or None))
    return Path.make_compound_path(*[
        Path(np.asarray(anel.coords), closed=True)
        for anel in (pol.exterior, *pol.interiors)])


def desenhar_planta_base(ax, dados, leituras_por_id=None):
    """Reproducao somente-leitura de DrawingMixin._redesenhar (editor/rendering.py)."""
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
        tem_leitura = bool(leituras_do_ponto(pt, leituras_por_id))
        if tipo == "medicao" and not tem_leitura:
            ax.scatter([pt["x"]], [pt["y"]], facecolors="none",
                       edgecolors=estilo["cor"], marker=estilo["marcador"],
                       zorder=8, linewidths=1.5)
        else:
            ax.scatter([pt["x"]], [pt["y"]], color=estilo["cor"],
                       marker=estilo["marcador"], zorder=8)
        ax.annotate(str(pt["id"]), (pt["x"], pt["y"]),
                    textcoords="offset points", xytext=(5, 5),
                    fontsize=8, color=estilo["cor"])


# ---------------------------------------------------------------------- #
# Estilos visuais do overlay de heatmap
# ---------------------------------------------------------------------- #


def campo_continuo(ax, grid_x, grid_y, valores_grid, cmap):
    return ax.pcolormesh(grid_x, grid_y, valores_grid, cmap=cmap,
                         shading="auto", alpha=0.75, zorder=1)


def bandas_contorno(ax, grid_x, grid_y, valores_grid, cmap):
    return ax.contourf(grid_x, grid_y, valores_grid, levels=12,
                       cmap=cmap, alpha=0.75, zorder=1)


def blobs(ax, coords, valores, cmap, raio=2.0):
    """Gradientes radiais translucidos centrados em cada ponto medido."""
    norm = plt.Normalize(valores.min(), valores.max())
    for (x, y), v in zip(coords, valores):
        cor = cmap(norm(v))
        for r, a in zip(np.linspace(raio, 0.15, 8), np.linspace(0.03, 0.35, 8)):
            ax.add_patch(plt.Circle((x, y), r, color=cor, alpha=a,
                                    zorder=1, linewidth=0))
    return plt.cm.ScalarMappable(norm=norm, cmap=cmap)


MODOS_RENDER = {
    "campo_continuo": ("Campo continuo", campo_continuo, "grade"),
    "bandas_contorno": ("Bandas / contornos", bandas_contorno, "grade"),
    "blobs": ("Blobs por ponto", blobs, "pontos"),
}
