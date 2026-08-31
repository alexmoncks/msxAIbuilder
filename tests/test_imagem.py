# tests/test_imagem.py
import pytest

from msxasm.errors import MontagemError
from msxasm.imagem import montar
from msxasm.mapper import LAYOUTS, Banco
from msxasm.source import Linha


def ls(*textos: str) -> list[Linha]:
    return [Linha(texto=t, arquivo="t.asm", numero=i) for i, t in enumerate(textos, 1)]


def banco(numero: int, janela: int, *textos: str) -> Banco:
    return Banco(numero=numero, janela=janela, linhas=ls(*textos))


def test_flat_produz_imagem_do_tamanho_pedido():
    img, _ = montar(LAYOUTS["FLAT"], 8192,
                    {0: banco(0, 0x4000, "    org 4000h", "    ret")}, [])
    assert len(img) == 8192
    assert img[0] == 0xC9
    assert img[-1] == 0xFF


def test_konami_posiciona_cada_banco_no_seu_offset():
    layout = LAYOUTS["KONAMI"]
    img, _ = montar(layout, 32768, {
        0: banco(0, 0x4000, "    db 0AAh"),
        2: banco(2, 0x6000, "    db 0BBh"),
    }, [])
    assert len(img) == 32768
    assert img[0] == 0xAA
    assert img[2 * 8192] == 0xBB


def test_banco_monta_no_endereco_da_sua_janela():
    """Um label no banco paginado deve refletir a janela onde ele vai rodar."""
    layout = LAYOUTS["KONAMI"]
    _, mapa = montar(layout, 32768, {
        0: banco(0, 0x4000, "RESIDENTE:", "    ret"),
        3: banco(3, 0xA000, "DADOS:", "    db 1"),
    }, [])
    assert mapa["RESIDENTE"] == (0, 0x4000)
    assert mapa["DADOS"] == (3, 0xA000), "banco 3 declarou WINDOW 0A000h"


def test_banco_que_nao_cabe_na_janela_e_erro():
    layout = LAYOUTS["KONAMI"]
    with pytest.raises(MontagemError) as exc:
        montar(layout, 32768, {1: banco(1, 0x6000, "    ds 9000")}, [])
    assert "banco 1" in str(exc.value).lower()
    assert "8192" in str(exc.value)
