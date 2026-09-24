"""Painel de edicao (botao direito) para paredes, aberturas, moveis e pontos."""

from .constants import (
    MATERIAIS_MOVEL,
    MATERIAIS_PAREDE,
    MATERIAL_MOVEL,
    MODOS_ABERTURA,
    PALETAS,
    ROTULO_MOVEL,
    TIPOS_MOVEL,
    TIPOS_PAREDE,
)
from .geometry import fmt
from .poligonos import transladar
from .widgets import definir_texto

# Campos de texto de cada categoria: (chave, rotulo). "dx"/"dy" da parede
# nao sao atributos: deslocam o poligono inteiro ao aplicar.
CAMPOS = {
    "parede": [("dx", "mover dx"), ("dy", "mover dy")],
    "abertura": [("x1", "x1"), ("y1", "y1"), ("x2", "x2"), ("y2", "y2")],
    "guia": [("x1", "x1"), ("y1", "y1"), ("x2", "x2"), ("y2", "y2")],
    "movel": [("nome", "nome"), ("x", "x"), ("y", "y"),
              ("largura", "largura"), ("profundidade", "profund.")],
    "ponto": [("id", "id"), ("x", "x"), ("y", "y")],
}
TITULOS = {
    "parede": "EDITAR PAREDE",
    "abertura": "EDITAR ABERTURA",
    "guia": "EDITAR GUIA",
    "movel": "EDITAR MOVEL",
    "ponto": "EDITAR PONTO",
}


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
        self._painel_teclas.set_visible(not visivel)
        self._atualizar_parametros()

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
        self._campos = CAMPOS[categoria]
        if categoria == "parede":
            self._edicao.update(dx=0.0, dy=0.0)

        com_tipo = categoria != "guia"
        com_material = categoria not in ("ponto", "guia")
        self._mostrar_edicao(True, n_caixas=len(self._campos),
                             com_tipo=com_tipo, com_material=com_material)
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
        dica = {"parede": "arraste um vertice ou a parede\ninteira; dx/dy movem com precisao.",
                "abertura": "arrastar/aplicar devolve a parede\ndo lugar antigo e recorta o novo.",
                "guia": "guia = parede antiga em linha,\nso referencia para redesenhar."
                }.get(categoria, "arraste o objeto para move-lo.")
        self._titulo_edicao.set_text(
            f"{TITULOS[categoria]}  #{indice + 1}\n\n"
            f"{dica}\n'aplicar' confirma, 'u' desfaz."
        )
        tipo = self._edicao.get("tipo", "medicao")
        if categoria == "movel":
            tipo = ROTULO_MOVEL.get(tipo, tipo)
        self._bt_tipo.label.set_text(f"tipo: {tipo.replace('_', ' ')}")
        if "material" in self._edicao:
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
                self._edicao["tipo"] = proximo(
                    list(TIPOS_PAREDE), self._edicao.get("tipo"))
            else:
                self._edicao["material"] = proximo(
                    MATERIAIS_PAREDE, self._edicao.get("material"))
        elif categoria == "abertura":
            if campo == "tipo":
                self._edicao["tipo"] = proximo(
                    list(MODOS_ABERTURA), self._edicao.get("tipo"))
                materiais = PALETAS[self._edicao["tipo"]][1]
                if self._edicao.get("material") not in materiais:
                    self._edicao["material"] = materiais[0]
            else:
                self._edicao["material"] = proximo(
                    PALETAS[self._edicao["tipo"]][1],
                    self._edicao.get("material"))
        elif categoria == "movel":
            if campo == "tipo":
                antigo = self._edicao.get("tipo")
                self._edicao["tipo"] = proximo(TIPOS_MOVEL, antigo)
                novo = self._edicao["tipo"]
                if novo != "personalizado":
                    self._edicao["material"] = MATERIAL_MOVEL[novo]
                    # o nome acompanha o tipo, a nao ser que tenha sido
                    # digitado a mao (movel personalizado)
                    caixa = self._caixa_de("nome")
                    if antigo != "personalizado" and caixa is not None:
                        self._edicao["nome"] = ROTULO_MOVEL[novo]
                        definir_texto(caixa, ROTULO_MOVEL[novo])
            else:
                self._edicao["material"] = proximo(
                    MATERIAIS_MOVEL, self._edicao.get("material"))
        elif categoria == "ponto" and campo == "tipo":
            self._edicao["tipo"] = proximo(
                PALETAS["ponto"][1], self._edicao.get("tipo", "medicao"))
        self._atualizar_botoes_edicao()
        self.fig.canvas.draw_idle()

    def _ler_campo(self, chave, texto):
        texto = texto.strip()
        if chave == "nome":
            if not texto:
                raise ValueError
            return texto
        texto = texto.replace(",", ".")
        return int(texto) if chave == "id" else round(float(texto), 3)

    def _aplicar_edicao(self):
        if self._fechando or not self._selecao_valida():
            return
        categoria, indice = self._sel
        objeto = self._lista(categoria)[indice]
        novo = dict(self._edicao)
        for caixa, (chave, rotulo) in zip(self._caixas, self._campos):
            try:
                novo[chave] = self._ler_campo(chave, caixa.text)
            except ValueError:
                print(f"Valor invalido em '{rotulo}': {caixa.text!r}")
                definir_texto(caixa, fmt(self._edicao.get(chave, 0)))
                self.fig.canvas.draw_idle()
                return

        if categoria == "movel" and (novo["largura"] <= 0
                                     or novo["profundidade"] <= 0):
            print("Largura e profundidade do movel precisam ser maiores que zero.")
            return
        if categoria == "parede":
            dx, dy = novo.pop("dx"), novo.pop("dy")
            if dx or dy:
                novo = transladar(novo, dx, dy)
        # as caixas voltam a mostrar o valor ja normalizado ("1,25" -> 1.25)
        for caixa, (chave, _rotulo) in zip(self._caixas, self._campos):
            valor = 0.0 if chave in ("dx", "dy") else novo[chave]
            definir_texto(caixa, fmt(valor))

        if novo == objeto:  # nada mudou: nao suja o historico do undo
            self.fig.canvas.draw_idle()
            return

        self._snapshot()
        if categoria == "abertura" and any(
                novo[k] != objeto[k] for k in ("x1", "y1", "x2", "y2")):
            self._reposicionar_abertura(objeto, novo)
        objeto.clear()
        objeto.update(novo)
        self._edicao = dict(novo)
        if categoria == "parede":
            self._edicao.update(dx=0.0, dy=0.0)
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
        if categoria == "abertura":
            removido = self._remover_abertura(indice)
            print(f"- {removido['tipo']} removida (a parede foi devolvida)")
        else:
            self._lista(categoria).pop(indice)
            print(f"- {categoria} removido")
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
