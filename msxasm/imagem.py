# msxasm/imagem.py
"""Montagem da imagem final do cartucho.

Em FLAT ha um banco so, montado no org declarado. Em Konami cada banco monta
no endereco da sua janela e vai para o offset banco * 8192 da imagem.

Nao truncar nunca: binario maior que o cartucho e erro. Passar do tamanho
declarado nao e 'ficar maior', muda o formato que o emulador detecta.
"""
import re
from pathlib import Path

from msxasm.errors import MontagemError
from msxasm.legacy import Z80Assembler
from msxasm.mapper import Banco, Layout
from msxasm.source import Linha
from msxasm.texto import corta_comentario

PREENCHIMENTO = 0xFF

# 'org' escrito no fonte, com ou sem label na frente ('INICIO: ORG 4000h' e
# valido -- legacy.Z80Assembler tira o label antes de casar a diretiva).
_ORG_DO_FONTE = re.compile(r"^\s*(?:[A-Za-z_][A-Za-z_0-9@]*\s*:)?\s*ORG\b", re.IGNORECASE)


def _declara_org(linhas: list[Linha]) -> bool:
    return any(_ORG_DO_FONTE.match(corta_comentario(l.texto)[0]) for l in linhas)


def _linha_org(endereco: int) -> Linha:
    """Diretiva ORG sintetica (arquivo '<org>', numero 0): garante que
    Z80Assembler.current_address comece no endereco certo quando o fonte NAO
    declara um 'org' proprio -- o caso normal de um banco Konami paginado, que
    so tem WINDOW na diretiva BANK, nunca um 'org' escrito a mao.

    Sem ela, current_address comeca sempre em 0 (Z80Assembler.assemble zera
    current_address a cada passagem e so a atualiza quando encontra uma
    diretiva ORG no proprio texto) e todo label do banco sai com o endereco
    errado -- o bug que a Tarefa 9 existe para fechar.

    Ela e injetada SO quando o fonte nao traz o seu proprio 'org' (ver
    _declara_org). A Tarefa 9 a injetava sempre, e isso REGREDIU um caso que
    montava antes dela: um fonte com 'org 8000h' montado com o --org padrao
    (0x4000) recebia a sintetica na frente, e o 'org' de verdade caia no ramo
    de preenchimento de _directive ('if v > current_address and
    current_address > 0'), zero-preenchendo 16K ate estourar o cartucho.
    Quatro linhas de assembly viravam 16387 bytes.

    A regra passa a ser a de qualquer assembler: o 'org' do FONTE manda; o
    org da CLI (ou a janela do banco) e o padrao usado quando o fonte se cala.
    """
    return Linha(texto=f"org 0{endereco:04X}h", arquivo="<org>", numero=0)


def _conferir_org_bate_com_a_janela(asm: Z80Assembler, numero: int, janela: int) -> None:
    """Num banco de mapper, um 'org' do fonte que DIVIRJA da janela declarada
    e erro do autor -- nao intencao.

    'BANK n WINDOW addr' existe justamente para substituir o org manual: o
    banco monta no endereco da janela e vai para o offset n * tamanho_banco da
    imagem. Um 'org 9000h' dentro de um banco com WINDOW 8000h nao move o
    banco para lugar nenhum; ele so mente para o assembler. O codigo continua
    no offset 0 do banco (CPU 0x8000), enquanto todo label sai calculado a
    partir de 0x9000: um 'jp ALVO' monta 'C3 00 90' e aponta para
    preenchimento 0xFF. ROM gravada, codigo de saida 0, maquina travada -- a
    falha exata que este projeto existe para eliminar.

    Ate a leva anterior o sintoma era outro (o org sintetico entrava sempre e
    o zero-fill de _directive empurrava o codigo ate 0x9000 de verdade:
    desperdicio de espaco, mas ROM correta). Preservar o org do fonte tirou o
    efeito colateral que salvava o caso, e a validacao que devia substitui-lo
    nao existia.

    Compara o valor JA AVALIADO por Z80Assembler (asm.orgs_do_fonte), nao o
    texto da linha: assim 'org JANELA' com JANELA vindo de um EQU tambem e
    conferido. O org sintetico de _linha_org e sempre igual a janela, entao
    nunca dispara aqui.

    FLAT nao passa por esta checagem: la nao ha janela nenhuma a respeitar, o
    org do fonte manda e o --org da CLI e so o padrao.
    """
    for valor, arquivo, linha in asm.orgs_do_fonte:
        if valor == janela:
            continue
        raise MontagemError(
            f"org 0x{valor:04X} diverge da janela 0x{janela:04X} declarada "
            f"para o banco {numero}: num banco paginado quem manda e a "
            f"janela do 'BANK {numero} WINDOW' -- remova o org ou escreva "
            f"'org 0{janela:04X}h'",
            linha=linha, arquivo=arquivo,
        )


