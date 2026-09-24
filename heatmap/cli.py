"""Interface de linha de comando do visualizador de mapa de calor."""

import argparse
from pathlib import Path

from .core import HeatmapViewer
from .io import carregar_planta
from .tabela import associar_leituras, ler_csv_leituras


def parse_args():
    parser = argparse.ArgumentParser(
        description="Visualizador interativo de mapa de calor de sinal Wi-Fi "
                     "sobre a planta baixa."
    )
    parser.add_argument("--entrada", required=True,
                         help="Planta JSON gerada pelo editor")
    parser.add_argument("--tabela", default=None,
                         help="CSV com coluna 'id' + colunas de leitura em dBm, "
                              "ligado aos pontos de medicao pelo id (sem ele, "
                              "usa leituras_dbm do JSON, de plantas antigas)")
    parser.add_argument("--saida", default=None,
                         help="Nome base para exportar PNG/SVG "
                              "(padrao: nome da entrada, sem extensao)")
    return parser.parse_args()


def main():
    args = parse_args()
    saida_base = Path(args.saida or args.entrada).with_suffix("")
    dados = carregar_planta(args.entrada)
    leituras = None
    if args.tabela:
        brutas, avisos = ler_csv_leituras(args.tabela)
        leituras, avisos_assoc = associar_leituras(dados, brutas)
        for aviso in avisos + avisos_assoc:
            print(f"Aviso: {aviso}")
        print(f"{len(leituras)} ponto(s) com leitura em {args.tabela}.")
    HeatmapViewer(dados, saida_base=saida_base, leituras_por_id=leituras).run()


if __name__ == "__main__":
    main()
