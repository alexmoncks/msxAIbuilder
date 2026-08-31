# msxasm/cli.py
"""Interface de linha de comando do assembler."""
import argparse
import sys
from pathlib import Path

from msxasm.errors import MontagemError
from msxasm.include import expandir
from msxasm.labels import expandir_locais
from msxasm.legacy import Z80Assembler
from msxasm.macro import expandir_macros

PREENCHIMENTO = 0xFF


def _tamanho(texto: str) -> int:
    t = texto.strip().upper()
    if t.endswith("K"):
        return int(t[:-1]) * 1024
    if t.endswith("M"):
        return int(t[:-1]) * 1024 * 1024
    return int(t, 0)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="msxasm", description="Assembler Z80 para cartuchos MSX")
    p.add_argument("fonte", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("--org", default="0x4000")
    p.add_argument("--size", default="16K", help="tamanho do cartucho, ex: 16K, 32K, 2M")
    p.add_argument("-I", "--include-path", action="append", default=[], type=Path)
    args = p.parse_args(argv)

    tamanho = _tamanho(args.size)

    try:
        asm = Z80Assembler()
        asm.org = int(args.org, 0)
        asm.include_paths = list(args.include_path)
        asm.arquivo_base = args.fonte

        # Cadeia de preparo do fonte, antes da montagem. Macros expandem
        # antes do escopo de labels locais: o corpo da macro gera
        # '@@espera_m1', e so entao expandir_locais aplica o escopo global
        # sobre o texto ja sufixado. Invertida, '@@' seria escopado antes
        # de o sufixo por expansao existir, e duas invocacoes da mesma
        # macro colidiriam. A Tarefa 7 acrescenta a extracao de BSS depois.
        linhas = expandir(args.fonte, args.include_path)
        linhas = expandir_macros(linhas)
        linhas = expandir_locais(linhas)
        asm.linhas_fonte = linhas
        binario = asm.assemble("\n".join(l.texto for l in linhas))

        if len(binario) > tamanho:
            raise MontagemError(
                f"binario com {len(binario)} bytes nao cabe no cartucho de {tamanho} bytes"
            )
        binario.extend([PREENCHIMENTO] * (tamanho - len(binario)))

        args.output.write_bytes(bytes(binario))
    except MontagemError as e:
        print(f"msxasm: {e}", file=sys.stderr)
        return 1

    print(f"{args.output}: {tamanho} bytes, {len(asm.labels)} labels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
