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
    assert mapa["RESIDENTE"] == [(0, 0x4000)]
    assert mapa["DADOS"] == [(3, 0xA000)], "banco 3 declarou WINDOW 0A000h"


def test_banco_que_nao_cabe_na_janela_e_erro():
    layout = LAYOUTS["KONAMI"]
    with pytest.raises(MontagemError) as exc:
        montar(layout, 32768, {1: banco(1, 0x6000, "    ds 9000")}, [])
    assert "banco 1" in str(exc.value).lower()
    assert "8192" in str(exc.value)


def test_org_do_fonte_manda_e_nao_dispara_zero_fill():
    """Regressao da Tarefa 9: a linha 'org' sintetica entrava SEMPRE, na
    frente de tudo. Se o fonte declarava o seu proprio 'org' com valor
    diferente, o ramo de preenchimento de _directive ('if v >
    current_address and current_address > 0') zero-preenchia a diferenca --
    duas linhas de assembly viravam 16385 bytes e o cartucho estourava.
    """
    img, _ = montar(LAYOUTS["FLAT"], 16384,
                    {0: banco(0, 0x4000, "    org 8000h", "    ret")},
                    [], org=0x4000)
    assert len(img) == 16384
    assert img[0] == 0xC9, "o 'ret' tem que ser o primeiro byte, sem zero-fill antes"
    assert img[1] == 0xFF


def test_org_injetado_continua_valendo_quando_o_fonte_se_cala():
    """O que a injecao resolve nao pode ser perdido: um banco paginado so
    tem WINDOW na diretiva BANK, nunca um 'org' escrito a mao, e sem a
    injecao todo label dele sai com o endereco errado.
    """
    _, mapa = montar(LAYOUTS["KONAMI"], 32768,
                     {1: banco(1, 0x8000, "DADOS:", "    db 1")}, [])
    assert mapa["DADOS"] == [(1, 0x8000)]


def test_simbolo_do_banco_residente_e_visivel_dos_outros_bancos():
    """A spec 4.4 diz que simbolo passa a ser (banco, endereco). O que
    existia eram tabelas por banco, isoladas: um 'call RT_INIT' do banco 1
    para o trampolim RESIDENTE -- que esta sempre mapeado e e obrigatorio,
    porque codigo que pagina nao pode ser paginado embaixo de si mesmo --
    simplesmente nao montava.
    """
    layout = LAYOUTS["KONAMI"]
    img, mapa = montar(layout, 32768, {
        0: banco(0, 0x4000, '    db "AB"', "RT_INIT:", "    ret"),
        1: banco(1, 0x8000, "    call RT_INIT"),
    }, [])
    assert mapa["RT_INIT"] == [(0, 0x4002)]
    assert list(img[8192:8195]) == [0xCD, 0x02, 0x40], "call RT_INIT -> 0x4002"


def test_simbolo_de_banco_paginado_continua_invisivel_de_outro_banco():
    """O oposto tem que continuar falhando: um call direto para um banco que
    pode nao estar mapeado e justamente o que a spec quer recusar.
    """
    layout = LAYOUTS["KONAMI"]
    with pytest.raises(MontagemError) as exc:
        montar(layout, 32768, {
            0: banco(0, 0x4000, '    db "AB"'),
            1: banco(1, 0x8000, "ALVO:", "    ret"),
            2: banco(2, 0x8000, "    call ALVO"),
        }, [])
    assert "ALVO" in str(exc.value)


def test_label_local_vence_o_simbolo_semeado_do_residente():
    layout = LAYOUTS["KONAMI"]
    img, mapa = montar(layout, 32768, {
        0: banco(0, 0x4000, '    db "AB"', "LOOP:", "    jp LOOP"),
        1: banco(1, 0x8000, "    nop", "LOOP:", "    jp LOOP"),
    }, [])
    assert list(img[8193:8196]) == [0xC3, 0x01, 0x80], \
        "jp LOOP no banco 1 aponta para o LOOP do banco 1, nao para o do residente"


def test_mapa_guarda_todas_as_definicoes_de_um_nome_homonimo():
    """O mapa e a unica ferramenta de depuracao de MegaROM que a ferramenta
    emite. 'LOOP:' no banco 0 e 'LOOP:' no banco 1 e legitimo (bancos sao
    espacos de endereco separados) e produzia UMA entrada, a do ultimo banco
    processado: resposta errada com cara de certa.
    """
    layout = LAYOUTS["KONAMI"]
    _, mapa = montar(layout, 32768, {
        0: banco(0, 0x4000, "INICIO:", "    nop", "LOOP:", "    nop"),
        1: banco(1, 0x8000, "LOOP:", "    nop"),
    }, [])
    assert sorted(mapa["LOOP"]) == [(0, 0x4001), (1, 0x8000)]
    assert mapa["INICIO"] == [(0, 0x4000)]
    assert sum(len(v) for v in mapa.values()) == 3


# ---------------------------------------------------------------------------
# Adjudicacao: as duas quebras deixadas em aberto pela leva anterior. Trocar a
# injecao incondicional do org sintetico por deteccao textual resolveu a
# regressao principal, mas removeu o efeito colateral (o zero-fill) do qual
# estes casos dependiam -- sem por no lugar a validacao que devia substitui-lo.


def test_org_do_fonte_divergindo_da_janela_do_banco_e_erro():
    """Quebra 1: 'org 9000h' num banco com WINDOW 8000h nao move o banco para
    lugar nenhum -- o codigo fica no offset 0 do banco (CPU 0x8000) enquanto
    os labels saem calculados a partir de 0x9000. O 'jp ALVO' montava
    'C3 00 90', apontando para preenchimento 0xFF, com ROM gravada e codigo
    de saida 0.
    """
    layout = LAYOUTS["KONAMI"]
    with pytest.raises(MontagemError) as exc:
        montar(layout, 65536, {
            0: banco(0, 0x4000, '    db "AB"'),
            1: banco(1, 0x8000, "    org 9000h", "ALVO:", "    jp ALVO"),
        }, [])
    msg = str(exc.value)
    assert "t.asm:1" in msg, msg          # arquivo e linha do org
    assert "0x9000" in msg, msg           # o valor encontrado
    assert "0x8000" in msg, msg           # a janela esperada
    assert "banco 1" in msg, msg


def test_org_que_coincide_com_a_janela_do_banco_continua_montando():
    """Divergir e erro; concordar nao. Um fonte que escreve o org certo a mao
    continua valido -- e o org sintetico injetado quando o fonte se cala e
    exatamente esse caso, entao ele nao pode disparar a checagem.
    """
    layout = LAYOUTS["KONAMI"]
    img, mapa = montar(layout, 32768, {
        0: banco(0, 0x4000, '    db "AB"'),
        1: banco(1, 0x8000, "    org 8000h", "ALVO:", "    jp ALVO"),
    }, [])
    assert mapa["ALVO"] == [(1, 0x8000)]
    assert list(img[8192:8195]) == [0xC3, 0x00, 0x80]


def test_org_divergente_em_flat_continua_valendo():
    """FLAT nao tem janela a respeitar: la o org do fonte manda e o --org da
    CLI e so o padrao (guarda do conserto ao lado, que nao pode vazar para o
    caminho comum -- o do golden).
    """
    img, _ = montar(LAYOUTS["FLAT"], 16384,
                    {0: banco(0, 0x4000, "    org 8000h", "    ret")},
                    [], org=0x4000)
    assert img[0] == 0xC9
