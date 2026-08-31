# msxasm — Assembler Z80 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar `minz80asm.py` — assembler Z80 de duas passagens que já monta um jogo real — num pacote `msxasm` com `INCLUDE`, macros, labels locais, alocação de RAM por `BSS` e bancos de MegaROM, sem perder um único byte de compatibilidade com a ROM que ele produz hoje.

**Architecture:** Refatoração guiada por golden file, não reescrita. O código atual monta o Pong AI v24 em 16384 bytes exatos e reprodutíveis. Esse artefato vira o teste de caracterização da Tarefa 1 e permanece verde em todas as tarefas seguintes: qualquer mudança que altere a codificação de opcodes falha imediatamente. Só depois de a rede existir é que a estrutura é quebrada em módulos e as funcionalidades novas entram.

**Tech Stack:** Python 3.13, pytest, venv. Sem dependências de runtime — o assembler é biblioteca padrão pura.

**Spec:** [`docs/superpowers/specs/2026-08-31-msxaibuilder-design.md`](../specs/2026-08-31-msxaibuilder-design.md), seção 4.

## Global Constraints

- **Golden file, imutável:** montar `tests/fixtures/pong-v24.asm` com `org=0x4000`, `tamanho=16384` produz exatamente 16384 bytes com `md5 = 03324e8f4febc0e537c9c808c6c33c00`. Toda tarefa termina com esse teste verde.
- **Python 3.13**, biblioteca padrão apenas no código de runtime. `pytest` só em dev.
- **Sem caminhos absolutos.** Nada de `/home/alexmarra/...` no código ou nos testes; tudo relativo à raiz do repositório.
- **Preenchimento de cartucho é `0xFF`**, e binário maior que o tamanho declarado é erro, não truncamento.
- Mensagem de commit em português, imperativo, sem prefixo de tipo.
- O repositório é `alexmoncks/msxAIbuilder`, branch `main`, licença Apache-2.0.

---

### Task 1: Esqueleto do pacote e a rede de segurança

O golden file vem antes de qualquer refatoração. Sem ele nada mais neste plano é seguro.

**Files:**
- Create: `pyproject.toml`
- Create: `msxasm/__init__.py`
- Create: `msxasm/legacy.py` (cópia literal de `minz80asm.py`)
- Create: `tests/fixtures/pong-v24.asm`
- Create: `tests/fixtures/pong-v24.rom`
- Create: `tests/test_golden.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: nada.
- Produces: `msxasm.legacy.Z80Assembler` (classe, método `assemble(source: str) -> bytearray`) e `msxasm.legacy.assemble_file(source_path=None, output_path=None, org=0x4000, source_text=None, tamanho=32768) -> tuple[dict[str, int], bytearray]`.

- [ ] **Step 1: Criar o ambiente e o pacote**

```bash
cd ~/projects/msxAIbuilder
python3 -m venv .venv
.venv/bin/pip install -q pytest
mkdir -p msxasm tests/fixtures
touch msxasm/__init__.py
```

- [ ] **Step 2: Escrever `pyproject.toml`**

```toml
[project]
name = "msxaibuilder"
version = "0.1.0"
description = "Construtor de ROMs MSX: assembler Z80, conversao de assets e runtime modular"
requires-python = ">=3.13"
license = "Apache-2.0"

[project.scripts]
msxasm = "msxasm.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Congelar o código provado e os artefatos golden**

O fonte do Pong é gerado por `build_pong.py`, que escreve `/tmp/pong_v22.asm` como efeito colateral. Rodá-lo produz os dois artefatos de uma vez.

```bash
WEBMSX=~/projects/WebMSX
cp "$WEBMSX/tools/minz80asm.py" msxasm/legacy.py
python3 "$WEBMSX/tools/build_pong.py" >/dev/null
cp /tmp/pong_v22.asm tests/fixtures/pong-v24.asm
cp "$WEBMSX/release/pong-ai.rom" tests/fixtures/pong-v24.rom
md5sum tests/fixtures/pong-v24.rom     # deve ser 03324e8f4febc0e537c9c808c6c33c00
rm -f "$WEBMSX"/release/pong-ai-v24-17*.rom
```

`build_pong.py` cria uma ROM com timestamp no nome a cada execução; a última linha remove o que esta etapa gerou, para não sujar o repositório antigo.

- [ ] **Step 4: Abrir exceção no `.gitignore` para os fixtures**

O `.gitignore` barra `*.rom` em todo lugar. A ROM golden precisa ser versionada — 16KB — para que uma falha mostre *onde* divergiu, não apenas *que* divergiu.

Acrescentar logo abaixo do bloco de ROMs:

```gitignore
# Excecao: a ROM golden e artefato de teste e precisa ser versionada.
!tests/fixtures/*.rom
```

Verificar:

```bash
git check-ignore -q tests/fixtures/pong-v24.rom && echo "AINDA IGNORADO (errado)" || echo "rastreavel (correto)"
```

- [ ] **Step 5: Escrever o teste de caracterização**

```python
# tests/test_golden.py
"""Rede de seguranca do projeto.

O Pong AI v24 e montado por codigo provado e produz 16384 bytes reprodutiveis.
Qualquer refatoracao do assembler que mude UM byte deste resultado quebrou a
codificacao de opcodes. Este teste roda em todas as tarefas do plano.
"""
import hashlib
from pathlib import Path

import pytest

from msxasm.legacy import Z80Assembler

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN_MD5 = "03324e8f4febc0e537c9c808c6c33c00"
CART_SIZE = 16384


def montar_pong() -> bytearray:
    fonte = (FIXTURES / "pong-v24.asm").read_text(encoding="utf-8")
    asm = Z80Assembler()
    asm.org = 0x4000
    binario = asm.assemble(fonte)
    assert len(binario) <= CART_SIZE, f"{len(binario)} bytes nao cabem em {CART_SIZE}"
    binario.extend([0xFF] * (CART_SIZE - len(binario)))
    return binario


def test_pong_v24_bate_com_o_golden_byte_a_byte():
    esperado = (FIXTURES / "pong-v24.rom").read_bytes()
    obtido = bytes(montar_pong())

    assert len(obtido) == CART_SIZE
    if obtido != esperado:
        divergencias = [i for i in range(CART_SIZE) if obtido[i] != esperado[i]]
        primeira = divergencias[0]
        pytest.fail(
            f"{len(divergencias)} bytes divergem. "
            f"Primeira em 0x{primeira + 0x4000:04X}: "
            f"esperado 0x{esperado[primeira]:02X}, obtido 0x{obtido[primeira]:02X}"
        )


def test_hash_do_golden_nao_mudou():
    conteudo = (FIXTURES / "pong-v24.rom").read_bytes()
    assert hashlib.md5(conteudo).hexdigest() == GOLDEN_MD5


def test_cabecalho_de_cartucho():
    binario = montar_pong()
    assert binario[0:2] == b"AB", "identificador de cartucho ausente"


def test_preenchimento_e_ff():
    binario = montar_pong()
    assert binario[-1] == 0xFF
```

- [ ] **Step 6: Rodar e confirmar que passa**

Run: `.venv/bin/pytest tests/test_golden.py -v`
Expected: PASS nos 4 testes. Se `test_pong_v24_bate_com_o_golden_byte_a_byte` falhar aqui, os fixtures foram copiados errado — corrigir antes de seguir, porque todo o resto do plano depende desta rede.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml msxasm tests .gitignore
git commit -m "Congela o assembler provado sob teste de caracterizacao

