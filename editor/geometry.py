"""Funcoes de geometria e formatacao usadas pelo editor de planta baixa."""

import math


def dist_ponto_segmento(px, py, x1, y1, x2, y2):
    """Distancia do ponto ao segmento (nao a reta infinita)."""
    dx, dy = x2 - x1, y2 - y1
    if dx == 0.0 and dy == 0.0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def dist_ponto_retangulo(px, py, x0, y0, largura, profundidade):
    """(distancia ate o contorno, esta dentro?) de um retangulo."""
    x1, y1 = x0 + largura, y0 + profundidade
    if x0 <= px <= x1 and y0 <= py <= y1:
        return min(px - x0, x1 - px, py - y0, y1 - py), True
    dx = max(x0 - px, 0.0, px - x1)
    dy = max(y0 - py, 0.0, py - y1)
    return math.hypot(dx, dy), False


def fmt(valor):
    return f"{valor:g}" if isinstance(valor, float) else str(valor)
