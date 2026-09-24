"""Constantes de configuracao do editor de planta baixa."""

USAGE = """
Editor interativo de planta baixa para o projeto de mapa de calor wifi.

Desenha paredes (poligonos com espessura real), janelas, portas, vaos,
moveis e pontos (de medicao de sinal ou access point) diretamente com o
mouse sobre um plano cartesiano (1 unidade = 1 metro), e salva tudo no
JSON que alimenta o heatmap. Os pontos de medicao guardam so id e
posicao: as leituras ficam numa tabela CSV, ligada aos pontos pelo id.

Uso:
    python planta_editor.py --largura 8 --altura 6 --saida planta_casa.json

    # grade de 0.5 m em vez do padrao de 0.25 m:
    python planta_editor.py --passo 0.5

    # para continuar editando uma planta ja existente:
    python planta_editor.py --entrada planta_casa.json --saida planta_casa.json

    # so gerar a tabela CSV em branco dos pontos de medicao (sem abrir a
    # janela); recusa sobrescrever um CSV existente sem --forcar:
    python planta_editor.py --entrada planta_casa.json --gerar-tabela medicao.csv

Mouse:
    esquerdo          marca os pontos do elemento do modo atual
    direito           edita o objeto que estiver sob o cursor
    arrastar          com um objeto aberto no painel: move o objeto, ou
                      so o vertice da parede que estiver sob o cursor
    scroll            zoom no ponto onde o cursor esta
    espaco + arrastar move a vista (pan); o botao do meio faz o mesmo

Modos:
    w   parede         polilinha: um clique por vertice; enter (ou clicar
                       de novo no ultimo vertice) conclui, clicar no 1o
                       vertice fecha o contorno. A espessura e o
                       alinhamento (centro/esquerda/direita, tecla l) ficam
                       no painel.
    m   meia parede    igual a parede
    y   contorno       parede desenhada pelo contorno do poligono (clique
                       nos cantos reais; enter ou 1o vertice fecha)
    j   janela         2 cliques; sobre uma parede, recorta o trecho
    d   porta          2 cliques; idem
    o   vao livre      2 cliques; passagem sem porta, idem
    f   movel          2 cantos opostos do retangulo
    p   ponto          1 clique; 1/2 escolhe medicao ou access point
    a   distribuir     espalha pontos de medicao automaticamente: clique
                       dentro de um comodo (so ele) ou enter (planta toda)

Outras teclas:
    1-9 escolher material / tipo / metodo do modo atual
    l   alternar o alinhamento da parede (centro, esquerda, direita)
    h   mostrar/esconder as guias (paredes antigas em linha)
    u   desfazer (inclui edicoes e exclusoes feitas no painel)
    esc cancelar os cliques pendentes do elemento em construcao
    g   ligar/desligar o snap (encaixe na grade)
    [ ] diminuir / aumentar o passo da grade (0.05 ... 1.0 m)
    0   enquadrar a vista em tudo que ja foi desenhado
    t   salvar e gerar a tabela CSV em branco dos pontos de medicao (id +
        3 colunas de leitura, para o heatmap); o caminho fica no painel do
        modo ponto. Se o CSV ja existir, tecle t de novo para sobrescrever
    s   salvar o estado atual em JSON
    q   salvar e fechar

Plantas antigas (paredes em linha) abrem com as paredes como guias
cinzas: redesenhe as paredes por cima delas (o snap encaixa nas pontas e
ao longo das guias). Ao sobrescrever uma planta antiga, uma copia do
original e salva como <nome>.antigo.json.

Snap (ligado por padrao, passo de 0.25 m): cada clique e encaixado num
vertice existente, numa aresta de parede/guia ou no ponto de grade mais
proximo, nessa ordem de prioridade.
"""

# Tecla -> modo.
TECLAS_MODO = {
    "w": "parede",
    "m": "meia_parede",
    "y": "contorno",
    "j": "janela",
    "d": "porta",
    "o": "vao",
    "f": "movel",
    "p": "ponto",
    "a": "distribuir",
}
# Modos que criam paredes (poligonos) e o "tipo" que cada um grava.
MODOS_PAREDE = ("parede", "meia_parede", "contorno")
TIPO_PAREDE = {"parede": "parede", "meia_parede": "meia_parede",
               "contorno": "parede"}
