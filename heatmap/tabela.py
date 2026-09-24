"""Leitura da tabela CSV de medicoes e associacao aos pontos da planta.

As leituras nao ficam mais no JSON da planta: o CSV e ligado aos pontos
de medicao pelo "id" na hora de gerar o heatmap.
"""

import csv
from pathlib import Path


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


def associar_leituras(dados, leituras_por_id):
    """Filtra as leituras do CSV para os pontos de medicao da planta.

    Retorna (leituras validas {id: [floats]}, avisos). Ids que nao existem
    na planta ou que sao de access point viram aviso e ficam de fora.
    """
    tipos = {p["id"]: p.get("tipo", "medicao")
             for p in dados.get("pontos_medicao", [])}
    validas, avisos = {}, []
    for pid, valores in leituras_por_id.items():
        if pid not in tipos:
            avisos.append(f"id {pid}: nao existe na planta, ignorado")
        elif tipos[pid] != "medicao":
            avisos.append(f"id {pid}: e access_point, ignorado")
        elif valores:
            validas[pid] = valores
    sem_leitura = [pid for pid, tipo in tipos.items()
                   if tipo == "medicao" and pid not in validas]
    if sem_leitura:
        avisos.append(f"{len(sem_leitura)} ponto(s) de medicao sem leitura "
                      f"na tabela: {sorted(sem_leitura)}")
    return validas, avisos
