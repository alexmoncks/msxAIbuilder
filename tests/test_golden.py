"""Rede de seguranca do projeto.

O Pong AI v24 e montado por codigo provado e produz 16384 bytes reprodutiveis.
Qualquer refatoracao do assembler que mude UM byte deste resultado quebrou a
codificacao de opcodes. Este teste roda em todas as tarefas do plano.
"""
import hashlib
from pathlib import Path

import pytest

from msxasm.legacy import Z80Assembler

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN_MD5 = "03324e8f4febc0e537c9c808c6c33c00"
CART_SIZE = 16384


def montar_pong() -> bytearray:
    fonte = (FIXTURES / "pong-v24.asm").read_text(encoding="utf-8")
    asm = Z80Assembler()
    asm.org = 0x4000
    binario = asm.assemble(fonte)
    assert len(binario) <= CART_SIZE, f"{len(binario)} bytes nao cabem em {CART_SIZE}"
    binario.extend([0xFF] * (CART_SIZE - len(binario)))
    return binario


def test_pong_v24_bate_com_o_golden_byte_a_byte():
    esperado = (FIXTURES / "pong-v24.rom").read_bytes()
    obtido = bytes(montar_pong())

    assert len(obtido) == CART_SIZE
    if obtido != esperado:
        divergencias = [i for i in range(CART_SIZE) if obtido[i] != esperado[i]]
        primeira = divergencias[0]
        pytest.fail(
            f"{len(divergencias)} bytes divergem. "
            f"Primeira em 0x{primeira + 0x4000:04X}: "
            f"esperado 0x{esperado[primeira]:02X}, obtido 0x{obtido[primeira]:02X}"
        )


def test_hash_do_golden_nao_mudou():
    conteudo = (FIXTURES / "pong-v24.rom").read_bytes()
    assert hashlib.md5(conteudo).hexdigest() == GOLDEN_MD5


def test_cabecalho_de_cartucho():
    binario = montar_pong()
    assert binario[0:2] == b"AB", "identificador de cartucho ausente"


def test_preenchimento_e_ff():
    binario = montar_pong()
    assert binario[-1] == 0xFF
