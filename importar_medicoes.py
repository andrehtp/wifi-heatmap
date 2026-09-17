"""
Importador de leituras de sinal (dBm) de uma tabela CSV para a planta JSON.

Ponto de entrada de linha de comando; a implementacao esta no pacote
`medicoes/`. Le uma planta gerada pelo editor e um CSV com coluna 'id' +
colunas de leitura (ex: leitura1, leitura2, ...), e grava ate 5 leituras
em dBm no campo "leituras_dbm" de cada ponto de medicao correspondente.

Uso:
    python importar_medicoes.py --planta planta_casa.json --tabela medicoes.csv

    # gravar em um arquivo separado em vez de sobrescrever --planta:
    python importar_medicoes.py --planta planta_casa.json --tabela medicoes.csv --saida planta_casa_com_leituras.json
"""

from medicoes.cli import main

if __name__ == "__main__":
    main()
