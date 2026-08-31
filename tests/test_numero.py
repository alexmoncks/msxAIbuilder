# tests/test_numero.py
"""A gramatica numerica unica.

Antes existiam tres copias divergentes (cli._tamanho, bss._numero,
mapper._numero) e a divergencia era observavel: '4000h' e a grafia que o
proprio assembler usa em todo lugar e mesmo assim '--size 4000h' estourava
com ValueError cru.
"""
import pytest

from msxasm.errors import MontagemError
from msxasm.numero import parse


@pytest.mark.parametrize("texto,esperado", [
    ("16K", 16 * 1024),
    ("2M", 2 * 1024 * 1024),
    ("2048K", 2048 * 1024),
    ("4000h", 0x4000),
    ("0C000h", 0xC000),
    ("0C000H", 0xC000),
    ("0x4000", 0x4000),
    ("0X4000", 0x4000),
    ("8192", 8192),
    ("010", 10),
    ("  32K  ", 32 * 1024),
    ("-8000h", -0x8000),
])
def test_formas_aceitas(texto, esperado):
    assert parse(texto) == esperado


def test_sufixo_h_vence_o_prefixo_0b():
    """'0BEEFh' e um hexadecimal terminado em 'h', nao um binario comecando
    em '0b'. O sufixo tem que ser testado antes do prefixo.
    """
    assert parse("0BEEFh") == 0xBEEF
    assert parse("0Bh") == 0x0B


@pytest.mark.parametrize("texto", ["ZZZ", "", "  ", "4000hh", "0xZZ", "K", "12X"])
def test_entrada_malformada_e_montagem_error_nunca_value_error(texto):
    with pytest.raises(MontagemError) as exc:
        parse(texto)
    assert "invalido" in str(exc.value).lower()


def test_erro_carrega_arquivo_e_linha_quando_a_origem_e_conhecida():
    with pytest.raises(MontagemError) as exc:
        parse("ZZZ", linha=7, arquivo="rt.asm", contexto="dentro de BSS")
    msg = str(exc.value)
    assert msg.startswith("rt.asm:7: ")
    assert "dentro de BSS" in msg


def test_erro_sem_origem_nao_inventa_localizacao():
    """Numero vindo de um argumento de linha de comando nao tem arquivo:linha
    para citar -- e nem por isso pode sair como traceback.
    """
    with pytest.raises(MontagemError) as exc:
        parse("ZZZ", contexto="em --size")
    assert str(exc.value) == "numero invalido em --size: 'ZZZ'"
