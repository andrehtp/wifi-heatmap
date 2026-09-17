"""
Visualizador interativo de mapa de calor de sinal Wi-Fi.

Ponto de entrada de linha de comando; a implementacao esta no pacote
`heatmap/`. Le uma planta JSON (gerada pelo editor, com leituras_dbm
preenchidas por importar_medicoes.py ou manualmente) e desenha o mapa de
calor por interpolacao dos pontos medidos, sobreposto ao desenho da
planta. Permite trocar o metodo de interpolacao e o estilo visual na
janela, e exportar o resultado em PNG ou SVG.

Uso:
    python heatmap_gerador.py --entrada planta_casa.json
"""

from heatmap.cli import main

if __name__ == "__main__":
    main()
