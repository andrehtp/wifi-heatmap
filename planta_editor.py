"""
Editor interativo de planta baixa para o projeto de mapa de calor wifi.

Ponto de entrada de linha de comando; a implementacao esta no pacote
`editor/`. Para o guia de uso completo (mouse, modos, teclas), veja
`editor.constants.USAGE` ou rode o editor uma vez: o texto e impresso
no terminal ao abrir a janela.

Uso:
    python planta_editor.py --largura 8 --altura 6 --saida planta_casa.json
"""

from editor.cli import main

if __name__ == "__main__":
    main()
