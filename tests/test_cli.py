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
