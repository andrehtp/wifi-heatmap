"""Widgets da coluna da direita (dentro do canvas, fora do plano)."""

from matplotlib.widgets import Button, TextBox

from .constants import PALETAS


def definir_texto(caixa, texto):
    """Troca o texto de uma TextBox sem o draw() sincrono de set_val()."""
    caixa.text_disp.set_text(texto)
    caixa.cursor_index = len(texto)


class WidgetsMixin:
    def _criar_widgets(self):
        col_x, col_larg = 0.635, 0.35

        self.fig.text(col_x, 0.965, "VISUALIZACAO (area visivel, m)",
                      fontsize=9, family="monospace", va="top", weight="bold")
        self._tb_largura = TextBox(
            self.fig.add_axes([0.750, 0.900, 0.10, 0.038]), "largura ")
        self._tb_altura = TextBox(
            self.fig.add_axes([0.750, 0.852, 0.10, 0.038]), "altura ")
        self._bt_vista = Button(
            self.fig.add_axes([0.872, 0.900, 0.113, 0.038]), "aplicar")
        self._bt_enquadrar = Button(
            self.fig.add_axes([0.872, 0.852, 0.113, 0.038]), "enquadrar")
        self._tb_largura.on_submit(lambda _t: self._aplicar_vista())
        self._tb_altura.on_submit(lambda _t: self._aplicar_vista())
        self._bt_vista.on_clicked(lambda _e: self._aplicar_vista())
        self._bt_enquadrar.on_clicked(lambda _e: self._enquadrar())

        # Painel de edicao: os widgets sao criados uma vez so e reaproveitados
        # a cada selecao (rotulo, valor e visibilidade mudam).
        self._bt_tipo = Button(
            self.fig.add_axes([col_x, 0.688, col_larg, 0.040]), "tipo")
        self._bt_material = Button(
            self.fig.add_axes([col_x, 0.640, col_larg, 0.040]), "material")
        self._caixas = []
        for i in range(5):
            eixo = self.fig.add_axes([0.800, 0.583 - i * 0.048, 0.185, 0.038])
            caixa = TextBox(eixo, "")
            caixa.on_submit(lambda _t: self._aplicar_edicao())
            self._caixas.append(caixa)
        self._bt_aplicar = Button(
            self.fig.add_axes([col_x, 0.300, 0.11, 0.045]), "aplicar")
        self._bt_excluir = Button(
            self.fig.add_axes([0.755, 0.300, 0.11, 0.045]), "excluir")
        self._bt_fechar = Button(
            self.fig.add_axes([0.875, 0.300, 0.11, 0.045]), "fechar")
        self._bt_tipo.on_clicked(lambda _e: self._ciclar("tipo"))
        self._bt_material.on_clicked(lambda _e: self._ciclar("material"))
        self._bt_aplicar.on_clicked(lambda _e: self._aplicar_edicao())
        self._bt_excluir.on_clicked(lambda _e: self._excluir_edicao())
        self._bt_fechar.on_clicked(lambda _e: self._fechar_edicao())

        self._widgets_edicao = [self._bt_tipo, self._bt_material, *self._caixas,
                                self._bt_aplicar, self._bt_excluir,
                                self._bt_fechar]
        self._textboxes = [self._tb_largura, self._tb_altura, *self._caixas]
        self._mostrar_edicao(False)

    def _digitando(self):
        """True enquanto alguma caixa de texto estiver capturando o teclado."""
        return any(c.capturekeystrokes for c in self._textboxes)

    # ------------------------------------------------------------------ #
    # Selecao de material / tipo (substitui os prompts do terminal)
    # ------------------------------------------------------------------ #
    def _paleta(self):
        """(rotulo, opcoes) da paleta do modo atual, ou None."""
        return PALETAS.get(self.modo)

    def _opcao_atual(self, modo=None):
        modo = modo or self.modo
        paleta = PALETAS.get(modo)
        if paleta is None:
            return None
        return paleta[1][self._selecao[modo]]

    def _selecionar_opcao(self, indice):
        paleta = self._paleta()
        if paleta is None or not (0 <= indice < len(paleta[1])):
            return
        self._selecao[self.modo] = indice
        print(f"{paleta[0]} do modo {self.modo}: {paleta[1][indice]}")
        self._atualizar_painel()
