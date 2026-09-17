"""Desenho do plano (paredes, moveis, pontos) e HUD do cursor em tempo real."""

from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.ticker import MultipleLocator

from .constants import (
    CORES_MATERIAL,
    COR_PADRAO,
    ESTILO_PONTO,
    ESTILO_SEGMENTO,
    PASSOS_GRADE,
    TECLAS_MODO,
)

# ---------------------------------------------------------------------- #
# Configuracao / desenho
# ---------------------------------------------------------------------- #


class DrawingMixin:
    def _configurar_eixos(self):
        self.ax.set_xlim(*self._xlim0)
        self.ax.set_ylim(*self._ylim0)
        self.ax.set_aspect("equal")
        self.ax.set_anchor("N")
        self._configurar_grade()
        self.ax.set_xlabel("x (m)")
        self.ax.set_ylabel("y (m)")

    def _configurar_grade(self):
        """Grade maior de 1 m e grade menor no passo do snap."""
        self.ax.xaxis.set_major_locator(MultipleLocator(1.0))
        self.ax.yaxis.set_major_locator(MultipleLocator(1.0))
        self.ax.xaxis.set_minor_locator(MultipleLocator(self.passo))
        self.ax.yaxis.set_minor_locator(MultipleLocator(self.passo))
        self.ax.grid(True, which="major", linestyle="--",
                     linewidth=0.6, alpha=0.6)
        self.ax.grid(True, which="minor", linestyle=":",
                     linewidth=0.4, alpha=0.3)

    def _vertices_existentes(self):
        """Todos os pontos ja definidos, para o clique se encaixar neles."""
        for p in self.paredes:
            yield (p["x1"], p["y1"])
            yield (p["x2"], p["y2"])
        for m in self.moveis:
            x0, y0 = m["x"], m["y"]
            x1, y1 = x0 + m["largura"], y0 + m["profundidade"]
            yield (x0, y0)
            yield (x1, y0)
            yield (x1, y1)
            yield (x0, y1)
        for pt in self.pontos_medicao:
            yield (pt["x"], pt["y"])
        yield from self._cliques_pendentes

    def _encaixar(self, x, y):
        """Encaixa o clique em um vertice proximo ou no ponto de grade."""
        if not self.snap:
            return round(x, 2), round(y, 2)

        tolerancia = self.passo / 2
        melhor, menor_d2 = None, tolerancia ** 2
        for vx, vy in self._vertices_existentes():
            d2 = (vx - x) ** 2 + (vy - y) ** 2
            if d2 <= menor_d2:
                melhor, menor_d2 = (vx, vy), d2
        if melhor is not None:
            return melhor

        return (round(round(x / self.passo) * self.passo, 3),
                round(round(y / self.passo) * self.passo, 3))

    def _mudar_passo(self, direcao):
        atual = min(range(len(PASSOS_GRADE)),
                    key=lambda i: abs(PASSOS_GRADE[i] - self.passo))
        novo = min(max(atual + direcao, 0), len(PASSOS_GRADE) - 1)
        self.passo = PASSOS_GRADE[novo]
        print(f"Passo da grade: {self.passo} m")
        self._redesenhar()

    def _cliques_necessarios(self):
        if self.modo == "ponto":
            return 1
        if self.modo is None:
            return 0
        return 2

    def _atualizar_titulo(self):
        modo_txt = self.modo or "nenhum (w m j d f p)"
        opcao = self._opcao_atual()
        if opcao:
            modo_txt = f"{modo_txt} ({opcao})"
        pendente = ""
        if self._cliques_pendentes:
            pendente = (f"   |   clique {len(self._cliques_pendentes)}/"
                        f"{self._cliques_necessarios()} (u desfaz)")
        n_ap = sum(1 for p in self.pontos_medicao
                   if p.get("tipo", "medicao") == "access_point")
        n_medicao = len(self.pontos_medicao) - n_ap
        snap_txt = f"snap {self.passo:g} m" if self.snap else "snap off"
        self.ax.set_title(
            f"modo: {modo_txt}   |   {snap_txt}   |   "
            f"paredes: {len(self.paredes)}  moveis: {len(self.moveis)}  "
            f"pontos: {n_medicao} medicao + {n_ap} ap"
            f"{pendente}",
            fontsize=10, loc="left",
        )
        self.fig.canvas.draw_idle()

    def _atualizar_painel(self):
        """Painel lateral: modos, paleta atual e demais teclas."""
        linhas = ["MODOS"]
        for tecla, modo in TECLAS_MODO.items():
            marca = ">" if modo == self.modo else " "
            linhas.append(f" {marca} {tecla}  {modo.replace('_', ' ')}")

        paleta = self._paleta()
        if paleta is not None:
            rotulo, opcoes = paleta
            linhas += ["", f"{rotulo.upper()} (teclas 1-{len(opcoes)})"]
            for i, opcao in enumerate(opcoes, start=1):
                marca = ">" if i - 1 == self._selecao[self.modo] else " "
                linhas.append(f" {marca} {i}  {opcao}")
        else:
            linhas += ["", "(escolha um modo para ver",
                       " os materiais disponiveis)"]

        linhas += [
            "",
            "MOUSE",
            " esq     marcar ponto",
            " dir     editar objeto sob o cursor",
            " scroll  zoom no cursor",
            " espaco + arrastar  mover a vista",
            " (ou arrastar com o botao do meio)",
            "",
            "u    desfazer",
            "esc  cancelar cliques",
            f"g    snap: {'on' if self.snap else 'off'}",
            f"[ ]  passo: {self.passo:g} m",
            "0    enquadrar a vista",
            "s    salvar",
            "q    salvar e sair",
        ]
        self._painel.set_text("\n".join(linhas))
        self._atualizar_titulo()

    def _redesenhar(self):
        xlim, ylim = self.ax.get_xlim(), self.ax.get_ylim()
        self._fundo = None  # o fundo guardado para o blit ficou obsoleto
        self.ax.cla()
        self.ax.set_xlim(xlim)
        self.ax.set_ylim(ylim)
        self.ax.set_aspect("equal")
        self.ax.set_anchor("N")
        self._configurar_grade()
        self.ax.set_xlabel("x (m)")
        self.ax.set_ylabel("y (m)")

        tipos_desenhados = set()
        for p in self.paredes:
            tipo = p.get("tipo", "parede")
            estilo = ESTILO_SEGMENTO.get(tipo, ESTILO_SEGMENTO["parede"])
            tipos_desenhados.add(tipo)
            xs, ys = [p["x1"], p["x2"]], [p["y1"], p["y2"]]

            if tipo in ("janela", "porta"):
                # a abertura "corta" a parede: apaga o trecho e desenha por cima
                largura = max(4.0, p["espessura"] * 20)
                self.ax.plot(xs, ys, color="white", linewidth=largura + 2.5,
                             solid_capstyle="butt", zorder=4)
                self.ax.plot(xs, ys, color=estilo["cor"], linewidth=largura,
                             solid_capstyle="butt", zorder=5)
                continue

            self.ax.plot(
                xs, ys,
                color=estilo["cor"], linestyle=estilo["linestyle"],
                linewidth=max(1.5, p["espessura"] * 20),
                solid_capstyle="butt", zorder=3,
            )

        for m in self.moveis:
            cor = CORES_MATERIAL.get(m["material"], COR_PADRAO)
            rect = Rectangle(
                (m["x"], m["y"]), m["largura"], m["profundidade"],
                facecolor=cor, alpha=0.4, edgecolor=cor,
            )
            self.ax.add_patch(rect)
            self.ax.text(
                m["x"] + m["largura"] / 2, m["y"] + m["profundidade"] / 2,
                m["tipo"], ha="center", va="center", fontsize=8,
            )

        tipos_ponto_desenhados = set()
        for pt in self.pontos_medicao:
            tipo = pt.get("tipo", "medicao")
            estilo = ESTILO_PONTO.get(tipo, ESTILO_PONTO["medicao"])
            tipos_ponto_desenhados.add(tipo)
            self.ax.scatter([pt["x"]], [pt["y"]], color=estilo["cor"],
                            marker=estilo["marcador"], zorder=7)
            self.ax.annotate(
                str(pt["id"]), (pt["x"], pt["y"]),
                textcoords="offset points", xytext=(5, 5),
                fontsize=8, color=estilo["cor"],
            )

        if tipos_desenhados or tipos_ponto_desenhados:
            handles = [
                Line2D([], [], color=ESTILO_SEGMENTO[t]["cor"],
                       linestyle=ESTILO_SEGMENTO[t]["linestyle"],
                       linewidth=2, label=ESTILO_SEGMENTO[t]["rotulo"])
                for t in ESTILO_SEGMENTO if t in tipos_desenhados
            ]
            handles += [
                Line2D([], [], color=ESTILO_PONTO[t]["cor"],
                       marker=ESTILO_PONTO[t]["marcador"], linestyle="none",
                       label=ESTILO_PONTO[t]["rotulo"])
                for t in ESTILO_PONTO if t in tipos_ponto_desenhados
            ]
            self.ax.legend(
                handles=handles,
                loc="upper right", fontsize=7, framealpha=0.8,
            )

        self._desenhar_selecao()
        self._desenhar_cliques_pendentes()
        # ax.cla() destruiu os artistas do HUD: eles precisam voltar
        self._criar_artistas_hud()
        self._atualizar_painel()
        self._atualizar_hud()

    def _desenhar_selecao(self):
        """Contorno do objeto aberto no painel de edicao."""
        if self._sel is None or not self._selecao_valida():
            return
        xs, ys = self._pontos_realce(*self._sel)
        self.ax.plot(xs, ys, color="gold", linewidth=5, alpha=0.75,
                     marker="o", markersize=7, zorder=2,
                     solid_capstyle="round")

    def _desenhar_cliques_pendentes(self):
        """Marca em laranja os cliques ja dados no elemento em construcao."""
        if not self._cliques_pendentes:
            return

        xs = [c[0] for c in self._cliques_pendentes]
        ys = [c[1] for c in self._cliques_pendentes]
        self.ax.scatter(
            xs, ys, marker="x", s=70, color="tab:orange",
            linewidths=2, zorder=6,
        )
        for i, (x, y) in enumerate(self._cliques_pendentes, start=1):
            self.ax.annotate(
                f"{i} ({x:.2f}, {y:.2f})", (x, y),
                textcoords="offset points", xytext=(6, -12),
                fontsize=7, color="tab:orange",
            )
        if len(xs) > 1:
            self.ax.plot(xs, ys, color="tab:orange", linewidth=1,
                         linestyle=":", zorder=6)


