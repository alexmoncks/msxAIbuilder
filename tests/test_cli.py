# tests/test_cli.py
import hashlib
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOLDEN_MD5 = "03324e8f4febc0e537c9c808c6c33c00"


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


def test_megarom_konami_monta_2mb_com_bancos(tmp_path):
    fonte = tmp_path / "mega.asm"
    fonte.write_text(
        "    MAPPER KONAMI, 2048K\n"
        "    BANK 0\n"
        '    db "AB"\n'
        "    BANK 255 WINDOW 8000h\n"
        "    db 0EEh\n"
    )
    saida = tmp_path / "mega.rom"
    mapa = tmp_path / "mega.map"

    r = rodar(str(fonte), "-o", str(saida), "--bank-map", str(mapa))

    assert r.returncode == 0, r.stderr
    b = saida.read_bytes()
    assert len(b) == 2 * 1024 * 1024
    assert b[0:2] == b"AB"
    assert b[255 * 8192] == 0xEE
    assert mapa.exists()


def test_golden_do_pong_via_cli_bate_com_o_md5(tmp_path):
    """Regressao de integracao da Tarefa 9: nao basta Z80Assembler.assemble()
    direto (test_golden.py) continuar batendo -- a CLI agora passa pelo
    corpo reescrito do try (particionar()/montar()), e e exatamente ali
    que uma regressao silenciosa entraria. O Pong nao declara MAPPER,
    entao cai em FLAT com um banco unico; tem que sair byte a byte igual
    tambem pela CLI real, nao so via Z80Assembler isolado.
    """
    saida = tmp_path / "pong.rom"

    r = rodar(str(FIXTURES / "pong-v24.asm"), "-o", str(saida),
              "--org", "0x4000", "--size", "16K")

    assert r.returncode == 0, r.stderr
    obtido = saida.read_bytes()
    assert len(obtido) == 16384
    assert hashlib.md5(obtido).hexdigest() == GOLDEN_MD5


def test_org_da_cli_e_usado_na_montagem_nao_ignorado(tmp_path):
    """O --org da CLI precisa chegar ate o binario de verdade. Um fonte SEM
    'org' proprio, montado com --org 0x8000, tem que gerar uma referencia
    absoluta ao proprio label apontando para 0x8000 -- nao para 0, que e
    onde Z80Assembler.current_address comecaria se msxasm.imagem nao
    propagasse explicitamente o org recebido da CLI para dentro do fonte
    assemblado (Z80Assembler zera current_address a cada passagem e so a
    atualiza quando encontra uma diretiva ORG no proprio texto).
    """
    fonte = tmp_path / "semorg.asm"
    fonte.write_text("INICIO:\n    ld hl,INICIO\n    ret\n")
    saida = tmp_path / "semorg.rom"

    r = rodar(str(fonte), "-o", str(saida), "--org", "0x8000", "--size", "8K")

    assert r.returncode == 0, r.stderr
    binario = saida.read_bytes()
    assert binario[0:3] == bytes([0x21, 0x00, 0x80]), \
        "ld hl,INICIO deveria apontar para 0x8000, o --org pedido"


def test_banco_fora_do_tamanho_pedido_por_size_falha_com_mensagem_clara(tmp_path):
    """Decisao de produto: quando o fonte declara 'MAPPER KONAMI' SEM
    tamanho, o --size da CLI e quem manda. particionar() devolve
    tamanho=0 e so limita bancos pelo teto absoluto do layout (256 para
    Konami); quem tem que recusar um banco que nao caiba na imagem final
    e montar(), usando o tamanho que a CLI escolheu. BANK 100 nao cabe
    numa imagem de 32K (4 bancos de 8KB) e tem que falhar com mensagem
    clara, nao montar em silencio nem estourar com traceback -- e, acima
    de tudo, nao pode deixar uma ROM parcial no disco.
    """
    fonte = tmp_path / "estourado.asm"
    fonte.write_text(
        "    MAPPER KONAMI\n"
        "    BANK 100\n"
        "    db 1\n"
    )
    saida = tmp_path / "estourado.rom"

    r = rodar(str(fonte), "-o", str(saida), "--size", "32K")

    assert r.returncode == 1
    assert "banco 100" in r.stderr.lower()
    assert not saida.exists(), "nao deve escrever ROM em caso de erro"


