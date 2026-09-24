"""Classe principal do editor interativo de planta baixa."""

from pathlib import Path

import matplotlib.pyplot as plt

from . import constants
from .distribuicao import MODOS_DISTRIBUICAO
from .edit_panel import EditPanelMixin
from .elements import ElementsMixin
from .events import EventsMixin
from .hit_testing import HitTestingMixin
from .navigation import NavigationMixin
from .rendering import DrawingMixin, HudMixin
from .widgets import WidgetsMixin

# Os atalhos padrao do matplotlib (pan, fullscreen, salvar figura, grade...)
# usam as mesmas teclas do editor; sem isso, "p" ligaria o pan e o clique
# arrastaria o grafico em vez de marcar um ponto.
for _keymap in ("keymap.fullscreen", "keymap.pan", "keymap.save",
                "keymap.quit", "keymap.grid", "keymap.grid_minor",
                "keymap.zoom", "keymap.home", "keymap.back", "keymap.forward",
                "keymap.xscale", "keymap.yscale"):
    plt.rcParams[_keymap] = []


class PlantaEditor(WidgetsMixin, DrawingMixin, HudMixin, HitTestingMixin,
                    EditPanelMixin, NavigationMixin, EventsMixin,
                    ElementsMixin):
    def __init__(self, largura, altura, output_path, input_path=None,
                 passo=0.25):
        self.output_path = Path(output_path)
        self.paredes = []      # poligonos (ver poligonos.py)
        self.aberturas = []    # janelas/portas/vaos, em segmento
        self.moveis = []
        self.pontos_medicao = []
        self.guias = []        # paredes antigas em linha, so como referencia
        self._next_ponto_id = 1
        self._historico = []  # pilha de snapshots completos, para o undo
        self._arquivo_legado = None  # planta antiga lida: copia antes de salvar

        self.modo = None
        self._cliques_pendentes = []
        self.passo = passo
        self.snap = True
        # cada modo lembra a sua propria escolha de material / tipo
        self._selecao = {modo: 0 for modo in constants.PALETAS}
        # parametros dos modos, editados nas caixas do painel
        self.espessura = constants.ESPESSURA_PADRAO
        self.alinhamento = constants.ALINHAMENTOS[0]
        self.mostrar_guias = True
        self._movel_nome = "Movel"
        self._movel_material = constants.MATERIAIS_MOVEL[0]
        self._valor_distribuicao = {
            chave: padrao
            for chave, (_r, _rv, padrao, _f, _i) in MODOS_DISTRIBUICAO.items()}
        self._margem_distribuicao = constants.MARGEM_PAREDE_PADRAO
        # tabela CSV de medicao (modo ponto / tecla t); o caminho que recusou
        # sobrescrever fica guardado para o proximo "t" confirmar
        self._caminho_tabela = str(self.output_path.with_name(
            self.output_path.stem + "_medicao.csv"))
        self._confirmar_tabela = None
        self._estado_param = None  # (modo, opcao) que as caixas mostram
        self._cache_geo = {}       # geometrias derivadas, limpas a cada redesenho

        # navegacao (espaco + arrastar / botao do meio / scroll)
        self._espaco = False
        self._timer_espaco = None
        self._pan = None
        self._arraste = None   # objeto selecionado sendo arrastado

        # leitura do cursor (HUD desenhado por blitting)
        self._fundo = None
        self._pos_cursor = None
        self._hud = []

        # edicao pelo botao direito
        self._sel = None       # (categoria, indice) do objeto selecionado
        self._edicao = None    # copia de trabalho, so confirmada em "aplicar"
        self._campos = []      # [(chave, rotulo)] das caixas em uso
        self._fechando = False

        self.fig, self.ax = plt.subplots(figsize=(13, 8))
        if self.fig.canvas.manager is not None:
            self.fig.canvas.manager.set_window_title("Editor de planta baixa")
        self.fig.subplots_adjust(left=0.06, right=0.60, top=0.94, bottom=0.10)
        # margem para as paredes coladas em x=0 / y=0 nao serem cortadas
        self._xlim0, self._ylim0 = (-0.3, largura + 0.3), (-0.3, altura + 0.3)

        if input_path:
            self._carregar(input_path)

        self._configurar_eixos()
        self._painel = self.fig.text(
            0.635, 0.815, "", fontsize=8.5, family="monospace", va="top",
        )
        self._painel_teclas = self.fig.text(
            0.815, 0.815, "", fontsize=8.5, family="monospace", va="top",
        )
        self._titulo_edicao = self.fig.text(
            0.635, 0.822, "", fontsize=8.5, family="monospace", va="top",
            visible=False,
        )
        self._status = self.fig.text(
            0.06, 0.015, "", fontsize=9, family="monospace", va="bottom",
            animated=True,
        )
        self._criar_widgets()
        self._criar_artistas_hud()
        self._redesenhar()
        self._sincronizar_caixas_vista()

        canvas = self.fig.canvas
        canvas.mpl_connect("button_press_event", self._on_click)
        canvas.mpl_connect("button_release_event", self._on_release)
        canvas.mpl_connect("motion_notify_event", self._on_motion)
        canvas.mpl_connect("scroll_event", self._on_scroll)
        canvas.mpl_connect("key_press_event", self._on_key)
        canvas.mpl_connect("key_release_event", self._on_key_release)
        canvas.mpl_connect("figure_leave_event", self._on_leave)
        canvas.mpl_connect("draw_event", self._on_draw)
        print(constants.USAGE)

    def run(self):
        plt.show()