# ---------------------------------------------------------------------- #
# Leitura do cursor em tempo real (mira, coordenada e objeto sob ela)
# ---------------------------------------------------------------------- #


class HudMixin:
    def _criar_artistas_hud(self):
        self._mira_v = self.ax.axvline(
            0.0, color="tab:green", linewidth=0.8, alpha=0.8,
            zorder=9, animated=True, visible=False)
        self._mira_h = self.ax.axhline(
            0.0, color="tab:green", linewidth=0.8, alpha=0.8,
            zorder=9, animated=True, visible=False)
        self._marca = Line2D(
            [], [], marker="+", markersize=13, markeredgewidth=1.8,
            color="tab:green", linestyle="none", zorder=10,
            animated=True, visible=False)
        self.ax.add_line(self._marca)
        self._realce = Line2D(
            [], [], color="tab:red", linewidth=3.5, alpha=0.55,
            marker="o", markersize=8, zorder=8,
            animated=True, visible=False)
        self.ax.add_line(self._realce)
        self._rotulo = self.ax.text(
            0.0, 0.0, "", fontsize=8, family="monospace", zorder=11,
            animated=True, visible=False, clip_on=True,
            bbox=dict(boxstyle="round,pad=0.25", facecolor="lightyellow",
                      edgecolor="tab:green", alpha=0.9),
        )
        self._hud = [self._mira_v, self._mira_h, self._realce,
                     self._marca, self._rotulo]

    def _on_draw(self, event):
        self._fundo = self.fig.canvas.copy_from_bbox(self.fig.bbox)
        self._desenhar_hud()

    def _desenhar_hud(self):
        for artista in self._hud:
            self.ax.draw_artist(artista)
        self.fig.draw_artist(self._status)
        self.fig.canvas.blit(self.fig.bbox)

    def _blit(self):
        if self._fundo is None:
            self.fig.canvas.draw_idle()
            return
        self.fig.canvas.restore_region(self._fundo)
        self._desenhar_hud()

    def _atualizar_hud(self):
        pos = self._pos_cursor
        if pos is None or pos[0] is None or pos[1] is None:
            for artista in self._hud:
                artista.set_visible(False)
            self._status.set_text(
                "cursor fora do plano   |   botao direito edita, "
                "espaco+arrastar move, scroll da zoom")
            self._blit()
            return

        x, y = pos
        xs, ys = self._encaixar(x, y)
        self._mira_v.set_xdata([x, x])
        self._mira_h.set_ydata([y, y])
        self._marca.set_data([xs], [ys])
        for artista in (self._mira_v, self._mira_h, self._marca):
            artista.set_visible(True)

        alvo = self._objeto_sob(x, y)
        if alvo is None:
            self._realce.set_visible(False)
            descricao = "-"
        else:
            rx, ry = self._pontos_realce(*alvo)
            self._realce.set_data(rx, ry)
            self._realce.set_visible(True)
            descricao = self._descricao(*alvo)

        # o rotulo acompanha o cursor com um deslocamento fixo em pixels
        px, py = self.ax.transData.transform((x, y))
        self._rotulo.set_position(
            self.ax.transData.inverted().transform((px + 12, py + 12)))
        self._rotulo.set_text(
            f"({xs:.2f}, {ys:.2f})" + ("" if alvo is None else f"\n{descricao}"))
        self._rotulo.set_visible(True)

        snap_txt = f"snap {self.passo:g} m" if self.snap else "snap off"
        self._status.set_text(
            f"cursor  x={x:7.2f}  y={y:7.2f} m   |   encaixe "
            f"({xs:.2f}, {ys:.2f})   |   {snap_txt}   |   "
            f"sob o cursor: {descricao}"
        )
        self._blit()
