# tests/test_cli.py
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def rodar(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "msxasm", *args],
        cwd=RAIZ, capture_output=True, text=True,
    )


def test_monta_arquivo_e_devolve_zero(tmp_path):
    fonte = tmp_path / "t.asm"
    fonte.write_text("    org 4000h\n    ld a,1\n    ret\n")
    saida = tmp_path / "t.rom"

    r = rodar(str(fonte), "-o", str(saida), "--org", "0x4000", "--size", "8K")

    assert r.returncode == 0, r.stderr
    assert saida.stat().st_size == 8192
    assert saida.read_bytes()[:4] == bytes([0x3E, 0x01, 0xC9, 0xFF])


def test_erro_de_simbolo_reporta_arquivo_e_linha(tmp_path):
    fonte = tmp_path / "ruim.asm"
    fonte.write_text("    org 4000h\n    ld a,1\n    ld hl,FANTASMA\n")

    r = rodar(str(fonte), "-o", str(tmp_path / "x.rom"))

    assert r.returncode == 1
    assert "ruim.asm:3" in r.stderr
    assert "FANTASMA" in r.stderr
    assert not (tmp_path / "x.rom").exists(), "nao deve escrever ROM em caso de erro"


def test_binario_maior_que_o_cartucho_e_erro(tmp_path):
    fonte = tmp_path / "grande.asm"
    fonte.write_text("    org 4000h\n" + "    ds 200\n" * 60)   # 12000 bytes

    r = rodar(str(fonte), "-o", str(tmp_path / "g.rom"), "--size", "8K")

    assert r.returncode == 1
    assert "nao cabe" in r.stderr.lower()


def test_mnemonico_desconhecido_reporta_arquivo_e_linha(tmp_path):
    """Furo encontrado na revisao da Tarefa 2: _encode levanta ValueError puro
    para mnemonico desconhecido, e o mecanismo legado em assemble acumulava
    isso em self.erros para sair via SystemExit -- sem arquivo, sem linha.
    Isso escapava do "except MontagemError" da CLI e saia sem localizacao
    nenhuma, o oposto do que esta tarefa promete.
    """
    fonte = tmp_path / "ruim2.asm"
    fonte.write_text("    org 4000h\n    ld a,1\n    fooble a,b\n")

    r = rodar(str(fonte), "-o", str(tmp_path / "y.rom"))

    assert r.returncode == 1
    assert "ruim2.asm:3" in r.stderr
    assert "fooble" in r.stderr.lower()
    assert not (tmp_path / "y.rom").exists(), "nao deve escrever ROM em caso de erro"


def test_db_sem_operando_reporta_arquivo_e_linha(tmp_path):
    """Achado Important da rodada de correcao 1: _directive() e chamado fora
    de qualquer try/except em assemble(), e _parse_nums(None) levanta um
    TypeError cru ("object of type 'NoneType' has no len()") quando DB nao
    tem operando. Isso escapava do "except MontagemError" da CLI e saia como
    traceback bruto, sem arquivo nem linha.
    """
    fonte = tmp_path / "semoperando.asm"
    fonte.write_text("    org 4000h\n    ld a,1\n    db\n")

    r = rodar(str(fonte), "-o", str(tmp_path / "z.rom"))

    assert r.returncode == 1
    assert "semoperando.asm:3" in r.stderr
    assert not (tmp_path / "z.rom").exists(), "nao deve escrever ROM em caso de erro"


def test_dw_sem_operando_tambem_reporta_arquivo_e_linha(tmp_path):
    """Mesma garantia para outra diretiva (DW), para provar que a correcao e
    do caminho -- o try/except em torno de _directive() -- e nao um remendo
    especifico para DB.
    """
    fonte = tmp_path / "semoperando2.asm"
    fonte.write_text("    org 4000h\n    ld a,1\n    dw\n")

    r = rodar(str(fonte), "-o", str(tmp_path / "w.rom"))

    assert r.returncode == 1
    assert "semoperando2.asm:3" in r.stderr
    assert not (tmp_path / "w.rom").exists(), "nao deve escrever ROM em caso de erro"


