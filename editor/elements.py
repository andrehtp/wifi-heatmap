"""Criacao de elementos, desfazer e persistencia em JSON."""

import copy
import json
from pathlib import Path

from .constants import ESPESSURA_MATERIAL, ESPESSURA_PADRAO, MATERIAL_MOVEL, MAX_HISTORICO


class ElementsMixin:
    # ------------------------------------------------------------------ #
    # Criacao dos elementos (atributos vem da selecao atual, sem prompt)
    # ------------------------------------------------------------------ #
    def _adicionar_segmento(self, tipo, x1, y1, x2, y2):
        material = self._opcao_atual(tipo)
        self._snapshot()
        self.paredes.append({
            "tipo": tipo,
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "espessura": ESPESSURA_MATERIAL.get(material, ESPESSURA_PADRAO),
            "material": material,
        })
        print(f"+ {tipo} ({material}) de ({x1}, {y1}) a ({x2}, {y2})")
        self._redesenhar()

    def _adicionar_movel(self, x1, y1, x2, y2):
        tipo = self._opcao_atual("movel")
        material = MATERIAL_MOVEL.get(tipo, "madeira")
        largura, profundidade = abs(x2 - x1), abs(y2 - y1)
        x0, y0 = min(x1, x2), min(y1, y2)
        self._snapshot()
        self.moveis.append({
            "tipo": tipo, "material": material,
            "x": x0, "y": y0, "largura": largura, "profundidade": profundidade,
        })
        print(f"+ movel {tipo} ({material}) em ({x0}, {y0}) "
              f"{largura} x {profundidade} m")
        self._redesenhar()

    def _adicionar_ponto(self, x, y):
        tipo = self._opcao_atual("ponto")
        self._snapshot()
        ponto_id = self._next_ponto_id
        self._next_ponto_id += 1
        ponto = {"id": ponto_id, "x": x, "y": y, "tipo": tipo}
        if tipo == "medicao":
            ponto["leituras_dbm"] = []
        self.pontos_medicao.append(ponto)
        rotulo = "access point" if tipo == "access_point" else "ponto de medicao"
        print(f"+ {rotulo} {ponto_id} em ({x}, {y})")
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

    def _snapshot(self):
        """Guarda o estado inteiro antes de qualquer alteracao (undo)."""
        self._historico.append(copy.deepcopy(
            (self.paredes, self.moveis, self.pontos_medicao,
             self._next_ponto_id)))
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
        (self.paredes, self.moveis, self.pontos_medicao,
         self._next_ponto_id) = self._historico.pop()
        print("Desfeito.")
        if self._sel is not None:
            self._fechar_edicao()  # a selecao pode nao existir mais
        else:
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
        for pt in self.pontos_medicao:  # idem para tipo/leituras dos pontos
            pt.setdefault("tipo", "medicao")
            if pt["tipo"] == "medicao":
                pt.setdefault("leituras_dbm", [])
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
