"""Interface de linha de comando do importador de medicoes."""

import argparse

from .core import aplicar_leituras, carregar_planta, ler_csv_leituras, salvar_planta


def parse_args():
    parser = argparse.ArgumentParser(
        description="Importa leituras de sinal (dBm) de uma tabela CSV para "
                     "os pontos de medicao de uma planta JSON.",
        epilog="Leituras existentes no ponto sao substituidas pelas do CSV, "
               "nao somadas.",
    )
    parser.add_argument("--planta", required=True,
                         help="Planta JSON de entrada")
    parser.add_argument("--tabela", required=True,
                         help="CSV com coluna 'id' + colunas de leitura em dBm")
    parser.add_argument("--saida", default=None,
                         help="Planta JSON de saida (padrao: sobrescreve --planta)")
    return parser.parse_args()


def main():
    args = parse_args()
    saida = args.saida or args.planta

    dados = carregar_planta(args.planta)
    leituras_por_id, avisos_csv = ler_csv_leituras(args.tabela)
    resumo = aplicar_leituras(dados, leituras_por_id)
    salvar_planta(dados, saida)

    avisos = avisos_csv + resumo["avisos"]
    print(f"Pontos atualizados: {resumo['atualizados']}")
    print(f"Leituras gravadas: {resumo['leituras_gravadas']}")
    if avisos:
        print(f"Avisos ({len(avisos)}):")
        for aviso in avisos:
            print(f"  - {aviso}")
    print(f"Planta salva em: {saida}")


if __name__ == "__main__":
    main()
