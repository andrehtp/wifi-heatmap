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

    # como combinar as leituras de cada ponto (padrao: media em potencia/mW)
    python heatmap_gerador.py --entrada planta_casa.json --tabela medicao.csv --agregacao mediana

Na janela: escolha o metodo de interpolacao, o estilo visual, a area e a
escala de cor nos seletores da direita. A caixa "parametro" ajusta o
parametro principal do metodo ativo (enter aplica). O titulo mostra o
RMSE da validacao cruzada leave-one-out do metodo; a tabela comparando
todos os metodos sai no terminal. Os botoes "Exportar PNG"/"Exportar SVG"
salvam o arquivo indicado na caixa de texto.
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
RESOLUCAO_M = 0.05     # lado da celula (quadrada) da grade de interpolacao, em metros
MAX_CELULAS = 80_000   # teto de celulas: plantas grandes ganham celula maior
RAIO_BLOB = 1.0        # alcance (m) de cada blob no estilo "blobs por ponto"
ALPHA_HEATMAP = 0.75   # opacidade maxima do overlay (planta visivel por baixo)

# Escala de cor fixa (modo "fixa"), compartilhada por todos os estilos, e
# limites das bandas alinhados a limiares usuais de qualidade Wi-Fi:
# -30 excelente, -50 muito bom, -60 bom, -67 minimo p/ voz/video,
# -70 fraco, -80 minimo p/ conectar, -90 praticamente sem sinal.
ESCALA_DBM = (-90.0, -30.0)
NIVEIS_DBM = [-90, -80, -70, -67, -60, -50, -30]

# Leituras de um mesmo ponto que variam mais que isso (max - min) geram aviso.
LIMITE_DISPERSAO_DB = 6.0

# --------------------------------------------------------------------------- #
# Modelos de propagacao (path_loss / multi_wall / hibrido)
# --------------------------------------------------------------------------- #

# Perda por parede atravessada em 2,4 GHz (dB), modelo multi-wall de
# Motley-Keenan. Fontes: COST 231 Final Report (1999), cap. 4 (multi-wall):
# parede leve ~3,4 dB e parede pesada ~6,9 dB (ajuste a 1,8 GHz); faixas
# tipicas em 2,4 GHz de medidas publicadas (ex.: Wilson, "Propagation
# losses through common building materials 2.4 GHz vs 5 GHz", Magis
# Networks, 2002): drywall/madeira ~3 dB, tijolo ~6-8 dB, bloco/alvenaria
# ~8-12 dB, concreto ~10-15 dB. Sao pontos de partida: P0 e n sao ajustados
# as medicoes, e o parametro do metodo escala todas as perdas.
ATENUACAO_MATERIAL = {
    "alvenaria": 10.0,
    "concreto": 12.0,
    "tijolo": 7.0,
    "drywall": 3.0,
    "madeira": 3.5,
}
ATENUACAO_PADRAO = 8.0     # material desconhecido
FATOR_MEIA_PAREDE = 0.5    # meia parede: o sinal passa em parte por cima
# Aberturas: as paredes ja estao cortadas por elas, entao isto e so a perda
# extra do que fica no vao (vidro da janela; porta/vao assumidos abertos).
ATENUACAO_ABERTURA = {"janela": 2.0, "porta": 0.0, "vao": 0.0}

D0 = 1.0                     # distancia de referencia do log-distancia (m)
D_MIN = 0.5                  # distancia minima (evita log de ~0 junto ao AP)
LOG_DIST_PADRAO = (-40.0, 3.0)   # (P0 em dBm a 1 m, n) sem dados para ajustar
LIMITES_N = (1.5, 6.0)           # expoente de perda plausivel em interiores

# Parametro principal de cada metodo, editavel no painel:
# (rotulo, padrao, (minimo, maximo)). None = metodo sem parametro.
# Kriging: padrao None = "auto" (nugget ajustado junto com o variograma);
# um numero fixa o nugget como fracao do patamar total.
# IDW p=3 (e nao 2): em 2D, p<=2 deixa os pontos distantes dominarem e
# gera "olhos de boi"; sigma=1 m ~ espacamento tipico entre pontos (2 m
# achatava a casa inteira num degrade so). Padroes escolhidos pelo LOOCV
# numa casa real e em dados sinteticos; a suavizacao do RBF e em unidades
# das coordenadas normalizadas (0 = interpola exatamente os pontos).
PARAMETROS_PADRAO = {
    "idw": ("potencia p", 3.0, (0.1, 10.0)),
    "gaussiana": ("sigma (m)", 1.0, (0.05, 20.0)),
    "vizinho": None,
    "linear": None,
    "rbf": ("suavizacao", 0.01, (0.0, 100.0)),
    "kriging": ("nugget rel.", None, (0.0, 1.0)),
    "path_loss": None,
    "multi_wall": ("escala perdas", 1.0, (0.0, 5.0)),
    "hibrido": ("escala perdas", 1.0, (0.0, 5.0)),
}
