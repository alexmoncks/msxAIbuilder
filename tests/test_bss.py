import pytest

from msxasm.bss import extrair
from msxasm.errors import MontagemError
from msxasm.source import Linha


def linhas(*textos: str) -> list[Linha]:
    return [Linha(texto=t, arquivo="t.asm", numero=i) for i, t in enumerate(textos, 1)]


def enderecos(mapa) -> dict[str, int]:
    """extrair() devolve Simbolo (nome, endereco, tamanho, arquivo, numero),
    nao um int solto: os testes que so olham o endereco passam por aqui.
    """
    return {nome: s.endereco for nome, s in mapa.items()}


def test_aloca_sequencialmente_a_partir_da_base():
    _, mapa = extrair(linhas(
        "    BSS 0C000h",
        "MUS_PTR:  DS 2",
        "MUS_TICK: DS 1",
        "MUS_VOZ:  DS 6",
        "    ENDBSS",
    ))
    assert enderecos(mapa) == {"MUS_PTR": 0xC000, "MUS_TICK": 0xC002, "MUS_VOZ": 0xC003}


def test_blocos_de_modulos_diferentes_se_concatenam():
    _, mapa = extrair(linhas(
        "    BSS 0C000h",
        "A: DS 4",
        "    ENDBSS",
        "    BSS",
        "B: DS 2",
        "    ENDBSS",
    ))
    assert enderecos(mapa) == {"A": 0xC000, "B": 0xC004}


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


def test_simbolo_duplicado_e_insensivel_a_caixa():
    """Rodada de correcao 1: a resolucao de label/equate e insensivel a
    caixa desde a Tarefa 5 -- 'Estado' e 'ESTADO' sao o MESMO simbolo. Sem
    normalizar a comparacao de duplicata, os dois modulos abaixo recebiam
    enderecos de RAM DIFERENTES em silencio: e a classe exata de corrupcao
    que o BSS existe para eliminar.
    """
    with pytest.raises(MontagemError) as exc:
        extrair(linhas(
            "    BSS 0C000h", "Estado: DS 1", "    ENDBSS",
            "    BSS", "ESTADO: DS 1", "    ENDBSS",
        ))
    msg = str(exc.value)
    assert "estado" in msg.lower()
    assert "duplicad" in msg.lower()
    assert "t.asm:2" in msg      # primeira declaracao ('Estado:')
    assert "t.asm:5" in msg      # segunda declaracao ('ESTADO:'), onde o erro e citado


def test_comentario_colado_sem_espaco_no_cabecalho_bss_nao_quebra():
    """Rodada de correcao 1: 'BSS;continua' (sem espaco antes do ';') fazia
    o '(\\S+)?' do _BSS engolir ';continua' inteiro como se fosse o
    endereco base, e a conversao numerica escapava como ValueError cru em
    vez de MontagemError. Aqui o bloco e o primeiro da lista (sem base
    anterior), entao o resultado correto e o erro de "precisa base", nunca
    um traceback.
    """
    with pytest.raises(MontagemError) as exc:
        extrair(linhas("BSS;continua", "V: DS 1", "ENDBSS"))
    assert "base" in str(exc.value).lower()


def test_comentario_colado_sem_espaco_no_ds_e_apenas_comentario():
    """Mesma classe de furo do teste acima, no outro ponto onde '(\\S+)' e
    guloso: 'V: DS 1;comentario' (comentario colado, sem espaco) e uso
    normal -- o assembler deve ler DS 1 e ignorar o comentario, nao
    quebrar com ValueError cru.
    """
    _, mapa = extrair(linhas(
        "BSS 0C000h",
        "V: DS 1;comentario",
        "ENDBSS",
    ))
    assert enderecos(mapa) == {"V": 0xC000}


def test_numero_invalido_dentro_de_bss_e_montagem_error_nao_traceback():
    """Guarda mais ampla pedida na revisao: qualquer entrada malformada
    dentro de um bloco BSS (nao so as duas reproducoes especificas acima)
    sai como MontagemError com arquivo e linha, nunca como ValueError cru.
    """
    with pytest.raises(MontagemError) as exc:
        extrair(linhas("BSS ZZZZ", "V: DS 1", "ENDBSS"))
    assert "invalido" in str(exc.value).lower()


def test_bases_declaradas_que_se_sobrepoem_sao_erro():
    """Achado Critical da revisao final: a deteccao de nome duplicado cobria
    metade do problema. Dois modulos que declarem cada um a SUA base -- e
    declarar a base e o que o exemplo da spec 4.3 mostra -- recebiam nomes
    diferentes nos MESMOS enderecos de RAM, sem erro. A ROM montava, rodava,
    e as variaveis dos dois modulos se corrompiam mutuamente: e exatamente o
    modo de falha que o BSS inteiro existe para eliminar.
    """
    with pytest.raises(MontagemError) as exc:
        extrair(linhas(
            "    BSS 0C000h", "A1: DS 4", "    ENDBSS",
            "    BSS 0C000h", "B1: DS 4", "    ENDBSS",
        ))
    msg = str(exc.value)
    assert "sobrep" in msg.lower()
    assert "A1" in msg and "B1" in msg
    assert "t.asm:2" in msg      # a faixa que ja estava alocada
    assert "t.asm:5" in msg      # a faixa nova, onde o erro e citado


def test_sobreposicao_parcial_de_faixas_tambem_e_erro():
    """Nao basta detectar bases iguais: uma base declarada NO MEIO de uma
    faixa ja alocada corrompe do mesmo jeito, e com nomes que nunca se
    repetem a checagem de duplicata nao ve nada.
    """
    with pytest.raises(MontagemError) as exc:
        extrair(linhas(
            "    BSS 0C000h", "BUFFER: DS 16", "    ENDBSS",
            "    BSS 0C008h", "OUTRO: DS 2", "    ENDBSS",
        ))
    assert "sobrep" in str(exc.value).lower()
    assert "BUFFER" in str(exc.value)


def test_base_declarada_depois_da_faixa_anterior_continua_valida():
    """A recusa e de SOBREPOSICAO, nao de redeclarar base: um modulo que
    escolhe uma regiao propria de RAM, sem encostar na do outro, e uso
    legitimo e tem que continuar montando.
    """
    _, mapa = extrair(linhas(
        "    BSS 0C000h", "A: DS 4", "    ENDBSS",
        "    BSS 0D000h", "B: DS 4", "    ENDBSS",
    ))
    assert enderecos(mapa) == {"A": 0xC000, "B": 0xD000}


def test_simbolo_carrega_arquivo_e_linha_da_declaracao():
    """Procedencia real, para que o EQU sintetico gerado a partir daqui
    (msxasm/cli.py) aponte para a linha que a pessoa escreveu, e nao para
    '<bss>:N'.
    """
    _, mapa = extrair(linhas(
        "    BSS 0C000h",
        "MUS_PTR: DS 2",
        "    ENDBSS",
    ))
    assert mapa["MUS_PTR"].arquivo == "t.asm"
    assert mapa["MUS_PTR"].numero == 2
    assert mapa["MUS_PTR"].tamanho == 2
    assert mapa["MUS_PTR"].origem == "t.asm:2"


def test_base_em_grafia_0x_continua_aceita_pela_gramatica_unificada():
    """A gramatica numerica passou a morar em msxasm.numero, compartilhada
    com mapper.py e com a CLI. As tres formas que o BSS ja aceitava
    (0C000h, 0xC000, decimal) continuam valendo.
    """
    _, mapa = extrair(linhas("    BSS 0xC000", "V: DS 1", "    ENDBSS"))
    assert enderecos(mapa) == {"V": 0xC000}