minz80asm.py entra como msxasm/legacy.py sem uma linha alterada. O
Pong AI v24 (16384 bytes, md5 03324e8f4febc0e537c9c808c6c33c00) e seu
fonte gerado viram fixtures.

Este teste e a rede que torna seguro refatorar um assembler que ja
monta um jogo real: qualquer mudanca que altere um byte da ROM falha
imediatamente e aponta o endereco exato da divergencia."
```

---

### Task 2: Expressão não resolvida vira erro, não aviso

**O bug mais caro do assembler atual.** `_eval` devolve `0` quando não consegue avaliar uma expressão, imprime um aviso em stderr e segue. Num build de 3355 linhas o aviso passa despercebido e a ROM monta "com sucesso" — e trava a máquina. O próprio autor deixou registrado no código: *"Silenciar isso foi o que deixou o bug acima invisivel por versoes."* `build_pong.py` chegou a carregar uma checagem manual pós-build para cobrir esse caso específico.

O build do Pong hoje emite **zero** avisos, então endurecer isso não quebra o golden.

**Files:**
- Modify: `msxasm/legacy.py` (método `_eval`, e `assemble` para coletar erros)
- Create: `tests/test_expressoes.py`

**Interfaces:**
- Consumes: `msxasm.legacy.Z80Assembler`.
- Produces: `msxasm.errors.MontagemError(mensagem: str, linha: int | None = None, arquivo: str | None = None, pilha_include: list[str] | None = None)` — exceção base usada por todas as tarefas seguintes.
- Create: `msxasm/errors.py`

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_expressoes.py
import pytest

from msxasm.errors import MontagemError
from msxasm.legacy import Z80Assembler


def montar(fonte: str, org: int = 0x4000) -> bytearray:
    asm = Z80Assembler()
    asm.org = org
    return asm.assemble(fonte)


def test_simbolo_inexistente_e_erro_e_nao_zero():
    with pytest.raises(MontagemError) as exc:
        montar("    org 4000h\n    ld hl,NAO_EXISTE\n")
    assert "NAO_EXISTE" in str(exc.value)


def test_referencia_adiante_continua_valendo():
    """Pass 1 nao conhece DEPOIS ainda; isso e legitimo, nao erro."""
    binario = montar("    org 4000h\n    jp DEPOIS\nDEPOIS:\n    ret\n")
    assert binario[0] == 0xC3
    assert binario[1] == 0x03 and binario[2] == 0x40   # 0x4003


def test_expressao_malformada_e_erro():
    with pytest.raises(MontagemError):
        montar("    org 4000h\n    ld a,(2 +* 3)\n")


def test_expressao_valida_com_aritmetica_de_label():
    binario = montar(
        "    org 4000h\n"
        "TAB:\n"
        "    db 1,2,3,4\n"
        "    ld hl,TAB+2\n"
    )
    assert binario[5] == 0x02 and binario[6] == 0x40   # TAB+2 = 0x4002
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_expressoes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'msxasm.errors'`

- [ ] **Step 3: Criar o módulo de erros**

```python
# msxasm/errors.py
"""Erros de montagem.

Toda falha do assembler passa por aqui. A regra do projeto: e melhor
recusar montar do que produzir uma ROM que trava a maquina.
"""


class MontagemError(Exception):
    def __init__(self, mensagem: str, linha: int | None = None,
                 arquivo: str | None = None, pilha_include: list[str] | None = None):
        self.mensagem = mensagem
        self.linha = linha
        self.arquivo = arquivo
        self.pilha_include = pilha_include or []
        super().__init__(str(self))

    def __str__(self) -> str:
        local = ""
        if self.arquivo:
            local = self.arquivo
            if self.linha is not None:
                local += f":{self.linha}"
            local += ": "
        elif self.linha is not None:
            local = f"linha {self.linha}: "

        texto = f"{local}{self.mensagem}"
        if self.pilha_include:
            trilha = "\n".join(f"    incluido de {p}" for p in reversed(self.pilha_include))
            texto += "\n" + trilha
        return texto
```

- [ ] **Step 4: Endurecer `_eval`**

Em `msxasm/legacy.py`, substituir o bloco `except:` de `_eval` (aquele que imprime `ASM WARN: expressao nao avaliada, virou 0`) por:

```python
        try:
            return int(eval(e, {"__builtins__": {}}, {}))
        except Exception:
            # Na passagem 1 referencias adiante ainda nao existem: devolver 0 e
            # correto, a passagem 2 resolve. Na ultima passagem, nao resolver
            # significa que o simbolo nao existe -- e devolver 0 em silencio
            # produz uma ROM que monta e trava.
            if self.pass_no == self.max_passes:
                raise MontagemError(
                    f"expressao nao pode ser avaliada: {expr!r} "
                    f"(apos substituicao de simbolos: {e!r})",
                    linha=getattr(self, "linha_atual", None),
                )
            return 0
```

E no topo do arquivo, junto dos outros imports:

```python
from msxasm.errors import MontagemError
```

- [ ] **Step 5: Rastrear a linha corrente**

Dentro do laço `while i < len(lines):` de `assemble`, logo após `line = lines[i]`, acrescentar:

```python
                self.linha_atual = i + 1
```

- [ ] **Step 6: Rodar os dois conjuntos de teste**

Run: `.venv/bin/pytest tests/ -v`
Expected: PASS em tudo, **incluindo `test_golden.py`**. Se o golden quebrar aqui, o Pong tem uma expressão que dependia do retorno 0 — investigar qual antes de prosseguir, não relaxar o erro.

- [ ] **Step 7: Commit**

```bash
git add msxasm/errors.py msxasm/legacy.py tests/test_expressoes.py
git commit -m "Expressao nao resolvida passa a ser erro, nao aviso

_eval devolvia 0 e seguia quando nao conseguia avaliar, imprimindo um
aviso que se perde num build de 3355 linhas. O resultado era uma ROM
que montava sem erro e travava a maquina -- o proprio codigo carregava
o comentario 'Silenciar isso foi o que deixou o bug invisivel por
versoes', e build_pong.py tinha uma checagem manual pos-build so para
esse caso.

Referencia adiante na passagem 1 continua devolvendo 0, que e correto.
Na ultima passagem vira MontagemError com a linha do fonte.

O build do Pong nao emitia nenhum aviso, entao o golden segue verde."
```

---

### Task 3: Localização de origem e a CLI

**Files:**
- Create: `msxasm/source.py`
- Create: `msxasm/cli.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: `msxasm.errors.MontagemError`, `msxasm.legacy.Z80Assembler`.
- Produces:
  - `msxasm.source.Linha(texto: str, arquivo: str, numero: int)` — dataclass congelada.
  - `msxasm.source.carregar(caminho: Path) -> list[Linha]`.
  - `msxasm.cli.main(argv: list[str] | None = None) -> int` — devolve 0 em sucesso, 1 em `MontagemError`.

- [ ] **Step 1: Escrever os testes que falham**

```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: FAIL — `No module named msxasm.__main__`

- [ ] **Step 3: Escrever `msxasm/source.py`**

