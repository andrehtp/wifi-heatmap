"""Interface de linha de comando do visualizador de mapa de calor."""

import argparse
from pathlib import Path

from .core import HeatmapViewer
from .io import carregar_planta


def parse_args():
    parser = argparse.ArgumentParser(
        description="Visualizador interativo de mapa de calor de sinal Wi-Fi "
                     "sobre a planta baixa."
    )
    parser.add_argument("--entrada", required=True,
                         help="Planta JSON com leituras_dbm preenchidas")
    parser.add_argument("--saida", default=None,
                         help="Nome base para exportar PNG/SVG "
                              "(padrao: nome da entrada, sem extensao)")
    return parser.parse_args()


def main():
    args = parse_args()
    saida_base = Path(args.saida or args.entrada).with_suffix("")
    dados = carregar_planta(args.entrada)
    HeatmapViewer(dados, saida_base=saida_base).run()


if __name__ == "__main__":
    main()
