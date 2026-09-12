"""Constantes de configuracao do editor de planta baixa."""

USAGE = """
Editor interativo de planta baixa para o projeto de mapa de calor wifi.

Desenha paredes, janelas, portas, moveis/eletrodomesticos e pontos de
medicao de sinal diretamente com o mouse sobre um plano cartesiano
(1 unidade = 1 metro), e salva tudo no JSON que alimenta a etapa de
interpolacao.

Uso:
    python planta_editor.py --largura 8 --altura 6 --saida planta_casa.json

    # grade de 0.5 m em vez do padrao de 0.25 m:
    python planta_editor.py --passo 0.5

    # para continuar editando uma planta ja existente:
    python planta_editor.py --entrada planta_casa.json --saida planta_casa.json

Requisitos:
    pip install matplotlib

Mouse:
    esquerdo          marca os pontos do elemento do modo atual
    direito           edita o objeto que estiver sob o cursor
    scroll            zoom no ponto onde o cursor esta
    espaco + arrastar move a vista (pan); o botao do meio faz o mesmo

A posicao do cursor aparece o tempo todo: mira, coordenada ja encaixada
na grade e destaque do objeto sob a mira, sem precisar clicar.

Modos (clique em 2 pontos, menos o ponto de medicao que e 1 clique):
    w   parede inteira
    m   meia parede / parede com vao
    j   janela
    d   porta
    f   movel / eletrodomestico  (2 cantos opostos do retangulo)
    p   ponto de medicao         (1 clique)

Outras teclas:
    1-9 escolher o material (ou o tipo de movel) do modo atual
    u   desfazer (inclui edicoes e exclusoes feitas no painel)
    esc cancelar os cliques pendentes do elemento em construcao
    g   ligar/desligar o snap (encaixe na grade)
    [ ] diminuir / aumentar o passo da grade (0.05 ... 1.0 m)
    0   enquadrar a vista em tudo que ja foi desenhado
    s   salvar o estado atual em JSON
    q   salvar e fechar

Nada e perguntado no terminal: o material/tipo do proximo elemento e
sempre o que estiver marcado no painel a direita da janela, e cada modo
lembra a sua propria escolha. Troque com as teclas 1-9 antes de clicar.

Clicando com o botao direito sobre uma parede, um movel ou um ponto, o
painel da direita vira um formulario com os atributos daquele objeto
(tipo, material, espessura, coordenadas). "aplicar" confirma, "excluir"
apaga e "u" desfaz.

No alto da coluna da direita, fora do plano, as caixas largura/altura
definem em metros a area visivel do grafico; elas acompanham o pan e o
zoom, e "enquadrar" volta para uma vista que cobre a planta inteira.

Snap (ligado por padrao, passo de 0.25 m): cada clique e encaixado no
ponto da grade mais proximo, ou em um vertice ja existente (ponta de
parede, canto de movel, ponto de medicao) quando houver um por perto.
Assim paredes vizinhas fecham exatamente no mesmo canto, sem sobrar
decimos de diferenca por causa da mira do mouse.
"""

# Modos de segmento (2 cliques) e as suas teclas.
TECLAS_MODO = {
    "w": "parede",
    "m": "meia_parede",
    "j": "janela",
    "d": "porta",
    "f": "movel",
    "p": "ponto",
}
MODOS_SEGMENTO = ("parede", "meia_parede", "janela", "porta")

# Paleta de cada modo: o que as teclas 1-9 escolhem.
PALETAS = {
    "parede":      ("material", ["concreto", "tijolo", "drywall", "madeira"]),
    "meia_parede": ("material", ["concreto", "tijolo", "drywall", "madeira"]),
    "janela":      ("material", ["vidro", "vidro duplo", "madeira", "metal"]),
    "porta":       ("material", ["madeira", "vidro", "metal"]),
    "movel":       ("tipo", ["geladeira", "fogao", "micro-ondas", "tv",
                             "sofa", "armario", "mesa", "cama", "outro"]),
}

# Espessura assumida por material, para nao precisar digitar nada.
ESPESSURA_MATERIAL = {
    "concreto": 0.15,
    "tijolo": 0.15,
    "drywall": 0.10,
    "madeira": 0.05,
    "vidro": 0.01,
    "vidro duplo": 0.03,
    "metal": 0.03,
}
ESPESSURA_PADRAO = 0.10

# Material assumido para cada tipo de movel.
MATERIAL_MOVEL = {
    "geladeira": "metal",
    "fogao": "metal",
    "micro-ondas": "metal",
    "tv": "vidro",
    "sofa": "madeira",
    "armario": "madeira",
    "mesa": "madeira",
    "cama": "madeira",
    "outro": "madeira",
}
# Materiais que o painel de edicao oferece para um movel.
MATERIAIS_MOVEL = ["madeira", "metal", "vidro"]

# Como cada tipo de segmento e desenhado.
ESTILO_SEGMENTO = {
    "parede":      {"cor": "black",      "linestyle": "-",           "rotulo": "parede"},
    "meia_parede": {"cor": "dimgray",    "linestyle": (0, (6, 4)),   "rotulo": "meia parede / vao"},
    "janela":      {"cor": "tab:cyan",   "linestyle": "-",           "rotulo": "janela"},
    "porta":       {"cor": "tab:orange", "linestyle": "-",           "rotulo": "porta"},
}

CORES_MATERIAL = {
    "metal": "tab:red",
    "vidro": "tab:cyan",
}
COR_PADRAO = "tab:brown"

PASSOS_GRADE = [0.05, 0.10, 0.20, 0.25, 0.50, 1.00]

# Navegacao.
ZOOM_FATOR = 1.15
EXTENSAO_MIN = 0.5     # menor largura/altura visivel, em metros
EXTENSAO_MAX = 500.0   # maior largura/altura visivel, em metros
TOLERANCIA_PX = 10     # raio de "acerto" do cursor sobre um objeto, em pixels
MAX_HISTORICO = 100
