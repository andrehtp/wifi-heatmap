"""Desenho do plano (paredes, moveis, pontos) e HUD do cursor em tempo real."""

import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, PathPatch, Rectangle
from matplotlib.path import Path
from matplotlib.ticker import MultipleLocator
from shapely import Point, Polygon
from shapely.geometry.polygon import orient

from .constants import (
    COR_MATERIAL_PAREDE,
    COR_PAREDE_PADRAO,
    CORES_MATERIAL,
    COR_PADRAO,
    ESTILO_ABERTURA,
    ESTILO_GUIA,
    ESTILO_PAREDE,
    ESTILO_PONTO,
    MODOS_ABERTURA,
    MODOS_PAREDE,
    PASSOS_GRADE,
    ROTULO_MOVEL,
    TECLAS_MODO,
)
from .distribuicao import MODOS_DISTRIBUICAO
from .poligonos import (
    bordas,
    corrigir,
    para_shapely,
    parede_de_polilinha,
    poligonos,
    ponto_em_aresta,
)


def caminho_poligono(pol):
    """Path do matplotlib para um Polygon shapely (com furos)."""
    pol = orient(pol)
    return Path.make_compound_path(*[
        Path(np.asarray(anel.coords), closed=True)
        for anel in (pol.exterior, *pol.interiors)])


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

    # ------------------------------------------------------------------ #
    # Snap
    # ------------------------------------------------------------------ #
    def _vertices_existentes(self):
        """Todos os pontos ja definidos, para o clique se encaixar neles."""
        ignorar = None
        if self._arraste is not None:
            ignorar = (self._arraste["categoria"], self._arraste["indice"])
        for i, p in enumerate(self.paredes):
            if ("parede", i) == ignorar:
                continue
            for anel in (p["vertices"], *p.get("furos", [])):
                for vx, vy in anel:
                    yield (vx, vy)
        if self.mostrar_guias:
            for g in self.guias:
                yield (g["x1"], g["y1"])
                yield (g["x2"], g["y2"])
        for i, a in enumerate(self.aberturas):
            if ("abertura", i) != ignorar:
                yield (a["x1"], a["y1"])
                yield (a["x2"], a["y2"])
        for i, m in enumerate(self.moveis):
            if ("movel", i) == ignorar:
                continue
            x0, y0 = m["x"], m["y"]
            x1, y1 = x0 + m["largura"], y0 + m["profundidade"]
            yield (x0, y0)
            yield (x1, y0)
            yield (x1, y1)
            yield (x0, y1)
        for i, pt in enumerate(self.pontos_medicao):
            if ("ponto", i) != ignorar:
                yield (pt["x"], pt["y"])
        yield from self._cliques_pendentes

    def _bordas(self):
        if "bordas" not in self._cache_geo:
            guias = self.guias if self.mostrar_guias else []
            self._cache_geo["bordas"] = bordas(self.paredes, guias)
        return self._cache_geo["bordas"]

    def _na_grade(self, v):
        return round(round(v / self.passo) * self.passo, 3)

    def _encaixar(self, x, y):
        """Encaixa o clique num vertice, numa aresta ou no ponto de grade."""
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

        # aresta de parede/guia (desligado ao arrastar uma parede, que
        # grudaria nas proprias arestas)
        arrastando_parede = (self._arraste is not None
                             and self._arraste["categoria"] == "parede")
        if not arrastando_parede:
            aresta = ponto_em_aresta(x, y, self._bordas(), self.passo / 3)
            if aresta is not None:
                qx, qy = aresta
                # de preferencia um ponto que esteja na aresta E na grade
                geo = self._bordas()
                candidatos = [c for c in ((self._na_grade(qx), qy),
                                          (qx, self._na_grade(qy)))
                              if geo.distance(Point(c)) < 1e-6]
                if candidatos:
                    qx, qy = min(candidatos, key=lambda c: (c[0] - qx) ** 2
                                 + (c[1] - qy) ** 2)
                return round(qx, 3), round(qy, 3)

        return self._na_grade(x), self._na_grade(y)

    def _mudar_passo(self, direcao):
        atual = min(range(len(PASSOS_GRADE)),
                    key=lambda i: abs(PASSOS_GRADE[i] - self.passo))
        novo = min(max(atual + direcao, 0), len(PASSOS_GRADE) - 1)
        self.passo = PASSOS_GRADE[novo]
        print(f"Passo da grade: {self.passo} m")
        self._redesenhar()

    def _cliques_necessarios(self):
        """Cliques que o modo atual precisa; None = quantos quiser (enter)."""
        if self.modo in ("ponto", "distribuir"):
            return 1
        if self.modo in MODOS_PAREDE:
            return None
        if self.modo is None:
            return 0
        return 2

    # ------------------------------------------------------------------ #
    # Titulo e painel lateral
    # ------------------------------------------------------------------ #
    def _rotulo_opcao(self, modo, opcao):
        if modo == "distribuir":
            return MODOS_DISTRIBUICAO[opcao][0]
        if modo == "movel":
            return ROTULO_MOVEL[opcao]
        return opcao.replace("_", " ")

    def _atualizar_titulo(self):
        modo_txt = self.modo or "nenhum"
        opcao = self._opcao_atual()
        if opcao:
            modo_txt = f"{modo_txt} ({self._rotulo_opcao(self.modo, opcao)})"
        pendente = ""
        if self._cliques_pendentes:
            n = len(self._cliques_pendentes)
            total = self._cliques_necessarios()
            pendente = (f"  |  clique {n}/{total} (u desfaz)" if total
                        else f"  |  {n} vertice(s), enter conclui")
        n_ap = sum(1 for p in self.pontos_medicao
                   if p.get("tipo", "medicao") == "access_point")
        n_medicao = len(self.pontos_medicao) - n_ap
        snap_txt = f"snap {self.passo:g} m" if self.snap else "snap off"
        self.ax.set_title(
            f"modo: {modo_txt}  |  {snap_txt}  |  "
            f"{len(self.paredes)} paredes, {len(self.aberturas)} aberturas, "
            f"{len(self.moveis)} moveis, {n_medicao}+{n_ap}ap pontos"
            f"{pendente}",
            fontsize=8, loc="left",
        )
        self.fig.canvas.draw_idle()

    def _atualizar_painel(self):
        """Painel lateral: modos e paleta (esquerda), teclas (direita)."""
        linhas = ["MODOS"]
        for tecla, modo in TECLAS_MODO.items():
            marca = ">" if modo == self.modo else " "
            linhas.append(f" {marca} {tecla}  {modo.replace('_', ' ')}")

        paleta = self._paleta()
        if paleta is not None:
            rotulo, opcoes = paleta
            linhas += ["", f"{rotulo.upper()} (1-{len(opcoes)})"]
            for i, opcao in enumerate(opcoes, start=1):
                marca = ">" if i - 1 == self._selecao[self.modo] else " "
                linhas.append(f" {marca} {i}  {self._rotulo_opcao(self.modo, opcao)}")
        else:
            linhas += ["", "(escolha um modo)"]
        self._painel.set_text("\n".join(linhas))

        guias = "on" if self.mostrar_guias else "off"
        self._painel_teclas.set_text("\n".join([
            "MOUSE",
            " esq    marcar",
            " dir    editar objeto",
            " arrastar  mover o",
            "   objeto em edicao",
            " scroll zoom",
            " espaco+arrastar  pan",
            "",
            "TECLAS",
            "enter concluir parede",
            "l    alinhamento",
            f"h    guias: {guias}",
            "u    desfazer",
            "esc  cancelar cliques",
            f"g    snap: {'on' if self.snap else 'off'}",
            f"[ ]  passo: {self.passo:g} m",
            "0    enquadrar",
            "t    gerar tabela CSV",
            "s    salvar",
            "q    salvar e sair",
        ]))
        self._atualizar_parametros()
        self._atualizar_titulo()

    # ------------------------------------------------------------------ #
    # Desenho completo
    # ------------------------------------------------------------------ #
    def _redesenhar(self):
        xlim, ylim = self.ax.get_xlim(), self.ax.get_ylim()
        self._fundo = None  # o fundo guardado para o blit ficou obsoleto
        self._cache_geo = {}  # paredes/aberturas podem ter mudado
        self.ax.cla()
        self.ax.set_xlim(xlim)
        self.ax.set_ylim(ylim)
        self.ax.set_aspect("equal")
        self.ax.set_anchor("N")
        self._configurar_grade()
        self.ax.set_xlabel("x (m)")
        self.ax.set_ylabel("y (m)")

        handles = []
        if self.mostrar_guias and self.guias:
            for g in self.guias:
                self.ax.plot([g["x1"], g["x2"]], [g["y1"], g["y2"]],
                             color=ESTILO_GUIA["cor"],
                             linestyle=ESTILO_GUIA["linestyle"],
                             linewidth=ESTILO_GUIA["linewidth"], zorder=1)
            handles.append(Line2D([], [], color=ESTILO_GUIA["cor"],
                                  linestyle=ESTILO_GUIA["linestyle"],
                                  label="guia (parede antiga)"))

        paredes_desenhadas = set()
        for p, pol in zip(self.paredes, self._paredes_geo()):
            estilo = ESTILO_PAREDE.get(p["tipo"], ESTILO_PAREDE["parede"])
            cor = COR_MATERIAL_PAREDE.get(p["material"], COR_PAREDE_PADRAO)
            paredes_desenhadas.add((p["tipo"], p["material"]))
            self.ax.add_patch(PathPatch(
                caminho_poligono(pol), facecolor=cor, edgecolor=cor,
                alpha=estilo["alpha"], hatch=estilo["hatch"],
                linewidth=0.6, zorder=3))
        for tipo, material in sorted(paredes_desenhadas):
            estilo = ESTILO_PAREDE.get(tipo, ESTILO_PAREDE["parede"])
            cor = COR_MATERIAL_PAREDE.get(material, COR_PAREDE_PADRAO)
            handles.append(Patch(facecolor=cor, edgecolor=cor,
                                 alpha=estilo["alpha"], hatch=estilo["hatch"],
                                 label=f"{estilo['rotulo']} {material}"))

        aberturas_desenhadas = set()
        for a in self.aberturas:
            estilo = ESTILO_ABERTURA.get(a["tipo"], ESTILO_ABERTURA["porta"])
            aberturas_desenhadas.add(a["tipo"])
            vidro = str(a.get("material", "")).startswith("vidro")
            for r in a.get("recorte", []):
                self.ax.add_patch(PathPatch(
                    caminho_poligono(para_shapely(r)), facecolor=estilo["cor"],
                    edgecolor=estilo["cor"], alpha=0.35,
                    hatch=".." if vidro else None, linewidth=0.8, zorder=4))
            self.ax.plot([a["x1"], a["x2"]], [a["y1"], a["y2"]],
                         color=estilo["cor"], linewidth=2.5,
                         linestyle=":" if a["tipo"] == "vao" else "-",
                         solid_capstyle="butt", zorder=5)
        handles += [
            Line2D([], [], color=ESTILO_ABERTURA[t]["cor"], linewidth=2.5,
                   label=ESTILO_ABERTURA[t]["rotulo"])
            for t in ESTILO_ABERTURA if t in aberturas_desenhadas]

        for m in self.moveis:
            cor = CORES_MATERIAL.get(m["material"], COR_PADRAO)
            self.ax.add_patch(Rectangle(
                (m["x"], m["y"]), m["largura"], m["profundidade"],
                facecolor=cor, alpha=0.4, edgecolor=cor, zorder=2))
            self.ax.text(
                m["x"] + m["largura"] / 2, m["y"] + m["profundidade"] / 2,
                m.get("nome", m["tipo"]), ha="center", va="center",
                fontsize=7, zorder=6, clip_on=True,
            )

        tipos_ponto = set()
        for pt in self.pontos_medicao:
            tipo = pt.get("tipo", "medicao")
            estilo = ESTILO_PONTO.get(tipo, ESTILO_PONTO["medicao"])
            tipos_ponto.add(tipo)
            self.ax.scatter([pt["x"]], [pt["y"]], color=estilo["cor"],
                            marker=estilo["marcador"], zorder=7)
            self.ax.annotate(
                str(pt["id"]), (pt["x"], pt["y"]),
                textcoords="offset points", xytext=(5, 5),
                fontsize=8, color=estilo["cor"],
            )
        handles += [
            Line2D([], [], color=ESTILO_PONTO[t]["cor"],
                   marker=ESTILO_PONTO[t]["marcador"], linestyle="none",
                   label=ESTILO_PONTO[t]["rotulo"])
            for t in ESTILO_PONTO if t in tipos_ponto]

        if handles:
            self.ax.legend(handles=handles, loc="upper right", fontsize=7,
                           framealpha=0.8)

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

    def _previa_parede(self, cliques):
        """Poligono que a parede em construcao vai virar, ou None."""
        try:
            if self.modo == "contorno":
                if len(cliques) < 3:
                    return None
                return corrigir(Polygon(cliques))
            if len(cliques) < 2:
                return None
            return parede_de_polilinha(cliques, self.espessura,
                                       self.alinhamento,
                                       existentes=self._paredes_geo())
        except (ValueError, TypeError):
            return None

    def _desenhar_cliques_pendentes(self):
        """Marca em laranja os cliques ja dados no elemento em construcao."""
        if not self._cliques_pendentes:
            return

        if self.modo in MODOS_PAREDE:
            previa = self._previa_parede(self._cliques_pendentes)
            for pol in poligonos(previa):
                self.ax.add_patch(PathPatch(
                    caminho_poligono(pol), facecolor="tab:orange",
                    edgecolor="tab:orange", alpha=0.3, linestyle="--",
                    zorder=6))

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
        # linha elastica do ultimo clique pendente ate a mira
        self._elastico = Line2D(
            [], [], color="tab:orange", linewidth=1.2, linestyle="--",
            zorder=8, animated=True, visible=False)
        self.ax.add_line(self._elastico)
        self._rotulo = self.ax.text(
            0.0, 0.0, "", fontsize=8, family="monospace", zorder=11,
            animated=True, visible=False, clip_on=True,
            bbox=dict(boxstyle="round,pad=0.25", facecolor="lightyellow",
                      edgecolor="tab:green", alpha=0.9),
        )
        self._hud = [self._mira_v, self._mira_h, self._realce,
                     self._elastico, self._marca, self._rotulo]

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

        if self._cliques_pendentes and self.modo is not None \
                and self.modo not in ("ponto", "distribuir"):
            ux, uy = self._cliques_pendentes[-1]
            self._elastico.set_data([ux, xs], [uy, ys])
            self._elastico.set_visible(True)
        else:
            self._elastico.set_visible(False)

        alvo = self._objeto_sob(x, y)
        if alvo is None:
            self._realce.set_visible(False)
            descricao = self._descricao_comodo(x, y) or "-"
        else:
            rx, ry = self._pontos_realce(*alvo)
            self._realce.set_data(rx, ry)
            self._realce.set_visible(True)
            descricao = self._descricao(*alvo)

        # o rotulo acompanha o cursor com um deslocamento fixo em pixels
        px, py = self.ax.transData.transform((x, y))
        self._rotulo.set_position(
            self.ax.transData.inverted().transform((px + 12, py + 12)))
        extra = ""
        if self._cliques_pendentes and self.modo in MODOS_PAREDE + MODOS_ABERTURA:
            ux, uy = self._cliques_pendentes[-1]
            extra = f"  +{np.hypot(xs - ux, ys - uy):.2f} m"
        self._rotulo.set_text(
            f"({xs:.2f}, {ys:.2f}){extra}"
            + ("" if descricao == "-" else f"\n{descricao}"))
        self._rotulo.set_visible(True)

        snap_txt = f"snap {self.passo:g} m" if self.snap else "snap off"
        self._status.set_text(
            f"cursor  x={x:7.2f}  y={y:7.2f} m   |   encaixe "
            f"({xs:.2f}, {ys:.2f})   |   {snap_txt}   |   "
            f"sob o cursor: {descricao}"
        )
        self._blit()
