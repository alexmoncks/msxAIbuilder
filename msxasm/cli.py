# msxasm/cli.py
"""Interface de linha de comando do assembler."""
import argparse
import sys
from pathlib import Path

from msxasm.errors import MontagemError
from msxasm.legacy import Z80Assembler

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

        texto_fonte = args.fonte.read_text(encoding="utf-8")
        # Ponto de costura para a Tarefa 4: expansao de INCLUDE entra aqui,
        # entre a leitura do fonte e a chamada a assemble().
        binario = asm.assemble(texto_fonte)

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
