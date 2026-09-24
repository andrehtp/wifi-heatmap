"""Criacao de elementos, desfazer e persistencia em JSON."""

import copy
import json
import shutil
from pathlib import Path

import numpy as np
from shapely import Point, Polygon, box
from shapely.ops import unary_union

from .constants import (
    MARGEM_MOVEL,
    MATERIAL_MOVEL,
    MAX_HISTORICO,
    MIGRACAO_MOVEL,
    MODOS_ABERTURA,
    PALETAS,
    ROTULO_MOVEL,
    TIPO_PAREDE,
)
from .distribuicao import MODOS_DISTRIBUICAO, ordenar_caminhada
from .poligonos import (
    comodos,
    corrigir,
    cortar,
    de_shapely,
    para_shapely,
    parede_de_polilinha,
    restaurar,
)
from .tabela import escrever_tabela


class ElementsMixin:
    # ------------------------------------------------------------------ #
    # Criacao dos elementos (atributos vem da selecao atual, sem prompt)
    # ------------------------------------------------------------------ #
    def _adicionar_parede(self, modo, cliques, fechada=False):
        material = self._opcao_atual(modo)
        tipo = TIPO_PAREDE[modo]
        if modo == "contorno":
            geom = corrigir(Polygon(cliques))
        else:
            geom = parede_de_polilinha(
                cliques, self.espessura, self.alinhamento, fechada,
                existentes=[para_shapely(p) for p in self.paredes])
        novas = de_shapely(geom, tipo, material)
        if not novas:
            print("Parede sem area (pontos repetidos ou alinhados); ignorada.")
            self._redesenhar()
            return

        self._snapshot()
        # a ordem de desenho nao importa: a parede nova ja nasce recortada
        # pelas aberturas que ela cruza
        for abertura in self.aberturas:
            novas, recorte = cortar(novas, abertura["x1"], abertura["y1"],
                                    abertura["x2"], abertura["y2"])
            abertura["recorte"] += recorte
        self.paredes += novas
        area = sum(para_shapely(p).area for p in novas)
        print(f"+ {tipo} ({material}) com {len(cliques)} vertices, "
              f"{area:.2f} m² em {len(novas)} poligono(s)")
        self._redesenhar()

    def _adicionar_abertura(self, tipo, x1, y1, x2, y2):
        material = self._opcao_atual(tipo)
        self._snapshot()
        self.paredes, recorte = cortar(self.paredes, x1, y1, x2, y2)
        self.aberturas.append({
            "tipo": tipo, "material": material,
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "recorte": recorte,
        })
        onde = (f"recortou {len(recorte)} trecho(s) de parede" if recorte
                else "nao esta sobre nenhuma parede")
        print(f"+ {tipo} ({material}) de ({x1}, {y1}) a ({x2}, {y2}): {onde}")
        self._redesenhar()

    def _reposicionar_abertura(self, abertura, novo):
        """Devolve a parede do lugar antigo e recorta no lugar novo."""
        self.paredes = restaurar(self.paredes, abertura.get("recorte", []))
        self.paredes, recorte = cortar(self.paredes, novo["x1"], novo["y1"],
                                       novo["x2"], novo["y2"])
        novo["recorte"] = recorte

    def _remover_abertura(self, indice):
        abertura = self.aberturas.pop(indice)
        self.paredes = restaurar(self.paredes, abertura.get("recorte", []))
        return abertura

    def _adicionar_movel(self, x1, y1, x2, y2):
        tipo = self._opcao_atual("movel")
        if tipo == "personalizado":
            nome, material = self._movel_nome, self._movel_material
        else:
            nome, material = ROTULO_MOVEL[tipo], MATERIAL_MOVEL[tipo]
        largura, profundidade = abs(x2 - x1), abs(y2 - y1)
        x0, y0 = min(x1, x2), min(y1, y2)
        self._snapshot()
        self.moveis.append({
            "tipo": tipo, "nome": nome, "material": material,
            "x": x0, "y": y0, "largura": largura, "profundidade": profundidade,
        })
        print(f"+ movel {nome} ({material}) em ({x0}, {y0}) "
              f"{largura} x {profundidade} m")
        self._redesenhar()

    def _adicionar_ponto(self, x, y):
        tipo = self._opcao_atual("ponto")
        self._snapshot()
        ponto_id = self._next_ponto_id
        self._next_ponto_id += 1
        self.pontos_medicao.append({"id": ponto_id, "x": x, "y": y, "tipo": tipo})
        rotulo = "access point" if tipo == "access_point" else "ponto de medicao"
        print(f"+ {rotulo} {ponto_id} em ({x}, {y})")
        self._redesenhar()

    # ------------------------------------------------------------------ #
    # Distribuidor automatico de pontos de medicao
    # ------------------------------------------------------------------ #
    def _comodos(self):
        """(comodos, fechado?) da planta atual, em cache ate o redesenho."""
        if "comodos" not in self._cache_geo:
            self._cache_geo["comodos"] = comodos(self.paredes, self.aberturas)
        return self._cache_geo["comodos"]

    def _distribuir(self, x=None, y=None):
        """Distribui pontos na planta toda, ou so no comodo sob (x, y)."""
        chave = self._opcao_atual("distribuir")
        rotulo, _rv, _padrao, funcao, inteiro = MODOS_DISTRIBUICAO[chave]
        valor = self._valor_distribuicao[chave]
        margem = self._margem_distribuicao

        salas, fechado = self._comodos()
        if not salas:
            print("Nenhuma area para distribuir: desenhe as paredes primeiro.")
            return
        if not fechado:
            print("Aviso: nenhum comodo fechado (paredes + portas/janelas); "
                  "usando a area envolvente das paredes.")
        if x is not None:
            alvo = [s for s in salas if s.buffer(1e-6).contains(Point(x, y))]
            if not alvo:
                print("Clique dentro de um comodo (ou enter para a planta toda).")
                return
        else:
            alvo = salas

        moveis = unary_union([
            box(m["x"], m["y"], m["x"] + m["largura"], m["y"] + m["profundidade"])
            for m in self.moveis]).buffer(MARGEM_MOVEL)
        regioes, crus = [], []
        for sala in alvo:
            regiao = sala.buffer(-margem, join_style="mitre").difference(moveis)
            if not regiao.is_empty:
                regioes.append(regiao)
                crus.append(sala)
        if not regioes:
            print(f"A margem de {margem:g} m nao deixa espaco livre no(s) comodo(s).")
            return

        aps = [(p["x"], p["y"]) for p in self.pontos_medicao
               if p.get("tipo") == "access_point"]
        ctx = {"rng": np.random.default_rng(0), "comodos": crus,
               "margem": margem, "aps": aps}
        novos = funcao(regioes, int(valor) if inteiro else valor, ctx)
        if not novos:
            print("Nenhum ponto gerado com esses parametros.")
            return

        self._snapshot()
        area_alvo = unary_union(alvo).buffer(1e-6)
        self.pontos_medicao = [
            p for p in self.pontos_medicao
            if p.get("tipo") == "access_point"
            or (x is not None
                and not area_alvo.contains(Point(p["x"], p["y"])))]
        for px, py in novos:
            self.pontos_medicao.append(
                {"id": 0, "x": round(float(px), 3), "y": round(float(py), 3),
                 "tipo": "medicao"})
        self._renumerar_caminhada(salas, aps)
        n_total = sum(1 for p in self.pontos_medicao if p["tipo"] == "medicao")
        onde = "na planta toda" if x is None else "no comodo"
        print(f"+ {len(novos)} pontos ({rotulo}, {valor:g}, margem {margem:g} m) "
              f"{onde}; {n_total} pontos de medicao renumerados 1..{n_total} "
              f"em ordem de caminhada. Tabelas CSV antigas nao batem mais "
              f"com esses ids.")
        if self._sel is not None:
            self._fechar_edicao()  # os indices dos pontos mudaram
        else:
            self._redesenhar()

    def _renumerar_caminhada(self, salas, aps):
        """ids 1..N dos pontos de medicao em ordem de caminhada; APs depois."""
        medicao = [p for p in self.pontos_medicao if p["tipo"] == "medicao"]
        outros = [p for p in self.pontos_medicao if p["tipo"] != "medicao"]
        if aps:
            inicio = aps[0]
        else:
            xs = [p["x"] for p in medicao] or [0.0]
            ys = [p["y"] for p in medicao] or [0.0]
            inicio = (min(xs), max(ys))  # canto superior esquerdo
        por_coord = {}
        for p in medicao:
            por_coord.setdefault((p["x"], p["y"]), []).append(p)
        ordem = ordenar_caminhada([(p["x"], p["y"]) for p in medicao],
                                  salas, inicio)
        novos = [por_coord[c].pop() for c in ordem]
        for i, p in enumerate(novos + outros, start=1):
            p["id"] = i
        self.pontos_medicao = novos + outros
        self._next_ponto_id = len(self.pontos_medicao) + 1

    # ------------------------------------------------------------------ #
    # Utilitarios
    # ------------------------------------------------------------------ #
    def _cancelar_pendentes(self):
        if not self._cliques_pendentes:
            return
        print(f"{len(self._cliques_pendentes)} clique(s) pendente(s) cancelado(s).")
        self._cliques_pendentes = []
        self._redesenhar()

    def _estado(self):
        return (self.paredes, self.aberturas, self.moveis,
                self.pontos_medicao, self.guias, self._next_ponto_id)

    def _snapshot(self):
        """Guarda o estado inteiro antes de qualquer alteracao (undo)."""
        self._historico.append(copy.deepcopy(self._estado()))
        if len(self._historico) > MAX_HISTORICO:
            self._historico.pop(0)

    def _desfazer(self):
        if self._cliques_pendentes:
            x, y = self._cliques_pendentes.pop()
            print(f"Clique pendente removido: ({x}, {y}).")
            self._redesenhar()
            return
        if not self._historico:
            print("Nada para desfazer.")
            return
        (self.paredes, self.aberturas, self.moveis, self.pontos_medicao,
         self.guias, self._next_ponto_id) = self._historico.pop()
        print("Desfeito.")
        if self._sel is not None:
            self._fechar_edicao()  # a selecao pode nao existir mais
        else:
            self._redesenhar()

    # ------------------------------------------------------------------ #
    # Persistencia
    # ------------------------------------------------------------------ #
    def _carregar(self, path):
        path = Path(path)
        if not path.exists():
            print(f"Aviso: {path} nao encontrado, comecando planta vazia.")
            return
        with open(path, "r", encoding="utf-8") as f:
            dados = json.load(f)
        legado = False

        self.guias = dados.get("guias", [])
        self.aberturas = dados.get("aberturas", [])
        self.paredes = []
        for p in dados.get("paredes", []):
            if "vertices" in p:
                p.setdefault("tipo", "parede")
                p.setdefault("material", "alvenaria")
                self.paredes.append(p)
                continue
            # formato antigo: parede em linha -> guia; janela/porta -> abertura
            legado = True
            tipo = p.get("tipo", "parede")
            seg = {k: p[k] for k in ("x1", "y1", "x2", "y2")}
            if tipo in MODOS_ABERTURA:
                material = p.get("material", PALETAS[tipo][1][0])
                self.aberturas.append(
                    {"tipo": tipo, "material": material, **seg, "recorte": []})
            else:
                self.guias.append(seg)
        for a in self.aberturas:
            a.setdefault("recorte", [])

        self.moveis = dados.get("moveis", [])
        for m in self.moveis:
            tipo = m.get("tipo", "personalizado")
            if tipo not in ROTULO_MOVEL:
                legado = True
                m.setdefault("nome", tipo)
                m["tipo"] = MIGRACAO_MOVEL.get(tipo, "personalizado")
            m.setdefault("nome", ROTULO_MOVEL[m["tipo"]])
            m.setdefault("material", MATERIAL_MOVEL[m["tipo"]])

        self.pontos_medicao = dados.get("pontos_medicao", [])
        for pt in self.pontos_medicao:
            pt.setdefault("tipo", "medicao")
            # as leituras agora vivem so na tabela CSV do heatmap
            if pt.pop("leituras_dbm", None) is not None:
                legado = True
        if self.pontos_medicao:
            self._next_ponto_id = max(p["id"] for p in self.pontos_medicao) + 1

        self._arquivo_legado = path if legado else None
        print(f"Planta carregada de {path} "
              f"({len(self.paredes)} paredes, {len(self.aberturas)} aberturas, "
              f"{len(self.moveis)} moveis, {len(self.pontos_medicao)} pontos, "
              f"{len(self.guias)} guias).")
        if legado:
            print("Formato antigo convertido: paredes em linha viraram guias "
                  "(redesenhe as paredes por cima), leituras_dbm foram "
                  "removidas dos pontos e os moveis migrados para os tipos novos.")

    def _salvar(self):
        legado = self._arquivo_legado
        if legado is not None and self.output_path.resolve() == legado.resolve():
            copia = legado.with_name(legado.stem + ".antigo.json")
            if not copia.exists():
                shutil.copy2(legado, copia)
                print(f"Copia do formato antigo salva em: {copia.resolve()}")
            self._arquivo_legado = None
        dados = {
            "paredes": self.paredes,
            "aberturas": self.aberturas,
            "moveis": self.moveis,
            "pontos_medicao": self.pontos_medicao,
            "guias": self.guias,
        }
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        print(f"Planta salva em: {self.output_path.resolve()}")

    def _gerar_tabela(self):
        """Salva a planta e escreve a tabela CSV em branco dos pontos de
        medicao. Um CSV existente so e sobrescrito no segundo pedido seguido
        para o mesmo caminho (ele pode ja ter leituras)."""
        # o caminho vem da caixa do modo ponto (a tecla t vale em qualquer modo)
        if self.modo == "ponto" and not self._ler_parametros():
            return
        # salva antes: os ids da tabela tem que bater com o JSON do heatmap
        self._salvar()
        caminho = Path(self._caminho_tabela)
        forcar = self._confirmar_tabela == caminho.resolve()
        try:
            n = escrever_tabela(self.pontos_medicao, caminho, forcar=forcar)
        except FileExistsError:
            self._confirmar_tabela = caminho.resolve()
            print(f"{caminho} ja existe (pode ter leituras preenchidas). "
                  "Tecle t (ou o botao) de novo para sobrescrever.")
            return
        except OSError as erro:
            print(f"Erro ao escrever a tabela: {erro}")
            return
        self._confirmar_tabela = None
        print(f"Tabela com {n} ponto(s) de medicao salva em: {caminho.resolve()}")
        if n == 0:
            print("Aviso: a planta nao tem pontos de medicao; a tabela so "
                  "tem o cabecalho.")
