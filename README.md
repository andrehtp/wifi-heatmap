# Wifi Heatmap — Editor de Planta Baixa

Ferramenta para desenhar a planta baixa de um ambiente (paredes como
polígonos com espessura real, janelas, portas, vãos, móveis e pontos de
medição de sinal ou access points) diretamente com o mouse, salvando tudo
em um arquivo JSON. O editor também distribui pontos de medição
automaticamente. Esse JSON é a base do mapa de calor (heatmap) de sinal
Wi-Fi (`heatmap_gerador.py`), que liga cada ponto de medição às leituras
em dBm de uma tabela CSV pelo `id` do ponto. O JSON guarda só o `id` e a
posição dos pontos; as leituras ficam no CSV.

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
> versão `3.11.2+` estiver disponível. A outra dependência é o
> `shapely`, usado na geometria das paredes em polígono.

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
| `--gerar-tabela` | `None`     | Só gera a tabela CSV em branco dos pontos de medição da `--entrada` e sai (ver [Gerar a tabela de medição](#gerar-a-tabela-de-medição)) |
| `--leituras` | `3`            | Quantidade de colunas de leitura da tabela               |
| `--forcar`   | —              | Sobrescreve a tabela CSV se ela já existir               |

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
| Arrastar (com um objeto em edição) | Move o objeto; sobre um vértice da parede, move só o vértice |
| Scroll                         | Zoom no ponto onde o cursor está                      |
| Espaço + arrastar (ou botão do meio) | Move a vista (pan)                              |

A posição do cursor é exibida em tempo real: mira, coordenada já
encaixada, distância até o último clique, objeto sob a mira e, dentro de
um cômodo, a área e as medidas dele. Não é preciso clicar.

### Modos de desenho

| Tecla | Modo | Como desenhar |
|-------|------|---------------|
| `w`   | Parede | Polilinha: um clique por vértice. `Enter` (ou clicar de novo no último vértice) conclui; clicar no 1º vértice fecha o contorno |
| `m`   | Meia parede | Igual à parede |
| `y`   | Parede por contorno | Clique nos cantos reais do polígono da parede; `Enter` ou o 1º vértice fecha |
| `j`   | Janela | 2 cliques; sobre uma parede, recorta aquele trecho dela |
| `d`   | Porta | 2 cliques; idem (porta de vidro = material `vidro`) |
| `o`   | Vão livre | 2 cliques; passagem sem porta, idem |
| `f`   | Móvel | 2 cantos opostos do retângulo |
| `p`   | Ponto de medição ou access point | 1 clique (`1`/`2` escolhe o tipo) |
| `a`   | Distribuir pontos | Clique dentro de um cômodo (só ele) ou `Enter` (planta toda) |

#### Paredes em polígono

O material padrão é **alvenaria** (0,15 m). A caixa **espessura** do
painel acompanha o material escolhido e pode ser sobrescrita. O
**alinhamento** (tecla `l` ou botão do painel) define de que lado da linha
clicada fica a espessura: `centro`, `esquerda` ou `direita`, em relação ao
sentido do desenho. Por exemplo, para desenhar clicando nas faces internas
de um cômodo, use o lado de fora. As pontas livres terminam exatamente
onde foram clicadas; uma ponta que encosta em outra parede é prolongada
para fechar o canto. Antes de concluir, a parede aparece em pré-visualização
já com a espessura.

#### Janelas, portas e vãos

Continuam sendo segmentos, mas ao cair sobre uma parede removem aquele
trecho, e a parede se divide em novos polígonos. Só são recortadas as
paredes que acompanham o segmento: uma parede perpendicular que apenas
encosta na ponta da porta fica intacta. Ao excluir ou mover a abertura,
a parede volta ao lugar antigo (e é recortada no novo). Se a abertura for
desenhada antes da parede, a parede já nasce recortada.

#### Móveis

Tipos fixos: armário, mesa, cama, equipamento elétrico, guarda-roupa e
balcão, cada um com o seu material predominante. O tipo **personalizado**
usa o nome digitado na caixa **nome** do painel e o material escolhido no
botão ao lado (madeira, metal, vidro, pedra, alvenaria, plástico, tecido).

#### Distribuidor automático de pontos de medição

Escolha o método com `1`-`7` e ajuste o **valor** e a **margem** (distância
mínima até as paredes, 0,30 m por padrão) no painel. Móveis são sempre
evitados.

| # | Método | Valor | Como distribui |
|---|--------|-------|----------------|
| 1 | Grade quadrada | pontos/m² | Grade regular centrada em cada cômodo |
| 2 | Grade hexagonal | pontos/m² | Cobre melhor que a quadrada, com a mesma densidade |
| 3 | Quantidade total | N | Exatamente N pontos espalhados por igual (k-means) |
| 4 | N por cômodo | N | N pontos em cada cômodo, qualquer que seja o tamanho |
| 5 | Junto às paredes | espaçamento (m) | Pontos ao longo das paredes + miolo com o dobro do espaçamento |
| 6 | Foco no AP | N | Mais denso perto dos access points, onde o sinal varia mais rápido |
| 7 | Aleatório (Poisson) | distância mínima (m) | Aleatório, sem padrão de grade |

Distribuir **substitui** os pontos de medição da área (os access points
ficam) e **renumera** todos os pontos de medição de 1 a N em ordem de
caminhada: cômodo a cômodo, a partir do access point. Os ids 1, 2, 3...
ficam fisicamente vizinhos, o que facilita a coleta. Os cômodos são as
áreas fechadas por paredes e aberturas. Como os ids mudam, uma tabela
CSV feita antes da redistribuição deixa de bater com a planta.

### Outras teclas

| Tecla   | Ação                                                       |
|---------|-------------------------------------------------------------|
| `1`-`9` | Escolher o material, o tipo de móvel, o tipo de ponto ou o método de distribuição do modo atual |
| `Enter` | Concluir a parede em construção / distribuir na planta toda |
| `l`     | Alternar o alinhamento da parede (centro, esquerda, direita) |
| `h`     | Mostrar/esconder as guias (paredes antigas em linha)         |
| `u`     | Desfazer (inclui edições, arrastes e exclusões)               |
| `Esc`   | Cancelar os cliques pendentes do elemento em construção      |
| `g`     | Ligar/desligar o snap (encaixe na grade)                     |
| `[` `]` | Diminuir / aumentar o passo da grade (0.05 a 1.0 m)          |
| `0`     | Enquadrar a vista em tudo que já foi desenhado                |
| `t`     | Salvar e gerar a tabela CSV em branco dos pontos de medição   |
| `s`     | Salvar o estado atual em JSON                                 |
| `q`     | Salvar e fechar                                                |

Nada é perguntado no terminal: o material/tipo do próximo elemento é
sempre o que estiver marcado no painel à direita da janela, e cada modo
lembra a sua própria escolha. Troque com as teclas `1`-`9` antes de
clicar.

### Edição de objetos

Clicando com o botão direito sobre uma parede, abertura, guia, móvel ou
ponto, o painel da direita vira um formulário com os atributos daquele
objeto: tipo, material, coordenadas, nome do móvel e, na parede, `dx`/`dy`
para movê-la com precisão. Com o formulário aberto, arrastar o objeto
com o botão esquerdo o move.

- **aplicar** confirma as alterações;
- **excluir** apaga o objeto (excluir uma abertura devolve a parede);
- `u` desfaz a última ação.

### Plantas antigas (paredes em linha)

Ao abrir uma planta do formato antigo, as paredes em linha viram **guias**
cinzas tracejadas, que servem só de referência para redesenhar as paredes
como polígonos por cima (o snap encaixa nas pontas e ao longo delas). As
janelas e portas antigas viram aberturas, e as paredes desenhadas por cima
delas já nascem recortadas. As `leituras_dbm` dos pontos são removidas
(agora ficam no CSV). Os móveis antigos são convertidos: geladeira,
fogão, micro-ondas e TV viram equipamento elétrico; sofá e outro viram
personalizado, com o tipo antigo como nome. Ao salvar por cima do arquivo
antigo, uma cópia do original é guardada como `<nome>.antigo.json`.

### Painel de visualização

No alto da coluna da direita, fora do plano, as caixas largura/altura
definem em metros a área visível do gráfico. Elas acompanham o pan e o
zoom, e a tecla `0` (ou botão "enquadrar") volta para uma vista que cobre
a planta inteira.

### Snap (encaixe)

Ligado por padrão, com passo de 0.25 m. Cada clique é encaixado, nesta
ordem de prioridade: num vértice já existente (canto de parede, ponta de
guia ou abertura, canto de móvel, ponto); numa aresta de parede ou guia
(de preferência num ponto que também esteja na grade), o que facilita
colocar portas exatamente sobre a parede; ou no ponto de grade mais
próximo.

## Gerar a tabela de medição

Com os pontos de medição posicionados, o editor gera a tabela CSV em
branco para anotar as leituras em campo: uma linha por ponto de medição
(access points ficam de fora), em ordem de id, com a coluna `id` e três
colunas de leitura vazias (`leitura_1`, `leitura_2`, `leitura_3`).

Pelo terminal, sem abrir a janela:

```bash
python planta_editor.py --entrada planta_casa.json --gerar-tabela medicao.csv

# outra quantidade de colunas de leitura
python planta_editor.py --entrada planta_casa.json --gerar-tabela medicao.csv --leituras 5
```

Se o CSV já existir (ele pode ter leituras preenchidas), o comando
recusa; use `--forcar` para sobrescrever.

Dentro do editor, a tecla `t` (ou o botão "gerar tabela" do painel no
modo ponto, `p`) salva a planta e gera a tabela no caminho da caixa `csv`
do painel — por padrão `<saída>_medicao.csv`, ao lado do JSON. Se o
arquivo já existir, o primeiro `t` só avisa; um segundo `t` seguido
sobrescreve.

Redistribuir os pontos (`a`) renumera os ids, então gere a tabela depois
de fechar a posição dos pontos.

## Gerar o mapa de calor

Depois de medir o sinal em campo, preencha a tabela CSV (a gerada acima,
ou uma feita à mão) com uma coluna `id` (o id do ponto, igual ao mostrado
no editor) e uma ou mais colunas de leitura, com qualquer nome
(`leitura_1`, `leitura_2`, ...). Células vazias são ignoradas. Abra o
visualizador com a planta e a tabela:

```bash
python heatmap_gerador.py --entrada planta_casa.json --tabela medicao.csv

# outra forma de combinar as leituras de cada ponto
python heatmap_gerador.py --entrada planta_casa.json --tabela medicao.csv --agregacao mediana
```

Ids da tabela que não existem na planta, ou que são de access point,
geram um aviso e são ignorados. Os pontos de medição sem leitura também
são listados no aviso. Plantas antigas com `leituras_dbm` no próprio JSON
ainda abrem sem `--tabela`.

### Leituras de cada ponto (`--agregacao`)

- `potencia` (padrão): converte cada leitura para mW, tira a média e
  volta para dBm. dBm é escala logarítmica, e a média direta em dBm
  subestima o sinal quando as leituras variam: `[-50, -70]` dá −52,97 dBm
  em potência e −60 dBm em dBm.
- `dbm`: média aritmética direta em dBm.
- `mediana`: mediana das leituras (robusta a uma leitura ruim).

Pontos cujas leituras variam mais de 6 dB entre a menor e a maior geram
um aviso no terminal com o id e as leituras, para achar medições ruins.

### Métodos de interpolação

| Método | O que faz | Parâmetro (caixa do painel) |
|---|---|---|
| IDW | média ponderada pelo inverso da distância | potência p (padrão 3) |
| Gaussiana | média ponderada por kernel gaussiano | σ em metros (padrão 1) |
| Vizinho mais próximo | valor do ponto mais próximo (Voronoi) | — |
| Linear (Delaunay) | interpolação linear nos triângulos; fora deles, vizinho mais próximo | — |
| RBF thin-plate | spline de placa fina + plano, com suavização | suavização λ (padrão 0,01) |
| Kriging ordinário | variograma (exponencial/esférico) ajustado às medições | nugget relativo (padrão auto) |
| Path loss | modelo log-distância `P0 − 10·n·log10(d)` ajustado às medições | — |
| Multi-wall | log-distância menos a perda de cada parede atravessada | escala das perdas (padrão 1) |
| Híbrido | multi-wall + resíduos (medido − modelo) interpolados por kriging | escala das perdas (padrão 1) |

Os quatro últimos usam a planta. Path loss, multi-wall e híbrido medem a
distância até o access point e, com vários APs, usam o mais forte em
cada ponto. Sem nenhum AP, path loss e multi-wall caem para IDW e o
híbrido para kriging, com aviso no título. O multi-wall conta as paredes
que o segmento AP → ponto atravessa. Como as paredes já estão recortadas
pelas aberturas, passar por uma porta ou vão não conta parede. A perda
por material (valores típicos em 2,4 GHz, com a fonte no comentário),
a meia parede (metade da perda) e a janela (2 dB) ficam em
`heatmap/constants.py`. `P0` e `n` são sempre ajustados às medições, e
o título mostra os valores ajustados.

### Validação cruzada (LOOCV)

Para escolher o método, o visualizador faz uma validação cruzada
*leave-one-out*: tira um ponto, interpola com os demais, compara com o
valor medido e repete para todos. Ao abrir, ele imprime no terminal uma
tabela com RMSE, MAE e viés (em dB) de cada método, marcando o de menor
RMSE. O título do gráfico mostra o RMSE do método e do parâmetro ativos.

### Janela

A janela mostra a planta desenhada por baixo do mapa de calor, com o
valor agregado ao lado do id de cada ponto medido (ex.: `12: −54`). Na
coluna da direita é possível trocar:

- o **método de interpolação** e o seu **parâmetro** (caixa de texto logo
  abaixo; enter aplica, e um valor inválido mantém o anterior com aviso
  no título);
- o **estilo visual**: campo contínuo, bandas ou blobs por ponto;
- a **área do mapa**: só dentro do imóvel (recortada pelo contorno
  real das paredes) ou expandida. Se as paredes não fecham o contorno,
  o recorte usa o fecho convexo das paredes e dos pontos, com aviso no título;
- a **escala de cor**: fixa (−90 a −30 dBm, igual para todos os métodos e
  estilos, então trocar de método não muda as cores sem o sinal mudar)
  ou automática (mínimo/máximo das leituras medidas).

As bandas usam limites fixos nos limiares de qualidade Wi-Fi (−30, −50,
−60, −67, −70, −80, −90 dBm), e a barra de cores marca esses valores.
A grade de interpolação tem células quadradas de 5 cm, com um teto de
células para plantas grandes.

Os botões "Exportar PNG"/"Exportar SVG" salvam o resultado (o nome do
arquivo pode ser editado na caixa de texto acima deles). Pontos de
medição sem leitura aparecem como marcador vazio. Access points nunca
entram como dado do heatmap: são desenhados como referência e servem de
origem para os modelos de propagação.

## Estrutura do projeto

```
Wifi_heatmap/
├── planta_editor.py       # ponto de entrada do editor de planta
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
│   ├── widgets.py         # widgets do painel (caixas de texto, botões)
│   ├── poligonos.py       # geometria das paredes (shapely): recorte, cômodos
│   ├── tabela.py          # tabela CSV em branco dos pontos de medição
│   └── distribuicao.py    # métodos de distribuição automática de pontos
└── heatmap/                # implementação do visualizador de heatmap
    ├── cli.py               # parsing de argumentos
    ├── core.py              # classe principal HeatmapViewer
    ├── io.py                # leitura da planta JSON
    ├── tabela.py            # leitura do CSV de medições e associação por id
    ├── mascara.py           # recorte do mapa ao interior do imóvel
    ├── interpolation.py     # agregação das leituras, grade e os 9 métodos (registro)
    ├── krigagem.py          # variograma e kriging ordinário
    ├── propagacao.py        # log-distância e multi-wall (paredes cruzadas)
    ├── validacao.py         # validação cruzada leave-one-out
    ├── rendering.py         # desenho da planta, escala de cor e estilos visuais
    ├── widgets.py           # seletores, caixa de parâmetro e botões de exportação
    └── constants.py         # estilos, escala dBm, atenuações e parâmetros padrão
```
