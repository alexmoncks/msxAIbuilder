import pytest

from msxasm.errors import MontagemError
from msxasm.macro import expandir_macros
from msxasm.source import Linha


def linhas(*textos: str) -> list[Linha]:
    return [Linha(texto=t, arquivo="t.asm", numero=i) for i, t in enumerate(textos, 1)]


def textos(ls: list[Linha]) -> list[str]:
    return [l.texto.strip() for l in ls if l.texto.strip()]


def test_macro_sem_parametro():
    r = expandir_macros(linhas(
        "    MACRO ESPERA_VBLANK",
        "    in a,(099h)",
        "    ENDM",
        "    ESPERA_VBLANK",
    ))
    assert textos(r) == ["in a,(099h)"]


def test_macro_com_parametros_substitui_por_posicao():
    r = expandir_macros(linhas(
        "    MACRO VDP_REG reg,valor",
        "    ld a,valor",
        "    ld c,reg",
        "    ENDM",
        "    VDP_REG 7,0x0F",
    ))
    assert textos(r) == ["ld a,0x0F", "ld c,7"]


def test_duas_expansoes_nao_compartilham_label_local():
    r = expandir_macros(linhas(
        "    MACRO ATRASO n",
        "    ld b,n",
        "@@espera:",
        "    djnz @@espera",
        "    ENDM",
        "    ATRASO 10",
        "    ATRASO 20",
    ))
    rotulos = [t for t in textos(r) if t.endswith(":")]
    assert len(rotulos) == 2
    assert rotulos[0] != rotulos[1], "expansoes distintas nao podem gerar o mesmo label"


def test_numero_errado_de_argumentos_e_erro():
    with pytest.raises(MontagemError) as exc:
        expandir_macros(linhas(
            "    MACRO PAR a,b",
            "    ld a,a",
            "    ENDM",
            "    PAR 1",
        ))
    assert "argumento" in str(exc.value).lower()


def test_macro_sem_endm_e_erro():
    with pytest.raises(MontagemError) as exc:
        expandir_macros(linhas("    MACRO SOLTA", "    ret"))
    assert "ENDM" in str(exc.value)


# ---------------------------------------------------------------------------
# Ponto 1: substituicao de parametro por regex e perigosa se o nome do
# parametro colidir com um registrador (ou flag de condicao) do Z80. Um
# `\b{param}\b` sobre o corpo nao consegue distinguir "a, o parametro" de
# "a, o registrador" -- sao o mesmo token. Em vez de arriscar substituir um
# registrador de verdade em silencio (ex.: "ld c,a" virando "ld c,5" onde
# o "a" que sobrou era pra ser o registrador), a EXPANSAO (nao a definicao
# -- ver test_numero_errado_de_argumentos_e_erro acima, que define uma
# macro com parametros "a,b" e depende de nunca chegar a expandir) recusa
# com MontagemError assim que uma invocacao valida tentaria de fato
# substituir. Ver nota no relatorio da Tarefa 6 sobre esta decisao.
def test_parametro_com_nome_de_registrador_e_erro():
    with pytest.raises(MontagemError) as exc:
        expandir_macros(linhas(
            "    MACRO CARREGA a",
            "    ld c,a",
            "    ENDM",
            "    CARREGA 5",
        ))
    msg = str(exc.value).lower()
    assert "registrador" in msg or "reservado" in msg


def test_parametro_com_nome_de_flag_de_condicao_e_erro():
    with pytest.raises(MontagemError):
        expandir_macros(linhas(
            "    MACRO SALTA z",
            "    jp z,FIM",
            "    ENDM",
            "    SALTA FIM",
        ))


def test_macro_com_parametro_perigoso_nunca_invocada_nao_e_erro():
    # Definir uma macro com parametro de nome perigoso e inofensivo por si
    # so -- so a expansao de verdade poderia corromper algo. Uma macro
    # nunca chamada nao deve impedir a montagem do resto do arquivo.
    r = expandir_macros(linhas(
        "    MACRO NUNCA_USADA a",
        "    ld c,a",
        "    ENDM",
        "    ret",
    ))
    assert textos(r) == ["ret"]