```python
# msxasm/source.py
"""Linhas de fonte com procedencia.

Uma linha sabe de que arquivo e de que numero veio. Sem isso, INCLUDE
transforma qualquer erro em "linha 2847 de um fonte que ninguem escreveu".
"""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Linha:
    texto: str
    arquivo: str
    numero: int


def carregar(caminho: Path) -> list[Linha]:
    nome = str(caminho)
    conteudo = caminho.read_text(encoding="utf-8")
    return [
        Linha(texto=t, arquivo=nome, numero=n)
        for n, t in enumerate(conteudo.split("\n"), start=1)
    ]
```

- [ ] **Step 4: Escrever `msxasm/cli.py`**

```python
# msxasm/cli.py
"""Interface de linha de comando do assembler."""
import argparse
import sys
from pathlib import Path

from msxasm.errors import MontagemError
from msxasm.legacy import Z80Assembler

PREENCHIMENTO = 0xFF


def _tamanho(texto: str) -> int:
    t = texto.strip().upper()
    if t.endswith("K"):
        return int(t[:-1]) * 1024
    if t.endswith("M"):
        return int(t[:-1]) * 1024 * 1024
    return int(t, 0)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="msxasm", description="Assembler Z80 para cartuchos MSX")
    p.add_argument("fonte", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("--org", default="0x4000")
    p.add_argument("--size", default="16K", help="tamanho do cartucho, ex: 16K, 32K, 2M")
    p.add_argument("-I", "--include-path", action="append", default=[], type=Path)
    args = p.parse_args(argv)

    tamanho = _tamanho(args.size)

    try:
        asm = Z80Assembler()
        asm.org = int(args.org, 0)
        asm.include_paths = list(args.include_path)
        asm.arquivo_base = args.fonte
        binario = asm.assemble(args.fonte.read_text(encoding="utf-8"))

        if len(binario) > tamanho:
            raise MontagemError(
                f"binario com {len(binario)} bytes nao cabe no cartucho de {tamanho} bytes"
            )
        binario.extend([PREENCHIMENTO] * (tamanho - len(binario)))

        args.output.write_bytes(bytes(binario))
    except MontagemError as e:
        print(f"msxasm: {e}", file=sys.stderr)
        return 1

    print(f"{args.output}: {tamanho} bytes, {len(asm.labels)} labels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Escrever `msxasm/__main__.py`**

```python
# msxasm/__main__.py
from msxasm.cli import main

raise SystemExit(main())
```

- [ ] **Step 6: Propagar arquivo e linha no erro**

Em `msxasm/legacy.py`, dentro de `__init__`, acrescentar os atributos que a CLI passa:

```python
        self.include_paths = []
        self.arquivo_base = None
        self.linha_atual = None
```

E em `_eval`, na construção do `MontagemError`, passar também o arquivo:

```python
                raise MontagemError(
                    f"expressao nao pode ser avaliada: {expr!r} "
                    f"(apos substituicao de simbolos: {e!r})",
                    linha=getattr(self, "linha_atual", None),
                    arquivo=str(self.arquivo_base) if self.arquivo_base else None,
                )
```

- [ ] **Step 7: Rodar tudo**

Run: `.venv/bin/pytest tests/ -v`
Expected: PASS em tudo, golden incluído.

- [ ] **Step 8: Commit**

```bash
git add msxasm tests/test_cli.py
git commit -m "CLI do assembler e procedencia de linha nos erros

msxasm fonte.asm -o saida.rom --org 0x4000 --size 16K. Erro imprime
arquivo:linha e devolve 1 sem escrever ROM -- ROM parcial em disco
depois de erro e pior que nenhuma, porque parece pronta.

Binario maior que o cartucho e erro: passar do tamanho declarado nao e
'ficar maior', muda o formato que o WebMSX detecta e o mapeamento vira
outro."
```

---

### Task 4: INCLUDE

**Files:**
- Create: `msxasm/include.py`
- Modify: `msxasm/legacy.py` (pré-processamento antes das passagens)
- Create: `tests/test_include.py`

**Interfaces:**
- Consumes: `msxasm.source.Linha`, `msxasm.source.carregar`, `msxasm.errors.MontagemError`.
- Produces: `msxasm.include.expandir(caminho: Path, search_paths: list[Path]) -> list[Linha]` — devolve o fonte achatado, cada `Linha` mantendo o arquivo e o número de origem.

- [ ] **Step 1: Escrever os testes que falham**

```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_include.py -v`
Expected: FAIL — `No module named 'msxasm.include'`

- [ ] **Step 3: Implementar `msxasm/include.py`**

```python
# msxasm/include.py
"""Achatamento de INCLUDE.

Resolve primeiro relativo ao arquivo que incluiu, depois pelo search path.
Cada linha do resultado carrega o arquivo e o numero de onde veio, para que
um erro no meio de um runtime de biblioteca aponte para a linha do modulo e
nao para um offset do fonte achatado.

Inclusao dupla entra uma vez so: modulos do runtime dependem uns dos outros
e um include-guard manual em cada arquivo seria ruido repetido.
"""
import re
from pathlib import Path

from msxasm.errors import MontagemError
from msxasm.source import Linha, carregar

_INCLUDE = re.compile(r'^\s*INCLUDE\s+"([^"]+)"\s*(?:;.*)?$', re.IGNORECASE)


def _resolver(alvo: str, incluidor: Path, search_paths: list[Path]) -> Path | None:
    candidato = incluidor.parent / alvo
    if candidato.is_file():
        return candidato.resolve()
    for base in search_paths:
        candidato = Path(base) / alvo
        if candidato.is_file():
            return candidato.resolve()
    return None


def expandir(caminho: Path, search_paths: list[Path]) -> list[Linha]:
    caminho = Path(caminho).resolve()
    ja_incluidos: set[Path] = set()
    return _expandir(caminho, search_paths, ja_incluidos, [])


def _expandir(caminho: Path, search_paths: list[Path],
              ja_incluidos: set[Path], pilha: list[str]) -> list[Linha]:
    if caminho in {Path(p.split(":")[0]).resolve() for p in pilha}:
        trilha = " -> ".join(pilha + [str(caminho)])
        raise MontagemError(f"inclusao circular detectada: {trilha}")

    ja_incluidos.add(caminho)
    resultado: list[Linha] = []

    for linha in carregar(caminho):
        m = _INCLUDE.match(linha.texto)
        if not m:
            resultado.append(linha)
            continue

        alvo = m.group(1)
        destino = _resolver(alvo, caminho, search_paths)
        if destino is None:
            tentativas = [str(caminho.parent)] + [str(p) for p in search_paths]
            raise MontagemError(
                f'INCLUDE nao encontrou "{alvo}" (procurado em: {", ".join(tentativas)})',
                linha=linha.numero,
                arquivo=linha.arquivo,
                pilha_include=pilha,
            )

        if destino in ja_incluidos:
            continue

        marca = f"{linha.arquivo}:{linha.numero}"
        resultado.extend(
            _expandir(destino, search_paths, ja_incluidos, pilha + [marca])
        )

    return resultado
```

- [ ] **Step 4: Rodar os testes de include**

Run: `.venv/bin/pytest tests/test_include.py -v`
Expected: PASS nos 6 testes.

- [ ] **Step 5: Ligar o achatamento à CLI**

Em `msxasm/cli.py`, trocar a leitura direta do fonte pela expansão:

```python
        from msxasm.include import expandir

        linhas = expandir(args.fonte, args.include_path)
        asm.linhas_fonte = linhas
        binario = asm.assemble("\n".join(l.texto for l in linhas))