def test_local_em_caixa_mista_resolve_ponta_a_ponta(tmp_path):
    """Rodada de correcao 1 da Tarefa 5: o mecanismo de macros da Tarefa 6
    sufixa labels locais de cada expansao com '_m{contador}' em minusculo,
    entao um '@@ESPERA' dentro de uma macro vira '@@ESPERA_m1' apos
    expandir_locais, e o label final e de caixa mista
    ('PSG_ON@@ESPERA_m1'). Antes da correcao de case-folding em _eval, so
    labels 100% maiusculos resolviam -- toda macro com label local
    quebraria a montagem. Este teste exercita a cadeia real da CLI
    (expandir -> expandir_locais -> assemble), nao so expandir_locais
    isolado.
    """
    fonte = tmp_path / "modulo.asm"
    fonte.write_text(
        "    org 4000h\n"
        "PSG_ON:\n"
        "@@ESPERA_m1:\n"
        "    djnz @@ESPERA_m1\n"
        "    ret\n"
    )
    saida = tmp_path / "modulo.rom"

    r = rodar(str(fonte), "-o", str(saida), "--org", "0x4000", "--size", "8K")

    assert r.returncode == 0, r.stderr
    binario = saida.read_bytes()
    assert binario[0] == 0x10          # DJNZ
    assert binario[1] == 0xFE          # salta para si mesmo
    assert binario[2] == 0xC9          # RET


def test_macro_invocada_duas_vezes_monta_sem_erro_de_label_redefinido(tmp_path):
    """Tarefa 6: prova ponta a ponta de que o sufixo por expansao funciona.

    expandir_macros roda ANTES de expandir_locais (ver comentario na cadeia
    em cli.py). Sem o sufixo '_m{contador}' por expansao, as duas chamadas
    de TABELA abaixo gerariam o mesmo '@@dados:' duas vezes sob o mesmo
    escopo global (INICIO), e a deteccao de label redefinido da Tarefa 5
    (MontagemError dentro da mesma passagem) pegaria a colisao.

    Rodada de correcao 2: a primeira versao deste teste usava um corpo
    autorreferente ('djnz @@espera', saltando para si mesmo) -- um salto
    RELATIVO que codifica -2 (0xFE) independente do endereco do label. A
    asercao de bytes so provava 'a montagem nao deu erro' (a deteccao de
    redefinicao da Tarefa 5); nao provava que os dois labels resolveram
    para enderecos DIFERENTES. Se o sufixo colidisse por algum motivo e as
    duas expansoes apontassem para o MESMO endereco, o byte -2 continuaria
    identico e a asercao nao teria como perceber.

    Corpo novo: 'ld hl,@@dados' e uma referencia ABSOLUTA ao proprio
    label -- o endereco de 16 bits fica gravado literalmente nos bytes da
    instrucao. A segunda expansao comeca 5 bytes depois da primeira
    (tamanho fixo do corpo), entao os bytes so batem com o valor esperado
    se 'INICIO@@dados_m1' e 'INICIO@@dados_m2' resolverem para enderecos
    distintos de verdade -- prova direta do endereco, nao por ausencia de
    erro.
    """
    fonte = tmp_path / "tabela.asm"
    fonte.write_text(
        "    org 4000h\n"
        "    MACRO TABELA n\n"
        "@@dados:\n"
        "    ld hl,@@dados\n"
        "    ld a,n\n"
        "    ENDM\n"
        "INICIO:\n"
        "    TABELA 5\n"
        "    TABELA 10\n"
        "    ret\n"
    )
    saida = tmp_path / "tabela.rom"

    r = rodar(str(fonte), "-o", str(saida), "--org", "0x4000", "--size", "8K")

    assert r.returncode == 0, r.stderr
    binario = saida.read_bytes()
    # 1a expansao: INICIO@@dados_m1 = 0x4000 -> ld hl,4000h / ld a,5
    assert binario[0:5] == bytes([0x21, 0x00, 0x40, 0x3E, 0x05])
    # 2a expansao: INICIO@@dados_m2 = 0x4005 -> ld hl,4005h / ld a,10
    # (endereco DIFERENTE do primeiro -- prova que os labels nao colidiram)
    assert binario[5:10] == bytes([0x21, 0x05, 0x40, 0x3E, 0x0A])
    assert binario[10] == 0xC9


