"""Navegacao: pan (espaco / botao do meio), zoom (scroll) e area visivel."""

from .constants import EXTENSAO_MAX, EXTENSAO_MIN, ZOOM_FATOR
from .widgets import definir_texto

try:
    from matplotlib.backend_tools import Cursors
except ImportError:  # pragma: no cover - backends antigos
    Cursors = None


class NavigationMixin:
    # ------------------------------------------------------------------ #
    # Navegacao: pan (espaco / botao do meio) e zoom (scroll)
    # ------------------------------------------------------------------ #
    def _toolbar_ativa(self):
        """True quando o pan/zoom da barra de ferramentas esta ligado."""
        toolbar = getattr(self.fig.canvas, "toolbar", None)
        return bool(str(getattr(toolbar, "mode", "") or ""))

    def _definir_cursor(self):
        if Cursors is None:
            return
        try:
            self.fig.canvas.set_cursor(
                Cursors.MOVE if (self._espaco or self._pan) else Cursors.POINTER)
        except Exception:  # pragma: no cover - depende do backend
            pass

    def _cancelar_timer_espaco(self):
        if self._timer_espaco is not None:
            self._timer_espaco.stop()
            self._timer_espaco = None

    def _liberar_espaco(self):
        self._timer_espaco = None
        self._espaco = False
        self._definir_cursor()

    def _iniciar_pan(self, event):
        bbox = self.ax.get_window_extent()
        if bbox.width <= 0 or bbox.height <= 0:
            return
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        self._pan = (event.x, event.y, x0, x1, y0, y1,
                     (x1 - x0) / bbox.width, (y1 - y0) / bbox.height)
        self._definir_cursor()

    def _arrastar_pan(self, event):
        if event.x is None or event.y is None:
            return
        px, py, x0, x1, y0, y1, escala_x, escala_y = self._pan
        dx = (event.x - px) * escala_x
        dy = (event.y - py) * escala_y
        self.ax.set_xlim(x0 - dx, x1 - dx)
        self.ax.set_ylim(y0 - dy, y1 - dy)
        self.fig.canvas.draw_idle()

    def _encerrar_pan(self):
        if self._pan is None:
            return
        self._pan = None
        self._sincronizar_caixas_vista()
        self._definir_cursor()
        self.fig.canvas.draw_idle()

    def _on_scroll(self, event):
        if event.inaxes is not self.ax or self._toolbar_ativa():
            return
        if event.xdata is None or event.ydata is None:
            return
        fator = ZOOM_FATOR if event.button == "down" else 1 / ZOOM_FATOR
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        larg, alt = (x1 - x0) * fator, (y1 - y0) * fator
        if not (EXTENSAO_MIN <= larg <= EXTENSAO_MAX):
            return
        if not (EXTENSAO_MIN <= alt <= EXTENSAO_MAX):
            return
        # mantem sob o cursor o mesmo ponto do plano
        fx = (event.xdata - x0) / (x1 - x0)
        fy = (event.ydata - y0) / (y1 - y0)
        novo_x0 = event.xdata - larg * fx
        novo_y0 = event.ydata - alt * fy
        self._definir_limites((novo_x0, novo_x0 + larg),
                              (novo_y0, novo_y0 + alt))

    # ------------------------------------------------------------------ #
    # Largura / altura da area visivel
    # ------------------------------------------------------------------ #
    def _definir_limites(self, xlim, ylim):
        self.ax.set_xlim(*xlim)
        self.ax.set_ylim(*ylim)
        self._sincronizar_caixas_vista()
        self.fig.canvas.draw_idle()

    def _sincronizar_caixas_vista(self):
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        definir_texto(self._tb_largura, f"{x1 - x0:.2f}")
        definir_texto(self._tb_altura, f"{y1 - y0:.2f}")

    def _aplicar_vista(self):
        try:
            larg = float(self._tb_largura.text.strip().replace(",", "."))
            alt = float(self._tb_altura.text.strip().replace(",", "."))
        except ValueError:
            print("Largura/altura da visualizacao invalidas.")
            self._sincronizar_caixas_vista()
            self.fig.canvas.draw_idle()
            return
        larg = min(max(larg, EXTENSAO_MIN), EXTENSAO_MAX)
        alt = min(max(alt, EXTENSAO_MIN), EXTENSAO_MAX)
        x0 = self.ax.get_xlim()[0]
        y0 = self.ax.get_ylim()[0]
        self._definir_limites((x0, x0 + larg), (y0, y0 + alt))

    def _enquadrar(self):
        xs, ys = [], []
        for p in self.paredes:
            xs += [v[0] for v in p["vertices"]]
            ys += [v[1] for v in p["vertices"]]
        for seg in self.aberturas + (self.guias if self.mostrar_guias else []):
            xs += [seg["x1"], seg["x2"]]
            ys += [seg["y1"], seg["y2"]]
        for m in self.moveis:
            xs += [m["x"], m["x"] + m["largura"]]
            ys += [m["y"], m["y"] + m["profundidade"]]
        for pt in self.pontos_medicao:
            xs.append(pt["x"])
            ys.append(pt["y"])
        if not xs:
            self._definir_limites(self._xlim0, self._ylim0)
            return
        margem = 0.5
        self._definir_limites((min(xs) - margem, max(xs) + margem),
                              (min(ys) - margem, max(ys) + margem))
