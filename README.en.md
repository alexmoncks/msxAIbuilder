# msxAIbuilder

**Languages:** [Português](README.md) · [English](README.en.md) · [Español](README.es.md)

A ROM builder for MSX and MSX2: a Z80 assembler in Python, an asset conversion
layer, and a modular assembly runtime, for writing cartridge games.

> **Status: the assembler exists and works.** 160 tests, and the Pong AI v24 ROM
> is still produced byte for byte. Still missing: the asset layer, the shared Z80
> runtime, and the Pong port.
>
> Assembler reference: [`docs/reference.en.md`](docs/reference.en.md).
> Full design: [`docs/superpowers/specs/2026-08-31-msxaibuilder-design.md`](docs/superpowers/specs/2026-08-31-msxaibuilder-design.md) (Portuguese).

## Where this comes from

The project grew out of **Pong AI v24**, a complete MSX2 game — title screen,
sound chip selection, music converted from MIDI, paddle AI, YM2413 rhythm-mode
effects, compressed logo — that was built by a single 2,400-line Python script
generating all the Z80 as a string.

The game works. The script does not scale to a second game.

msxAIbuilder separates what was reusable in that work (VDP, sprites, text, PSG,
YM2413, music player, input, LZ decompression) from what was Pong.

## How it works

Game code is real assembly, in `.asm` files:

```asm
    INCLUDE "rt/vdp.asm"
    INCLUDE "rt/sprite.asm"
    INCLUDE "rt/input.asm"

MAIN:
    call VDP_INIT_SCREEN5
LOOP:
    call INPUT_READ
    call SPR_FLUSH
    jr   LOOP
```

Python comes in only where there is computation — converting BMP into sprite
patterns, MIDI into music data, generating per-chip frequency tables:

```python
from msxbuild import Project

p = Project("mygame", mapper="konami", size="2048K")
p.image("art/logo.bmp", compress="lz")
p.music("midi/theme.mid", chip=("psg", "ym2413"))
p.build("game.asm")
```

## Components

| Package | Responsibility |
|---|---|
| `msxasm` | Z80 assembler. `INCLUDE`, macros, `BSS` with RAM allocation, MegaROM banks. Does not know what a sprite is. |
| `msxbuild` | Asset conversion, project assembly, `.asm` runtime. Does not know how to encode Z80. |
| `games/` | The cartridges. [`example/`](games/example/) assembles and runs today; `pong/` awaits the port. |
| [`roms/`](roms/) | The playable ROMs. Today: Pong AI v24, 16 KB, MSX2. |

## MegaROM

Support for cartridges up to 2 MB with paging. The default mapper is **Konami**,
for a concrete reason: it keeps `4000h-5FFFh` pinned to segment 0 of the ROM,
which gives 8 KB of resident space where the bank-switching trampoline has to
live — code that pages cannot be paged out from under itself.

The detail that bites, and which the reference documents: the four compatible
mappers share an identical detection rule in WebMSX, and the lower priority
wins. A 2 MB ROM would load as ASCII8 silently, with the wrong windows. That is
why the builder emits the name with the format hint — `mygame [Konami].rom`.

## Getting started

```sh
git clone --recurse-submodules https://github.com/alexmoncks/msxAIbuilder.git
cd msxAIbuilder
python3 -m venv .venv && .venv/bin/pip install pytest

./games/example/build.sh      # -> games/example/build/example.rom
```

The example is a 16 KB MSX cartridge that assembles, with a valid header and a
correct entry vector. It exists to show `INCLUDE`, `MACRO`, `BSS` and `@@` local
labels in a program you can hold in your head all at once.

## Tests

WebMSX comes in as a submodule at `vendor/webmsx` and runs the ROMs headless:
the emulator's real Z80 and VDP execute the cartridge, with scripted input, and
the tests assert on the resulting state.

Already cloned without the submodules?

```sh
git submodule update --init --depth 1
```

## Licence

[Apache-2.0](LICENSE). The assembly runtime is under the same licence — using it
in a game does not require opening the game's source.

WebMSX (Copyright Paulo Augusto Peccin) is a test dependency referenced by
submodule, not redistributed by this repository. See [NOTICE](NOTICE).