# ---------------------------------------------------------------------------
# Leva final de correcao (revisao da branch inteira). Cada teste abaixo
# falharia sem o conserto que ele acompanha.


def test_org_do_fonte_divergindo_do_org_padrao_ainda_monta(tmp_path):
    """Regressao da Tarefa 9, no caminho de invocacao PADRAO: a linha 'org'
    sintetica entrava sempre e o 'org' do fonte caia no ramo de
    preenchimento, zero-preenchendo ate estourar o cartucho ('binario com
    16385 bytes nao cabe no cartucho de 16384'). Duas linhas de assembly.
    """
    fonte = tmp_path / "org8.asm"
    fonte.write_text("    org 8000h\n    ret\n")
    saida = tmp_path / "org8.rom"

    r = rodar(str(fonte), "-o", str(saida), "--size", "16K")

    assert r.returncode == 0, r.stderr
    binario = saida.read_bytes()
    assert len(binario) == 16384
    assert binario[:2] == bytes([0xC9, 0xFF])


def test_size_em_grafia_hexadecimal_do_assembler_e_aceito(tmp_path):
    """'4000h' e a grafia hexadecimal que o proprio assembler usa em todo
    lugar (0C000h, BSS 0C000h, WINDOW 8000h). A pessoa digitava a sintaxe da
    ferramenta e recebia um traceback de Python.
    """
    fonte = tmp_path / "t.asm"
    fonte.write_text("    org 4000h\n    ret\n")
    saida = tmp_path / "t.rom"

    r = rodar(str(fonte), "-o", str(saida), "--size", "4000h", "--org", "4000h")

    assert r.returncode == 0, r.stderr
    assert saida.stat().st_size == 0x4000


def test_size_malformado_sai_como_mensagem_limpa_nao_traceback(tmp_path):
    fonte = tmp_path / "t.asm"
    fonte.write_text("    ret\n")

    r = rodar(str(fonte), "-o", str(tmp_path / "t.rom"), "--size", "ZZZ")

    assert r.returncode == 1
    assert "Traceback" not in r.stderr, r.stderr
    assert "--size" in r.stderr
    assert not (tmp_path / "t.rom").exists()


def test_org_malformado_sai_como_mensagem_limpa_nao_traceback(tmp_path):
    fonte = tmp_path / "t.asm"
    fonte.write_text("    ret\n")

    r = rodar(str(fonte), "-o", str(tmp_path / "t.rom"), "--org", "nada")

    assert r.returncode == 1
    assert "Traceback" not in r.stderr, r.stderr
    assert "--org" in r.stderr


def test_fonte_inexistente_sai_como_mensagem_limpa_nao_traceback(tmp_path):
    r = rodar(str(tmp_path / "nao_existe.asm"), "-o", str(tmp_path / "t.rom"))

    assert r.returncode == 1
    assert "Traceback" not in r.stderr, r.stderr
    assert "nao_existe.asm" in r.stderr


def test_diretorio_de_saida_inexistente_sai_como_mensagem_limpa(tmp_path):
    fonte = tmp_path / "t.asm"
    fonte.write_text("    org 4000h\n    ret\n")

    r = rodar(str(fonte), "-o", str(tmp_path / "nao" / "existe" / "t.rom"))

    assert r.returncode == 1
    assert "Traceback" not in r.stderr, r.stderr


def test_incbin_emite_os_bytes_e_nao_desloca_os_labels_seguintes(tmp_path):
    """A diretiva era RECONHECIDA pelo regex e ignorada por _directive: nada
    era emitido, todo label depois dela saia deslocado, e o codigo de saida
    era 0. Unico ponto da branch que aceitava corromper enderecos em
    silencio -- contra a regra que abre errors.py.
    """
    (tmp_path / "dados.bin").write_bytes(bytes([0xDE, 0xAD, 0xBE, 0xEF]))
    fonte = tmp_path / "t.asm"
    fonte.write_text(
        "    org 4000h\n"
        'INICIO: db "AB"\n'
        '    INCBIN "dados.bin"\n'
        "FIM:    ret\n"
    )
    saida = tmp_path / "t.rom"
    mapa = tmp_path / "t.map"

    r = rodar(str(fonte), "-o", str(saida), "--size", "8K", "--bank-map", str(mapa))

    assert r.returncode == 0, r.stderr
    assert saida.read_bytes()[:7] == bytes([0x41, 0x42, 0xDE, 0xAD, 0xBE, 0xEF, 0xC9])
    assert "0x4006  FIM" in mapa.read_text(encoding="utf-8"), \
        "FIM depois de 2 bytes de db mais 4 de INCBIN"


