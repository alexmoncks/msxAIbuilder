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
