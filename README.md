# msxAIbuilder

Construtor de ROMs para MSX e MSX2: um assembler Z80 em Python, uma camada de
conversao de assets e um runtime modular em assembly, para escrever jogos de
cartucho.

> **Estado: em design.** Nada foi implementado ainda. O desenho completo esta em
> [`docs/superpowers/specs/2026-08-31-msxaibuilder-design.md`](docs/superpowers/specs/2026-08-31-msxaibuilder-design.md).

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
| `games/` | Os jogos. `pong/` e a porta de entrada e o teste de regressao. |

## MegaROM

Suporte a cartuchos de ate 2 MB com paginacao. O mapper padrao e o **Konami**,
por um motivo concreto: ele mantem `4000h-5FFFh` fixo no segmento 0 da ROM, o
que da 8 KB residentes onde o trampolim de troca de banco precisa morar — codigo
que pagina nao pode ser paginado embaixo de si mesmo.

Detalhe que morde e que a spec documenta: os quatro mappers compativeis tem
regra de deteccao identica no WebMSX, e o de menor prioridade vence. Uma ROM de
2 MB seria carregada como ASCII8 em silencio, com as janelas erradas. Por isso o
builder emite o nome com o hint de formato — `meujogo [Konami].rom`.

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