def test_macro_com_parametro_no_meio_da_linha_e_comentario_na_invocacao_monta_bytes_certos(tmp_path):
    """Rodada de correcao 1 da Tarefa 6.

    Reproduz o caso relatado: com o parametro usado no MEIO da linha do
    corpo (nao no fim), o comentario da linha de invocacao entrava no valor
    do argumento antes da correcao -- 'GUARDA 0C000h   ; salva estado'
    expandia para 'ld (0C000h   ; salva estado),a', e a montagem falhava com
    um erro interno de Python ('not enough values to unpack'), sem relacao
    nenhuma com o texto escrito. Aqui a montagem tem que completar e os
    bytes tem que estar corretos -- nao so ausencia de excecao.
    """
    fonte = tmp_path / "guarda.asm"
    fonte.write_text(
        "    org 4000h\n"
        "    MACRO GUARDA dst\n"
        "    ld (dst),a\n"
        "    ENDM\n"
        "    ld a,1\n"
        "    GUARDA 0C000h   ; salva estado\n"
        "    ret\n"
    )
    saida = tmp_path / "guarda.rom"

    r = rodar(str(fonte), "-o", str(saida), "--org", "0x4000", "--size", "8K")

    assert r.returncode == 0, r.stderr
    binario = saida.read_bytes()
    # ld a,1 / ld (0C000h),a / ret
    assert binario[0:2] == bytes([0x3E, 0x01])
    assert binario[2:5] == bytes([0x32, 0x00, 0xC0])
    assert binario[5] == 0xC9


def test_macro_com_parametro_no_fim_da_linha_e_comentario_na_invocacao_monta_bytes_certos(tmp_path):
    """Antes da correcao, este caso 'passava' so por acidente: o parametro
    usado no FIM da linha do corpo fazia o comentario colado ficar no fim
    do valor substituido, e como esse era o ultimo token da linha expandida,
    o corte de comentario em legacy.py ainda separava tudo corretamente por
    coincidencia de posicao -- nao porque a substituicao estivesse certa.
    Preservado como teste de regressao, verificando os BYTES montados (nao
    so a ausencia de excecao, que e o que fazia esse caso parecer correto
    antes da correcao).
    """
    fonte = tmp_path / "vdp.asm"
    fonte.write_text(
        "    org 4000h\n"
        "    MACRO VDP_REG reg,valor\n"
        "    ld a,valor\n"
        "    ld c,reg\n"
        "    ENDM\n"
        "    VDP_REG 7,0x0F   ; liga sprites\n"
        "    ret\n"
    )
    saida = tmp_path / "vdp.rom"

    r = rodar(str(fonte), "-o", str(saida), "--org", "0x4000", "--size", "8K")

    assert r.returncode == 0, r.stderr
    binario = saida.read_bytes()
    # ld a,0x0F / ld c,7 / ret
    assert binario[0:2] == bytes([0x3E, 0x0F])
    assert binario[2:4] == bytes([0x0E, 0x07])
    assert binario[4] == 0xC9


def test_locais_identicos_sob_globais_diferentes_continuam_validos(tmp_path):
    """Rodada de correcao 2 da Tarefa 5: a deteccao de label global
    redefinido NAO pode confundir '@@LOOP' definido sob 'PSG_ON:' com
    '@@LOOP' definido sob 'FM_ON:' -- depois do escopamento de
    expandir_locais eles sao simbolos distintos ('PSG_ON@@LOOP' e
    'FM_ON@@LOOP'), exatamente o caso de uso que a Tarefa 5 original
    existe para resolver.
    """
    fonte = tmp_path / "runtime.asm"
    fonte.write_text(
        "    org 4000h\n"
        "PSG_ON:\n"
        "@@LOOP:\n"
        "    djnz @@LOOP\n"
        "    ret\n"
        "FM_ON:\n"
        "@@LOOP:\n"
        "    djnz @@LOOP\n"
        "    ret\n"
    )
    saida = tmp_path / "runtime.rom"

    r = rodar(str(fonte), "-o", str(saida), "--org", "0x4000", "--size", "8K")

    assert r.returncode == 0, r.stderr
    binario = saida.read_bytes()
    # PSG_ON: djnz PSG_ON@@LOOP ; ret
    assert binario[0:3] == bytes([0x10, 0xFE, 0xC9])
    # FM_ON: djnz FM_ON@@LOOP ; ret (mesmo padrao, endereco proprio)
    assert binario[3:6] == bytes([0x10, 0xFE, 0xC9])


