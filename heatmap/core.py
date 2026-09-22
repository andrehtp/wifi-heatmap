"""Classe principal do visualizador interativo de mapa de calor."""

from pathlib import Path

import matplotlib.pyplot as plt

from . import constants
from .interpolation import MODOS_INTERPOLACAO, extents, grade, preparar_amostras
from .rendering import MODOS_RENDER, desenhar_planta_base
from .widgets import WidgetsMixin


class HeatmapViewer(WidgetsMixin):
    def __init__(self, dados, saida_base, metodo="idw", estilo="campo_continuo"):
        self.dados = dados
        self.saida_base = saida_base
        self.metodo = metodo
        self.estilo = estilo

        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        if self.fig.canvas.manager is not None:
            self.fig.canvas.manager.set_window_title("Mapa de calor Wi-Fi")
        self.fig.subplots_adjust(left=0.06, right=0.58, top=0.94, bottom=0.10)
        # eixo fixo da colorbar, criado uma unica vez: fig.colorbar(..., ax=self.ax)
        # encolheria self.ax de novo a cada chamada (cumulativo entre redesenhos),
        # por isso desenhamos sempre dentro deste cax reservado (cla() + colorbar(cax=...))
        self._cax = self.fig.add_axes([0.615, 0.10, 0.02, 0.80])

        self._criar_widgets()
        self._redesenhar()
        print(constants.USAGE)

    def run(self):
        plt.show()

    def _redesenhar(self):
        self.ax.cla()
        self._cax.cla()

        xmin, xmax, ymin, ymax = extents(self.dados)
        self.ax.set_xlim(xmin, xmax)
        self.ax.set_ylim(ymin, ymax)
        self.ax.set_aspect("equal")
        self.ax.set_xlabel("x (m)")
        self.ax.set_ylabel("y (m)")

        coords, valores, _vazios = preparar_amostras(self.dados)
        cmap = plt.get_cmap(constants.COLORMAP_SINAL)
        mappable = None

        if len(coords) == 0:
            self.ax.set_title("Sem leituras ainda (leituras_dbm vazio em "
                              "todos os pontos de medicao)", fontsize=10, loc="left")
        else:
            _, funcao_interp = MODOS_INTERPOLACAO[self.metodo]
            rotulo_estilo, funcao_render, tipo_entrada = MODOS_RENDER[self.estilo]

            if tipo_entrada == "grade":
                grid_x, grid_y = grade(self.dados)
                valores_grid = funcao_interp(grid_x, grid_y, coords, valores)
                mappable = funcao_render(self.ax, grid_x, grid_y, valores_grid, cmap)
            else:
                mappable = funcao_render(self.ax, coords, valores, cmap)

            self.ax.set_title(
                f"metodo: {MODOS_INTERPOLACAO[self.metodo][0]}   |   "
                f"estilo: {rotulo_estilo}   |   {len(coords)} pontos com leitura",
                fontsize=10, loc="left")

        desenhar_planta_base(self.ax, self.dados)

        if mappable is not None:
            self.fig.colorbar(mappable, cax=self._cax, label=constants.ROTULO_COLORBAR)

        self.fig.canvas.draw_idle()

    def _exportar(self, ext):
        caminho = Path(self._tb_export.text.strip()).with_suffix(f".{ext}")
        self.fig.savefig(caminho, dpi=150 if ext == "png" else None,
                         bbox_inches="tight")
        print(f"Exportado: {caminho.resolve()}")