# ---------------------------------------------------------------------------
# Ponto 2: substituicao de parametro (e o sufixo de label local) nao pode
# tocar o conteudo de uma string literal nem de um comentario -- mesma
# classe de bug da Tarefa 5 (labels.py): um DB com "n pontos" nao pode virar
# "7 pontos" so porque o parametro se chama "n".
def test_parametro_nao_substitui_dentro_de_string_literal():
    r = expandir_macros(linhas(
        "    MACRO MOSTRA n",
        '    db "n pontos"',
        "    ld a,n",
        "    ENDM",
        "    MOSTRA 7",
    ))
    assert textos(r) == ['db "n pontos"', "ld a,7"]


def test_parametro_nao_substitui_dentro_de_comentario():
    r = expandir_macros(linhas(
        "    MACRO ATRASO n",
        "    ld b,n        ; espera n ciclos",
        "    ENDM",
        "    ATRASO 5",
    ))
    assert textos(r) == ["ld b,5        ; espera n ciclos"]


def test_sufixo_de_label_local_nao_substitui_dentro_de_string_literal():
    r = expandir_macros(linhas(
        "    MACRO NOTA",
        '    db "vai para @@x"',
        "    ENDM",
        "    NOTA",
    ))
    assert textos(r) == ['db "vai para @@x"']


# ---------------------------------------------------------------------------
# Rodada de correcao 1: comentario na linha de INVOCACAO (nao no corpo) era
# cortado tarde demais -- ou nunca era cortado, e _dividir_args rodava sobre
# a linha inteira. Um ';' de verdade depois dos argumentos entrava no valor
# do ultimo argumento. Corrigido cortando o comentario da invocacao ANTES de
# dividir os argumentos (mesma _corta_comentario do corpo, um nivel acima).
# Os testes de bytes montados (comentario no meio e no fim da linha do
# corpo) estao em tests/test_cli.py, porque so a montagem completa prova o
# byte final -- ver os dois testes la para o caso que quebrava de verdade.
def test_ponto_e_virgula_dentro_de_string_do_argumento_nao_e_cortado_como_comentario():
    r = expandir_macros(linhas(
        "    MACRO MOSTRA txt",
        "    db txt",
        "    ENDM",
        '    MOSTRA "a;b"   ; comentario de verdade',
    ))
    assert textos(r) == ['db "a;b" ; comentario de verdade']


# ---------------------------------------------------------------------------
# Leva final de correcao: a linha de DEFINICAO da macro era o unico ponto da
# cadeia fora da convencao corta_comentario de msxasm.texto (que bss.py e
# mapper.py ja seguiam). O '(.*)$' do regex engolia o comentario inteiro como
# lista de parametros.
def test_comentario_na_linha_de_definicao_nao_vira_parametro():
    r = expandir_macros(linhas(
        "    MACRO CARREGA v      ; carrega v no acumulador",
        "    ld a,v",
        "    ENDM",
        "    CARREGA 7",
    ))
    assert textos(r) == ["ld a,7"]


def test_virgula_dentro_do_comentario_da_definicao_nao_inventa_parametro():
    """O caso pior: com virgula no comentario (idiomatico em assembly) o
    erro era INVENTADO -- 'macro CARREGA espera 2 argumento(s), recebeu 1'
    para um fonte perfeitamente valido.
    """
    r = expandir_macros(linhas(
        "    MACRO CARREGA v      ; carrega v, depois retorna",
        "    ld a,v",
        "    ret",
        "    ENDM",
        "    CARREGA 7",
    ))
    assert textos(r) == ["ld a,7", "ret"]


def test_redefinicao_de_macro_e_erro_citando_as_duas_localizacoes():
    """Coerente com label redefinido (Tarefa 5), EQU redefinido e simbolo BSS
    duplicado (Tarefa 7). Antes a segunda definicao vencia em silencio: dois
    modulos do runtime que definissem WAIT_VBLANK colidiam e o build ficava
    com a definicao do modulo errado, sem erro nenhum.
    """
    with pytest.raises(MontagemError) as exc:
        expandir_macros(linhas(
            "    MACRO CARREGA",
            "    ld a,7",
            "    ENDM",
            "    MACRO CARREGA",
            "    ld b,7",
            "    ENDM",
            "    CARREGA",
        ))
    msg = str(exc.value)
    assert "CARREGA" in msg
    assert "t.asm:1" in msg      # primeira definicao
    assert "t.asm:4" in msg      # segunda definicao, onde o erro e citado
