# tests/test_mapper.py
import pytest

from msxasm.errors import MontagemError
from msxasm.mapper import LAYOUTS, hint_de_arquivo, particionar
from msxasm.source import Linha


def linhas(*textos: str) -> list[Linha]:
    return [Linha(texto=t, arquivo="t.asm", numero=i) for i, t in enumerate(textos, 1)]


def test_konami_tem_janela_residente_em_4000h():
    k = LAYOUTS["KONAMI"]
    assert k.tamanho_banco == 8192
    assert k.janelas == (0x4000, 0x6000, 0x8000, 0xA000)
    assert k.janela_residente == 0x4000


def test_konami_em_2mb_da_256_bancos():
    k = LAYOUTS["KONAMI"]
    assert 2 * 1024 * 1024 // k.tamanho_banco == 256
    assert k.max_bancos == 256


def test_hint_de_formato_entra_no_nome_do_arquivo():
    assert hint_de_arquivo("meujogo", LAYOUTS["KONAMI"]) == "meujogo [Konami].rom"


def test_flat_nao_recebe_hint():
    assert hint_de_arquivo("pong", LAYOUTS["FLAT"]) == "pong.rom"


def test_particiona_linhas_por_banco():
    layout, tamanho, bancos = particionar(linhas(
        "    MAPPER KONAMI, 2048K",
        "    BANK 0",
        "    org 4000h",
        "    ret",
        "    BANK 12 WINDOW 8000h",
        "    db 1,2,3",
    ))
    assert layout.nome == "KONAMI"
    assert tamanho == 2 * 1024 * 1024
    assert set(bancos) == {0, 12}
    assert any("ret" in l.texto for l in bancos[0].linhas)
    assert any("db 1,2,3" in l.texto for l in bancos[12].linhas)


def test_banco_guarda_a_janela_declarada():
    _, _, bancos = particionar(linhas(
        "    MAPPER KONAMI, 64K",
        "    BANK 0",
        "    ret",
        "    BANK 1 WINDOW 8000h",
        "    ret",
        "    BANK 2 WINDOW 0A000h",
        "    ret",
    ))
    assert bancos[0].janela == 0x4000     # residente, janela implicita
    assert bancos[1].janela == 0x8000
    assert bancos[2].janela == 0xA000


def test_banco_sem_window_explicito_usa_a_primeira_paginavel():
    _, _, bancos = particionar(linhas("    MAPPER KONAMI, 64K", "    BANK 5", "    ret"))
    assert bancos[5].janela == 0x6000


def test_banco_acima_do_maximo_e_erro():
    with pytest.raises(MontagemError) as exc:
        particionar(linhas("    MAPPER KONAMI, 64K", "    BANK 99"))
    assert "99" in str(exc.value)


def test_janela_inexistente_no_mapper_e_erro():
    with pytest.raises(MontagemError) as exc:
        particionar(linhas("    MAPPER KONAMI, 64K", "    BANK 1 WINDOW 0C000h"))
    assert "janela" in str(exc.value).lower()


def test_tamanho_acima_do_teto_do_mapper_e_erro():
    with pytest.raises(MontagemError) as exc:
        particionar(linhas("    MAPPER KONAMI, 4096K"))
    assert "2048" in str(exc.value) or "teto" in str(exc.value).lower()


def test_fonte_sem_mapper_e_flat():
    layout, tamanho, bancos = particionar(linhas("    org 4000h", "    ret"))
    assert layout.nome == "FLAT"
    assert set(bancos) == {0}


# Rodada de correcao 1: _numero() nao pode deixar ValueError escapar cru, e
# uma diretiva MAPPER/BANK malformada nao pode ser tratada como codigo
# comum em silencio -- a mesma classe de furo que a Tarefa 7 corrigiu em
# bss.py, reaberta aqui porque o codigo veio verbatim do mesmo brief.

def test_janela_nao_numerica_e_montagem_error_com_arquivo_e_linha():
    with pytest.raises(MontagemError) as exc:
        particionar(linhas("    MAPPER KONAMI, 64K", "    BANK 1 WINDOW ZZZZ"))
    assert exc.value.arquivo == "t.asm"
    assert exc.value.linha == 2


def test_tamanho_de_mapper_malformado_e_montagem_error_com_arquivo_e_linha():
    with pytest.raises(MontagemError) as exc:
        particionar(linhas("    MAPPER KONAMI, 64X"))
    assert exc.value.arquivo == "t.asm"
    assert exc.value.linha == 1


def test_bank_com_operando_nao_numerico_e_erro_de_sintaxe_nao_silencio():
    with pytest.raises(MontagemError) as exc:
        particionar(linhas("    MAPPER KONAMI, 64K", "    BANK ABC"))
    assert exc.value.linha == 2
    assert exc.value.arquivo == "t.asm"


def test_mapper_sem_virgula_antes_do_tamanho_tambem_e_erro_de_sintaxe():
    # Forma malformada diferente das anteriores (falta a virgula, nao um
    # numero invalido) -- prova que a protecao cobre a CLASSE de diretiva
    # malformada, tanto em MAPPER quanto em BANK, nao so os dois literais
    # que o revisor reproduziu.
    with pytest.raises(MontagemError) as exc:
        particionar(linhas("    MAPPER KONAMI 64K"))
    assert exc.value.linha == 1
    assert exc.value.arquivo == "t.asm"
