"""Tabela CSV em branco para anotar as leituras dos pontos de medicao.

O formato e o que o heatmap le (`heatmap/tabela.py`): coluna "id" + uma
coluna por leitura; celulas vazias sao ignoradas la.
"""

import csv
from pathlib import Path

from .constants import N_LEITURAS_PADRAO


def colunas_leitura(n):
    return [f"leitura_{i}" for i in range(1, n + 1)]


def escrever_tabela(pontos, caminho, n_leituras=N_LEITURAS_PADRAO, forcar=False):
    """Escreve uma linha por ponto de medicao (access points ficam de fora),
    em ordem de id, com as colunas de leitura vazias.

    Levanta FileExistsError se o arquivo ja existe e forcar=False (ele pode
    ter leituras preenchidas). Retorna quantos pontos foram escritos.
    """
    caminho = Path(caminho)
    if caminho.exists() and not forcar:
        raise FileExistsError(caminho)
    ids = sorted(p["id"] for p in pontos if p.get("tipo", "medicao") == "medicao")
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["id"] + colunas_leitura(n_leituras))
        for pid in ids:
            escritor.writerow([pid] + [""] * n_leituras)
    return len(ids)
