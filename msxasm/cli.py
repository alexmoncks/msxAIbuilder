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
from msxasm.numero import parse as _numero
from msxasm.source import Linha


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
        # Os argumentos numericos passam pela MESMA gramatica do fonte
        # (msxasm.numero): '4000h' e a grafia que o assembler usa em todo
        # lugar, e antes disto '--size 4000h' e '--org 4000h' saiam como
        # traceback de ValueError. Ficam DENTRO do try para que o erro caia
        # no mesmo handler de MontagemError que o resto -- a invariante da
        # Tarefa 3 ("todo erro sai como MontagemError, nunca traceback")
        # valia por dentro e estava aberta justamente na fronteira onde e
        # observavel pelo usuario.
        tamanho_pedido = _numero(args.size, contexto="em --size")
        org = _numero(args.org, contexto="em --org")

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
        # Cada EQU sintetico herda a PROCEDENCIA REAL da linha 'NOME: DS n'
        # que o gerou, em vez de '<bss>:1'. Quando o EQU falha ao montar (por
        # exemplo um simbolo BSS com '@@' no nome), o erro precisa ter caminho
        # de volta ao fonte que a pessoa escreveu -- com '<bss>:N' nao tinha.
        equates = [
            Linha(texto=f"{sim.nome} EQU 0{sim.endereco:04X}h",
                  arquivo=sim.arquivo, numero=sim.numero)
            for sim in ram.values()
        ]

        # Particionamento em bancos (FLAT quando o fonte nao declara
        # MAPPER: um unico banco 0 na janela 0x4000, sem paginacao) e
        # montagem propriamente dita: cada banco monta no endereco da sua
        # janela e vai para o offset banco * tamanho_banco da imagem final.
        layout, tamanho_mapper, bancos = particionar(linhas)
        tamanho = tamanho_mapper or tamanho_pedido

        binario, mapa = montar(layout, tamanho, bancos, equates, org=org,
                               include_paths=args.include_path)
        args.output.write_bytes(bytes(binario))

        # O mapa e 'nome -> lista de (banco, endereco)': o MESMO nome pode ser
        # definido em bancos diferentes (bancos sao espacos de endereco
        # separados, e isso e legitimo). Guardar so a ultima ocorrencia fazia
        # o unico artefato de depuracao de MegaROM responder errado com cara
        # de certo (achado da revisao final).
        definicoes = sorted(
            (banco, endereco, nome)
            for nome, ocorrencias in mapa.items()
            for banco, endereco in ocorrencias
        )
        if args.bank_map:
            with open(args.bank_map, "w", encoding="utf-8") as f:
                f.write(f"# {layout.nome}, {tamanho} bytes\n")
                for banco, endereco, nome in definicoes:
                    f.write(f"{banco:3d}  0x{endereco:04X}  {nome}\n")
    except MontagemError as e:
        print(f"msxasm: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        # Fonte inexistente, diretorio de saida inexistente, permissao
        # negada: tudo isso saia como traceback de Python. Nao ha
        # arquivo:linha a citar (a falha e sobre o arquivo inteiro), mas a
        # mensagem tem que ser legivel como qualquer outro erro da
        # ferramenta.
        alvo = e.filename or args.fonte
        print(f"msxasm: {alvo}: {e.strerror or e}", file=sys.stderr)
        return 1

    print(f"{args.output}: {tamanho} bytes, {len(definicoes)} labels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
