"""Widgets da coluna da direita: seletores de metodo/estilo e exportacao."""

from matplotlib.widgets import Button, RadioButtons, TextBox

from .interpolation import MODOS_INTERPOLACAO
from .rendering import MODOS_RENDER


def definir_texto(caixa, texto):
    """Troca o texto de uma TextBox sem o draw() sincrono de set_val()."""
    caixa.text_disp.set_text(texto)
    caixa.cursor_index = len(texto)


class WidgetsMixin:
    def _criar_widgets(self):
        col_x, col_larg = 0.660, 0.30

        self.fig.text(col_x, 0.960, "METODO DE INTERPOLACAO",
                      fontsize=9, family="monospace", va="top", weight="bold")
        rotulos_metodo = [rotulo for rotulo, _ in MODOS_INTERPOLACAO.values()]
        self._radio_metodo = RadioButtons(
            self.fig.add_axes([col_x, 0.760, col_larg, 0.180]),
            rotulos_metodo, active=list(MODOS_INTERPOLACAO).index(self.metodo))

        self.fig.text(col_x, 0.720, "ESTILO VISUAL",
                      fontsize=9, family="monospace", va="top", weight="bold")
        rotulos_estilo = [rotulo for rotulo, _, _ in MODOS_RENDER.values()]
        self._radio_estilo = RadioButtons(
            self.fig.add_axes([col_x, 0.560, col_larg, 0.140]),
            rotulos_estilo, active=list(MODOS_RENDER).index(self.estilo))

        self._radio_metodo.on_clicked(self._mudar_metodo)
        self._radio_estilo.on_clicked(self._mudar_estilo)

        self.fig.text(col_x, 0.220, "EXPORTAR",
                      fontsize=9, family="monospace", va="top", weight="bold")
        self._tb_export = TextBox(
            self.fig.add_axes([col_x, 0.150, col_larg, 0.040]), "arquivo ",
            initial=str(self.saida_base))
        self._bt_png = Button(
            self.fig.add_axes([col_x, 0.090, 0.145, 0.045]), "Exportar PNG")
        self._bt_svg = Button(
            self.fig.add_axes([col_x + 0.155, 0.090, 0.145, 0.045]), "Exportar SVG")
        self._bt_png.on_clicked(lambda _e: self._exportar("png"))
        self._bt_svg.on_clicked(lambda _e: self._exportar("svg"))

        self._textboxes = [self._tb_export]

    def _mudar_metodo(self, rotulo):
        for chave, (r, _) in MODOS_INTERPOLACAO.items():
            if r == rotulo:
                self.metodo = chave
                break
        self._redesenhar()

    def _mudar_estilo(self, rotulo):
        for chave, (r, _, _) in MODOS_RENDER.items():
            if r == rotulo:
                self.estilo = chave
                break
        self._redesenhar()
