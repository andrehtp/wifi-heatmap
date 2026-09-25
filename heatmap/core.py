"""Classe principal do visualizador interativo de mapa de calor."""

import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch
from mpl_toolkits.axes_grid1 import make_axes_locatable

from . import constants
from .interpolation import (
    MODOS_INTERPOLACAO,
    descrever_ajuste,
    extents,
    grade,
    montar_ctx,
    preparar_amostras,
)
from .mascara import MODOS_AREA, contorno_interior, mascara_interior
from .rendering import (
    MODOS_ESCALA,
    MODOS_RENDER,
    caminho_geometria,
    desenhar_planta_base,
    niveis_na_escala,
)
from .validacao import loocv, rotulo_com_parametro, tabela_loocv
from .widgets import WidgetsMixin

LARGURA_EIXO = 0.54   # fracao da figura para o mapa (+ colorbar); o resto e o painel
FONTE_TITULO = 8.5


class HeatmapViewer(WidgetsMixin):
    def __init__(self, dados, saida_base, metodo="idw", estilo="campo_continuo",
                 area="dentro", escala="fixa", agregacao="potencia",
                 leituras_por_id=None, validar=True):
        self.dados = dados
        # {id: [dBm]} vindo do CSV; None = leituras_dbm do proprio JSON
        self.leituras_por_id = leituras_por_id
        self.saida_base = saida_base
        self.metodo = metodo
        self.estilo = estilo
        self.area = area
        self.escala = escala

        # tudo que nao depende das escolhas do painel e calculado uma vez
        self._coords, self._valores, _vazios, ids = preparar_amostras(
            dados, leituras_por_id, agregacao)
        self._valores_por_id = dict(zip(ids, self._valores))
        self._grade = grade(dados)
        self._cache = {}          # barreiras, STRtree e perdas de parede (ctx)
        self._cache_interp = {}   # (metodo, parametro) -> (grade, avisos, ajuste)
        self._cache_loocv = {}    # (metodo, parametro) -> {"rmse", ...}
        self._contorno = None     # (geometria, fechado) do recorte vetorial
        self._parametros = {m: (p[1] if p else None)
                            for m, (_, _, p) in MODOS_INTERPOLACAO.items()}
        self._aviso_parametro = None
        try:
            self._contorno = contorno_interior(dados)
        except Exception as erro:  # geometria invalida: fica o recorte raster
            print(f"Aviso: contorno vetorial falhou ({erro}); usando mascara raster.")

        self.fig = plt.figure(figsize=(13, 8))
        if self.fig.canvas.manager is not None:
            self.fig.canvas.manager.set_window_title("Mapa de calor Wi-Fi")
        self.ax = self.fig.add_axes([0.05, 0.07, LARGURA_EIXO, 0.80])
        # eixo da colorbar criado uma unica vez via divider: fig.colorbar(..., ax=self.ax)
        # encolheria self.ax de novo a cada chamada (cumulativo entre redesenhos), e um
        # retangulo fixo nao acompanha self.ax quando set_aspect("equal") o encolhe para
        # caber a proporcao da planta - o divider resolve os dois problemas de uma vez,
        # recalculando a posicao do cax a partir da posicao REAL de self.ax a cada desenho.
        self._cax = make_axes_locatable(self.ax).append_axes("right", size="3%", pad="2%")
        # cada Colorbar com extend embrulha o locator atual do cax num que o
        # encolhe para caber os triangulos; cax.cla() nao desfaz isso, entao
        # sem restaurar o original o cax encolheria de novo a cada redesenho
        self._cax_locator = self._cax.get_axes_locator()

        self._criar_widgets()
        print(constants.USAGE)
        if validar and len(self._valores):
            print(tabela_loocv(dados, self._coords, self._valores, self._cache))
        self._redesenhar()

    def run(self):
        plt.show()

    # ------------------------------------------------------------------ #

    def _interpolar(self, metodo, parametro):
        chave = (metodo, parametro)
        if chave not in self._cache_interp:
            ctx = montar_ctx(self.dados, parametro, self._cache)
            grid_x, grid_y = self._grade
            valores_grid = MODOS_INTERPOLACAO[metodo][1](
                grid_x, grid_y, self._coords, self._valores, ctx)
            self._cache_interp[chave] = (valores_grid, ctx["avisos"], ctx["ajuste"])
        return self._cache_interp[chave]

    def _loocv(self, metodo, parametro):
        chave = (metodo, parametro)
        if chave not in self._cache_loocv:
            self._cache_loocv[chave] = loocv(metodo, self.dados, self._coords,
                                             self._valores, parametro, self._cache)
        return self._cache_loocv[chave]

    def _recorte(self):
        """(clip path | None, mascara raster | None, avisos) para a area "dentro"."""
        if self._contorno is not None:
            geom, fechado = self._contorno
            avisos = [] if fechado else [
                "contorno das paredes aberto: recorte pelo fecho convexo"]
            if geom is None:  # planta sem paredes: nada a recortar
                return None, None, avisos
            return PathPatch(caminho_geometria(geom), transform=self.ax.transData), None, avisos
        mascara, fechado = mascara_interior(self.dados, *self._grade)
        avisos = [] if fechado else [
            "contorno das paredes aberto: recorte pelo fecho convexo"]
        return None, mascara, avisos

    def _redesenhar(self):
        self._ler_parametro()
        self.ax.cla()
        self._cax.cla()
        self.ax.set_aspect("equal")
        self.ax.set_xlabel("x (m)")
        self.ax.set_ylabel("y (m)")

        coords, valores = self._coords, self._valores
        cmap = plt.get_cmap(constants.COLORMAP_SINAL)
        mappable = norm = None

        if len(coords) == 0:
            self._titulo_linhas = ["Sem leituras: passe a tabela CSV com --tabela "
                                   "(ids iguais aos dos pontos)"]
            self._aplicar_titulo()
        else:
            parametro = self._parametros[self.metodo]
            rotulo_estilo, funcao_render, tipo_entrada = MODOS_RENDER[self.estilo]
            rotulo_area, recortar_area = MODOS_AREA[self.area]
            rotulo_escala, funcao_norma = MODOS_ESCALA[self.escala]
            norm = funcao_norma(valores)
            avisos, detalhes = [], []

            if tipo_entrada == "grade":
                entrada, avisos_metodo, ajuste = self._interpolar(self.metodo, parametro)
                avisos += avisos_metodo
                resultado = self._loocv(self.metodo, parametro)
                if resultado is not None:
                    detalhes.append(f"LOOCV RMSE {resultado['rmse']:.1f} dB")
                if descrever_ajuste(ajuste):
                    detalhes.append(descrever_ajuste(ajuste))
                rotulo_metodo = rotulo_com_parametro(self.metodo, parametro)
            else:
                entrada = (coords, valores)
                rotulo_metodo = "(blobs nao interpolam)"

            clip, mascara = None, None
            if recortar_area:
                clip, mascara, avisos_recorte = self._recorte()
                avisos += avisos_recorte
            artistas, mappable = funcao_render(
                self.ax, *self._grade, entrada, norm, cmap, mascara=mascara)
            if clip is not None:
                for artista in artistas:
                    artista.set_clip_path(clip)

            if self._aviso_parametro:
                avisos.append(self._aviso_parametro)
            linhas = [f"{rotulo_metodo} | {rotulo_estilo} | {rotulo_area} | "
                      f"escala {self.escala} | {len(coords)} pontos"]
            if detalhes:
                linhas.append(" | ".join(detalhes))
            if avisos:
                linhas.append("aviso: " + "; ".join(avisos))
            self._titulo_linhas = linhas
            self._aplicar_titulo()

        desenhar_planta_base(self.ax, self.dados, self._valores_por_id)

        # imshow (blobs) reajusta os limites: fixa por ultimo
        xmin, xmax, ymin, ymax = extents(self.dados)
        self.ax.set_xlim(xmin, xmax)
        self.ax.set_ylim(ymin, ymax)

        if mappable is not None:
            self._cax.set_axis_on()
            self._cax.set_axes_locator(self._cax_locator)
            bandas = self.estilo == "bandas_contorno"
            fixa = self.escala == "fixa"
            cbar = self.fig.colorbar(
                mappable, cax=self._cax, label=constants.ROTULO_COLORBAR,
                extend="both", spacing="proportional" if bandas else "uniform",
                ticks=niveis_na_escala(norm) if (bandas or fixa) else None)
            cbar.ax.tick_params(labelsize=8)
        else:
            self._cax.set_axis_off()

        self.fig.canvas.draw_idle()

    def _aplicar_titulo(self):
        """Titulo do mapa quebrado na largura do eixo, com fonte proporcional a
        janela (em janelas pequenas nao invade o painel da direita)."""
        tamanho = FONTE_TITULO * self._fator_fonte()
        largura_pt = LARGURA_EIXO * self.fig.get_figwidth() * 72
        caracteres = max(40, int(largura_pt / (0.52 * tamanho)))
        self.ax.set_title("\n".join(
            parte for linha in self._titulo_linhas
            for parte in textwrap.wrap(linha, caracteres)), fontsize=tamanho, loc="left")

    def _exportar(self, ext):
        """Salva so o mapa e a colorbar: o painel de widgets (demais eixos e
        textos da figura) fica oculto durante o savefig, e bbox_inches="tight"
        ignora artistas invisiveis, entao o recorte fecha no mapa + escala."""
        caminho = Path(self._tb_export.text.strip()).with_suffix(f".{ext}")
        manter = {self.ax}
        if self._cax.axison:  # sem mappable a colorbar fica desligada
            manter.add(self._cax)
        ocultos = [a for a in (*self.fig.axes, *self.fig.texts)
                   if a not in manter and a.get_visible()]
        for artista in ocultos:
            artista.set_visible(False)
        try:
            self.fig.savefig(caminho, dpi=150 if ext == "png" else None,
                             bbox_inches="tight", pad_inches=0.15)
        finally:
            for artista in ocultos:
                artista.set_visible(True)
            self.fig.canvas.draw_idle()
        print(f"Exportado: {caminho.resolve()}")