def _montar_bloco(linhas: list[Linha], endereco: int,
                  include_paths: list[Path] | None,
                  semear: dict[str, int]) -> tuple[bytearray, Z80Assembler]:
    """Monta um bloco de linhas (o cartucho inteiro em FLAT, um banco em
    Konami) num Z80Assembler proprio, semeado com os simbolos de `semear`.
    """
    if not _declara_org(linhas):
        linhas = [_linha_org(endereco)] + linhas

    asm = Z80Assembler()
    asm.include_paths = list(include_paths or [])
    asm.labels.update(semear)
    asm.linhas_fonte = linhas
    return asm.assemble("\n".join(l.texto for l in linhas)), asm


def montar(layout: Layout, tamanho: int, bancos: dict[int, Banco],
           linhas_globais: list[Linha],
           org: int = 0x4000,
           include_paths: list[Path] | None = None,
           ) -> tuple[bytearray, dict[str, list[tuple[int, int]]]]:
    if layout.nome == "FLAT":
        unico = bancos.get(0)
        linhas = linhas_globais + (unico.linhas if unico else [])
        binario, asm = _montar_bloco(linhas, org, include_paths, {})
        alvo = tamanho or len(binario)
        if len(binario) > alvo:
            raise MontagemError(
                f"binario com {len(binario)} bytes nao cabe no cartucho de {alvo} bytes"
            )
        binario.extend([PREENCHIMENTO] * (alvo - len(binario)))
        return binario, {n: [(0, asm.labels[n])] for n in asm.labels_proprios}

    imagem = bytearray([PREENCHIMENTO] * tamanho)
    # nome -> lista de (banco, endereco). Lista, e nao um par so: o MESMO nome
    # pode ser definido em bancos diferentes -- bancos sao espacos de endereco
    # separados e 'LOOP:' nos dois e legitimo. Guardar so a ultima ocorrencia
    # fazia o mapa (a unica ferramenta de depuracao de MegaROM que existe, e a
    # entrada natural da validacao de FARCALL) responder errado com cara de
    # certo (achado da revisao final).
    mapa: dict[str, list[tuple[int, int]]] = {}
    residente = layout.janela_residente
    # Simbolos do banco residente, visiveis para TODOS os bancos. Cada banco
    # ganhava um Z80Assembler novo com tabela de simbolos vazia, entao um
    # 'call RT_INIT' de um banco paginado para o trampolim residente -- que
    # esta SEMPRE mapeado e e obrigatorio, porque codigo que pagina nao pode
    # ser paginado embaixo de si mesmo -- simplesmente nao montava. Bancos nao
    # residentes continuam invisiveis uns para os outros, e isso e correto: um
    # call direto para um banco que pode nao estar mapeado tem mesmo que
    # falhar. Uma definicao local vence a semeada, entao 'LOOP:' no banco 1
    # continua sendo o LOOP do banco 1.
    #
    # NAO entregue: o modelo de simbolo (banco, endereco) completo que a spec
    # 4.4 descreve, com validacao de call entre bancos paginados exigindo
    # FARCALL. Isto aqui e o minimo que torna MegaROM utilizavel.
    simbolos_residentes: dict[str, int] = {}

    for numero in sorted(bancos):
        banco = bancos[numero]

        if numero == 0 and residente is not None and banco.janela != residente:
            raise MontagemError(
                f"banco 0 e residente em {layout.nome} e precisa ficar na janela "
                f"0x{residente:04X}, nao 0x{banco.janela:04X}"
            )

        binario, asm = _montar_bloco(linhas_globais + banco.linhas, banco.janela,
                                     include_paths, simbolos_residentes)

        # Antes das checagens de tamanho: um org divergente pode disparar
        # zero-fill e estourar o banco, e ai o usuario receberia 'banco 1 tem
        # 36864 bytes' -- verdadeiro, mas sem dizer o que ele escreveu de
        # errado nem em que linha.
        _conferir_org_bate_com_a_janela(asm, numero, banco.janela)

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

        # So os labels DEFINIDOS neste banco entram no mapa -- os semeados a
        # partir do residente pertencem ao banco 0 e ja foram registrados la.
        proprios = {nome: asm.labels[nome] for nome in asm.labels_proprios}
        for nome, endereco in proprios.items():
            mapa.setdefault(nome, []).append((numero, endereco))

        if numero == 0 and residente is not None:
            simbolos_residentes = proprios

    return imagem, mapa
