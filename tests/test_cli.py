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
