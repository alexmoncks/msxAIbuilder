# msxasm/cli.py
"""Interface de linha de comando do assembler."""
import argparse
import sys
from pathlib import Path

from msxasm.bss import extrair
from msxasm.errors import MontagemError
from msxasm.imagem import montar
from msxasm.include import expandir
from msxasm.labels import expandir_locais
from msxasm.macro import expandir_macros
from msxasm.mapper import particionar
from msxasm.source import Linha


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
    p.add_argument("--bank-map", type=Path, help="grava o mapa simbolo -> (banco, endereco)")
    args = p.parse_args(argv)

    try:
        # Cadeia de preparo do fonte, antes da montagem. Macros expandem
        # antes do escopo de labels locais: o corpo da macro gera
        # '@@espera_m1', e so entao expandir_locais aplica o escopo global
        # sobre o texto ja sufixado. Invertida, '@@' seria escopado antes
        # de o sufixo por expansao existir, e duas invocacoes da mesma
        # macro colidiriam. A extracao de BSS vem por ultimo: um bloco BSS
        # pode vir de dentro de um INCLUDE e pode ser gerado por macro, entao
        # so faz sentido procurar por ele depois que as duas expansoes
        # anteriores ja achataram o fonte inteiro.
        linhas = expandir_locais(expandir_macros(expandir(args.fonte, args.include_path)))
        linhas, ram = extrair(linhas)
        equates = [
            Linha(texto=f"{nome} EQU 0{endereco:04X}h", arquivo="<bss>", numero=n)
            for n, (nome, endereco) in enumerate(ram.items(), start=1)
        ]

        # Particionamento em bancos (FLAT quando o fonte nao declara
        # MAPPER: um unico banco 0 na janela 0x4000, sem paginacao) e
        # montagem propriamente dita: cada banco monta no endereco da sua
        # janela e vai para o offset banco * tamanho_banco da imagem final.
        layout, tamanho_mapper, bancos = particionar(linhas)
        tamanho = tamanho_mapper or _tamanho(args.size)

        binario, mapa = montar(layout, tamanho, bancos, equates, org=int(args.org, 0))
        args.output.write_bytes(bytes(binario))

        if args.bank_map:
            with open(args.bank_map, "w", encoding="utf-8") as f:
                f.write(f"# {layout.nome}, {tamanho} bytes\n")
                for nome, (banco, endereco) in sorted(mapa.items(), key=lambda x: x[1]):
                    f.write(f"{banco:3d}  0x{endereco:04X}  {nome}\n")
    except MontagemError as e:
        print(f"msxasm: {e}", file=sys.stderr)
        return 1

    print(f"{args.output}: {tamanho} bytes, {len(mapa)} labels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
