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


def test_inclusao_em_diamante_inclui_uma_vez_sem_falso_positivo_de_ciclo(tmp_path):
    """a inclui b e c; b e c incluem o mesmo d. Nao e ciclo -- e dependencia
    compartilhada (o caso comum de um runtime: varios modulos incluindo o
    mesmo modulo base). O algoritmo separa "concluidos" (guarda de
    repeticao) de "em andamento na pilha atual" (deteccao de ciclo); esta
    interacao e exatamente a sutileza que ja produziu um bug real nesta
    tarefa (ciclo verdadeiro nao detectado), entao o diamante -- que exercita
    o mesmo par de estruturas sem ser um ciclo -- precisa de rede propria.
    """
    (tmp_path / "d.asm").write_text("    ld a,4\n    ld b,4\n")
    (tmp_path / "b.asm").write_text('    INCLUDE "d.asm"\n')
    (tmp_path / "c.asm").write_text('    INCLUDE "d.asm"\n')
    principal = tmp_path / "a.asm"
    principal.write_text('    INCLUDE "b.asm"\n    INCLUDE "c.asm"\n')

    linhas = expandir(principal, [])  # nao pode levantar MontagemError de ciclo

    linhas_a = [l for l in linhas if "ld a,4" in l.texto]
    linhas_b = [l for l in linhas if "ld b,4" in l.texto]
    assert len(linhas_a) == 1, "d.asm deve entrar uma unica vez, via b ou c"
    assert len(linhas_b) == 1, "d.asm deve entrar uma unica vez, via b ou c"
    assert linhas_a[0].arquivo.endswith("d.asm")
    assert linhas_a[0].numero == 1
    assert linhas_b[0].arquivo.endswith("d.asm")
    assert linhas_b[0].numero == 2


def test_inclusao_em_diamante_dois_niveis_inclui_uma_vez_sem_falso_positivo_de_ciclo(tmp_path):
    """Diamante mais fundo: e e alcancado por dois ramos em profundidades
    DIFERENTES -- a->b->d->e (profundidade 3) e a->f->e (profundidade 2) --
    e alem disso d tambem e um diamante raso (incluido por b e por c). O bug
    original de deteccao de ciclo so se manifestava a partir do segundo
    nivel de recursao, entao um diamante raso sozinho nao bastaria como rede
    de regressao para essa classe de erro.
    """
    (tmp_path / "e.asm").write_text("    ld a,5\n")
    (tmp_path / "d.asm").write_text('    INCLUDE "e.asm"\n')
    (tmp_path / "b.asm").write_text('    INCLUDE "d.asm"\n')
    (tmp_path / "c.asm").write_text('    INCLUDE "d.asm"\n')
    (tmp_path / "f.asm").write_text('    INCLUDE "e.asm"\n')
    principal = tmp_path / "a.asm"
    principal.write_text(
        '    INCLUDE "b.asm"\n    INCLUDE "c.asm"\n    INCLUDE "f.asm"\n'
    )

    linhas = expandir(principal, [])  # nao pode levantar MontagemError de ciclo

    linhas_e = [l for l in linhas if "ld a,5" in l.texto]
    assert len(linhas_e) == 1, "e.asm deve entrar uma unica vez, apesar de dois ramos"
    assert linhas_e[0].arquivo.endswith("e.asm")
    assert linhas_e[0].numero == 1
