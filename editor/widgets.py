"""Widgets da coluna da direita (dentro do canvas, fora do plano)."""

from matplotlib.widgets import Button, TextBox

from .constants import (
    ALINHAMENTOS,
    ESPESSURA_MATERIAL,
    ESPESSURA_PADRAO,
    MATERIAIS_MOVEL,
    MODOS_PAREDE,
    PALETAS,
)
from .distribuicao import MODOS_DISTRIBUICAO
from .geometry import fmt


def definir_texto(caixa, texto):
    """Troca o texto de uma TextBox sem o draw() sincrono de set_val()."""
    caixa.text_disp.set_text(texto)
    caixa.cursor_index = len(texto)


def _mostrar(widget, visivel):
    # set_visible() sozinho nao basta: AxesWidget.ignore() so olha o
    # estado "active", entao um widget escondido continuaria clicavel.
    widget.ax.set_visible(visivel)
    widget.set_active(visivel)


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

        # Parametros do modo atual (espessura/alinhamento da parede, nome e
        # material do movel personalizado, valor/margem da distribuicao).
        self._titulo_param = self.fig.text(
            col_x, 0.300, "", fontsize=8.5, family="monospace", va="top")
        self._tb_param1 = TextBox(
            self.fig.add_axes([0.800, 0.210, 0.185, 0.038]), "")
        self._tb_param2 = TextBox(
            self.fig.add_axes([0.800, 0.162, 0.185, 0.038]), "")
        self._bt_param = Button(
            self.fig.add_axes([col_x, 0.100, col_larg, 0.045]), "")
        self._tb_param1.on_submit(lambda _t: self._ler_parametros())
        self._tb_param2.on_submit(lambda _t: self._ler_parametros())
        self._bt_param.on_clicked(lambda _e: self._acao_parametro())
        self._widgets_param = [self._tb_param1, self._tb_param2, self._bt_param]

        self._textboxes = [self._tb_largura, self._tb_altura, *self._caixas,
                           self._tb_param1, self._tb_param2]
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
        opcao = paleta[1][indice]
        print(f"{paleta[0]} do modo {self.modo}: {opcao}")
        if self.modo in MODOS_PAREDE:
            # a espessura acompanha o material; da para sobrescrever na caixa
            self.espessura = ESPESSURA_MATERIAL.get(opcao, ESPESSURA_PADRAO)
            self._estado_param = None
        self._atualizar_painel()
        if self._cliques_pendentes:
            self._redesenhar()  # a previa da parede muda de espessura

    # ------------------------------------------------------------------ #
    # Parametros do modo
    # ------------------------------------------------------------------ #
    def _config_parametros(self):
        """(titulo, caixa1, caixa2, botao) do modo atual; None = nada.

        caixa = (rotulo, valor) ou None; botao = texto ou None.
        """
        if self._sel is not None:
            return None
        modo, opcao = self.modo, self._opcao_atual()
        if modo in ("parede", "meia_parede"):
            return ("PAREDE: um clique por vertice;\n"
                    "enter conclui, 1o vertice fecha",
                    ("espessura m ", fmt(self.espessura)), None,
                    f"alinhamento: {self.alinhamento}  (l)")
        if modo == "contorno":
            return ("CONTORNO: clique os cantos da\n"
                    "parede; enter ou 1o vertice fecha", None, None, None)
        if modo == "movel" and opcao == "personalizado":
            return ("MOVEL PERSONALIZADO", ("nome ", self._movel_nome),
                    None, f"material: {self._movel_material}")
        if modo == "ponto":
            return ("PONTO: 1 clique; 1/2 tipo\n"
                    "tabela CSV p/ anotar as leituras:",
                    ("csv ", self._caminho_tabela), None, "gerar tabela (t)")
        if modo == "distribuir":
            rotulo, rotulo_valor, _p, _f, _i = MODOS_DISTRIBUICAO[opcao]
            return (f"DISTRIBUIR ({rotulo}):\n"
                    "clique num comodo, ou",
                    (rotulo_valor + " ", fmt(self._valor_distribuicao[opcao])),
                    ("margem m ", fmt(self._margem_distribuicao)),
                    "distribuir na planta toda (enter)")
        return None

    def _atualizar_parametros(self):
        cfg = self._config_parametros()
        if cfg is None:
            self._titulo_param.set_visible(False)
            for widget in self._widgets_param:
                _mostrar(widget, False)
            self._estado_param = None
            return

        titulo, caixa1, caixa2, botao = cfg
        self._titulo_param.set_text(titulo)
        self._titulo_param.set_visible(True)
        # o texto das caixas so e reescrito quando o modo/opcao muda, para
        # nao apagar o que o usuario esta digitando
        estado = (self.modo, self._opcao_atual())
        reescrever = estado != self._estado_param
        self._estado_param = estado
        for caixa, conf in ((self._tb_param1, caixa1), (self._tb_param2, caixa2)):
            _mostrar(caixa, conf is not None)
            if conf is not None and reescrever:
                caixa.label.set_text(conf[0])
                definir_texto(caixa, conf[1])
        _mostrar(self._bt_param, botao is not None)
        if botao is not None:
            self._bt_param.label.set_text(botao)

    def _ler_numero(self, caixa, positivo=True, inteiro=False):
        """Numero da caixa (aceita virgula), ou None se invalido."""
        texto = caixa.text.strip().replace(",", ".")
        try:
            valor = int(float(texto)) if inteiro else float(texto)
        except ValueError:
            return None
        if valor < 0 or (positivo and valor == 0):
            return None
        return valor

    def _ler_parametros(self):
        """Le as caixas de parametro do modo atual. Chamado no enter da caixa
        e antes de cada acao; com valor invalido a caixa volta ao anterior e
        retorna False (a acao nao deve seguir)."""
        if self._config_parametros() is None:
            return True
        modo, opcao = self.modo, self._opcao_atual()
        invalido = False
        if modo in ("parede", "meia_parede"):
            valor = self._ler_numero(self._tb_param1)
            if valor is None:
                invalido = True
            elif valor != self.espessura:
                self.espessura = round(valor, 3)
                print(f"Espessura da parede: {self.espessura:g} m")
                if self._cliques_pendentes:
                    self._redesenhar()
        elif modo == "movel":
            nome = self._tb_param1.text.strip()
            if nome:
                self._movel_nome = nome
            else:
                invalido = True
        elif modo == "ponto":
            caminho = self._tb_param1.text.strip()
            if caminho:
                self._caminho_tabela = caminho
            else:
                invalido = True
        elif modo == "distribuir":
            inteiro = MODOS_DISTRIBUICAO[opcao][4]
            valor = self._ler_numero(self._tb_param1, inteiro=inteiro)
            margem = self._ler_numero(self._tb_param2, positivo=False)
            if valor is None or margem is None:
                invalido = True
            else:
                self._valor_distribuicao[opcao] = valor
                self._margem_distribuicao = margem
        if invalido:
            print("Valor invalido no painel; mantido o anterior.")
            self._estado_param = None
            self._atualizar_parametros()
            self.fig.canvas.draw_idle()
        return not invalido

    def _acao_parametro(self):
        """Botao da area de parametros."""
        if self.modo in ("parede", "meia_parede"):
            self._ciclar_alinhamento()
        elif self.modo == "movel":
            i = MATERIAIS_MOVEL.index(self._movel_material)
            self._movel_material = MATERIAIS_MOVEL[(i + 1) % len(MATERIAIS_MOVEL)]
            self._atualizar_parametros()
            self.fig.canvas.draw_idle()
        elif self.modo == "ponto":
            self._gerar_tabela()
        elif self.modo == "distribuir" and self._ler_parametros():
            self._distribuir()

    def _ciclar_alinhamento(self):
        i = ALINHAMENTOS.index(self.alinhamento)
        self.alinhamento = ALINHAMENTOS[(i + 1) % len(ALINHAMENTOS)]
        print(f"Alinhamento da parede: {self.alinhamento} "
              "(lado da linha clicada em que fica a espessura)")
        self._redesenhar()
