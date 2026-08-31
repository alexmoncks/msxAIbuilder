# tests/test_colisao_simbolos.py
"""Requisito adicional da Tarefa 7 (BSS): fecha a porta dos fundos por onde a
mesma classe de corrupcao que o BSS existe para eliminar (dois simbolos com
o mesmo nome, um vencendo sem aviso) entrava via EQU/label em vez de
endereco de RAM literal.

Achado na revisao: os simbolos alocados pelo BSS sao injetados na CLI (Passo
5 da Tarefa 7) como linhas 'NOME EQU endereco'. Antes desta correcao,

    ESTADO EQU 0C000h
    ESTADO:

produzia labels={} e equates={'ESTADO': 49152} -- o label sumia em SILENCIO,
porque o `if label_part.upper() not in self.equates` em legacy.py pulava o
bloco que grava o label sempre que o nome ja existia como equate, sem
levantar erro nenhum. Todo salto que apontava para o label ficava orfao.

Estes testes exercitam Z80Assembler diretamente (nao a extracao de BSS em
si, que ja tem sua propria suite em tests/test_bss.py) porque o buraco
estava no ponto onde equates e labels compartilham a mesma tabela de
simbolos, nao na extracao.
"""
import subprocess
import sys
from pathlib import Path

import pytest

from msxasm.errors import MontagemError
from msxasm.legacy import Z80Assembler

RAIZ = Path(__file__).resolve().parent.parent


def montar(fonte: str, org: int = 0x4000) -> bytearray:
    asm = Z80Assembler()
    asm.org = org
    return asm.assemble(fonte)


def rodar(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "msxasm", *args],
        cwd=RAIZ, capture_output=True, text=True,
    )


def test_equ_seguido_de_label_de_mesmo_nome_e_erro_nao_descarte_silencioso():
    """O repro exato que motivou a correcao: um EQU (como os que o BSS
    injeta) seguido de um label de codigo com o mesmo nome. Antes, o label
    era descartado em silencio; agora e MontagemError citando as duas
    localizacoes.
    """
    with pytest.raises(MontagemError) as exc:
        montar("    org 4000h\nESTADO EQU 0C000h\nESTADO:\n    ret\n")
    msg = str(exc.value)
    assert "ESTADO" in msg
    assert "colide" in msg.lower()


def test_label_seguido_de_equ_de_mesmo_nome_tambem_e_erro():
    """A ordem inversa: um label de codigo definido primeiro, e um EQU
    manual mais adiante no arquivo tentando reusar o mesmo nome. Os EQU
    gerados pelo BSS nunca caem neste caso (sao sempre injetados na FRENTE
    do fonte inteiro -- Passo 5 da Tarefa 7), mas um EQU escrito a mao pode.
    """
    with pytest.raises(MontagemError) as exc:
        montar("    org 4000h\nESTADO:\n    ret\nESTADO EQU 5\n")
    msg = str(exc.value)
    assert "ESTADO" in msg
    assert "colide" in msg.lower()


def test_dois_equ_com_mesmo_nome_e_erro():
    """'ou com um EQU ja existente': dois modulos que declarem EQU com o
    mesmo nome (um deles podendo ser um simbolo de BSS) colidem, em vez de
    o segundo sobrescrever o primeiro em silencio.
    """
    with pytest.raises(MontagemError) as exc:
        montar("    org 4000h\nESTADO EQU 1\nESTADO EQU 2\n")
    msg = str(exc.value)
    assert "ESTADO" in msg
    assert "ja foi definido" in msg.lower()


def test_colisao_de_simbolo_e_insensivel_a_caixa():
    """A resolucao de label/equate e insensivel a caixa desde a Tarefa 5:
    'Estado' e 'ESTADO' sao o mesmo simbolo, e a deteccao de colisao precisa
    respeitar isso.
    """
    with pytest.raises(MontagemError) as exc:
        montar("    org 4000h\nEstado EQU 1\nESTADO EQU 2\n")
    assert "ESTADO" in str(exc.value)


def test_equ_referenciando_a_si_mesmo_em_passagens_diferentes_nao_e_colisao():
    """Guarda contra falso-positivo: o mesmo EQU fisico (uma unica linha) e
    reavaliado em TODA passagem (comentario original em legacy.py) -- isso
    NAO pode disparar a deteccao de EQU duplicado, ou toda montagem de duas
    passagens quebraria.
    """
    binario = montar(
        "    org 4000h\n"
        "TAM EQU FIM - INICIO\n"
        "INICIO:\n"
        "    nop\n    nop\n    nop\n"
        "FIM:\n"
        "    ld a,TAM\n"
    )
    assert binario[-1] == 3


def test_simbolo_de_bss_colidindo_com_label_de_rom_e_erro_ponta_a_ponta(tmp_path):
    """Prova ponta a ponta, pela CLI real (expandir -> expandir_macros ->
    expandir_locais -> msxasm.bss.extrair -> assemble): um simbolo BSS
    (ESTADO, endereco de RAM) e um label de codigo (ESTADO:, alvo de jp) com
    o MESMO NOME.

    tests/test_bss.py ja prova que dois simbolos BSS colidindo entre si sao
    pegos dentro do proprio extrair() -- isso NAO exercita este buraco,
    porque os dois nomes ali nunca chegam a virar um label de codigo.
    Este teste cobre o caso que so aparece depois que o Passo 5 da Tarefa 7
    injeta o mapa do BSS como linhas EQU na frente do fonte inteiro: sem a
    correcao em legacy.py, o EQU vencia em silencio, o label 'ESTADO:'
    sumia, e 'jp ESTADO' apontava para 0xC000 (o endereco de RAM) em vez do
    endereco real do label -- travamento sem nenhum erro de montagem.
    """
    fonte = tmp_path / "d.asm"
    fonte.write_text(
        "    org 4000h\n"
        "    BSS 0C000h\n"
        "ESTADO: DS 1\n"
        "    ENDBSS\n"
        "    jp ESTADO\n"
        "ESTADO:\n"
        "    ret\n"
    )

    r = rodar(str(fonte), "-o", str(tmp_path / "d.rom"))

    assert r.returncode == 1
    assert "ESTADO" in r.stderr
    assert "d.asm:6" in r.stderr, r.stderr    # o label de codigo que colidiu
    assert "<bss>" in r.stderr, r.stderr      # onde o simbolo BSS foi injetado
    assert not (tmp_path / "d.rom").exists(), "nao deve escrever ROM em caso de erro"