```

E em `msxasm/legacy.py`, no `__init__`, acrescentar `self.linhas_fonte = None`. No `_eval`, usar a procedência real quando ela existir:

```python
            origem = None
            if self.linhas_fonte and self.linha_atual:
                idx = self.linha_atual - 1
                if 0 <= idx < len(self.linhas_fonte):
                    origem = self.linhas_fonte[idx]
            if self.pass_no == self.max_passes:
                raise MontagemError(
                    f"expressao nao pode ser avaliada: {expr!r} "
                    f"(apos substituicao de simbolos: {e!r})",
                    linha=origem.numero if origem else self.linha_atual,
                    arquivo=origem.arquivo if origem else (
                        str(self.arquivo_base) if self.arquivo_base else None),
                )
```

- [ ] **Step 6: Teste de ponta a ponta pela CLI**

Acrescentar a `tests/test_cli.py`:

```python
def test_erro_dentro_de_include_aponta_o_modulo(tmp_path):
    (tmp_path / "rt.asm").write_text("; cabecalho\n    ld hl,SUMIDO\n")
    principal = tmp_path / "jogo.asm"
    principal.write_text('    org 4000h\n    INCLUDE "rt.asm"\n')

    r = rodar(str(principal), "-o", str(tmp_path / "j.rom"))

    assert r.returncode == 1
    assert "rt.asm:2" in r.stderr, r.stderr
    assert "SUMIDO" in r.stderr
```

- [ ] **Step 7: Rodar tudo**

Run: `.venv/bin/pytest tests/ -v`
Expected: PASS em tudo, golden incluído. O fonte do Pong não tem `INCLUDE`, então o achatamento é identidade para ele — se o golden quebrar aqui, a expansão está alterando linhas que deveria repassar intactas.

- [ ] **Step 8: Commit**

```bash
git add msxasm tests
git commit -m "INCLUDE com procedencia, guarda de repeticao e deteccao de ciclo

Resolve relativo ao incluidor, depois pelo search path (-I). Cada linha
do fonte achatado guarda arquivo e numero de origem, entao um erro num
modulo do runtime aponta para a linha do modulo.

Inclusao dupla entra uma vez so: modulos do runtime dependem uns dos
outros e include-guard manual em cada arquivo seria ruido repetido.
Ciclo e erro com a trilha completa, nao recursao infinita."
```

---

### Task 5: Labels locais

Sem escopo local, dois módulos do runtime com um `LOOP:` cada colidem. Com `@@`, cada label local pertence ao último label global acima dele.

**Files:**
- Create: `msxasm/labels.py`
- Modify: `msxasm/cli.py`
- Create: `tests/test_labels.py`

**Interfaces:**
- Consumes: `msxasm.source.Linha`.
- Produces: `msxasm.labels.expandir_locais(linhas: list[Linha]) -> list[Linha]` — reescreve `@@nome` para `nome_global@@nome`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_labels.py
from msxasm.labels import expandir_locais
from msxasm.source import Linha


def linhas(*textos: str) -> list[Linha]:
    return [Linha(texto=t, arquivo="t.asm", numero=i) for i, t in enumerate(textos, 1)]


def textos(ls: list[Linha]) -> list[str]:
    return [l.texto for l in ls]


def test_local_recebe_prefixo_do_global_acima():
    r = expandir_locais(linhas("VDP_INIT:", "@@loop:", "    djnz @@loop", "    ret"))
    assert textos(r) == [
        "VDP_INIT:",
        "VDP_INIT@@loop:",
        "    djnz VDP_INIT@@loop",
        "    ret",
    ]


def test_dois_modulos_com_mesmo_local_nao_colidem():
    r = expandir_locais(linhas(
        "PSG_ON:", "@@loop:", "    djnz @@loop",
        "FM_ON:", "@@loop:", "    djnz @@loop",
    ))
    assert "PSG_ON@@loop:" in textos(r)
    assert "FM_ON@@loop:" in textos(r)
    assert textos(r).count("    djnz PSG_ON@@loop") == 1
    assert textos(r).count("    djnz FM_ON@@loop") == 1


def test_label_global_nao_e_tocado():
    r = expandir_locais(linhas("MAIN:", "    call VDP_INIT", "    jp MAIN"))
    assert textos(r) == ["MAIN:", "    call VDP_INIT", "    jp MAIN"]


def test_local_dentro_de_comentario_e_ignorado():
    r = expandir_locais(linhas("A:", "    ret        ; volta para @@loop"))
    assert textos(r)[1] == "    ret        ; volta para @@loop"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_labels.py -v`
Expected: FAIL — `No module named 'msxasm.labels'`

- [ ] **Step 3: Implementar `msxasm/labels.py`**

```python
# msxasm/labels.py
"""Escopo de labels locais.

'@@nome' pertence ao ultimo label global acima dele e vira
'GLOBAL@@nome' no fonte achatado. Sem isso, dois modulos do runtime que
usem '@@loop' colidem, e a colisao e silenciosa: o segundo simplesmente
salta para o primeiro.
"""
import re

from msxasm.source import Linha

_GLOBAL = re.compile(r"^([A-Za-z_][A-Za-z_0-9]*):")
_LOCAL = re.compile(r"@@([A-Za-z_][A-Za-z_0-9]*)")


def _corta_comentario(texto: str) -> tuple[str, str]:
    fora_de_string = True
    for i, c in enumerate(texto):
        if c == '"':
            fora_de_string = not fora_de_string
        elif c == ";" and fora_de_string:
            return texto[:i], texto[i:]
    return texto, ""


def expandir_locais(linhas: list[Linha]) -> list[Linha]:
    resultado: list[Linha] = []
    escopo = ""

    for linha in linhas:
        codigo, comentario = _corta_comentario(linha.texto)

        m = _GLOBAL.match(codigo.strip())
        if m and not codigo.strip().startswith("@@"):
            escopo = m.group(1)

        if "@@" in codigo:
            if not escopo:
                from msxasm.errors import MontagemError
                raise MontagemError(
                    "label local '@@' sem nenhum label global acima dele",
                    linha=linha.numero, arquivo=linha.arquivo,
                )
            codigo = _LOCAL.sub(lambda mm: f"{escopo}@@{mm.group(1)}", codigo)

        resultado.append(Linha(texto=codigo + comentario,
                               arquivo=linha.arquivo, numero=linha.numero))

    return resultado
```

- [ ] **Step 4: Aceitar `@` como caractere de label no assembler**

`_is_valid_label` em `msxasm/legacy.py` precisa reconhecer `VDP_INIT@@loop`. Localizar o método e ajustar a expressão para incluir `@`:

```python
    def _is_valid_label(self, s: str) -> bool:
        return bool(re.match(r'^[A-Za-z_][A-Za-z_0-9@]*$', s))
```

E em `_eval`, o `re.escape(lbl)` já cuida do `@`, então nada muda ali.

- [ ] **Step 5: Ligar à CLI**

Em `msxasm/cli.py`, entre a expansão de include e a montagem:

```python
        from msxasm.labels import expandir_locais

        linhas = expandir_locais(expandir(args.fonte, args.include_path))
```

