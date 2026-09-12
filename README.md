# Wifi Heatmap — Editor de Planta Baixa

Ferramenta para desenhar a planta baixa de um ambiente (paredes, janelas,
portas, móveis/eletrodomésticos e pontos de medição de sinal) diretamente
com o mouse, salvando tudo em um arquivo JSON. Esse JSON é a base para a
etapa seguinte do projeto: gerar o mapa de calor (heatmap) de sinal Wi-Fi
por interpolação dos pontos medidos.

## Instalação

Requisitos: Python 3.10 (recomendado 3.10.9 — veja a nota sobre a versão
do matplotlib abaixo).

```bash
# clonar o repositório
git clone <url-do-repositorio>
cd Wifi_heatmap

# (opcional, recomendado) criar um ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# instalar as dependências
pip install -r requirements.txt
```

> **Nota:** a versão do `matplotlib` está fixada em `3.10.9` porque as
> versões `3.11.0`/`3.11.1` têm um bug conhecido que quebra as caixas de
> texto do editor ao redimensionar a janela. Atualize apenas quando uma
> versão `3.11.2+` estiver disponível.

## Como usar

O ponto de entrada é o script `planta_editor.py`:

```bash
python planta_editor.py --largura 8 --altura 6 --saida planta_casa.json
```

Isso abre uma janela com um plano cartesiano (1 unidade = 1 metro) onde
você desenha os elementos do ambiente com o mouse. Ao fechar (tecla `q`)
ou salvar (tecla `s`), o estado é gravado no arquivo JSON indicado em
`--saida`.

### Argumentos

| Argumento    | Padrão         | Descrição                                              |
|--------------|----------------|---------------------------------------------------------|
| `--largura`  | `10.0`         | Largura do ambiente em metros (eixo x)                  |
| `--altura`   | `8.0`          | Altura do ambiente em metros (eixo y)                   |
| `--saida`    | `planta.json`  | Arquivo JSON de saída                                    |
| `--entrada`  | `None`         | Arquivo JSON existente para continuar editando           |
| `--passo`    | `0.25`         | Passo da grade de encaixe (snap), em metros              |

Exemplos:

```bash
# grade de 0.5 m em vez do padrão de 0.25 m
python planta_editor.py --passo 0.5

# continuar editando uma planta já existente, sobrescrevendo o mesmo arquivo
python planta_editor.py --entrada planta_casa.json --saida planta_casa.json
```

O texto de uso completo também é impresso no terminal toda vez que o
editor é aberto.

## Funcionalidades

### Mouse

| Ação                          | Efeito                                              |
|--------------------------------|------------------------------------------------------|
| Botão esquerdo                 | Marca os pontos do elemento do modo atual             |
| Botão direito                  | Edita o objeto que estiver sob o cursor               |
| Scroll                         | Zoom no ponto onde o cursor está                      |
| Espaço + arrastar (ou botão do meio) | Move a vista (pan)                              |

A posição do cursor é exibida em tempo real: mira, coordenada já
encaixada na grade e destaque do objeto sob a mira — sem precisar clicar.

### Modos de desenho

Cada modo é ativado por uma tecla. Os modos de segmento pedem 2 cliques
(início e fim); o ponto de medição pede apenas 1 clique.

| Tecla | Modo                          |
|-------|-------------------------------|
| `w`   | Parede inteira                |
| `m`   | Meia parede / parede com vão  |
| `j`   | Janela                        |
| `d`   | Porta                         |
| `f`   | Móvel / eletrodoméstico (2 cantos opostos do retângulo) |
| `p`   | Ponto de medição (1 clique)   |

### Outras teclas

| Tecla   | Ação                                                       |
|---------|-------------------------------------------------------------|
| `1`-`9` | Escolher o material (ou o tipo de móvel) do modo atual       |
| `u`     | Desfazer (inclui edições e exclusões feitas no painel)       |
| `Esc`   | Cancelar os cliques pendentes do elemento em construção      |
| `g`     | Ligar/desligar o snap (encaixe na grade)                     |
| `[` `]` | Diminuir / aumentar o passo da grade (0.05 a 1.0 m)          |
| `0`     | Enquadrar a vista em tudo que já foi desenhado                |
| `s`     | Salvar o estado atual em JSON                                 |
| `q`     | Salvar e fechar                                                |

Nada é perguntado no terminal: o material/tipo do próximo elemento é
sempre o que estiver marcado no painel à direita da janela, e cada modo
lembra a sua própria escolha — troque com as teclas `1`-`9` antes de
clicar.

### Edição de objetos

Clicando com o botão direito sobre uma parede, um móvel ou um ponto, o
painel da direita vira um formulário com os atributos daquele objeto
(tipo, material, espessura, coordenadas):

- **aplicar** confirma as alterações;
- **excluir** apaga o objeto;
- `u` desfaz a última ação.

### Painel de visualização

No alto da coluna da direita, fora do plano, as caixas largura/altura
definem em metros a área visível do gráfico. Elas acompanham o pan e o
zoom, e a tecla `0` (ou botão "enquadrar") volta para uma vista que cobre
a planta inteira.

### Snap (encaixe na grade)

Ligado por padrão, com passo de 0.25 m. Cada clique é encaixado no ponto
da grade mais próximo, ou em um vértice já existente (ponta de parede,
canto de móvel, ponto de medição) quando houver um por perto. Isso faz
com que paredes vizinhas fechem exatamente no mesmo canto, sem sobrar
décimos de diferença por causa da mira do mouse.

## Estrutura do projeto

```
Wifi_heatmap/
├── planta_editor.py       # ponto de entrada de linha de comando
├── requirements.txt
├── planta_*.json          # plantas já desenhadas (saída do editor)
└── editor/                # implementação do editor
    ├── cli.py             # parsing de argumentos
    ├── core.py            # classe principal PlantaEditor
    ├── constants.py       # paletas, teclas, estilos e texto de ajuda
    ├── elements.py        # criação/edição dos elementos da planta
    ├── rendering.py       # desenho do plano e do HUD
    ├── hit_testing.py     # detecção do objeto sob o cursor
    ├── navigation.py      # zoom e pan
    ├── events.py          # tratamento de eventos de mouse/teclado
    ├── edit_panel.py      # formulário de edição no painel lateral
    └── widgets.py         # widgets do painel (caixas de texto, botões)
```