def test_incbin_resolve_pelo_include_path(tmp_path):
    """Mesma regra do INCLUDE: relativo ao arquivo que contem a linha
    primeiro, depois pelo search path do -I.
    """
    ativos = tmp_path / "ativos"
    ativos.mkdir()
    (ativos / "tiles.bin").write_bytes(bytes([0x01, 0x02]))
    fonte = tmp_path / "t.asm"
    fonte.write_text('    org 4000h\n    INCBIN "tiles.bin"\n')
    saida = tmp_path / "t.rom"

    r = rodar(str(fonte), "-o", str(saida), "--size", "8K", "-I", str(ativos))

    assert r.returncode == 0, r.stderr
    assert saida.read_bytes()[:2] == bytes([0x01, 0x02])


def test_incbin_de_arquivo_ausente_falha_com_arquivo_e_linha(tmp_path):
    fonte = tmp_path / "t.asm"
    fonte.write_text('    org 4000h\n    INCBIN "sumiu.bin"\n')
    saida = tmp_path / "t.rom"

    r = rodar(str(fonte), "-o", str(saida), "--size", "8K")

    assert r.returncode == 1
    assert "t.asm:2" in r.stderr, r.stderr
    assert "sumiu.bin" in r.stderr
    assert not saida.exists(), "nao deve escrever ROM em caso de erro"


def test_label_local_dentro_de_bss_resolve_ponta_a_ponta(tmp_path):
    """Composicao labels x bss x legacy. Dois defeitos empilhados: o regex de
    EQU nao aceitava '@' (o EQU sintetico caia no caminho de instrucao e
    morria como 'Unknown instruction'), e corrigido isso, _eval comia o
    prefixo -- 'MUSICA@@TICK' virava '16384@@TICK' -- porque labels e
    equates eram substituidos em dois lacos separados.
    """
    fonte = tmp_path / "t.asm"
    fonte.write_text(
        "    org 4000h\n"
        "MUSICA:\n"
        "    BSS 0C000h\n"
        "@@ptr:  DS 2\n"
        "@@tick: DS 1\n"
        "    ENDBSS\n"
        "    ld a,(@@tick)\n"
        "    ret\n"
    )
    saida = tmp_path / "t.rom"

    r = rodar(str(fonte), "-o", str(saida), "--size", "8K")

    assert r.returncode == 0, r.stderr
    assert saida.read_bytes()[:4] == bytes([0x3A, 0x02, 0xC0, 0xC9]), \
        "ld a,(0C002h): @@ptr ocupa C000-C001, @@tick cai em C002"


def test_erro_em_simbolo_de_bss_aponta_a_linha_real_do_fonte(tmp_path):
    """Procedencia real nas linhas EQU sinteticas. Com '<bss>:N' o erro nao
    tinha caminho de volta ao fonte que a pessoa escreveu.
    """
    fonte = tmp_path / "t.asm"
    fonte.write_text(
        "    org 4000h\n"
        "    BSS 0C000h\n"
        "ESTADO: DS 1\n"
        "    ENDBSS\n"
        "ESTADO:\n"
        "    ret\n"
    )

    r = rodar(str(fonte), "-o", str(tmp_path / "t.rom"))

    assert r.returncode == 1
    assert "t.asm:3" in r.stderr, r.stderr
    assert "<bss>" not in r.stderr, r.stderr


def test_call_do_banco_paginado_para_o_residente_monta(tmp_path):
    """Cada banco ganhava um Z80Assembler novo com tabela de simbolos vazia,
    entao o call para o trampolim residente -- que esta SEMPRE mapeado e e o
    padrao obrigatorio da Konami -- nao montava. O recurso MegaROM estava
    sintaticamente pronto e semanticamente inutilizavel.
    """
    fonte = tmp_path / "cross.asm"
    fonte.write_text(
        "    MAPPER KONAMI, 32K\n"
        "    BANK 0\n"
        '    db "AB"\n'
        "RT_INIT:\n"
        "    ret\n"
        "    BANK 1 WINDOW 8000h\n"
        "    call RT_INIT\n"
    )
    saida = tmp_path / "cross.rom"

    r = rodar(str(fonte), "-o", str(saida))

    assert r.returncode == 0, r.stderr
    b = saida.read_bytes()
    assert b[8192:8195] == bytes([0xCD, 0x02, 0x40]), "call RT_INIT -> 0x4002"


