# roms/

**Languages:** [Português](README.md) · [English](README.en.md) · [Español](README.es.md)

What **actually runs**. The project's `.gitignore` blocks `*.rom` everywhere
precisely so that dozens of test builds do not get mixed up with playable ROMs;
this directory is the declared exception.

| ROM | Size | md5 | Machine |
|---|---|---|---|
| `pong-ai-v24.rom` | 16 KB | `03324e8f4febc0e537c9c808c6c33c00` | MSX2 |

## Pong AI v24

The game this project grew out of. A complete MSX2 title: title screen, sound
chip selection (PSG, YM2413 or no music), music converted from MIDI files,
paddle AI with three difficulty levels, YM2413 rhythm-mode effects, a compressed
logo and a 10-point match.

Running it in WebMSX:

```
http://localhost:PORT/?ROM=pong-ai-v24.rom&MACHINE=MSX2PE
```

This ROM is **byte for byte identical** to `tests/fixtures/pong-v24.rom`. Both
copies exist because they serve different purposes: the one in `tests/fixtures/`
is a test contract, frozen forever — the assembler must keep producing those
exact bytes after any refactor. This one is the playable artefact, and will be
replaced once the port to the library is done.

**It is the only thing in this repository that cannot be rebuilt from here.**
The source that generates it is `build_pong.py`, a 2,400-line Python script
living in the old repository. That is precisely the problem this project exists
to solve — and why the binary stays versioned until the port happens.

## What is not here, and why

**The example ROM** (`games/example/`) is deliberately not versioned: one
command rebuilds it, and a tracked binary would age silently alongside the
sources that produce it.

```sh
./games/example/build.sh
```

**Third-party ROMs** do not go here. The repository is Apache-2.0 and does not
redistribute other people's work without a clear licence — the same reason
WebMSX comes in as a submodule rather than a copy. See [NOTICE](../NOTICE).
