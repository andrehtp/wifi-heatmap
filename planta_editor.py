"""
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

Modos (clique em 2 pontos, menos o ponto de medicao que e 1 clique):
    w   parede inteira
    m   meia parede / parede com vao
    j   janela
    d   porta
    f   movel / eletrodomestico  (2 cantos opostos do retangulo)
    p   ponto de medicao         (1 clique)

Outras teclas:
    1-9 escolher o material (ou o tipo de movel) do modo atual
    u   desfazer o ultimo clique pendente ou o ultimo elemento adicionado
    esc cancelar os cliques pendentes do elemento em construcao
    g   ligar/desligar o snap (encaixe na grade)
    [ ] diminuir / aumentar o passo da grade (0.05 ... 1.0 m)
    s   salvar o estado atual em JSON
    q   salvar e fechar

Nada e perguntado no terminal: o material/tipo do proximo elemento e
sempre o que estiver marcado no painel a direita da janela, e cada modo
lembra a sua propria escolha. Troque com as teclas 1-9 antes de clicar.

Os cliques ja dados em um elemento ainda incompleto ficam marcados em
laranja no grafico, servindo de referencia ate o elemento ser fechado.

Snap (ligado por padrao, passo de 0.25 m): cada clique e encaixado no
ponto da grade mais proximo, ou em um vertice ja existente (ponta de
parede, canto de movel, ponto de medicao) quando houver um por perto.
Assim paredes vizinhas fecham exatamente no mesmo canto, sem sobrar
decimos de diferenca por causa da mira do mouse.
"""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.ticker import MultipleLocator

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

# Os atalhos padrao do matplotlib (pan, fullscreen, salvar figura, grade...)
# usam as mesmas teclas do editor; sem isso, "p" ligaria o pan e o clique
# arrastaria o grafico em vez de marcar um ponto.
for _keymap in ("keymap.fullscreen", "keymap.pan", "keymap.save",
                "keymap.quit", "keymap.grid", "keymap.grid_minor",
                "keymap.zoom", "keymap.home", "keymap.back", "keymap.forward"):
    plt.rcParams[_keymap] = []