def test_mapa_de_bancos_nao_perde_labels_homonimos(tmp_path):
    fonte = tmp_path / "homo.asm"
    fonte.write_text(
        "    MAPPER KONAMI, 32K\n"
        "    BANK 0\n"
        '    db "AB"\n'
        "LOOP:\n"
        "    nop\n"
        "    BANK 1 WINDOW 8000h\n"
        "LOOP:\n"
        "    nop\n"
    )
    mapa = tmp_path / "homo.map"

    r = rodar(str(fonte), "-o", str(tmp_path / "homo.rom"), "--bank-map", str(mapa))

    assert r.returncode == 0, r.stderr
    linhas_mapa = [l for l in mapa.read_text(encoding="utf-8").splitlines()
                   if l.strip() and not l.startswith("#")]
    assert sorted(linhas_mapa) == ["  0  0x4002  LOOP", "  1  0x8000  LOOP"]
    assert "2 labels" in r.stdout, r.stdout


def test_cadeia_completa_include_macro_local_bss_e_bancos(tmp_path):
    """As seis etapas juntas -- expandir -> expandir_macros ->
    expandir_locais -> extrair -> particionar -> montar -- com assercao de
    BYTES, nao de codigo de saida. Nenhum teste da suite passava por mais de
    duas etapas ao mesmo tempo, e foi exatamente ai que a revisao final
    achou os defeitos que as revisoes por tarefa nao viam.
    """
    (tmp_path / "rt.asm").write_text(
        "    BSS 0C000h\n"
        "MUS_PTR:  DS 2\n"
        "MUS_TICK: DS 1\n"
        "    ENDBSS\n"
        "    MACRO ESPERA n      ; gasta n voltas, depois segue\n"
        "    ld b,n\n"
        "@@laco:\n"
        "    djnz @@laco\n"
        "    ENDM\n"
        "RT_INIT:\n"
        "    ret\n"
    )
    fonte = tmp_path / "main.asm"
    fonte.write_text(
        "    MAPPER KONAMI, 32K\n"
        "    BANK 0\n"
        '    INCLUDE "rt.asm"\n'
        "INICIO:\n"
        "    ld a,(MUS_TICK)\n"
        "    ESPERA 10\n"
        "    ESPERA 20\n"
        "    BANK 1 WINDOW 8000h\n"
        "OUTRO:\n"
        "    ESPERA 30\n"
        "    ld a,(MUS_PTR)\n"
        "    call RT_INIT\n"
    )
    saida = tmp_path / "main.rom"

    r = rodar(str(fonte), "-o", str(saida))

    assert r.returncode == 0, r.stderr
    b = saida.read_bytes()
    assert len(b) == 32768
    # Banco 0: ret (RT_INIT), ld a,(0C002h) (MUS_TICK, do BSS do modulo
    # incluido), e as duas expansoes de ESPERA com sufixos distintos.
    assert b[0:12] == bytes([
        0xC9,                    # RT_INIT: ret
        0x3A, 0x02, 0xC0,        # ld a,(MUS_TICK)
        0x06, 0x0A, 0x10, 0xFE,  # ESPERA 10  -> ld b,10 / djnz @@laco_m1
        0x06, 0x14, 0x10, 0xFE,  # ESPERA 20  -> ld b,20 / djnz @@laco_m2
    ])
    # Banco 1: terceira expansao da macro (sufixo unico ATRAVES dos bancos),
    # simbolo de BSS visivel aqui tambem, e call para o residente.
    assert b[8192:8203] == bytes([
        0x06, 0x1E, 0x10, 0xFE,  # ESPERA 30 -> ld b,30 / djnz @@laco_m3
        0x3A, 0x00, 0xC0,        # ld a,(MUS_PTR)
        0xCD, 0x00, 0x40,        # call RT_INIT (banco residente)
        0xFF,                    # preenchimento
    ])
