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