class PlantaEditor:
    def __init__(self, largura, altura, output_path, input_path=None,
                 passo=0.25):
        self.output_path = Path(output_path)
        self.paredes = []
        self.moveis = []
        self.pontos_medicao = []
        self._next_ponto_id = 1
        self._historico = []  # pilha de categorias, para o undo

        self.modo = None
        self._cliques_pendentes = []
        self.passo = passo
        self.snap = True
        # cada modo lembra a sua propria escolha de material / tipo
        self._selecao = {modo: 0 for modo in PALETAS}

        self.fig, self.ax = plt.subplots(figsize=(11, 7))
        self.fig.subplots_adjust(left=0.08, right=0.68, top=0.93, bottom=0.09)
        # margem para as paredes coladas em x=0 / y=0 nao serem cortadas
        self._xlim0, self._ylim0 = (-0.3, largura + 0.3), (-0.3, altura + 0.3)

        if input_path:
            self._carregar(input_path)

        self._configurar_eixos()
        self._painel = self.fig.text(
            0.70, 0.93, "", fontsize=9, family="monospace", va="top",
        )
        self._redesenhar()

        self.fig.canvas.mpl_connect("button_press_event", self._on_click)
        self.fig.canvas.mpl_connect("key_press_event", self._on_key)
        print(__doc__)

    # ------------------------------------------------------------------ #
    # Selecao de material / tipo (substitui os prompts do terminal)
    # ------------------------------------------------------------------ #
    def _paleta(self):
        """(rotulo, opcoes) da paleta do modo atual, ou None."""
        return PALETAS.get(self.modo)

    def _opcao_atual(self, modo=None):
        modo = modo or self.modo
        paleta = PALETAS.get(modo)
        if paleta is None:
            return None
        return paleta[1][self._selecao[modo]]

    def _selecionar_opcao(self, indice):
        paleta = self._paleta()
        if paleta is None or not (0 <= indice < len(paleta[1])):
            return
        self._selecao[self.modo] = indice
        print(f"{paleta[0]} do modo {self.modo}: {paleta[1][indice]}")
        self._atualizar_painel()

    # ------------------------------------------------------------------ #
    # Configuracao / desenho
    # ------------------------------------------------------------------ #
    def _configurar_eixos(self):
        self.ax.set_xlim(*self._xlim0)
        self.ax.set_ylim(*self._ylim0)
        self.ax.set_aspect("equal")
        self._configurar_grade()
        self.ax.set_xlabel("x (m)")
        self.ax.set_ylabel("y (m)")

    def _configurar_grade(self):
        """Grade maior de 1 m e grade menor no passo do snap."""
        self.ax.xaxis.set_major_locator(MultipleLocator(1.0))
        self.ax.yaxis.set_major_locator(MultipleLocator(1.0))
        self.ax.xaxis.set_minor_locator(MultipleLocator(self.passo))
        self.ax.yaxis.set_minor_locator(MultipleLocator(self.passo))
        self.ax.grid(True, which="major", linestyle="--",
                     linewidth=0.6, alpha=0.6)
        self.ax.grid(True, which="minor", linestyle=":",
                     linewidth=0.4, alpha=0.3)

    def _vertices_existentes(self):
        """Todos os pontos ja definidos, para o clique se encaixar neles."""
        for p in self.paredes:
            yield (p["x1"], p["y1"])
            yield (p["x2"], p["y2"])
        for m in self.moveis:
            x0, y0 = m["x"], m["y"]
            x1, y1 = x0 + m["largura"], y0 + m["profundidade"]
            yield (x0, y0)
            yield (x1, y0)
            yield (x1, y1)
            yield (x0, y1)
        for pt in self.pontos_medicao:
            yield (pt["x"], pt["y"])
        yield from self._cliques_pendentes

    def _encaixar(self, x, y):
        """Encaixa o clique em um vertice proximo ou no ponto de grade."""
        if not self.snap:
            return round(x, 2), round(y, 2)

        tolerancia = self.passo / 2
        melhor, menor_d2 = None, tolerancia ** 2
        for vx, vy in self._vertices_existentes():
            d2 = (vx - x) ** 2 + (vy - y) ** 2
            if d2 <= menor_d2:
                melhor, menor_d2 = (vx, vy), d2
        if melhor is not None:
            return melhor

        return (round(round(x / self.passo) * self.passo, 3),
                round(round(y / self.passo) * self.passo, 3))

    def _mudar_passo(self, direcao):
        atual = min(range(len(PASSOS_GRADE)),
                    key=lambda i: abs(PASSOS_GRADE[i] - self.passo))
        novo = min(max(atual + direcao, 0), len(PASSOS_GRADE) - 1)
        self.passo = PASSOS_GRADE[novo]
        print(f"Passo da grade: {self.passo} m")
        self._redesenhar()

    def _cliques_necessarios(self):
        if self.modo == "ponto":
            return 1
        if self.modo is None:
            return 0
        return 2

    def _atualizar_titulo(self):
        modo_txt = self.modo or "nenhum (pressione w / m / j / d / f / p)"
        opcao = self._opcao_atual()
        if opcao:
            modo_txt = f"{modo_txt} ({opcao})"
        pendente = ""
        if self._cliques_pendentes:
            pendente = (f"   |   clique {len(self._cliques_pendentes)}/"
                        f"{self._cliques_necessarios()} (u desfaz)")
        snap_txt = f"snap {self.passo:g} m" if self.snap else "snap off"
        self.ax.set_title(
            f"Modo atual: {modo_txt}   |   {snap_txt}   |   "
            f"paredes: {len(self.paredes)}  moveis: {len(self.moveis)}  "
            f"pontos: {len(self.pontos_medicao)}"
            f"{pendente}"
        )
        self.fig.canvas.draw_idle()

    def _atualizar_painel(self):
        """Painel lateral: modos, paleta atual e demais teclas."""
        linhas = ["MODOS"]
        for tecla, modo in TECLAS_MODO.items():
            marca = ">" if modo == self.modo else " "
            linhas.append(f" {marca} {tecla}  {modo.replace('_', ' ')}")

        paleta = self._paleta()
        if paleta is not None:
            rotulo, opcoes = paleta
            linhas += ["", f"{rotulo.upper()} (teclas 1-{len(opcoes)})"]
            for i, opcao in enumerate(opcoes, start=1):
                marca = ">" if i - 1 == self._selecao[self.modo] else " "
                linhas.append(f" {marca} {i}  {opcao}")
        else:
            linhas += ["", "(escolha um modo para ver",
                       " os materiais disponiveis)"]

        linhas += [
            "",
            "u    desfazer",
            "esc  cancelar cliques",
            f"g    snap: {'on' if self.snap else 'off'}",
            f"[ ]  passo: {self.passo:g} m",
            "s    salvar",
            "q    salvar e sair",
        ]
        self._painel.set_text("\n".join(linhas))
        self._atualizar_titulo()

    def _redesenhar(self):
        xlim, ylim = self.ax.get_xlim(), self.ax.get_ylim()
        self.ax.cla()
        self.ax.set_xlim(xlim if xlim != (0.0, 1.0) else self._xlim0)
        self.ax.set_ylim(ylim if ylim != (0.0, 1.0) else self._ylim0)
        self.ax.set_aspect("equal")
        self._configurar_grade()
        self.ax.set_xlabel("x (m)")
        self.ax.set_ylabel("y (m)")

        tipos_desenhados = set()
        for p in self.paredes:
            tipo = p.get("tipo", "parede")
            estilo = ESTILO_SEGMENTO.get(tipo, ESTILO_SEGMENTO["parede"])
            tipos_desenhados.add(tipo)
            xs, ys = [p["x1"], p["x2"]], [p["y1"], p["y2"]]

            if tipo in ("janela", "porta"):
                # a abertura "corta" a parede: apaga o trecho e desenha por cima
                largura = max(4.0, p["espessura"] * 20)
                self.ax.plot(xs, ys, color="white", linewidth=largura + 2.5,
                             solid_capstyle="butt", zorder=4)
                self.ax.plot(xs, ys, color=estilo["cor"], linewidth=largura,
                             solid_capstyle="butt", zorder=5)
                continue

            self.ax.plot(
                xs, ys,
                color=estilo["cor"], linestyle=estilo["linestyle"],
                linewidth=max(1.5, p["espessura"] * 20),
                solid_capstyle="butt", zorder=3,
            )

        for m in self.moveis:
            cor = CORES_MATERIAL.get(m["material"], COR_PADRAO)
            rect = Rectangle(
                (m["x"], m["y"]), m["largura"], m["profundidade"],
                facecolor=cor, alpha=0.4, edgecolor=cor,
            )
            self.ax.add_patch(rect)
            self.ax.text(
                m["x"] + m["largura"] / 2, m["y"] + m["profundidade"] / 2,
                m["tipo"], ha="center", va="center", fontsize=8,
            )

        for pt in self.pontos_medicao:
            self.ax.scatter([pt["x"]], [pt["y"]], color="tab:blue", zorder=7)
            self.ax.annotate(
                str(pt["id"]), (pt["x"], pt["y"]),
                textcoords="offset points", xytext=(5, 5),
                fontsize=8, color="tab:blue",
            )

        if tipos_desenhados:
            self.ax.legend(
                handles=[
                    Line2D([], [], color=ESTILO_SEGMENTO[t]["cor"],
                           linestyle=ESTILO_SEGMENTO[t]["linestyle"],
                           linewidth=2, label=ESTILO_SEGMENTO[t]["rotulo"])
                    for t in ESTILO_SEGMENTO if t in tipos_desenhados
                ],
                loc="upper right", fontsize=7, framealpha=0.8,
            )

        self._desenhar_cliques_pendentes()
        self._atualizar_painel()

    def _desenhar_cliques_pendentes(self):
        """Marca em laranja os cliques ja dados no elemento em construcao."""
        if not self._cliques_pendentes:
            return

        xs = [c[0] for c in self._cliques_pendentes]
        ys = [c[1] for c in self._cliques_pendentes]
        self.ax.scatter(
            xs, ys, marker="x", s=70, color="tab:orange",
            linewidths=2, zorder=6,
        )
        for i, (x, y) in enumerate(self._cliques_pendentes, start=1):
            self.ax.annotate(
                f"{i} ({x:.2f}, {y:.2f})", (x, y),
                textcoords="offset points", xytext=(6, -12),
                fontsize=7, color="tab:orange",
            )
        if len(xs) > 1:
            self.ax.plot(xs, ys, color="tab:orange", linewidth=1,
                         linestyle=":", zorder=6)

    # ------------------------------------------------------------------ #
    # Eventos de teclado / mouse
    # ------------------------------------------------------------------ #
    def _on_key(self, event):
        if event.key in TECLAS_MODO:
            self.modo = TECLAS_MODO[event.key]
            self._cliques_pendentes = []
            self._redesenhar()
        elif event.key and event.key in "123456789":
            self._selecionar_opcao(int(event.key) - 1)
        elif event.key == "escape":
            self._cancelar_pendentes()
        elif event.key == "u":
            self._desfazer()
        elif event.key == "g":
            self.snap = not self.snap
            print("Snap " + ("ligado" if self.snap else "desligado") + ".")
            self._redesenhar()
        elif event.key == "[":
            self._mudar_passo(-1)
        elif event.key == "]":
            self._mudar_passo(+1)
        elif event.key == "s":
            self._salvar()
        elif event.key == "q":
            self._salvar()
            plt.close(self.fig)

    def _on_click(self, event):
        if event.inaxes != self.ax or self.modo is None:
            return
        if event.xdata is None or event.ydata is None:
            return
        x, y = self._encaixar(event.xdata, event.ydata)

        self._cliques_pendentes.append((x, y))
        self._redesenhar()

        if len(self._cliques_pendentes) < self._cliques_necessarios():
            return

        cliques = self._cliques_pendentes
        self._cliques_pendentes = []

        if self.modo == "ponto":
            self._adicionar_ponto(*cliques[0])
        elif self.modo == "movel":
            (x1, y1), (x2, y2) = cliques
            self._adicionar_movel(x1, y1, x2, y2)
        else:
            (x1, y1), (x2, y2) = cliques
            self._adicionar_segmento(self.modo, x1, y1, x2, y2)

    # ------------------------------------------------------------------ #
    # Criacao dos elementos (atributos vem da selecao atual, sem prompt)
    # ------------------------------------------------------------------ #
    def _adicionar_segmento(self, tipo, x1, y1, x2, y2):
        material = self._opcao_atual(tipo)
        self.paredes.append({
            "tipo": tipo,
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "espessura": ESPESSURA_MATERIAL.get(material, ESPESSURA_PADRAO),
            "material": material,
        })
        self._historico.append("parede")
        print(f"+ {tipo} ({material}) de ({x1}, {y1}) a ({x2}, {y2})")
        self._redesenhar()

    def _adicionar_movel(self, x1, y1, x2, y2):
        tipo = self._opcao_atual("movel")
        material = MATERIAL_MOVEL.get(tipo, "madeira")
        largura, profundidade = abs(x2 - x1), abs(y2 - y1)
        x0, y0 = min(x1, x2), min(y1, y2)
        self.moveis.append({
            "tipo": tipo, "material": material,
            "x": x0, "y": y0, "largura": largura, "profundidade": profundidade,
        })
        self._historico.append("movel")
        print(f"+ movel {tipo} ({material}) em ({x0}, {y0}) "
              f"{largura} x {profundidade} m")
        self._redesenhar()

    def _adicionar_ponto(self, x, y):
        ponto_id = self._next_ponto_id
        self._next_ponto_id += 1
        self.pontos_medicao.append({"id": ponto_id, "x": x, "y": y})
        self._historico.append("ponto")
        print(f"+ ponto de medicao {ponto_id} em ({x}, {y})")
        self._redesenhar()

    # ------------------------------------------------------------------ #
    # Utilitarios
    # ------------------------------------------------------------------ #
    def _cancelar_pendentes(self):
        if not self._cliques_pendentes:
            return
        print(f"{len(self._cliques_pendentes)} clique(s) pendente(s) cancelado(s).")
        self._cliques_pendentes = []
        self._redesenhar()

    def _desfazer(self):
        if self._cliques_pendentes:
            x, y = self._cliques_pendentes.pop()
            print(f"Clique pendente removido: ({x}, {y}).")
            self._redesenhar()
            return
        if not self._historico:
            print("Nada para desfazer.")
            return
        categoria = self._historico.pop()
        if categoria == "parede":
            self.paredes.pop()
        elif categoria == "movel":
            self.moveis.pop()
        elif categoria == "ponto":
            self.pontos_medicao.pop()
        self._redesenhar()

    def _carregar(self, path):
        path = Path(path)
        if not path.exists():
            print(f"Aviso: {path} nao encontrado, comecando planta vazia.")
            return
        with open(path, "r", encoding="utf-8") as f:
            dados = json.load(f)
        self.paredes = dados.get("paredes", [])
        self.moveis = dados.get("moveis", [])
        self.pontos_medicao = dados.get("pontos_medicao", [])
        for p in self.paredes:  # plantas antigas nao tinham o campo "tipo"
            p.setdefault("tipo", "parede")
        if self.pontos_medicao:
            self._next_ponto_id = max(p["id"] for p in self.pontos_medicao) + 1
        print(f"Planta carregada de {path} "
              f"({len(self.paredes)} segmentos, {len(self.moveis)} moveis, "
              f"{len(self.pontos_medicao)} pontos).")

    def _salvar(self):
        dados = {
            "paredes": self.paredes,
            "moveis": self.moveis,
            "pontos_medicao": self.pontos_medicao,
        }
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        print(f"Planta salva em: {self.output_path.resolve()}")

    def run(self):
        plt.show()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Editor interativo de planta baixa para o projeto de mapa de calor wifi."
    )
    parser.add_argument("--largura", type=float, default=10.0,
                         help="Largura do ambiente em metros (eixo x)")
    parser.add_argument("--altura", type=float, default=8.0,
                         help="Altura do ambiente em metros (eixo y)")
    parser.add_argument("--saida", type=str, default="planta.json",
                         help="Arquivo JSON de saida")
    parser.add_argument("--entrada", type=str, default=None,
                         help="Arquivo JSON existente para continuar editando")
    parser.add_argument("--passo", type=float, default=0.25,
                         help="Passo da grade de encaixe (snap) em metros")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    editor = PlantaEditor(
        largura=args.largura, altura=args.altura,
        output_path=args.saida, input_path=args.entrada,
        passo=args.passo,
    )
    editor.run()