- [ ] **Step 6: Rodar tudo**

Run: `.venv/bin/pytest tests/ -v`
Expected: PASS. O Pong não usa `@@`, então a passagem é identidade para ele.

- [ ] **Step 7: Commit**

```bash
git add msxasm tests/test_labels.py
git commit -m "Labels locais com @@ escopados pelo global acima

Dois modulos do runtime que usem @@loop deixam de colidir. A colisao
que isto evita e silenciosa: sem escopo, o segundo modulo simplesmente
salta para o label do primeiro e o assembler nao reclama de nada."
```

---

### Task 6: Macros

**Files:**
- Create: `msxasm/macro.py`
- Modify: `msxasm/cli.py`
- Create: `tests/test_macro.py`

**Interfaces:**
- Consumes: `msxasm.source.Linha`, `msxasm.errors.MontagemError`.
- Produces: `msxasm.macro.expandir_macros(linhas: list[Linha]) -> list[Linha]`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_macro.py
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_macro.py -v`
Expected: FAIL — `No module named 'msxasm.macro'`

- [ ] **Step 3: Implementar `msxasm/macro.py`**

```python
# msxasm/macro.py
"""Macros com parametros posicionais.

Labels locais dentro do corpo (@@nome) recebem um sufixo por expansao, para
que duas invocacoes da mesma macro nao gerem dois labels iguais. Sem isso, a
segunda expansao redefine o label da primeira e todos os saltos passam a
apontar para o lugar errado -- sem erro de montagem.
"""
import re

from msxasm.errors import MontagemError
from msxasm.source import Linha

_MACRO = re.compile(r"^\s*MACRO\s+([A-Za-z_][A-Za-z_0-9]*)\s*(.*)$", re.IGNORECASE)
_ENDM = re.compile(r"^\s*ENDM\s*(?:;.*)?$", re.IGNORECASE)


class _Definicao:
    def __init__(self, nome: str, params: list[str], corpo: list[Linha]):
        self.nome = nome
        self.params = params
        self.corpo = corpo


def _coletar(linhas: list[Linha]) -> tuple[dict[str, _Definicao], list[Linha]]:
    macros: dict[str, _Definicao] = {}
    resto: list[Linha] = []
    i = 0

    while i < len(linhas):
        m = _MACRO.match(linhas[i].texto)
        if not m:
            resto.append(linhas[i])
            i += 1
            continue

        nome = m.group(1).upper()
        params = [p.strip() for p in m.group(2).split(",") if p.strip()]
        abertura = linhas[i]
        corpo: list[Linha] = []
        i += 1

        while i < len(linhas) and not _ENDM.match(linhas[i].texto):
            corpo.append(linhas[i])
            i += 1

        if i >= len(linhas):
            raise MontagemError(
                f"macro {nome} aberta sem ENDM",
                linha=abertura.numero, arquivo=abertura.arquivo,
            )

        macros[nome] = _Definicao(nome, params, corpo)
        i += 1

    return macros, resto


def _dividir_args(texto: str) -> list[str]:
    args, atual, dentro = [], "", False
    for c in texto:
        if c == '"':
            dentro = not dentro
            atual += c
        elif c == "," and not dentro:
            args.append(atual.strip())
            atual = ""
        else:
            atual += c
    if atual.strip():
        args.append(atual.strip())
    return args


def expandir_macros(linhas: list[Linha]) -> list[Linha]:
    macros, corpo = _coletar(linhas)
    if not macros:
        return corpo

    resultado: list[Linha] = []
    contador = 0

    for linha in corpo:
        bruto = linha.texto.strip()
        primeira = bruto.split()[0].upper() if bruto else ""

        if primeira not in macros:
            resultado.append(linha)
            continue

        definicao = macros[primeira]
        args = _dividir_args(bruto[len(primeira):])

        if len(args) != len(definicao.params):
            raise MontagemError(
                f"macro {definicao.nome} espera {len(definicao.params)} "
                f"argumento(s), recebeu {len(args)}",
                linha=linha.numero, arquivo=linha.arquivo,
            )

        contador += 1
        sufixo = f"_m{contador}"

        for corpo_linha in definicao.corpo:
            texto = corpo_linha.texto
            for param, valor in zip(definicao.params, args):
                texto = re.sub(rf"\b{re.escape(param)}\b", valor, texto)
            texto = re.sub(
                r"@@([A-Za-z_][A-Za-z_0-9]*)",
                lambda mm: f"@@{mm.group(1)}{sufixo}",
                texto,
            )
            resultado.append(
                Linha(texto=texto, arquivo=linha.arquivo, numero=linha.numero)
            )

    return resultado
```

- [ ] **Step 4: Rodar os testes de macro**

Run: `.venv/bin/pytest tests/test_macro.py -v`
Expected: PASS nos 5 testes.

- [ ] **Step 5: Ligar à CLI, na ordem correta**

Macros expandem **antes** dos labels locais: o corpo da macro gera `@@espera_m1`, e só então o escopo global é aplicado. Em `msxasm/cli.py`:

```python
        from msxasm.include import expandir
        from msxasm.labels import expandir_locais
        from msxasm.macro import expandir_macros

        linhas = expandir_locais(expandir_macros(expandir(args.fonte, args.include_path)))
```

- [ ] **Step 6: Rodar tudo**

Run: `.venv/bin/pytest tests/ -v`
Expected: PASS, golden incluído.

- [ ] **Step 7: Commit**

```bash
git add msxasm tests/test_macro.py
git commit -m "Macros com parametros e labels locais unicos por expansao

Cada expansao sufixa os @@ do corpo. Sem isso a segunda invocacao da
mesma macro redefine os labels da primeira e os saltos passam a apontar
para o lugar errado, sem nenhum erro de montagem.

Macros expandem antes do escopo de labels locais, para que o sufixo por
expansao ja esteja no texto quando o escopo global for aplicado."
```

---

### Task 7: BSS — alocação de RAM

Resolve o problema descrito na seção 4.3 da spec: o Pong grava `0C000h`, `0C020h`, `0C05Ch` literais espalhados pelo código. Numa biblioteca modular isso é corrupção silenciosa.

**Files:**
- Create: `msxasm/bss.py`
- Modify: `msxasm/cli.py`
- Create: `tests/test_bss.py`

**Interfaces:**
- Consumes: `msxasm.source.Linha`, `msxasm.errors.MontagemError`.
- Produces: `msxasm.bss.extrair(linhas: list[Linha], limite: int = 0xFFFF) -> tuple[list[Linha], dict[str, int]]` — devolve as linhas sem os blocos BSS e o mapa símbolo → endereço, pronto para virar `EQU`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_bss.py
import pytest

from msxasm.bss import extrair
from msxasm.errors import MontagemError
from msxasm.source import Linha


def linhas(*textos: str) -> list[Linha]:
    return [Linha(texto=t, arquivo="t.asm", numero=i) for i, t in enumerate(textos, 1)]


def test_aloca_sequencialmente_a_partir_da_base():
    _, mapa = extrair(linhas(
        "    BSS 0C000h",
        "MUS_PTR:  DS 2",
        "MUS_TICK: DS 1",
        "MUS_VOZ:  DS 6",
        "    ENDBSS",
    ))
    assert mapa == {"MUS_PTR": 0xC000, "MUS_TICK": 0xC002, "MUS_VOZ": 0xC003}


def test_blocos_de_modulos_diferentes_se_concatenam():
    _, mapa = extrair(linhas(
        "    BSS 0C000h",
        "A: DS 4",
        "    ENDBSS",
        "    BSS",
        "B: DS 2",
        "    ENDBSS",
    ))
    assert mapa == {"A": 0xC000, "B": 0xC004}


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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_bss.py -v`
Expected: FAIL — `No module named 'msxasm.bss'`

