import pytest

from msxasm.bss import extrair
from msxasm.errors import MontagemError
from msxasm.source import Linha


def linhas(*textos: str) -> list[Linha]:
    return [Linha(texto=t, arquivo="t.asm", numero=i) for i, t in enumerate(textos, 1)]


def test_aloca_sequencialmente_a_partir_da_base():
    _, mapa = extrair(linhas(
        "    BSS 0C000h",
        "MUS_PTR:  DS 2",
        "MUS_TICK: DS 1",
        "MUS_VOZ:  DS 6",
        "    ENDBSS",
    ))
    assert mapa == {"MUS_PTR": 0xC000, "MUS_TICK": 0xC002, "MUS_VOZ": 0xC003}


def test_blocos_de_modulos_diferentes_se_concatenam():
    _, mapa = extrair(linhas(
        "    BSS 0C000h",
        "A: DS 4",
        "    ENDBSS",
        "    BSS",
        "B: DS 2",
        "    ENDBSS",
    ))
    assert mapa == {"A": 0xC000, "B": 0xC004}


def test_simbolo_repetido_e_erro():
    with pytest.raises(MontagemError) as exc:
        extrair(linhas(
            "    BSS 0C000h", "X: DS 1", "    ENDBSS",
            "    BSS", "X: DS 1", "    ENDBSS",
        ))
    assert "X" in str(exc.value)
    assert "duplicad" in str(exc.value).lower()


def test_estouro_de_ram_e_erro():
    with pytest.raises(MontagemError) as exc:
        extrair(linhas("    BSS 0FFF0h", "GRANDE: DS 32", "    ENDBSS"), limite=0xFFFF)
    assert "ram" in str(exc.value).lower()


def test_linhas_do_bloco_somem_do_fonte():
    resto, _ = extrair(linhas(
        "    org 4000h",
        "    BSS 0C000h",
        "V: DS 1",
        "    ENDBSS",
        "    ret",
    ))
    assert [l.texto.strip() for l in resto if l.texto.strip()] == ["org 4000h", "ret"]


def test_bloco_sem_endbss_e_erro():
    with pytest.raises(MontagemError) as exc:
        extrair(linhas("    BSS 0C000h", "V: DS 1"))
    assert "ENDBSS" in str(exc.value)


def test_primeiro_bloco_sem_base_e_erro():
    with pytest.raises(MontagemError) as exc:
        extrair(linhas("    BSS", "V: DS 1", "    ENDBSS"))
    assert "base" in str(exc.value).lower()
