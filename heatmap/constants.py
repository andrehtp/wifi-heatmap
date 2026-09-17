"""Constantes de estilo/config do visualizador de heatmap.

Duplica (nao importa) os poucos estilos que precisa de `editor/constants.py`
para manter esta ferramenta desacoplada do editor de planta baixa - sao
duas etapas independentes do pipeline.
"""

USAGE = """
Visualizador interativo de mapa de calor de sinal Wi-Fi.

Le uma planta JSON (gerada pelo editor e com leituras_dbm preenchidas,
ex: por importar_medicoes.py) e desenha o mapa de calor por cima dela.

Uso:
    python heatmap_gerador.py --entrada planta_casa.json

    # nome base para os arquivos exportados (padrao: nome da entrada sem extensao)
    python heatmap_gerador.py --entrada planta_casa.json --saida mapa_casa

Na janela: escolha o metodo de interpolacao e o estilo visual nos
seletores da direita; os botoes "Exportar PNG"/"Exportar SVG" salvam o
arquivo indicado na caixa de texto.
"""

ESTILO_SEGMENTO = {
    "parede":      {"cor": "black",      "linestyle": "-",         "rotulo": "parede"},
    "meia_parede": {"cor": "dimgray",    "linestyle": (0, (6, 4)), "rotulo": "meia parede / vao"},
    "janela":      {"cor": "tab:cyan",   "linestyle": "-",         "rotulo": "janela"},
    "porta":       {"cor": "tab:orange", "linestyle": "-",         "rotulo": "porta"},
}

ESTILO_PONTO = {
    "medicao":      {"cor": "tab:blue", "marcador": "o", "rotulo": "ponto de medicao"},
    "access_point": {"cor": "tab:red",  "marcador": "^", "rotulo": "access point"},
}

CORES_MATERIAL = {
    "metal": "tab:red",
    "vidro": "tab:cyan",
}
COR_PADRAO = "tab:brown"

# Sinal fraco -> forte: colormap sequencial de um so matiz (perceptualmente
# uniforme e seguro para daltonismo), nunca um rainbow/jet.
COLORMAP_SINAL = "viridis"
ROTULO_COLORBAR = "Sinal (dBm)"

MARGEM_GRADE = 0.5     # metros, ao redor dos extremos da planta
RESOLUCAO_GRADE = 150  # celulas por eixo da grade de interpolacao