- [ ] **Step 3: Implementar `msxasm/bss.py`**

```python
# msxasm/bss.py
"""Alocacao de variaveis em RAM.

Um bloco BSS reserva enderecos sem emitir bytes. Cada modulo declara o seu; o
assembler concatena na ordem de inclusao e recusa montar se dois simbolos
colidirem ou se a RAM estourar.

O que isto substitui: enderecos literais espalhados pelo codigo (0C000h,
0C020h, 0C05Ch). Com um runtime modular, dois modulos que escolham o mesmo
endereco se corrompem mutuamente e nada avisa.
"""
import re

from msxasm.errors import MontagemError
from msxasm.source import Linha

_BSS = re.compile(r"^\s*BSS\s*(\S+)?\s*(?:;.*)?$", re.IGNORECASE)
_ENDBSS = re.compile(r"^\s*ENDBSS\s*(?:;.*)?$", re.IGNORECASE)
_RESERVA = re.compile(
    r"^\s*([A-Za-z_][A-Za-z_0-9@]*)\s*:\s*DS\s+(\S+)\s*(?:;.*)?$", re.IGNORECASE
)


def _numero(texto: str) -> int:
    t = texto.strip().upper()
    if t.endswith("H"):
        return int(t[:-1], 16)
    if t.startswith("0X"):
        return int(t, 16)
    return int(t, 10)


def extrair(linhas: list[Linha], limite: int = 0xFFFF) -> tuple[list[Linha], dict[str, int]]:
    resto: list[Linha] = []
    mapa: dict[str, int] = {}
    origem: dict[str, str] = {}
    cursor: int | None = None
    i = 0

    while i < len(linhas):
        m = _BSS.match(linhas[i].texto)
        if not m:
            resto.append(linhas[i])
            i += 1
            continue

        abertura = linhas[i]
        if m.group(1) is not None:
            cursor = _numero(m.group(1))
        elif cursor is None:
            raise MontagemError(
                "primeiro bloco BSS precisa declarar o endereco base, ex: BSS 0C000h",
                linha=abertura.numero, arquivo=abertura.arquivo,
            )

        i += 1
        fechado = False

        while i < len(linhas):
            if _ENDBSS.match(linhas[i].texto):
                fechado = True
                i += 1
                break

            corpo = linhas[i]
            if corpo.texto.strip() and not corpo.texto.strip().startswith(";"):
                r = _RESERVA.match(corpo.texto)
                if not r:
                    raise MontagemError(
                        f"dentro de BSS so cabe 'NOME: DS n', encontrado: {corpo.texto.strip()!r}",
                        linha=corpo.numero, arquivo=corpo.arquivo,
                    )

                nome, tamanho = r.group(1), _numero(r.group(2))
                if nome in mapa:
                    raise MontagemError(
                        f"simbolo BSS duplicado: {nome} (ja declarado em {origem[nome]})",
                        linha=corpo.numero, arquivo=corpo.arquivo,
                    )

                if cursor + tamanho - 1 > limite:
                    raise MontagemError(
                        f"RAM estourou ao alocar {nome} ({tamanho} bytes em "
                        f"0x{cursor:04X}); limite e 0x{limite:04X}",
                        linha=corpo.numero, arquivo=corpo.arquivo,
                    )

                mapa[nome] = cursor
                origem[nome] = f"{corpo.arquivo}:{corpo.numero}"
                cursor += tamanho

            i += 1

        if not fechado:
            raise MontagemError(
                "bloco BSS aberto sem ENDBSS",
                linha=abertura.numero, arquivo=abertura.arquivo,
            )

    return resto, mapa
```

- [ ] **Step 4: Rodar os testes de BSS**

Run: `.venv/bin/pytest tests/test_bss.py -v`
Expected: PASS nos 7 testes.

- [ ] **Step 5: Injetar o mapa como EQU e ligar à CLI**

Os símbolos alocados precisam existir para o assembler. Em `msxasm/cli.py`, depois da expansão de labels locais:

```python
        from msxasm.bss import extrair

        linhas, ram = extrair(linhas)
        equates = [
            Linha(texto=f"{nome} EQU 0{endereco:04X}h", arquivo="<bss>", numero=n)
            for n, (nome, endereco) in enumerate(ram.items(), start=1)
        ]
        linhas = equates + linhas
```

Acrescentar `from msxasm.source import Linha` aos imports de `cli.py`.

- [ ] **Step 6: Teste de ponta a ponta pela CLI**

Acrescentar a `tests/test_cli.py`:

```python
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
```

- [ ] **Step 7: Rodar tudo**

Run: `.venv/bin/pytest tests/ -v`
Expected: PASS, golden incluído. O Pong não usa `BSS` ainda — ele será migrado no plano do port, não aqui.

- [ ] **Step 8: Commit**

```bash
git add msxasm tests
git commit -m "BSS: alocacao de RAM com deteccao de colisao e estouro

Um bloco BSS reserva enderecos sem emitir bytes; blocos de modulos
diferentes se concatenam na ordem de inclusao. Simbolo duplicado e
estouro de RAM recusam a montagem.

Isto substitui os enderecos literais espalhados pelo codigo do Pong
(0C000h, 0C020h, 0C05Ch). Com runtime modular, dois modulos que
escolham o mesmo endereco se corrompem e nada avisa."
```

---

### Task 8: MAPPER e bancos de MegaROM

**Files:**
- Create: `msxasm/mapper.py`
- Modify: `msxasm/cli.py`
- Create: `tests/test_mapper.py`

**Interfaces:**
- Consumes: `msxasm.errors.MontagemError`, `msxasm.source.Linha`.
- Produces:
  - `msxasm.mapper.LAYOUTS: dict[str, Layout]` com chaves `"KONAMI"`, `"FLAT"`.
  - `msxasm.mapper.Layout(nome: str, tamanho_banco: int, janelas: tuple[int, ...], janela_residente: int | None, max_bancos: int, hint: str | None)` — dataclass congelada.
  - `msxasm.mapper.Banco(numero: int, janela: int, linhas: list[Linha])` — dataclass.
  - `msxasm.mapper.hint_de_arquivo(nome_base: str, layout: Layout) -> str` — devolve `"jogo [Konami].rom"`.
  - `msxasm.mapper.particionar(linhas: list[Linha]) -> tuple[Layout, int, dict[int, Banco]]` — layout, tamanho total em bytes, e os bancos. **Cada banco guarda a sua janela**: sem isso, `BANK 12 WINDOW 8000h` montaria em `0x6000` e todo símbolo do banco sairia com endereço errado.

- [ ] **Step 1: Escrever os testes que falham**

```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_mapper.py -v`
Expected: FAIL — `No module named 'msxasm.mapper'`

- [ ] **Step 3: Implementar `msxasm/mapper.py`**

