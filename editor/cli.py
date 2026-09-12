"""Interface de linha de comando do editor de planta baixa."""

import argparse

from .core import PlantaEditor


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


def main():
    args = parse_args()
    editor = PlantaEditor(
        largura=args.largura, altura=args.altura,
        output_path=args.saida, input_path=args.entrada,
        passo=args.passo,
    )
    editor.run()
