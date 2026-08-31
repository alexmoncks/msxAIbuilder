# tests/test_expressoes.py
import pytest

from msxasm.errors import MontagemError
from msxasm.legacy import Z80Assembler


def montar(fonte: str, org: int = 0x4000) -> bytearray:
    asm = Z80Assembler()
    asm.org = org
    return asm.assemble(fonte)


def test_simbolo_inexistente_e_erro_e_nao_zero():
    with pytest.raises(MontagemError) as exc:
        montar("    org 4000h\n    ld hl,NAO_EXISTE\n")
    assert "NAO_EXISTE" in str(exc.value)


def test_referencia_adiante_continua_valendo():
    """Pass 1 nao conhece DEPOIS ainda; isso e legitimo, nao erro."""
    binario = montar("    org 4000h\n    jp DEPOIS\nDEPOIS:\n    ret\n")
    assert binario[0] == 0xC3
    assert binario[1] == 0x03 and binario[2] == 0x40   # 0x4003


def test_expressao_malformada_e_erro():
    with pytest.raises(MontagemError):
        montar("    org 4000h\n    ld a,(2 +* 3)\n")


def test_expressao_valida_com_aritmetica_de_label():
    binario = montar(
        "    org 4000h\n"
        "TAB:\n"
        "    db 1,2,3,4\n"
        "    ld hl,TAB+2\n"
    )
    assert binario[5] == 0x02 and binario[6] == 0x40   # TAB+2 = 0x4002


def test_equ_com_simbolo_inexistente_e_erro():
    """EQU so era avaliado na passagem 1, e _eval so levanta na ultima --
    entao 'FOO EQU NAO_EXISTE' montava sem erro e FOO valia 0 para sempre.
    """
    with pytest.raises(MontagemError) as exc:
        montar("    org 4000h\nFOO EQU NAO_EXISTE\n    ld hl,FOO\n")
    assert "NAO_EXISTE" in str(exc.value)


def test_equ_com_referencia_adiante_a_label_resolve():
    """Caso legitimo: TAM EQU FIM - INICIO, com FIM definido depois. Nao
    resolver na passagem 1 e normal (label ainda nao existe); nao resolver
    na passagem final e que seria erro.
    """
    binario = montar(
        "    org 4000h\n"
        "INICIO:\n"
        "    ld a,1\n"
        "TAM EQU FIM - INICIO\n"
        "    ld hl,TAM\n"
        "    ret\n"
        "FIM:\n"
        "    nop\n"
    )
    # INICIO = 0x4000, FIM = 0x4000 + 2 (ld a,1) + 3 (ld hl,TAM) + 1 (ret) = 0x4006
    # TAM = FIM - INICIO = 6
    assert binario[3] == 0x06 and binario[4] == 0x00   # ld hl,6


def test_label_totalmente_minusculo_resolve():
    """Rodada de correcao 1 da Tarefa 5: _eval maiusculiza a expressao antes
    de substituir simbolos, mas a definicao de label guardava a chave com a
    caixa original -- um label 100% minusculo nunca batia com a busca e
    'assemble' morria com 'expressao nao pode ser avaliada'.
    """
    binario = montar("    org 4000h\nloop:\n    djnz loop\n")
    assert binario[0] == 0x10          # DJNZ
    assert binario[1] == 0xFE          # salta para si mesmo: 0x4000-(0x4000+2)


def test_label_caixa_mista_no_formato_gerado_por_macro_resolve():
    """Formato que o mecanismo de macros da Tarefa 6 produz ao sufixar um
    label local por expansao: 'ESPERA_m1', com o sufixo '_m{contador}' em
    minusculo. Antes da correcao, so o 'ESPERA' maiusculo batia depois do
    .upper() em _eval, e o '_M1' maiusculizado nao encontrava a chave
    'ESPERA_m1' guardada com o sufixo original em minusculo.
    """
    binario = montar("    org 4000h\nESPERA_m1:\n    djnz ESPERA_m1\n")
    assert binario[0] == 0x10
    assert binario[1] == 0xFE


def test_equ_em_minusculas_resolve():
    binario = montar("    org 4000h\ntempo equ 5\n    ld hl,tempo\n")
    assert binario[0] == 0x21 and binario[1] == 0x05 and binario[2] == 0x00


