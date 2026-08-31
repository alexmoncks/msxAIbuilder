from msxasm.labels import expandir_locais
from msxasm.source import Linha


def linhas(*textos: str) -> list[Linha]:
    return [Linha(texto=t, arquivo="t.asm", numero=i) for i, t in enumerate(textos, 1)]


def textos(ls: list[Linha]) -> list[str]:
    return [l.texto for l in ls]


def test_local_recebe_prefixo_do_global_acima():
    r = expandir_locais(linhas("VDP_INIT:", "@@loop:", "    djnz @@loop", "    ret"))
    assert textos(r) == [
        "VDP_INIT:",
        "VDP_INIT@@loop:",
        "    djnz VDP_INIT@@loop",
        "    ret",
    ]


def test_dois_modulos_com_mesmo_local_nao_colidem():
    r = expandir_locais(linhas(
        "PSG_ON:", "@@loop:", "    djnz @@loop",
        "FM_ON:", "@@loop:", "    djnz @@loop",
    ))
    assert "PSG_ON@@loop:" in textos(r)
    assert "FM_ON@@loop:" in textos(r)
    assert textos(r).count("    djnz PSG_ON@@loop") == 1
    assert textos(r).count("    djnz FM_ON@@loop") == 1


def test_label_global_nao_e_tocado():
    r = expandir_locais(linhas("MAIN:", "    call VDP_INIT", "    jp MAIN"))
    assert textos(r) == ["MAIN:", "    call VDP_INIT", "    jp MAIN"]


def test_local_dentro_de_comentario_e_ignorado():
    r = expandir_locais(linhas("A:", "    ret        ; volta para @@loop"))
    assert textos(r)[1] == "    ret        ; volta para @@loop"


def test_local_dentro_de_string_literal_e_ignorado():
    # DB com string contendo "@@" nao pode ser reescrito -- corromperia
    # dados da ROM em silencio (ex.: um e-mail gravado como texto).
    r = expandir_locais(linhas("A:", '    db "e-mail: a@@b"'))
    assert textos(r)[1] == '    db "e-mail: a@@b"'


def test_local_dentro_de_string_sem_escopo_nao_gera_erro():
    # "@@" dentro de uma string e dado, nao referencia a label local --
    # nao deve disparar o erro de "label local sem global acima".
    r = expandir_locais(linhas('    db "sem escopo: a@@b"'))
    assert textos(r) == ['    db "sem escopo: a@@b"']


def test_local_fora_de_string_ainda_e_expandido_na_mesma_linha():
    r = expandir_locais(linhas(
        "A:", '    db "a@@b"', "@@loop:", "    djnz @@loop",
    ))
    assert textos(r) == [
        "A:",
        '    db "a@@b"',
        "A@@loop:",
        "    djnz A@@loop",
    ]


def test_local_sem_global_acima_gera_erro():
    import pytest
    from msxasm.errors import MontagemError

    with pytest.raises(MontagemError):
        expandir_locais(linhas("    djnz @@loop"))
