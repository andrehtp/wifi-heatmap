# Wifi Heatmap — Editor de Planta Baixa

Ferramenta para desenhar a planta baixa de um ambiente (paredes, janelas,
portas, móveis/eletrodomésticos e pontos de medição de sinal ou access
points) diretamente com o mouse, salvando tudo em um arquivo JSON. Esse
JSON é a base para as etapas seguintes do projeto: importar as leituras de
sinal medidas em campo (`importar_medicoes.py`) e gerar o mapa de calor
(heatmap) de sinal Wi-Fi por interpolação dos pontos medidos
(`heatmap_gerador.py`). Cada ponto de medição já é salvo com um campo
`leituras_dbm` vazio, que o importador preenche com até 5 leituras de
potência do sinal em dBm.

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
(início e fim); o ponto pede apenas 1 clique.

| Tecla | Modo                          |
|-------|-------------------------------|
| `w`   | Parede inteira                |
| `m`   | Meia parede / parede com vão  |
| `j`   | Janela                        |
| `d`   | Porta                         |
| `f`   | Móvel / eletrodoméstico (2 cantos opostos do retângulo) |
| `p`   | Ponto de medição ou access point (1 clique; `1`/`2` escolhe o tipo) |

### Outras teclas

| Tecla   | Ação                                                       |
|---------|-------------------------------------------------------------|
| `1`-`9` | Escolher o material, o tipo de móvel ou o tipo de ponto (medição/access point) do modo atual |
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

## Importar leituras de sinal (CSV → JSON)

Depois de medir o sinal em campo, importe os valores em dBm de uma tabela
CSV para os pontos de medição da planta com `importar_medicoes.py`. O CSV
deve ter uma coluna `id` (o id do ponto, igual ao mostrado no editor) e
uma ou mais colunas de leitura, com qualquer nome (`leitura1`,
`leitura2`, ...); células vazias são ignoradas e no máximo 5 leituras por
ponto são gravadas.

```bash
python importar_medicoes.py --planta planta_casa.json --tabela medicoes.csv

# gravar em um arquivo separado em vez de sobrescrever --planta
python importar_medicoes.py --planta planta_casa.json --tabela medicoes.csv --saida planta_casa_com_leituras.json
```

As leituras importadas **substituem** (não somam) as leituras já
existentes no ponto. Ids que não existem na planta, ou que pertencem a um
access point, são ignorados com um aviso — o comando nunca falha por
causa de uma linha inválida do CSV, só por um arquivo sem a coluna `id`.

## Gerar o mapa de calor

Com a planta já com leituras (`leituras_dbm` preenchido em pelo menos um
ponto de medição), abra o visualizador interativo com
`heatmap_gerador.py`:

```bash
python heatmap_gerador.py --entrada planta_casa.json
```

A janela mostra a planta desenhada por baixo do mapa de calor. Na coluna
da direita é possível trocar:

- o **método de interpolação** — IDW, gaussiana ou vizinho mais próximo;
- o **estilo visual** — campo contínuo, bandas/contornos ou blobs por
  ponto;

e exportar o resultado em PNG ou SVG pelos botões "Exportar PNG"/"Exportar
SVG" (o nome do arquivo pode ser editado na caixa de texto acima deles).
Pontos de medição sem leitura ainda aparecem como marcador vazio; access
points nunca entram no cálculo do heatmap, só são desenhados como
referência.

## Estrutura do projeto

```
Wifi_heatmap/
├── planta_editor.py       # ponto de entrada do editor de planta
├── importar_medicoes.py   # ponto de entrada do importador de medições CSV
├── heatmap_gerador.py     # ponto de entrada do visualizador de heatmap
├── requirements.txt
├── planta_*.json          # plantas já desenhadas (saída do editor)
├── editor/                # implementação do editor
│   ├── cli.py             # parsing de argumentos
│   ├── core.py            # classe principal PlantaEditor
│   ├── constants.py       # paletas, teclas, estilos e texto de ajuda
│   ├── elements.py        # criação/edição dos elementos da planta
│   ├── rendering.py       # desenho do plano e do HUD
│   ├── hit_testing.py     # detecção do objeto sob o cursor
│   ├── navigation.py      # zoom e pan
│   ├── events.py          # tratamento de eventos de mouse/teclado
│   ├── edit_panel.py      # formulário de edição no painel lateral
│   └── widgets.py         # widgets do painel (caixas de texto, botões)
├── medicoes/               # implementação do importador de medições
│   ├── cli.py              # parsing de argumentos
│   └── core.py             # leitura do CSV e gravação em leituras_dbm
└── heatmap/                # implementação do visualizador de heatmap
    ├── cli.py               # parsing de argumentos
    ├── core.py              # classe principal HeatmapViewer
    ├── io.py                # leitura da planta JSON
    ├── interpolation.py     # métodos de interpolação (IDW, gaussiana, vizinho)
    ├── rendering.py         # desenho da planta e dos estilos visuais do heatmap
    ├── widgets.py            # seletores de método/estilo e botões de exportação
    └── constants.py          # estilos, colormap e texto de ajuda
```