```python
# msxasm/mapper.py
"""Layouts de mapper e particionamento em bancos.

Konami e o padrao para MegaROM por um motivo concreto, verificado em
CartridgeKonami.js do WebMSX: a janela 4000h-5FFFh e fixa no segmento 0 e
nunca pagina. E onde o cabecalho, o trampolim e a rotina de troca de banco
precisam morar, porque codigo que pagina nao pode ser paginado embaixo de si
mesmo.

O teto de 2MB nao e arbitrario: o registrador de banco tem 8 bits e o
emulador aplica 'value % numBanks', entao 256 bancos de 8KB e o limite.
"""
import re
from dataclasses import dataclass

from msxasm.errors import MontagemError
from msxasm.source import Linha


@dataclass(frozen=True)
class Layout:
    nome: str
    tamanho_banco: int
    janelas: tuple[int, ...]
    janela_residente: int | None
    max_bancos: int
    hint: str | None


LAYOUTS: dict[str, Layout] = {
    "KONAMI": Layout(
        nome="KONAMI", tamanho_banco=8192,
        janelas=(0x4000, 0x6000, 0x8000, 0xA000),
        janela_residente=0x4000, max_bancos=256, hint="Konami",
    ),
    "FLAT": Layout(
        nome="FLAT", tamanho_banco=0,
        janelas=(0x4000,), janela_residente=0x4000,
        max_bancos=1, hint=None,
    ),
}

@dataclass
class Banco:
    numero: int
    janela: int
    linhas: list[Linha]


_MAPPER = re.compile(r"^\s*MAPPER\s+(\w+)\s*(?:,\s*(\S+))?\s*(?:;.*)?$", re.IGNORECASE)
_BANK = re.compile(
    r"^\s*BANK\s+(\d+)\s*(?:WINDOW\s+(\S+))?\s*(?:;.*)?$", re.IGNORECASE
)


def _numero(texto: str) -> int:
    t = texto.strip().upper()
    if t.endswith("K"):
        return int(t[:-1]) * 1024
    if t.endswith("M"):
        return int(t[:-1]) * 1024 * 1024
    if t.endswith("H"):
        return int(t[:-1], 16)
    if t.startswith("0X"):
        return int(t, 16)
    return int(t, 10)


def hint_de_arquivo(nome_base: str, layout: Layout) -> str:
    """O colchete nao e enfeite.

    ASCII8 (911), ASCII16 (912), Konami (913) e KonamiSCC (914) tem regra de
    deteccao identica no WebMSX e vence a prioridade menor. Sem o hint, uma
    ROM de 2MB nossa carrega como ASCII8, em silencio, com janelas erradas.
    """
    if layout.hint is None:
        return f"{nome_base}.rom"
    return f"{nome_base} [{layout.hint}].rom"


def _janela_padrao(layout: Layout, numero: int) -> int:
    """Banco 0 e residente; os demais caem na primeira janela paginavel."""
    if numero == 0 and layout.janela_residente is not None:
        return layout.janela_residente
    paginaveis = [j for j in layout.janelas if j != layout.janela_residente]
    return paginaveis[0] if paginaveis else layout.janelas[0]


def particionar(linhas: list[Linha]) -> tuple[Layout, int, dict[int, Banco]]:
    layout = LAYOUTS["FLAT"]
    tamanho = 0
    bancos: dict[int, Banco] = {0: Banco(0, layout.janelas[0], [])}
    atual = 0

    for linha in linhas:
        m = _MAPPER.match(linha.texto)
        if m:
            nome = m.group(1).upper()
            if nome not in LAYOUTS:
                raise MontagemError(
                    f"mapper desconhecido: {nome} (conhecidos: {', '.join(sorted(LAYOUTS))})",
                    linha=linha.numero, arquivo=linha.arquivo,
                )
            layout = LAYOUTS[nome]
            if m.group(2):
                tamanho = _numero(m.group(2))
                teto = layout.max_bancos * layout.tamanho_banco if layout.tamanho_banco else tamanho
                if tamanho > teto:
                    raise MontagemError(
                        f"{nome} suporta no maximo {teto // 1024}K "
                        f"({layout.max_bancos} bancos de {layout.tamanho_banco} bytes); "
                        f"pedido: {tamanho // 1024}K",
                        linha=linha.numero, arquivo=linha.arquivo,
                    )
            continue

        m = _BANK.match(linha.texto)
        if m:
            numero = int(m.group(1))
            if numero >= layout.max_bancos:
                raise MontagemError(
                    f"banco {numero} nao existe em {layout.nome}: "
                    f"o maximo e {layout.max_bancos - 1}",
                    linha=linha.numero, arquivo=linha.arquivo,
                )
            if m.group(2):
                janela = _numero(m.group(2))
                if janela not in layout.janelas:
                    validas = ", ".join(f"0x{j:04X}" for j in layout.janelas)
                    raise MontagemError(
                        f"janela 0x{janela:04X} nao existe em {layout.nome} "
                        f"(validas: {validas})",
                        linha=linha.numero, arquivo=linha.arquivo,
                    )
            else:
                janela = _janela_padrao(layout, numero)

            atual = numero
            if atual in bancos:
                bancos[atual].janela = janela
            else:
                bancos[atual] = Banco(atual, janela, [])
            continue

        if atual not in bancos:
            bancos[atual] = Banco(atual, _janela_padrao(layout, atual), [])
        bancos[atual].linhas.append(linha)

    return layout, tamanho, bancos
```

- [ ] **Step 4: Rodar os testes de mapper**

Run: `.venv/bin/pytest tests/test_mapper.py -v`
Expected: PASS nos 9 testes.

- [ ] **Step 5: Rodar tudo**

Run: `.venv/bin/pytest tests/ -v`
Expected: PASS, golden incluído. O Pong não declara `MAPPER`, então cai em `FLAT` com um único banco — exatamente o comportamento atual.

- [ ] **Step 6: Commit**

```bash
git add msxasm/mapper.py tests/test_mapper.py
git commit -m "Layouts de mapper e particionamento em bancos

Konami e Flat. Konami e o padrao para MegaROM porque a janela
4000h-5FFFh e fixa no segmento 0 (verificado em CartridgeKonami.js):
e onde o cabecalho, o trampolim e a rotina de paginacao precisam
morar, ja que codigo que pagina nao pode ser paginado embaixo de si.

Teto de 2MB validado: registrador de banco de 8 bits com 'value %
numBanks' da 256 bancos de 8KB.

hint_de_arquivo emite 'jogo [Konami].rom'. ASCII8, ASCII16, Konami e
KonamiSCC tem deteccao identica no WebMSX e vence a prioridade menor,
entao sem o hint uma ROM de 2MB carrega como ASCII8 em silencio."
```

---

### Task 9: Montagem multi-banco e mapa de bancos

Fecha o assembler: cada banco monta na sua janela, a imagem final é concatenada e o mapa de bancos sai para depuração.

**Files:**
- Modify: `msxasm/cli.py`
- Create: `msxasm/imagem.py`
- Create: `tests/test_imagem.py`

**Interfaces:**
- Consumes: `msxasm.mapper.Layout`, `msxasm.legacy.Z80Assembler`.
- Produces: `msxasm.imagem.montar(layout: Layout, tamanho: int, bancos: dict[int, Banco], linhas_globais: list[Linha], org: int = 0x4000) -> tuple[bytearray, dict[str, tuple[int, int]]]` — imagem final e mapa símbolo → (banco, endereço).

