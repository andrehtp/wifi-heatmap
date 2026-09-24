"""Eventos de teclado e mouse."""

import copy
import math

import matplotlib.pyplot as plt
from shapely import Point

from .constants import MODOS_ABERTURA, MODOS_PAREDE, TECLAS_MODO
from .geometry import dist_ponto_retangulo, dist_ponto_segmento
from .poligonos import CASAS, para_shapely, transladar


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
        elif event.key == "enter":
            self._concluir()
        elif event.key == "l":
            self._ciclar_alinhamento()
        elif event.key == "h":
            self.mostrar_guias = not self.mostrar_guias
            print("Guias " + ("visiveis" if self.mostrar_guias else "escondidas") + ".")
            self._redesenhar()
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
        elif event.key == "t":
            self._gerar_tabela()
        elif event.key == "s":
            self._salvar()
        elif event.key == "q":
            self._salvar()
            plt.close(self.fig)

    def _concluir(self, fechada=False):
        """enter: conclui a parede em construcao ou distribui na planta toda."""
        if self.modo == "distribuir":
            if self._ler_parametros():
                self._distribuir()
            return
        if self.modo not in MODOS_PAREDE:
            return
        cliques = self._cliques_pendentes
        # o contorno e sempre fechado; a polilinha precisa de 2+ vertices
        minimo = 3 if self.modo == "contorno" else 2
        if len(cliques) < minimo:
            print(f"Sao precisos pelo menos {minimo} vertices.")
            return
        if not self._ler_parametros():
            return
        self._cliques_pendentes = []
        self._adicionar_parede(self.modo, cliques,
                               fechada=fechada and self.modo != "contorno")

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
        if self._arraste is not None:
            self._mover_arraste(event)
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
        self._encerrar_arraste()

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
        if event.button == 1 and self._iniciar_arraste(event):
            return
        if event.button != 1 or self.modo is None:
            return

        x, y = self._encaixar(event.xdata, event.ydata)

        if self.modo == "distribuir":
            if self._ler_parametros():
                self._distribuir(x, y)
            return

        if self.modo in MODOS_PAREDE:
            self._clique_parede(x, y)
            return

        self._cliques_pendentes.append((x, y))
        self._redesenhar()

        if len(self._cliques_pendentes) < self._cliques_necessarios():
            return

        cliques = self._cliques_pendentes
        self._cliques_pendentes = []

        if self.modo == "ponto":
            self._adicionar_ponto(*cliques[0])
        elif self.modo == "movel":
            if not self._ler_parametros():
                self._redesenhar()
                return
            (x1, y1), (x2, y2) = cliques
            self._adicionar_movel(x1, y1, x2, y2)
        elif self.modo in MODOS_ABERTURA:
            (x1, y1), (x2, y2) = cliques
            self._adicionar_abertura(self.modo, x1, y1, x2, y2)

    def _clique_parede(self, x, y):
        """Polilinha: repetir o ultimo vertice conclui, o primeiro fecha."""
        cliques = self._cliques_pendentes
        if cliques and (x, y) == cliques[-1]:
            self._concluir()
            return
        if len(cliques) >= 3 and (x, y) == cliques[0]:
            self._concluir(fechada=True)
            return
        cliques.append((x, y))
        self._redesenhar()

    # ------------------------------------------------------------------ #
    # Arrastar o objeto aberto no painel de edicao
    # ------------------------------------------------------------------ #
    def _iniciar_arraste(self, event):
        """Comeca a arrastar o objeto selecionado, se o clique cair nele."""
        if self._sel is None or not self._selecao_valida():
            return False
        categoria, indice = self._sel
        obj = self._lista(categoria)[indice]
        x, y = event.xdata, event.ydata
        tol = self._tolerancia_dados()
        alvo = None

        if categoria == "parede":
            for anel, pontos in [("vertices", obj["vertices"]),
                                 *[(("furos", k), f) for k, f in
                                   enumerate(obj.get("furos", []))]]:
                for i, (vx, vy) in enumerate(pontos):
                    if math.hypot(vx - x, vy - y) <= tol:
                        alvo = ("vertice", anel, i)
                        break
                if alvo:
                    break
            if alvo is None:
                pol = para_shapely(obj)
                if pol.contains(Point(x, y)) or pol.boundary.distance(Point(x, y)) <= tol:
                    alvo = ("mover",)
        elif categoria in ("abertura", "guia"):
            if math.hypot(obj["x1"] - x, obj["y1"] - y) <= tol:
                alvo = ("ponta", 1)
            elif math.hypot(obj["x2"] - x, obj["y2"] - y) <= tol:
                alvo = ("ponta", 2)
            elif dist_ponto_segmento(x, y, obj["x1"], obj["y1"],
                                     obj["x2"], obj["y2"]) <= tol:
                alvo = ("mover",)
        elif categoria == "movel":
            d, dentro = dist_ponto_retangulo(
                x, y, obj["x"], obj["y"], obj["largura"], obj["profundidade"])
            if dentro or d <= tol:
                alvo = ("mover",)
        elif math.hypot(obj["x"] - x, obj["y"] - y) <= tol:
            alvo = ("mover",)

        if alvo is None:
            return False
        self._arraste = {
            "categoria": categoria, "indice": indice, "alvo": alvo,
            "original": copy.deepcopy(obj), "movido": False,
        }
        # com _arraste ja definido, o snap ignora o proprio objeto
        self._arraste["origem"] = self._encaixar(x, y)
        self._snapshot()
        return True

    def _mover_arraste(self, event):
        if event.xdata is None or event.ydata is None:
            return
        arr = self._arraste
        x, y = self._encaixar(event.xdata, event.ydata)
        dx = round(x - arr["origem"][0], CASAS)
        dy = round(y - arr["origem"][1], CASAS)
        if arr.get("ultimo") == (x, y):
            return
        arr["ultimo"] = (x, y)
        arr["movido"] = arr["movido"] or dx != 0 or dy != 0
        orig = arr["original"]
        obj = self._lista(arr["categoria"])[arr["indice"]]
        alvo = arr["alvo"]

        if alvo[0] == "vertice":
            _, anel, i = alvo
            if anel == "vertices":
                obj["vertices"] = copy.deepcopy(orig["vertices"])
                obj["vertices"][i] = [x, y]
            else:
                k = anel[1]
                obj["furos"] = copy.deepcopy(orig["furos"])
                obj["furos"][k][i] = [x, y]
        elif alvo[0] == "ponta":
            obj[f"x{alvo[1]}"], obj[f"y{alvo[1]}"] = x, y
        elif arr["categoria"] == "parede":
            obj.update(transladar(orig, dx, dy))
        elif arr["categoria"] in ("abertura", "guia"):
            for n in (1, 2):
                obj[f"x{n}"] = round(orig[f"x{n}"] + dx, CASAS)
                obj[f"y{n}"] = round(orig[f"y{n}"] + dy, CASAS)
        else:
            obj["x"] = round(orig["x"] + dx, CASAS)
            obj["y"] = round(orig["y"] + dy, CASAS)
        self._pos_cursor = (event.xdata, event.ydata)
        self._redesenhar()

    def _encerrar_arraste(self):
        arr = self._arraste
        if arr is None:
            return
        self._arraste = None
        if not arr["movido"]:
            self._historico.pop()  # clique sem mover: nada a desfazer
            self._redesenhar()
            return
        categoria, indice = arr["categoria"], arr["indice"]
        obj = self._lista(categoria)[indice]
        if categoria == "parede" and not para_shapely(obj).is_valid:
            print("O vertice cruzou a propria parede; movimento desfeito.")
            obj.clear()
            obj.update(arr["original"])
            self._historico.pop()
            self._redesenhar()
            return
        if categoria == "abertura":
            # a parede volta no lugar antigo e e recortada no novo
            novo = dict(obj)
            obj["recorte"] = arr["original"].get("recorte", [])
            self._reposicionar_abertura(obj, novo)
            obj.update(novo)
        print(f"~ {self._descricao(categoria, indice)} movido")
        self._abrir_edicao(categoria, indice)
