"""Deteccao do objeto (parede, movel ou ponto) sob o cursor."""

import math

from .constants import TOLERANCIA_PX
from .geometry import dist_ponto_retangulo, dist_ponto_segmento


class HitTestingMixin:
    def _lista(self, categoria):
        return {"parede": self.paredes,
                "movel": self.moveis,
                "ponto": self.pontos_medicao}[categoria]

    def _selecao_valida(self):
        if self._sel is None:
            return False
        categoria, indice = self._sel
        return 0 <= indice < len(self._lista(categoria))

    def _tolerancia_dados(self, pixels=TOLERANCIA_PX):
        """Converte um raio em pixels para unidades do plano (metros)."""
        largura_px = self.ax.get_window_extent().width
        if largura_px <= 0:
            return pixels * 0.01
        x0, x1 = self.ax.get_xlim()
        return pixels * (x1 - x0) / largura_px

    def _objeto_sob(self, x, y):
        """(categoria, indice) do objeto sob o cursor, ou None."""
        if x is None or y is None:
            return None
        tolerancia = self._tolerancia_dados()
        melhor, menor = None, tolerancia

        for i, p in enumerate(self.paredes):
            d = dist_ponto_segmento(x, y, p["x1"], p["y1"], p["x2"], p["y2"])
            if d <= menor:
                melhor, menor = ("parede", i), d
        for i, m in enumerate(self.moveis):
            d, _dentro = dist_ponto_retangulo(
                x, y, m["x"], m["y"], m["largura"], m["profundidade"])
            if d <= menor:
                melhor, menor = ("movel", i), d
        # pontos por ultimo: em caso de empate eles ganham, por serem o alvo
        # mais dificil de acertar
        for i, pt in enumerate(self.pontos_medicao):
            d = math.hypot(x - pt["x"], y - pt["y"])
            if d <= menor:
                melhor, menor = ("ponto", i), d
        if melhor is not None:
            return melhor

        # longe de qualquer borda: vale o movel cujo interior contem o cursor
        dentro = [
            (m["largura"] * m["profundidade"], i)
            for i, m in enumerate(self.moveis)
            if dist_ponto_retangulo(
                x, y, m["x"], m["y"], m["largura"], m["profundidade"])[1]
        ]
        if dentro:
            return ("movel", min(dentro)[1])
        return None

    def _pontos_realce(self, categoria, indice):
        obj = self._lista(categoria)[indice]
        if categoria == "parede":
            return [obj["x1"], obj["x2"]], [obj["y1"], obj["y2"]]
        if categoria == "movel":
            x0, y0 = obj["x"], obj["y"]
            x1, y1 = x0 + obj["largura"], y0 + obj["profundidade"]
            return [x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0]
        return [obj["x"]], [obj["y"]]

    def _descricao(self, categoria, indice):
        obj = self._lista(categoria)[indice]
        if categoria == "parede":
            comp = math.hypot(obj["x2"] - obj["x1"], obj["y2"] - obj["y1"])
            return (f"{obj.get('tipo', 'parede').replace('_', ' ')} "
                    f"{obj['material']} ({comp:.2f} m)")
        if categoria == "movel":
            return (f"movel {obj['tipo']} {obj['material']} "
                    f"({obj['largura']:g} x {obj['profundidade']:g} m)")
        return f"ponto de medicao {obj['id']}"
