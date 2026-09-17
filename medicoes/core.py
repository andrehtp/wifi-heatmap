"""Leitura da tabela CSV de medicoes e aplicacao no JSON da planta."""

import csv
import json
from pathlib import Path

MAX_LEITURAS = 5


def carregar_planta(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_planta(dados, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)


def ler_csv_leituras(path):
    """Le um CSV com coluna 'id' + colunas de leitura (qualquer nome/quantidade).

    Celulas em branco sao ignoradas. Celulas nao numericas viram aviso
    (a celula e pulada, a linha nao e abortada). Retorna
    (leituras_por_id, avisos) onde leituras_por_id e {id: [floats]}.
    """
    path = Path(path)
    avisos = []
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "id" not in reader.fieldnames:
            raise SystemExit(f"Erro: {path} nao tem uma coluna 'id' no cabecalho.")
        colunas_leitura = [c for c in reader.fieldnames if c != "id"]

        leituras_por_id = {}
        for n_linha, linha in enumerate(reader, start=2):  # 1 = cabecalho
            try:
                pid = int(linha["id"])
            except (TypeError, ValueError):
                avisos.append(f"linha {n_linha}: id '{linha.get('id')}' invalido, linha ignorada")
                continue

            valores = []
            for col in colunas_leitura:
                bruto = (linha.get(col) or "").strip()
                if not bruto:
                    continue
                try:
                    valores.append(float(bruto))
                except ValueError:
                    avisos.append(
                        f"linha {n_linha}: valor '{bruto}' na coluna '{col}' "
                        f"nao e numerico, celula ignorada")
            leituras_por_id[pid] = valores
    return leituras_por_id, avisos


def aplicar_leituras(dados, leituras_por_id):
    """Grava leituras_dbm nos pontos de medicao correspondentes.

    Politica: substitui as leituras do ponto pelas do CSV (nao soma).
    Nunca lanca excecao por dado ruim: ids desconhecidos ou de
    access_point viram aviso e sao ignorados.
    """
    pontos_por_id = {p["id"]: p for p in dados["pontos_medicao"]}
    resumo = {"atualizados": 0, "avisos": [], "leituras_gravadas": 0}

    for pid, valores in leituras_por_id.items():
        pt = pontos_por_id.get(pid)
        if pt is None:
            resumo["avisos"].append(f"id {pid}: nao existe na planta, ignorado")
            continue
        if pt.get("tipo") != "medicao":
            resumo["avisos"].append(f"id {pid}: e access_point, ignorado")
            continue
        if len(valores) > MAX_LEITURAS:
            resumo["avisos"].append(
                f"id {pid}: {len(valores)} leituras no CSV, usando as primeiras {MAX_LEITURAS}")
            valores = valores[:MAX_LEITURAS]
        pt["leituras_dbm"] = valores
        resumo["atualizados"] += 1
        resumo["leituras_gravadas"] += len(valores)

    return resumo
