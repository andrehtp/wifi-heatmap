"""Painel de edicao (botao direito) para paredes, moveis e pontos."""

from .constants import (
    ESPESSURA_MATERIAL,
    ESPESSURA_PADRAO,
    MATERIAIS_MOVEL,
    MATERIAL_MOVEL,
    MODOS_SEGMENTO,
    PALETAS,
)
from .geometry import fmt
from .widgets import definir_texto


def proximo(opcoes, atual):
    if atual not in opcoes:
        return opcoes[0]
    return opcoes[(opcoes.index(atual) + 1) % len(opcoes)]


class EditPanelMixin:
    def _mostrar_edicao(self, visivel, n_caixas=5, com_tipo=True,
                        com_material=None):
        if com_material is None:
            com_material = com_tipo
        # set_visible() sozinho nao basta: AxesWidget.ignore() so olha o
        # estado "active", entao um widget escondido continuaria clicavel.
        for widget in self._widgets_edicao:
            widget.ax.set_visible(visivel)
            widget.set_active(visivel)
        if visivel:
            for i, caixa in enumerate(self._caixas):
                ativa = i < n_caixas
                caixa.ax.set_visible(ativa)
                caixa.set_active(ativa)
            for botao, ativo in ((self._bt_tipo, com_tipo),
                                 (self._bt_material, com_material)):
                botao.ax.set_visible(ativo)
                botao.set_active(ativo)
        self._titulo_edicao.set_visible(visivel)
        self._painel.set_visible(not visivel)

    def _clique_direito(self, event):
        alvo = self._objeto_sob(event.xdata, event.ydata)
        if alvo is None:
            if self._sel is not None:
                self._fechar_edicao()
            else:
                print("Nada sob o cursor para editar.")
            return
        self._abrir_edicao(*alvo)

    def _abrir_edicao(self, categoria, indice):
        self._sel = (categoria, indice)
        self._edicao = dict(self._lista(categoria)[indice])
        if categoria == "parede":
            self._campos = [("espessura", "espessura"), ("x1", "x1"),
                            ("y1", "y1"), ("x2", "x2"), ("y2", "y2")]
        elif categoria == "movel":
            self._campos = [("x", "x"), ("y", "y"), ("largura", "largura"),
                            ("profundidade", "profund.")]
        else:
            self._campos = [("id", "id"), ("x", "x"), ("y", "y")]

        self._mostrar_edicao(True, n_caixas=len(self._campos),
                             com_tipo=True, com_material=categoria != "ponto")
        for caixa, (chave, rotulo) in zip(self._caixas, self._campos):
            caixa.label.set_text(rotulo + " ")
            definir_texto(caixa, fmt(self._edicao.get(chave, 0)))
        self._atualizar_botoes_edicao()
        print(f"Editando {self._descricao(categoria, indice)}")
        self._redesenhar()

    def _atualizar_botoes_edicao(self):
        if self._sel is None:
            return
        categoria, indice = self._sel
        titulo = {"parede": "EDITAR SEGMENTO",
                  "movel": "EDITAR MOVEL",
                  "ponto": "EDITAR PONTO"}[categoria]
        self._titulo_edicao.set_text(
            f"{titulo}  #{indice + 1}\n\n"
            "os botoes trocam tipo/material;\n"
            "'aplicar' confirma, 'u' desfaz."
        )
        if categoria == "ponto":
            self._bt_tipo.label.set_text(
                f"tipo: {self._edicao.get('tipo', 'medicao').replace('_', ' ')}")
        else:
            self._bt_tipo.label.set_text(
                f"tipo: {self._edicao['tipo'].replace('_', ' ')}")
            self._bt_material.label.set_text(
                f"material: {self._edicao['material']}")

    def _caixa_de(self, chave):
        for caixa, (k, _rotulo) in zip(self._caixas, self._campos):
            if k == chave:
                return caixa
        return None

    def _ciclar(self, campo):
        if self._sel is None:
            return
        categoria = self._sel[0]
        if categoria == "parede":
            if campo == "tipo":
                opcoes = list(MODOS_SEGMENTO)
                self._edicao["tipo"] = proximo(
                    opcoes, self._edicao.get("tipo"))
                materiais = PALETAS[self._edicao["tipo"]][1]
                if self._edicao.get("material") not in materiais:
                    self._edicao["material"] = materiais[0]
                    self._aplicar_espessura_padrao()
            else:
                materiais = PALETAS[self._edicao["tipo"]][1]
                self._edicao["material"] = proximo(
                    materiais, self._edicao.get("material"))
                self._aplicar_espessura_padrao()
        elif categoria == "movel":
            if campo == "tipo":
                self._edicao["tipo"] = proximo(
                    PALETAS["movel"][1], self._edicao.get("tipo"))
                self._edicao["material"] = MATERIAL_MOVEL.get(
                    self._edicao["tipo"], "madeira")
            else:
                self._edicao["material"] = proximo(
                    MATERIAIS_MOVEL, self._edicao.get("material"))
        elif categoria == "ponto" and campo == "tipo":
            self._edicao["tipo"] = proximo(
                PALETAS["ponto"][1], self._edicao.get("tipo", "medicao"))
            if self._edicao["tipo"] == "medicao":
                self._edicao.setdefault("leituras_dbm", [])
            else:
                self._edicao.pop("leituras_dbm", None)
        self._atualizar_botoes_edicao()
        self.fig.canvas.draw_idle()

    def _aplicar_espessura_padrao(self):
        espessura = ESPESSURA_MATERIAL.get(
            self._edicao["material"], ESPESSURA_PADRAO)
        self._edicao["espessura"] = espessura
        caixa = self._caixa_de("espessura")
        if caixa is not None:
            definir_texto(caixa, fmt(espessura))

    def _aplicar_edicao(self):
        if self._fechando or not self._selecao_valida():
            return
        categoria, indice = self._sel
        objeto = self._lista(categoria)[indice]
        novo = dict(self._edicao)
        for caixa, (chave, rotulo) in zip(self._caixas, self._campos):
            texto = caixa.text.strip().replace(",", ".")
            try:
                novo[chave] = int(texto) if chave == "id" else round(float(texto), 3)
            except ValueError:
                print(f"Valor invalido em '{rotulo}': {caixa.text!r}")
                definir_texto(caixa, fmt(objeto[chave]))
                self.fig.canvas.draw_idle()
                return

        if categoria == "parede" and novo["espessura"] <= 0:
            print("A espessura precisa ser maior que zero.")
            return
        if categoria == "movel" and (novo["largura"] <= 0
                                     or novo["profundidade"] <= 0):
            print("Largura e profundidade do movel precisam ser maiores que zero.")
            return
        # as caixas voltam a mostrar o valor ja normalizado ("1,25" -> 1.25)
        for caixa, (chave, _rotulo) in zip(self._caixas, self._campos):
            definir_texto(caixa, fmt(novo[chave]))

        if novo == objeto:  # nada mudou: nao suja o historico do undo
            self.fig.canvas.draw_idle()
            return

        self._snapshot()
        objeto.clear()
        objeto.update(novo)
        self._edicao = dict(novo)
        if categoria == "ponto":
            self._next_ponto_id = max(self._next_ponto_id, novo["id"] + 1)
        print(f"~ {self._descricao(categoria, indice)} atualizado")
        self._atualizar_botoes_edicao()
        self._redesenhar()

    def _excluir_edicao(self):
        if not self._selecao_valida():
            return
        categoria, indice = self._sel
        self._snapshot()
        removido = self._lista(categoria).pop(indice)
        print(f"- {categoria} removido: {removido}")
        self._fechar_edicao()

    def _fechar_edicao(self):
        self._fechando = True
        try:
            for caixa in self._caixas:
                if caixa.capturekeystrokes:
                    caixa.stop_typing()
        finally:
            self._fechando = False
        self._sel = None
        self._edicao = None
        self._campos = []
        self._mostrar_edicao(False)
        self._redesenhar()
