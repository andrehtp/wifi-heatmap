"""Desenho da planta (somente leitura) e dos estilos visuais do heatmap."""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from .constants import CORES_MATERIAL, COR_PADRAO, ESTILO_PONTO, ESTILO_SEGMENTO


def desenhar_planta_base(ax, dados):
    """Reproducao somente-leitura de DrawingMixin._redesenhar (editor/rendering.py)."""
    for p in dados.get("paredes", []):
        tipo = p.get("tipo", "parede")
        estilo = ESTILO_SEGMENTO.get(tipo, ESTILO_SEGMENTO["parede"])
        xs, ys = [p["x1"], p["x2"]], [p["y1"], p["y2"]]

        if tipo in ("janela", "porta"):
            largura = max(4.0, p["espessura"] * 20)
            ax.plot(xs, ys, color="white", linewidth=largura + 2.5,
                    solid_capstyle="butt", zorder=4)
            ax.plot(xs, ys, color=estilo["cor"], linewidth=largura,
                    solid_capstyle="butt", zorder=5)
            continue

        ax.plot(xs, ys, color=estilo["cor"], linestyle=estilo["linestyle"],
                linewidth=max(1.5, p["espessura"] * 20),
                solid_capstyle="butt", zorder=3)

    for m in dados.get("moveis", []):
        cor = CORES_MATERIAL.get(m["material"], COR_PADRAO)
        ax.add_patch(Rectangle(
            (m["x"], m["y"]), m["largura"], m["profundidade"],
            facecolor=cor, alpha=0.4, edgecolor=cor, zorder=3))

    for pt in dados.get("pontos_medicao", []):
        tipo = pt.get("tipo", "medicao")
        estilo = ESTILO_PONTO.get(tipo, ESTILO_PONTO["medicao"])
        tem_leitura = bool(pt.get("leituras_dbm"))
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
