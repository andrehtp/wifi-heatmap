"""Constantes de estilo/config do visualizador de heatmap.

Duplica (nao importa) os poucos estilos que precisa de `editor/constants.py`
para manter esta ferramenta desacoplada do editor de planta baixa - sao
duas etapas independentes do pipeline.
"""

USAGE = """
Visualizador interativo de mapa de calor de sinal Wi-Fi.

Le uma planta JSON (gerada pelo editor) e uma tabela CSV de medicoes
(coluna "id" + colunas de leitura em dBm, ligadas aos pontos de medicao
pelo id) e desenha o mapa de calor por cima da planta.

Uso:
    python heatmap_gerador.py --entrada planta_casa.json --tabela medicao.csv

    # nome base para os arquivos exportados (padrao: nome da entrada sem extensao)
    python heatmap_gerador.py --entrada planta_casa.json --tabela medicao.csv --saida mapa_casa

Na janela: escolha o metodo de interpolacao e o estilo visual nos
seletores da direita; os botoes "Exportar PNG"/"Exportar SVG" salvam o
arquivo indicado na caixa de texto.
"""

ESTILO_PAREDE = {
    "parede":      {"alpha": 0.95, "hatch": None},
    "meia_parede": {"alpha": 0.45, "hatch": "////"},
}
COR_MATERIAL_PAREDE = {
    "alvenaria": "#6b5b4f",
    "concreto": "#4a4a4a",
    "tijolo": "#a0522d",
    "drywall": "#9e9e9e",
    "madeira": "#b08355",
}
COR_PAREDE_PADRAO = "#4a4a4a"

ESTILO_ABERTURA = {
    "janela": {"cor": "tab:cyan"},
    "porta":  {"cor": "tab:orange"},
    "vao":    {"cor": "gold"},
}

ESTILO_PONTO = {
    "medicao":      {"cor": "tab:blue", "marcador": "o", "rotulo": "ponto de medicao"},
    "access_point": {"cor": "tab:red",  "marcador": "^", "rotulo": "access point"},
}

CORES_MATERIAL = {
    "metal": "tab:red",
    "vidro": "tab:cyan",
    "pedra": "tab:gray",
    "alvenaria": "tab:gray",
}
COR_PADRAO = "tab:brown"

# Sinal fraco -> forte: colormap sequencial de um so matiz (perceptualmente
# uniforme e seguro para daltonismo), nunca um rainbow/jet.
COLORMAP_SINAL = "viridis"
ROTULO_COLORBAR = "Sinal (dBm)"

MARGEM_GRADE = 0.5     # metros, ao redor dos extremos da planta
RESOLUCAO_GRADE = 150  # celulas por eixo da grade de interpolacao
