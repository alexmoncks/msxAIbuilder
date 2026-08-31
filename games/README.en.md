# games/

**Languages:** [Português](README.md) · [English](README.en.md) · [Español](README.es.md)

Each subdirectory is a cartridge. The repository versions what **produces** the
ROM — `.asm` sources, art, MIDI, build scripts — never the binary. A ROM in git
ages silently: nobody knows which commit of the sources it came from.

## `example/`

A minimal cartridge that assembles and runs. Paints the background blue and
counts frames.

```sh
./games/example/build.sh
# -> games/example/build/example.rom (16 KB) + example.map
```

It does nothing else on purpose. The point is to show the four constructs
msxasm adds to the Z80 — `INCLUDE`, `MACRO`, `BSS` and `@@` local labels — in a
program small enough to hold in your head all at once.

```
example/
├── game.asm          the game
├── rt/
│   ├── header.asm    MSX cartridge header
│   └── vdp.asm       VDP register write
└── build.sh
```

The runtime modules come **before** the game code in the source. That is not
style: the first `BSS` block in the flattened source is the one that declares
the RAM base, and later blocks concatenate from it.

The file carries a comment about a real trap you only find by writing code: a
macro argument starting with a parenthesis changes the addressing mode of the
expanded instruction, and the ROM comes out wrong with no assembly error.

## `pong/`

Empty on purpose — see [`pong/README.md`](pong/README.md). Pong AI v24 is the
game this project grew out of, and porting it to the library is the project's
regression test, with a plan of its own.

## Reference

The full assembler syntax lives in
[`docs/reference.en.md`](../docs/reference.en.md).
