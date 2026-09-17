"""Leitura standalone do JSON da planta (sem estado/GUI do editor)."""

import json


def carregar_planta(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
