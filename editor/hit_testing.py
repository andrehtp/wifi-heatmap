"""Deteccao do objeto (parede, abertura, guia, movel ou ponto) sob o cursor."""

import math

from shapely import Point

from .constants import ESTILO_PONTO, TOLERANCIA_PX
from .geometry import dist_ponto_retangulo, dist_ponto_segmento
from .poligonos import espessura_aproximada, para_shapely


class HitTestingMixin:
    def _lista(self, categoria):
        return {"parede": self.paredes,
                "abertura": self.aberturas,
                "guia": self.guias,
                "movel": self.moveis,
                "ponto": self.pontos_medicao}[categoria]

    def _paredes_geo(self):
        """Polygon de cada parede, em cache ate o proximo redesenho."""
        if "paredes" not in self._cache_geo:
            self._cache_geo["paredes"] = [para_shapely(p) for p in self.paredes]
        return self._cache_geo["paredes"]

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
        cursor = Point(x, y)

        # dentro de uma parede conta como meia tolerancia: bordas de moveis,
        # aberturas e pontos por perto continuam ganhando dela
        for i, pol in enumerate(self._paredes_geo()):
            d = tolerancia / 2 if pol.contains(cursor) else pol.boundary.distance(cursor)
            if d <= menor:
                melhor, menor = ("parede", i), d
        if self.mostrar_guias:
            for i, g in enumerate(self.guias):
                d = dist_ponto_segmento(x, y, g["x1"], g["y1"], g["x2"], g["y2"])
                if d <= menor:
                    melhor, menor = ("guia", i), d
        for i, a in enumerate(self.aberturas):
            d = dist_ponto_segmento(x, y, a["x1"], a["y1"], a["x2"], a["y2"])
            if d <= menor:
                melhor, menor = ("abertura", i), d
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
            vs = obj["vertices"] + obj["vertices"][:1]
            return [v[0] for v in vs], [v[1] for v in vs]
        if categoria in ("abertura", "guia"):
            return [obj["x1"], obj["x2"]], [obj["y1"], obj["y2"]]
        if categoria == "movel":
            x0, y0 = obj["x"], obj["y"]
            x1, y1 = x0 + obj["largura"], y0 + obj["profundidade"]
            return [x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0]
        return [obj["x"]], [obj["y"]]

    def _descricao(self, categoria, indice):
        obj = self._lista(categoria)[indice]
        if categoria == "parede":
            pol = para_shapely(obj)
            return (f"{obj['tipo'].replace('_', ' ')} {obj['material']} "
                    f"({pol.area:.2f} m², esp. ~{espessura_aproximada(pol):.2f} m)")
        if categoria in ("abertura", "guia"):
            comp = math.hypot(obj["x2"] - obj["x1"], obj["y2"] - obj["y1"])
            if categoria == "guia":
                return f"guia ({comp:.2f} m)"
            material = "" if obj["tipo"] == "vao" else f" {obj['material']}"
            return f"{obj['tipo'].replace('_', ' ')}{material} ({comp:.2f} m)"
        if categoria == "movel":
            return (f"{obj['nome']} {obj['material']} "
                    f"({obj['largura']:g} x {obj['profundidade']:g} m)")
        estilo = ESTILO_PONTO.get(obj.get("tipo", "medicao"), ESTILO_PONTO["medicao"])
        return f"{estilo['rotulo']} {obj['id']}"

    def _descricao_comodo(self, x, y):
        """Area do comodo sob o cursor, para conferir medidas na hora."""
        salas, fechado = self._comodos()
        if not fechado:
            return None
        cursor = Point(x, y)
        for sala in salas:
            if sala.contains(cursor):
                x0, y0, x1, y1 = sala.bounds
                return (f"comodo {sala.area:.2f} m² "
                        f"({x1 - x0:.2f} x {y1 - y0:.2f} m)")
        return None
