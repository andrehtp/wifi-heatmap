"""Validacao cruzada leave-one-out (LOOCV) dos metodos de interpolacao.

Para cada ponto medido: tira o ponto, interpola so no lugar dele com os
demais e compara com o valor medido. Como os metodos aceitam grid_x/grid_y
de qualquer forma, cada rodada avalia um unico ponto (nada de grade), o
que deixa a validacao barata o bastante para rodar ao abrir o viewer.
"""

import numpy as np

from .interpolation import MODOS_INTERPOLACAO, montar_ctx

MIN_PONTOS_LOOCV = 3


def loocv(metodo, dados, coords, valores, parametro=None, cache=None):
    """{"rmse", "mae", "vies"} em dB (vies = media de previsto - medido), ou None."""
    n = len(valores)
    if n < MIN_PONTOS_LOOCV:
        return None
    funcao = MODOS_INTERPOLACAO[metodo][1]
    cache = {} if cache is None else cache
    previstos = np.empty(n)
    for i in range(n):
        resto = np.arange(n) != i
        ctx = montar_ctx(dados, parametro, cache)
        previstos[i] = funcao(coords[i:i + 1, 0], coords[i:i + 1, 1],
                              coords[resto], valores[resto], ctx)[0]
    erro = previstos - valores
    return {"rmse": float(np.sqrt(np.mean(erro**2))),
            "mae": float(np.mean(np.abs(erro))),
            "vies": float(np.mean(erro))}


def rotulo_com_parametro(metodo, parametro=None):
    """'IDW (potencia p=3)'; o padrao de PARAMETROS_PADRAO se parametro for None."""
    rotulo, _, param = MODOS_INTERPOLACAO[metodo]
    if param is None:
        return rotulo
    valor = param[1] if parametro is None else parametro
    return f"{rotulo} ({param[0]}={'auto' if valor is None else f'{valor:g}'})"


def tabela_loocv(dados, coords, valores, cache=None, parametros=None):
    """Tabela em texto comparando todos os metodos (parametros padrao, ou os
    de `parametros` {metodo: valor})."""
    parametros = parametros or {}
    linhas = [f"Validacao cruzada leave-one-out ({len(valores)} pontos com leitura):",
              f"  {'metodo':<40} {'RMSE':>6} {'MAE':>6} {'vies':>6}  (dB)"]
    resultados = {m: loocv(m, dados, coords, valores, parametros.get(m), cache)
                  for m in MODOS_INTERPOLACAO}
    validos = {m: r for m, r in resultados.items() if r is not None}
    if not validos:
        return f"LOOCV: precisa de ao menos {MIN_PONTOS_LOOCV} pontos com leitura."
    melhor = min(validos, key=lambda m: validos[m]["rmse"])
    for m, r in validos.items():
        marca = " *" if m == melhor else ""
        linhas.append(f"  {rotulo_com_parametro(m, parametros.get(m)):<40} "
                      f"{r['rmse']:6.2f} {r['mae']:6.2f} {r['vies']:+6.2f}{marca}")
    linhas.append(f"  * menor RMSE: {MODOS_INTERPOLACAO[melhor][0]}")
    return "\n".join(linhas)
