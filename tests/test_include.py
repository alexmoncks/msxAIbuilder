# tests/test_include.py
from pathlib import Path

import pytest

from msxasm.errors import MontagemError
from msxasm.include import expandir


def test_inclui_relativo_ao_arquivo_incluidor(tmp_path):
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "vdp.asm").write_text("    ld a,2\n")
    principal = tmp_path / "jogo.asm"
    principal.write_text('    org 4000h\n    INCLUDE "lib/vdp.asm"\n    ret\n')

    linhas = expandir(principal, [])

    textos = [l.texto.strip() for l in linhas if l.texto.strip()]
    assert textos == ["org 4000h", "ld a,2", "ret"]


def test_linha_incluida_preserva_arquivo_e_numero_de_origem(tmp_path):
    (tmp_path / "m.asm").write_text("; c1\n; c2\n    ld a,7\n")
    principal = tmp_path / "p.asm"
    principal.write_text('    INCLUDE "m.asm"\n')

    linhas = expandir(principal, [])

    alvo = [l for l in linhas if "ld a,7" in l.texto][0]
    assert alvo.arquivo.endswith("m.asm")
    assert alvo.numero == 3


def test_search_path_quando_relativo_nao_acha(tmp_path):
    lib = tmp_path / "rt"
    lib.mkdir()
    (lib / "psg.asm").write_text("    ld a,9\n")
    principal = tmp_path / "j.asm"
    principal.write_text('    INCLUDE "psg.asm"\n')

    linhas = expandir(principal, [lib])

    assert any("ld a,9" in l.texto for l in linhas)


def test_inclusao_dupla_entra_uma_vez_so(tmp_path):
    (tmp_path / "u.asm").write_text("    ld a,1\n")
    principal = tmp_path / "p.asm"
    principal.write_text('    INCLUDE "u.asm"\n    INCLUDE "u.asm"\n')

    linhas = expandir(principal, [])

    assert sum(1 for l in linhas if "ld a,1" in l.texto) == 1


def test_inclusao_circular_e_erro_com_a_trilha(tmp_path):
    (tmp_path / "a.asm").write_text('    INCLUDE "b.asm"\n')
    (tmp_path / "b.asm").write_text('    INCLUDE "a.asm"\n')

    with pytest.raises(MontagemError) as exc:
        expandir(tmp_path / "a.asm", [])

    assert "circular" in str(exc.value).lower()


def test_arquivo_ausente_reporta_onde_foi_pedido(tmp_path):
    principal = tmp_path / "p.asm"
    principal.write_text('    org 4000h\n    INCLUDE "sumiu.asm"\n')

    with pytest.raises(MontagemError) as exc:
        expandir(principal, [])

    msg = str(exc.value)
    assert "sumiu.asm" in msg
    assert "p.asm:2" in msg
