"""Interface de linha de comando do editor de planta baixa."""

import argparse
import json
from pathlib import Path

from .constants import N_LEITURAS_PADRAO
from .core import PlantaEditor
from .tabela import escrever_tabela


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
    parser.add_argument("--gerar-tabela", type=str, default=None, metavar="CSV",
                         help="So gera a tabela CSV em branco (id + colunas de "
                              "leitura) dos pontos de medicao da --entrada, "
                              "sem abrir o editor")
    parser.add_argument("--leituras", type=int, default=N_LEITURAS_PADRAO,
                         help="Quantidade de colunas de leitura da tabela")
    parser.add_argument("--forcar", action="store_true",
                         help="Sobrescreve a tabela CSV se ela ja existir")
    args = parser.parse_args()
    if args.gerar_tabela is not None and args.entrada is None:
        parser.error("--gerar-tabela precisa de --entrada (a planta com os pontos)")
    if args.leituras < 1:
        parser.error("--leituras precisa ser pelo menos 1")
    return args


def gerar_tabela(args):
    entrada = Path(args.entrada)
    if not entrada.exists():
        raise SystemExit(f"Erro: {entrada} nao encontrado.")
    with open(entrada, "r", encoding="utf-8") as f:
        pontos = json.load(f).get("pontos_medicao", [])
    try:
        n = escrever_tabela(pontos, args.gerar_tabela,
                            n_leituras=args.leituras, forcar=args.forcar)
    except FileExistsError:
        raise SystemExit(f"Erro: {args.gerar_tabela} ja existe (pode ter leituras "
                         "preenchidas); use --forcar para sobrescrever.")
    print(f"Tabela com {n} ponto(s) de medicao salva em: "
          f"{Path(args.gerar_tabela).resolve()}")
    if n == 0:
        print(f"Aviso: {entrada} nao tem pontos de medicao; a tabela so tem o cabecalho.")


def main():
    args = parse_args()
    if args.gerar_tabela is not None:
        gerar_tabela(args)
        return
    editor = PlantaEditor(
        largura=args.largura, altura=args.altura,
        output_path=args.saida, input_path=args.entrada,
        passo=args.passo,
    )
    editor.run()
