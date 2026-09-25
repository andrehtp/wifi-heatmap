"""Widgets da coluna da direita: seletores, parametro do metodo e exportacao.

A coluna e montada de cima para baixo, com a altura de cada seletor
proporcional ao numero de opcoes do registro correspondente - um metodo
novo em MODOS_INTERPOLACAO nao exige mexer em coordenada nenhuma.
"""

from matplotlib.widgets import Button, RadioButtons, TextBox

from .interpolation import MODOS_INTERPOLACAO
from .mascara import MODOS_AREA
from .rendering import MODOS_ESCALA, MODOS_RENDER

COL_X, COL_LARG = 0.665, 0.315   # coluna da direita, em fracao da figura
TOPO = 0.965
H_TITULO = 0.030                 # altura de um titulo de secao
H_ITEM = 0.031                   # altura por opcao de um RadioButtons
H_CAIXA = 0.036                  # TextBox / Button
ESPACO = 0.016                   # entre secoes
ALTURA_REF = 8.0                 # polegadas de figura em que as fontes abaixo valem
FONTE_TITULO, FONTE_ITEM = 9.0, 8.5


def definir_texto(caixa, texto):
    """Troca o texto de uma TextBox sem o draw() sincrono de set_val()."""
    caixa.text_disp.set_text(texto)
    caixa.cursor_index = len(texto)


def _chave_por_rotulo(registro, rotulo):
    return next(chave for chave, valor in registro.items() if valor[0] == rotulo)