TIPOS_PAREDE = ("parede", "meia_parede")
# Aberturas: continuam segmentos, mas recortam as paredes que tocam.
MODOS_ABERTURA = ("janela", "porta", "vao")

MATERIAIS_PAREDE = ["alvenaria", "concreto", "tijolo", "drywall", "madeira"]

TIPOS_MOVEL = ["armario", "mesa", "cama", "equipamento_eletrico",
               "guarda_roupa", "balcao", "personalizado"]

# Paleta de cada modo: o que as teclas 1-9 escolhem. As opcoes de
# "distribuir" sao as chaves de distribuicao.MODOS_DISTRIBUICAO.
PALETAS = {
    "parede":      ("material", MATERIAIS_PAREDE),
    "meia_parede": ("material", MATERIAIS_PAREDE),
    "contorno":    ("material", MATERIAIS_PAREDE),
    "janela":      ("material", ["vidro", "vidro duplo", "madeira", "metal"]),
    "porta":       ("material", ["madeira", "vidro", "metal"]),
    "vao":         ("material", ["livre"]),
    "movel":       ("tipo", TIPOS_MOVEL),
    "ponto":       ("tipo", ["medicao", "access_point"]),
    "distribuir":  ("metodo", ["grade", "hexagonal", "quantidade",
                               "por_comodo", "paredes", "foco_ap",
                               "aleatorio"]),
}

# Espessura sugerida por material (a caixa "espessura" do painel volta a
# este valor quando o material da parede muda).
ESPESSURA_MATERIAL = {
    "alvenaria": 0.15,
    "concreto": 0.15,
    "tijolo": 0.15,
    "drywall": 0.10,
    "madeira": 0.05,
}
ESPESSURA_PADRAO = 0.15

ALINHAMENTOS = ["centro", "esquerda", "direita"]

# Moveis: rotulo exibido e material predominante de cada tipo fixo.
ROTULO_MOVEL = {
    "armario": "Armario",
    "mesa": "Mesa",
    "cama": "Cama",
    "equipamento_eletrico": "Equipamento eletrico",
    "guarda_roupa": "Guarda-roupa",
    "balcao": "Balcao",
    "personalizado": "Movel",
}
MATERIAL_MOVEL = {
    "armario": "madeira",
    "mesa": "madeira",
    "cama": "madeira",
    "equipamento_eletrico": "metal",
    "guarda_roupa": "madeira",
    "balcao": "pedra",
    "personalizado": "madeira",
}
MATERIAIS_MOVEL = ["madeira", "metal", "vidro", "pedra", "alvenaria",
                   "plastico", "tecido"]
# Tipos de movel das plantas antigas -> tipo novo (o antigo vira "nome").
MIGRACAO_MOVEL = {
    "geladeira": "equipamento_eletrico",
    "fogao": "equipamento_eletrico",
    "micro-ondas": "equipamento_eletrico",
    "tv": "equipamento_eletrico",
}

# Como cada tipo de parede e desenhado (a cor vem do material).
ESTILO_PAREDE = {
    "parede":      {"alpha": 0.95, "hatch": None, "rotulo": "parede"},
    "meia_parede": {"alpha": 0.45, "hatch": "////", "rotulo": "meia parede"},
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
    "janela": {"cor": "tab:cyan",   "rotulo": "janela"},
    "porta":  {"cor": "tab:orange", "rotulo": "porta"},
    "vao":    {"cor": "gold",       "rotulo": "vao livre"},
}

ESTILO_GUIA = {"cor": "0.6", "linestyle": (0, (4, 3)), "linewidth": 1.0}

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

PASSOS_GRADE = [0.05, 0.10, 0.20, 0.25, 0.50, 1.00]

# Distribuidor automatico de pontos.
MARGEM_PAREDE_PADRAO = 0.30   # distancia minima entre ponto e parede, m
MARGEM_MOVEL = 0.10           # distancia minima entre ponto e movel, m

# Tabela CSV de medicao gerada a partir dos pontos (tecla t / --gerar-tabela).
N_LEITURAS_PADRAO = 3

# Navegacao.
ZOOM_FATOR = 1.15
EXTENSAO_MIN = 0.5     # menor largura/altura visivel, em metros
EXTENSAO_MAX = 500.0   # maior largura/altura visivel, em metros
TOLERANCIA_PX = 10     # raio de "acerto" do cursor sobre um objeto, em pixels
MAX_HISTORICO = 100
