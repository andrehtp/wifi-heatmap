"""Eventos de teclado e mouse."""

import matplotlib.pyplot as plt

from .constants import TECLAS_MODO


class EventsMixin:
    def _on_key(self, event):
        if not event.key or self._digitando():
            return  # o texto esta sendo digitado em uma caixa do painel

        if event.key == " ":
            self._cancelar_timer_espaco()
            if not self._espaco:
                self._espaco = True
                self._definir_cursor()
        elif event.key in TECLAS_MODO:
            self.modo = TECLAS_MODO[event.key]
            self._cliques_pendentes = []
            self._redesenhar()
        elif event.key in "123456789":
            self._selecionar_opcao(int(event.key) - 1)
        elif event.key == "0":
            self._enquadrar()
        elif event.key == "escape":
            self._espaco = False
            self._definir_cursor()
            self._cancelar_pendentes()
        elif event.key == "u":
            self._desfazer()
        elif event.key == "g":
            self.snap = not self.snap
            print("Snap " + ("ligado" if self.snap else "desligado") + ".")
            self._redesenhar()
        elif event.key == "[":
            self._mudar_passo(-1)
        elif event.key == "]":
            self._mudar_passo(+1)
        elif event.key == "s":
            self._salvar()
        elif event.key == "q":
            self._salvar()
            plt.close(self.fig)

    def _on_key_release(self, event):
        if event.key != " " or self._digitando():
            return
        if self._pan is not None:
            return  # segurando o botao: o pan so termina quando ele soltar
        # O autorepeat do X11 emite pares release/press enquanto a tecla
        # continua pressionada; so soltamos de verdade se nao vier um novo
        # press logo em seguida.
        self._cancelar_timer_espaco()
        timer = self.fig.canvas.new_timer(interval=90)
        timer.single_shot = True
        timer.add_callback(self._liberar_espaco)
        timer.start()
        self._timer_espaco = timer

    def _on_leave(self, event):
        self._pos_cursor = None
        self._atualizar_hud()

    def _on_motion(self, event):
        if self._pan is not None:
            self._arrastar_pan(event)
            return
        if event.inaxes is not self.ax:
            if self._pos_cursor is not None:
                self._pos_cursor = None
                self._atualizar_hud()
            return
        self._pos_cursor = (event.xdata, event.ydata)
        self._atualizar_hud()

    def _on_release(self, event):
        self._encerrar_pan()

    def _on_click(self, event):
        if event.inaxes is not self.ax or self._toolbar_ativa():
            return
        if event.xdata is None or event.ydata is None:
            return

        if event.button == 3:
            self._clique_direito(event)
            return
        if event.button == 2 or (event.button == 1 and self._espaco):
            self._iniciar_pan(event)
            return
        if event.button != 1 or self.modo is None:
            return

        x, y = self._encaixar(event.xdata, event.ydata)

        self._cliques_pendentes.append((x, y))
        self._redesenhar()

        if len(self._cliques_pendentes) < self._cliques_necessarios():
            return

        cliques = self._cliques_pendentes
        self._cliques_pendentes = []

        if self.modo == "ponto":
            self._adicionar_ponto(*cliques[0])
        elif self.modo == "movel":
            (x1, y1), (x2, y2) = cliques
            self._adicionar_movel(x1, y1, x2, y2)
        else:
            (x1, y1), (x2, y2) = cliques
            self._adicionar_segmento(self.modo, x1, y1, x2, y2)