def test_constante_hex_terminada_em_0b_nao_e_corrompida_pela_normalizacao_de_caixa():
    """Rede de regressao explicita para o comentario de _eval sobre
    '0C00Bh': sem o lookbehind correto na normalizacao de literal binario,
    essa constante virava 0x0C0 (192) em silencio depois da conversao hex.
    A correcao de case-folding desta rodada nao mexeu nessas linhas, mas
    este teste prova isso em vez de so confiar no golden (que tambem usa
    '0C00Bh', em 'PAUSA equ 0C00Bh').
    """
    binario = montar("    org 4000h\n    ld hl,0C00Bh\n")
    assert binario[0] == 0x21 and binario[1] == 0x0B and binario[2] == 0xC0


def test_label_redefinido_e_erro_citando_a_primeira_definicao():
    """Rodada de correcao 2 da Tarefa 5: a correcao de caixa da rodada 1
    expos um buraco maior -- label duplicado (de qualquer caixa) era
    aceito em silencio, a segunda definicao vencia, e toda referencia ia
    para ela. O escopo de '@@' so protege LOCAIS; isto fecha o caso GLOBAL
    (dois modulos do runtime que declarem o mesmo simbolo, ex.: VDP_INIT).
    """
    with pytest.raises(MontagemError) as exc:
        montar("    org 4000h\nLOOP:\n    nop\nLOOP:\n    nop\n")
    msg = str(exc.value)
    assert "linha 4" in msg or ":4" in msg      # segunda definicao (LOOP: na linha 4)
    assert "linha 2" in msg or ":2" in msg      # primeira definicao, citada (LOOP: na linha 2)
    assert "LOOP" in msg


def test_duas_grafias_de_caixa_do_mesmo_label_e_erro():
    """'Loop:' e 'LOOP:' sao o MESMO simbolo depois da correcao de
    case-folding da rodada 1 -- portanto tambem precisam colidir como
    redefinicao, nao como dois labels diferentes.
    """
    with pytest.raises(MontagemError) as exc:
        montar("    org 4000h\nLoop:\n    nop\nLOOP:\n    nop\n")
    assert "LOOP" in str(exc.value)


def test_muitos_labels_distintos_continuam_montando():
    """Prova de que a deteccao de redefinicao e DENTRO de uma passagem, nao
    ENTRE passagens -- do contrario a segunda passagem (que redefine todo
    label de novo) acusaria falso-positivo para absolutamente qualquer
    fonte com mais de um label, e nada montaria.
    """
    binario = montar(
        "    org 4000h\n"
        "A:\n    nop\n"
        "B:\n    nop\n"
        "C:\n    nop\n"
        "D:\n    jp A\n"
        "E:\n    jp B\n"
        "F:\n    jp C\n"
    )
    assert len(binario) == 3 + 3 * 3   # 3 NOPs + 3 JP (3 bytes cada)


def test_equ_com_dollar_e_referencia_adiante_resolve_igual_nas_duas_passagens():
    """Regressao recomendada na revisao: o revisor verificou empiricamente que
    EQU referenciando '$' e seguro entre passagens (current_address e
    identico na passagem 1 e na final, mesmo com referencia adiante antes do
    '$'), mas nao havia teste nenhum disso. Como EQU agora reavalia em toda
    passagem (guarda 'if self.pass_no == 1' removida), essa combinacao e
    exatamente o que pode quebrar em silencio numa mudanca futura.
    """
    binario = montar(
        "    org 4000h\n"
        "    ld a,1\n"
        "HERE EQU FIM - $\n"
        "    ld hl,HERE\n"
        "    ret\n"
        "FIM:\n"
        "    nop\n"
    )
    # '$' no ponto da linha EQU = 0x4002 (depois de 'ld a,1', 2 bytes).
    # FIM = 0x4002 + 3 (ld hl,HERE) + 1 (ret) = 0x4006.
    # HERE = FIM - $ = 0x4006 - 0x4002 = 4, resolvido so na passagem final.
    assert binario[3] == 0x04 and binario[4] == 0x00   # ld hl,4