class WidgetsMixin:
    def _criar_widgets(self):
        self._y_coluna = TOPO
        self._titulos, self._radios = [], []

        self._radio_metodo = self._secao_radio(
            "METODO DE INTERPOLACAO", MODOS_INTERPOLACAO, self.metodo, self._mudar_metodo)

        # parametro principal do metodo ativo (p, sigma, suavizacao...)
        self._y_coluna -= H_CAIXA
        self._tb_param = TextBox(
            self.fig.add_axes([COL_X + 0.13, self._y_coluna, COL_LARG - 0.13, H_CAIXA]),
            "parametro ", initial="")
        self._tb_param.on_submit(lambda _t: self._redesenhar())
        self._metodo_param = None  # metodo cujo parametro a caixa mostra
        self._sincronizar_parametro()
        self._y_coluna -= ESPACO

        self._radio_estilo = self._secao_radio(
            "ESTILO VISUAL", MODOS_RENDER, self.estilo, self._mudar_estilo)
        self._radio_area = self._secao_radio(
            "AREA DO MAPA", MODOS_AREA, self.area, self._mudar_area)
        self._radio_escala = self._secao_radio(
            "ESCALA DE COR", MODOS_ESCALA, self.escala, self._mudar_escala)

        self._titulo_secao("EXPORTAR")
        self._y_coluna -= H_CAIXA
        self._tb_export = TextBox(
            self.fig.add_axes([COL_X + 0.07, self._y_coluna, COL_LARG - 0.07, H_CAIXA]),
            "arquivo ", initial=str(self.saida_base))
        self._y_coluna -= H_CAIXA + 0.008
        meia = (COL_LARG - 0.01) / 2
        self._bt_png = Button(
            self.fig.add_axes([COL_X, self._y_coluna, meia, H_CAIXA]), "Exportar PNG")
        self._bt_svg = Button(
            self.fig.add_axes([COL_X + meia + 0.01, self._y_coluna, meia, H_CAIXA]),
            "Exportar SVG")
        self._bt_png.on_clicked(lambda _e: self._exportar("png"))
        self._bt_svg.on_clicked(lambda _e: self._exportar("svg"))

        self._textboxes = [self._tb_param, self._tb_export]
        self._ajustar_fontes()
        self.fig.canvas.mpl_connect("resize_event", lambda _e: self._ajustar_fontes())

    def _titulo_secao(self, texto):
        self._titulos.append(self.fig.text(
            COL_X, self._y_coluna, texto, family="monospace", va="top", weight="bold"))
        self._y_coluna -= H_TITULO

    def _secao_radio(self, titulo, registro, ativo, callback):
        self._titulo_secao(titulo)
        altura = H_ITEM * len(registro)
        self._y_coluna -= altura
        radio = RadioButtons(
            self.fig.add_axes([COL_X, self._y_coluna, COL_LARG, altura]),
            [valor[0] for valor in registro.values()], active=list(registro).index(ativo))
        radio.on_clicked(callback)
        self._radios.append(radio)
        self._y_coluna -= ESPACO
        return radio

    def _fator_fonte(self):
        return min(max(self.fig.get_figheight() / ALTURA_REF, 0.7), 1.2)

    def _ajustar_fontes(self):
        """Fontes proporcionais a altura da janela: em janelas menores os
        seletores encolhem, mas o texto (em pontos) nao - sem isto, ele
        transbordaria e se sobreporia."""
        fator = self._fator_fonte()
        for titulo in self._titulos:
            titulo.set_fontsize(FONTE_TITULO * fator)
        for radio in self._radios:
            for rotulo in radio.labels:
                rotulo.set_fontsize(FONTE_ITEM * fator)
        for caixa in (self._tb_param, self._tb_export):
            caixa.label.set_fontsize(FONTE_ITEM * fator)
            caixa.text_disp.set_fontsize(FONTE_ITEM * fator)
        if hasattr(self, "_titulo_linhas"):  # titulo do mapa: re-quebra na largura nova
            self._aplicar_titulo()

    # ------------------------------------------------------------------ #
    # parametro do metodo
    # ------------------------------------------------------------------ #

    def _sincronizar_parametro(self):
        """Mostra na caixa o rotulo/valor do parametro do metodo ativo."""
        param = MODOS_INTERPOLACAO[self.metodo][2]
        if param is None:
            rotulo, texto = "sem parametro ", "-"
        else:
            valor = self._parametros[self.metodo]
            rotulo, texto = f"{param[0]} ", "auto" if valor is None else f"{valor:g}"
        self._tb_param.label.set_text(rotulo)
        definir_texto(self._tb_param, texto)
        self._metodo_param = self.metodo

    def _ler_parametro(self):
        """Le a caixa (chamado a cada redesenho). Valor invalido ou fora da
        faixa mantem o anterior e vira aviso no titulo."""
        if self._metodo_param != self.metodo:  # metodo trocado por fora do painel
            self._sincronizar_parametro()
            return
        self._aviso_parametro = None
        param = MODOS_INTERPOLACAO[self.metodo][2]
        if param is None:
            return
        rotulo, padrao, (minimo, maximo) = param
        texto = self._tb_param.text.strip().replace(",", ".")
        if texto.lower() in ("", "auto"):
            valor = padrao
        else:
            try:
                valor = float(texto)
            except ValueError:
                valor = None
            if valor is None or not minimo <= valor <= maximo:
                atual = self._parametros[self.metodo]
                self._aviso_parametro = (
                    f"{rotulo} '{texto}' invalido (faixa {minimo:g} a {maximo:g}), "
                    f"mantido {'auto' if atual is None else f'{atual:g}'}")
                return
        self._parametros[self.metodo] = valor

    # ------------------------------------------------------------------ #
    # callbacks dos seletores
    # ------------------------------------------------------------------ #

    def _mudar_metodo(self, rotulo):
        self._ler_parametro()  # guarda o que foi digitado para o metodo anterior
        self.metodo = _chave_por_rotulo(MODOS_INTERPOLACAO, rotulo)
        self._sincronizar_parametro()
        self._redesenhar()

    def _mudar_estilo(self, rotulo):
        self.estilo = _chave_por_rotulo(MODOS_RENDER, rotulo)
        self._redesenhar()

    def _mudar_area(self, rotulo):
        self.area = _chave_por_rotulo(MODOS_AREA, rotulo)
        self._redesenhar()

    def _mudar_escala(self, rotulo):
        self.escala = _chave_por_rotulo(MODOS_ESCALA, rotulo)
        self._redesenhar()
