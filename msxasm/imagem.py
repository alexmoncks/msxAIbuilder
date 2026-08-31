# msxasm/imagem.py
"""Montagem da imagem final do cartucho.

Em FLAT ha um banco so, montado no org declarado. Em Konami cada banco monta
no endereco da sua janela e vai para o offset banco * 8192 da imagem.

Nao truncar nunca: binario maior que o cartucho e erro. Passar do tamanho
declarado nao e 'ficar maior', muda o formato que o emulador detecta.
"""
from msxasm.errors import MontagemError
from msxasm.legacy import Z80Assembler
from msxasm.mapper import Banco, Layout
from msxasm.source import Linha

PREENCHIMENTO = 0xFF


def _linha_org(endereco: int) -> Linha:
    """Diretiva ORG sintetica, no mesmo estilo dos EQU de BSS em cli.py
    (arquivo '<org>', numero 0): garante que Z80Assembler.current_address
    comece no endereco certo mesmo quando o fonte do banco nao declara um
    'org' proprio -- e o caso normal de um banco Konami paginado, que so
    tem WINDOW na diretiva BANK, nunca um 'org' escrito a mao.

    Sem isto, current_address comeca sempre em 0 (Z80Assembler.assemble
    zera current_address a cada passagem e so a atualiza quando encontra
    uma diretiva ORG no proprio texto) e todo label do banco sai com o
    endereco errado -- exatamente o bug que a Tarefa 9 existe para fechar
    (banco.janela, nao um indice fixo). E idempotente quando o fonte ja
    declara o mesmo 'org' (caso do Pong, que nao usa bancos): a segunda
    diretiva ORG com o mesmo valor nao preenche nada, so confirma.
    """
    return Linha(texto=f"org 0{endereco:04X}h", arquivo="<org>", numero=0)


def montar(layout: Layout, tamanho: int, bancos: dict[int, Banco],
           linhas_globais: list[Linha],
           org: int = 0x4000) -> tuple[bytearray, dict[str, tuple[int, int]]]:
    if layout.nome == "FLAT":
        unico = bancos.get(0)
        linhas = [_linha_org(org)] + linhas_globais + (unico.linhas if unico else [])
        asm = Z80Assembler()
        asm.org = org
        asm.linhas_fonte = linhas
        binario = asm.assemble("\n".join(l.texto for l in linhas))
        alvo = tamanho or len(binario)
        if len(binario) > alvo:
            raise MontagemError(
                f"binario com {len(binario)} bytes nao cabe no cartucho de {alvo} bytes"
            )
        binario.extend([PREENCHIMENTO] * (alvo - len(binario)))
        return binario, {n: (0, e) for n, e in asm.labels.items()}

    imagem = bytearray([PREENCHIMENTO] * tamanho)
    mapa: dict[str, tuple[int, int]] = {}
    residente = layout.janela_residente

    for numero in sorted(bancos):
        banco = bancos[numero]

        if numero == 0 and residente is not None and banco.janela != residente:
            raise MontagemError(
                f"banco 0 e residente em {layout.nome} e precisa ficar na janela "
                f"0x{residente:04X}, nao 0x{banco.janela:04X}"
            )

        linhas = [_linha_org(banco.janela)] + linhas_globais + banco.linhas

        asm = Z80Assembler()
        asm.org = banco.janela
        asm.linhas_fonte = linhas
        binario = asm.assemble("\n".join(l.texto for l in linhas))

        if len(binario) > layout.tamanho_banco:
            raise MontagemError(
                f"banco {numero} tem {len(binario)} bytes e nao cabe na "
                f"janela de {layout.tamanho_banco} bytes"
            )

        offset = numero * layout.tamanho_banco
        if offset + len(binario) > tamanho:
            raise MontagemError(
                f"banco {numero} comeca em 0x{offset:X} e ultrapassa a "
                f"imagem de {tamanho} bytes"
            )
        imagem[offset:offset + len(binario)] = binario

        for nome, endereco in asm.labels.items():
            mapa[nome] = (numero, endereco)

    return imagem, mapa
