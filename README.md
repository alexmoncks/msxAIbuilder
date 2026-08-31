# msxAIbuilder

**Idiomas:** [Português](README.md) · [English](README.en.md) · [Español](README.es.md)

Construtor de ROMs para MSX e MSX2: um assembler Z80 em Python, uma camada de
conversao de assets e um runtime modular em assembly, para escrever jogos de
cartucho.

> **Estado: o assembler existe e funciona.** 160 testes, e a ROM do Pong AI v24
> continua sendo produzida byte a byte. Falta a camada de assets, o runtime Z80
> compartilhado e o port do Pong.
>
> Referencia do assembler: [`docs/referencia.md`](docs/referencia.md).
> Desenho completo: [`docs/superpowers/specs/2026-08-31-msxaibuilder-design.md`](docs/superpowers/specs/2026-08-31-msxaibuilder-design.md).

## De onde isso vem

O projeto nasce do **Pong AI v24**, um jogo MSX2 completo — tela de titulo,
selecao de chip de som, musica convertida de MIDI, IA de raquete, efeitos em
modo ritmo do YM2413, logo comprimido — que foi construido por um script Python
unico de 2.400 linhas gerando todo o Z80 como string.

O jogo funciona. O script nao escala para um segundo jogo.

O msxAIbuilder separa o que era reusavel daquele trabalho (VDP, sprites, texto,
PSG, YM2413, player de musica, input, descompressao LZ) do que era Pong.

## Como vai funcionar

O codigo do jogo e assembly de verdade, em arquivos `.asm`:

```asm
    INCLUDE "msxbuild/rt/vdp.asm"
    INCLUDE "msxbuild/rt/sprite.asm"
    INCLUDE "msxbuild/rt/input.asm"

MAIN:
    call VDP_INIT_SCREEN5
LOOP:
    call INPUT_READ
    call SPR_FLUSH
    jr   LOOP
```

O Python entra so onde ha calculo — converter BMP em padroes de sprite, MIDI em
dados de musica, gerar tabelas de frequencia por chip:

```python
from msxbuild import Project

p = Project("meujogo", mapper="konami", size="2048K")
p.image("art/logo.bmp", compress="lz")
p.music("midi/tema.mid", chip=("psg", "ym2413"))
p.build("game.asm")
```

## Componentes

| Pacote | Responsabilidade |
|---|---|
| `msxasm` | Assembler Z80. `INCLUDE`, macros, `BSS` com alocacao de RAM, bancos de MegaROM. Nao sabe o que e um sprite. |
| `msxbuild` | Conversao de assets, montagem do projeto, runtime `.asm`. Nao sabe codificar Z80. |
| `games/` | Os cartuchos. [`example/`](games/example/) monta e roda hoje; `pong/` aguarda o port. |
| [`roms/`](roms/) | As ROMs jogaveis. Hoje: o Pong AI v24, 16 KB, MSX2. |

## MegaROM

Suporte a cartuchos de ate 2 MB com paginacao. O mapper padrao e o **Konami**,
por um motivo concreto: ele mantem `4000h-5FFFh` fixo no segmento 0 da ROM, o
que da 8 KB residentes onde o trampolim de troca de banco precisa morar — codigo
que pagina nao pode ser paginado embaixo de si mesmo.

Detalhe que morde e que a spec documenta: os quatro mappers compativeis tem
regra de deteccao identica no WebMSX, e o de menor prioridade vence. Uma ROM de
2 MB seria carregada como ASCII8 em silencio, com as janelas erradas. Por isso o
builder emite o nome com o hint de formato — `meujogo [Konami].rom`.

## Composite por blitter (planejado, pós-v1)

Uma segunda trilha desenha personagens e bosses pelo **command engine do V9938**
em vez de sprites de hardware: `LMMM` com operacao logica transparente sobre
double buffer em paginas de VRAM, com os sprites reservados para hitboxes
invisiveis nos pontos fracos. Especificacao completa em
[`docs/msx2-spec-grafica.md`](docs/msx2-spec-grafica.md).

Uma ressalva que a validacao dessa spec produziu e que vale para qualquer
projeto MSX2: **o orcamento de ciclos do blitter nao e mensuravel em emulador.**
O WebMSX estima a duracao dos comandos e nao modela a disputa por slots de
acesso a VRAM — exatamente a variavel que decide quantos objetos cabem em tela.
Esse numero precisa de hardware real.

## Comecando

```sh
git clone --recurse-submodules https://github.com/alexmoncks/msxAIbuilder.git
cd msxAIbuilder
python3 -m venv .venv && .venv/bin/pip install pytest

./games/example/build.sh      # -> games/example/build/example.rom
```

O exemplo e um cartucho MSX de 16 KB que monta, com cabecalho valido e vetor de
entrada correto. Ele existe para mostrar `INCLUDE`, `MACRO`, `BSS` e labels
locais `@@` num programa que cabe na cabeca de uma vez.

## Testes

O WebMSX entra como submodule em `vendor/webmsx` e roda as ROMs em modo
headless: o Z80 e o VDP reais do emulador executam o cartucho, com input
roteirizado, e os testes afirmam sobre o estado resultante.

```bash
git clone --recurse-submodules https://github.com/alexmoncks/msxAIbuilder.git
```

Ja clonou sem os submodules?

```bash
git submodule update --init --depth 1
```

## Licenca

[Apache-2.0](LICENSE). O runtime em assembly esta sob a mesma licenca — usa-lo
num jogo nao obriga a abrir o codigo do jogo.

O WebMSX (Copyright Paulo Augusto Peccin) e dependencia de teste referenciada
por submodule, nao redistribuida por este repositorio. Ver [NOTICE](NOTICE).