def test_label_global_colidindo_entre_dois_includes_e_erro_nomeando_os_dois_arquivos(tmp_path):
    """O cenario real da biblioteca de runtime: dois modulos incluidos
    (vdp.asm e sprite.asm) declaram o mesmo label global (VDP_INIT). Sem
    deteccao, a segunda definicao venceria em silencio e toda chamada
    para VDP_INIT iria para o modulo errado -- travamento em runtime, sem
    erro de montagem nenhum. A mensagem precisa nomear os DOIS arquivos:
    onde a colisao foi detectada (segunda definicao) e onde foi a
    primeira.
    """
    (tmp_path / "vdp.asm").write_text("; cabecalho vdp\nVDP_INIT:\n    nop\n    ret\n")
    (tmp_path / "sprite.asm").write_text("; cabecalho sprite\nVDP_INIT:\n    nop\n    ret\n")
    principal = tmp_path / "jogo.asm"
    principal.write_text(
        '    org 4000h\n'
        '    INCLUDE "vdp.asm"\n'
        '    INCLUDE "sprite.asm"\n'
    )

    r = rodar(str(principal), "-o", str(tmp_path / "j.rom"))

    assert r.returncode == 1
    assert "sprite.asm:2" in r.stderr, r.stderr    # segunda definicao
    assert "vdp.asm:2" in r.stderr, r.stderr       # primeira definicao, citada
    assert "VDP_INIT" in r.stderr
    assert not (tmp_path / "j.rom").exists(), "nao deve escrever ROM em caso de erro"


def test_erro_dentro_de_include_aponta_o_modulo(tmp_path):
    (tmp_path / "rt.asm").write_text("; cabecalho\n    ld hl,SUMIDO\n")
    principal = tmp_path / "jogo.asm"
    principal.write_text('    org 4000h\n    INCLUDE "rt.asm"\n')

    r = rodar(str(principal), "-o", str(tmp_path / "j.rom"))

    assert r.returncode == 1
    assert "rt.asm:2" in r.stderr, r.stderr
    assert "SUMIDO" in r.stderr


def test_mnemonico_desconhecido_dentro_de_include_aponta_o_modulo(tmp_path):
    """Mesma garantia do teste de simbolo inexistente dentro de INCLUDE, mas
    para o caminho de codificacao de instrucao (mnemonico desconhecido). A
    correcao de procedencia da Tarefa 4 originalmente so cobria _eval; este
    teste prova que o helper _origem() tambem cobre este segundo ponto de
    erro em assemble().
    """
    (tmp_path / "vdp.asm").write_text("; cabecalho\n    fooble a,b\n")
    principal = tmp_path / "jogo.asm"
    principal.write_text('    org 4000h\n    INCLUDE "vdp.asm"\n')

    r = rodar(str(principal), "-o", str(tmp_path / "j.rom"))

    assert r.returncode == 1
    assert "vdp.asm:2" in r.stderr, r.stderr
    assert "jogo.asm:2" not in r.stderr, r.stderr
    assert "fooble" in r.stderr.lower()
    assert not (tmp_path / "j.rom").exists(), "nao deve escrever ROM em caso de erro"


def test_diretiva_malformada_dentro_de_include_aponta_o_modulo(tmp_path):
    """Mesma garantia, para o terceiro ponto de erro em assemble() (diretiva
    malformada, ex.: DB sem operando).
    """
    (tmp_path / "sprite.asm").write_text("; cabecalho\n    db\n")
    principal = tmp_path / "jogo.asm"
    principal.write_text('    org 4000h\n    INCLUDE "sprite.asm"\n')

    r = rodar(str(principal), "-o", str(tmp_path / "j.rom"))

    assert r.returncode == 1
    assert "sprite.asm:2" in r.stderr, r.stderr
    assert "jogo.asm:2" not in r.stderr, r.stderr
    assert not (tmp_path / "j.rom").exists(), "nao deve escrever ROM em caso de erro"


def test_bss_vira_endereco_real_no_binario(tmp_path):
    fonte = tmp_path / "b.asm"
    fonte.write_text(
        "    org 4000h\n"
        "    BSS 0C000h\n"
        "CONTADOR: DS 1\n"
        "PONTEIRO: DS 2\n"
        "    ENDBSS\n"
        "    ld hl,PONTEIRO\n"
        "    ret\n"
    )
    saida = tmp_path / "b.rom"

    r = rodar(str(fonte), "-o", str(saida), "--size", "8K")

    assert r.returncode == 0, r.stderr
    b = saida.read_bytes()
    assert b[0] == 0x21                      # ld hl,nn
    assert b[1] == 0x01 and b[2] == 0xC0     # PONTEIRO = 0xC001


def test_colisao_de_bss_impede_a_montagem(tmp_path):
    fonte = tmp_path / "c.asm"
    fonte.write_text(
        "    org 4000h\n"
        "    BSS 0C000h\n"
        "ESTADO: DS 1\n"
        "    ENDBSS\n"
        "    BSS\n"
        "ESTADO: DS 1\n"
        "    ENDBSS\n"
    )

    r = rodar(str(fonte), "-o", str(tmp_path / "c.rom"))

    assert r.returncode == 1
    assert "ESTADO" in r.stderr