- [ ] **Step 1: Escrever os testes que falham**

```python
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
    assert mapa["RESIDENTE"] == (0, 0x4000)
    assert mapa["DADOS"] == (3, 0xA000), "banco 3 declarou WINDOW 0A000h"


def test_banco_que_nao_cabe_na_janela_e_erro():
    layout = LAYOUTS["KONAMI"]
    with pytest.raises(MontagemError) as exc:
        montar(layout, 32768, {1: banco(1, 0x6000, "    ds 9000")}, [])
    assert "banco 1" in str(exc.value).lower()
    assert "8192" in str(exc.value)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_imagem.py -v`
Expected: FAIL — `No module named 'msxasm.imagem'`

- [ ] **Step 3: Implementar `msxasm/imagem.py`**

```python
# msxasm/imagem.py
"""Montagem da imagem final do cartucho.

Em FLAT ha um banco so, montado no org declarado. Em Konami cada banco monta
no endereco da sua janela e vai para o offset banco * 8192 da imagem.

Nao truncar nunca: binario maior que o cartucho e erro. Passar do tamanho
declarado nao e 'ficar maior', muda o formato que o emulador detecta.
"""
from msxasm.errors import MontagemError
from msxasm.legacy import Z80Assembler
from msxasm.mapper import Banco, Layout
from msxasm.source import Linha

PREENCHIMENTO = 0xFF


def montar(layout: Layout, tamanho: int, bancos: dict[int, Banco],
           linhas_globais: list[Linha],
           org: int = 0x4000) -> tuple[bytearray, dict[str, tuple[int, int]]]:
    if layout.nome == "FLAT":
        unico = bancos.get(0)
        linhas = linhas_globais + (unico.linhas if unico else [])
        asm = Z80Assembler()
        asm.org = org
        asm.linhas_fonte = linhas
        binario = asm.assemble("\n".join(l.texto for l in linhas))
        alvo = tamanho or len(binario)
        if len(binario) > alvo:
            raise MontagemError(
                f"binario com {len(binario)} bytes nao cabe no cartucho de {alvo} bytes"
            )
        binario.extend([PREENCHIMENTO] * (alvo - len(binario)))
        return binario, {n: (0, e) for n, e in asm.labels.items()}

    imagem = bytearray([PREENCHIMENTO] * tamanho)
    mapa: dict[str, tuple[int, int]] = {}
    residente = layout.janela_residente

    for numero in sorted(bancos):
        banco = bancos[numero]
        linhas = linhas_globais + banco.linhas

        if numero == 0 and residente is not None and banco.janela != residente:
            raise MontagemError(
                f"banco 0 e residente em {layout.nome} e precisa ficar na janela "
                f"0x{residente:04X}, nao 0x{banco.janela:04X}"
            )

        asm = Z80Assembler()
        asm.org = banco.janela
        asm.linhas_fonte = linhas
        binario = asm.assemble("\n".join(l.texto for l in linhas))

        if len(binario) > layout.tamanho_banco:
            raise MontagemError(
                f"banco {numero} tem {len(binario)} bytes e nao cabe na "
                f"janela de {layout.tamanho_banco} bytes"
            )

        offset = numero * layout.tamanho_banco
        if offset + len(binario) > tamanho:
            raise MontagemError(
                f"banco {numero} comeca em 0x{offset:X} e ultrapassa a "
                f"imagem de {tamanho} bytes"
            )
        imagem[offset:offset + len(binario)] = binario

        for nome, endereco in asm.labels.items():
            mapa[nome] = (numero, endereco)

    return imagem, mapa
```

- [ ] **Step 4: Rodar os testes de imagem**

Run: `.venv/bin/pytest tests/test_imagem.py -v`
Expected: PASS nos 4 testes.

- [ ] **Step 5: Ligar tudo na CLI e emitir o mapa de bancos**

Reescrever o corpo do `try` em `msxasm/cli.py`:

```python
        linhas = expandir_locais(expandir_macros(expandir(args.fonte, args.include_path)))
        linhas, ram = extrair(linhas)
        equates = [
            Linha(texto=f"{nome} EQU 0{endereco:04X}h", arquivo="<bss>", numero=n)
            for n, (nome, endereco) in enumerate(ram.items(), start=1)
        ]

        layout, tamanho_mapper, bancos = particionar(linhas)
        tamanho = tamanho_mapper or _tamanho(args.size)

        binario, mapa = montar(layout, tamanho, bancos, equates, org=int(args.org, 0))
        args.output.write_bytes(bytes(binario))

        if args.bank_map:
            with open(args.bank_map, "w", encoding="utf-8") as f:
                f.write(f"# {layout.nome}, {tamanho} bytes\n")
                for nome, (banco, endereco) in sorted(mapa.items(), key=lambda x: x[1]):
                    f.write(f"{banco:3d}  0x{endereco:04X}  {nome}\n")
```

Acrescentar o argumento e os imports:

```python
    p.add_argument("--bank-map", type=Path, help="grava o mapa simbolo -> (banco, endereco)")
```

```python
from msxasm.bss import extrair
from msxasm.imagem import montar
from msxasm.include import expandir
from msxasm.labels import expandir_locais
from msxasm.macro import expandir_macros
from msxasm.mapper import particionar
from msxasm.source import Linha
```

- [ ] **Step 6: Teste de integração pela CLI**

Acrescentar a `tests/test_cli.py`:

```python
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
```

- [ ] **Step 7: Rodar a suíte inteira**

Run: `.venv/bin/pytest tests/ -v`
Expected: PASS em tudo. **`test_golden.py` continua verde** — é a confirmação final de que nove tarefas de refatoração não moveram um byte da ROM do Pong.

- [ ] **Step 8: Commit**

```bash
git add msxasm tests
git commit -m "Montagem multi-banco, mapa de bancos e integracao da CLI

Cada banco monta no endereco da sua janela e vai para o offset
banco * 8192 da imagem. Simbolo passa a ser (banco, endereco), gravado
em --bank-map.

Banco que nao cabe na janela e imagem que ultrapassa o tamanho sao
erro, nunca truncamento.

O golden do Pong segue verde depois de nove tarefas de refatoracao:
nenhum byte da ROM mudou."
```

---

## Estado ao fim deste plano

`msxasm` monta Z80 com `INCLUDE`, macros, labels locais escopados, `BSS` com detecção de colisão, e MegaROM Konami de até 2MB com mapa de bancos — e continua produzindo a ROM do Pong AI v24 byte a byte.

**Não entra aqui, por dependerem de outro plano:**

- **Validação de `FARCALL`** (spec 4.4): rejeitar `call` direto para símbolo em banco não-residente. Precisa do runtime `mapper.asm` existir para saber o que é o trampolim — fica no plano do runtime.
- **`msxbuild`**, conversores de asset e runtime `.asm`: plano próprio.
- **Harness de regressão** (input roteirizado, traço de VDP e som): plano próprio, e **precisa vir antes do port do Pong**, porque o gate tem de existir para validar o port. Validá-lo comparando a v24 contra ela mesma é o primeiro teste dele — se o harness não provar que v24 ≡ v24, não prova nada.
- **Port do Pong** para a biblioteca: último plano, atrás do gate.
