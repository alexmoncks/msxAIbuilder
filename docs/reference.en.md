# msxasm — reference

**Languages:** [Português](referencia.md) · [English](reference.en.md) · [Español](referencia.es.md)

Z80 assembler for MSX cartridges. Two passes, no dependencies outside the
Python standard library.

```
msxasm SOURCE -o OUTPUT [--org ADDRESS] [--size SIZE]
               [-I PATH]... [--bank-map FILE]
```

| Option | Meaning | Default |
|---|---|---|
| `-o`, `--output` | Output ROM | required |
| `--org` | Assembly address, when the source declares no `org` | `0x4000` |
| `--size` | Cartridge size | `16K` |
| `-I`, `--include-path` | Extra directory for resolving `INCLUDE` and `INCBIN` | — |
| `--bank-map` | Writes the symbol → (bank, address) map | — |

An assembly error is reported with `file:line`, exits with status 1, and
**no ROM is written**. A partial ROM on disk looks finished.

## Number syntax

One grammar, accepted everywhere — directives, expressions, command-line
arguments:

| Form | Example | Value |
|---|---|---|
| `K` / `M` suffix | `16K`, `2M` | multiples of 1024 |
| `H` suffix (Intel) | `0C000h`, `4000h` | hexadecimal |
| `0x` / `0b` / `0o` prefix | `0x4000`, `0b1010` | Python style |
| Decimal | `49152` | — |

The suffix is tried before the prefix: `0BEEFh` is a hexadecimal ending in
`h`, not a binary starting with `0b`.

## Z80 directives

`ORG`, `DB`, `DW`, `DS`, `INCBIN`, `EQU` — the traditional set.

`INCBIN "file"` embeds a binary. The path resolves relative to the file
**containing the line**, then through `-I`. A missing file is an error, not
silence.

A label on the `ORG` line itself (`START: ORG 4000h`) resolves to the address
**after** the `ORG`. Other directives bind the label to the address preceding
them, as usual.

## `INCLUDE`

```asm
    INCLUDE "rt/vdp.asm"
```

Resolves relative to the including file, then through `-I`. The same file
included twice enters **only once** — runtime modules depend on each other and
a manual guard in every file would be repeated noise. Circular inclusion is an
error with the full trail, never infinite recursion.

Every line of the flattened source keeps its originating file and line number.
An error inside `vdp.asm` reports `vdp.asm:12`, not an offset into the
flattened text.

## Local labels

```asm
PSG_ON:
@@loop:
    djnz @@loop
```

`@@name` belongs to the last global label above it, becoming `PSG_ON@@loop`.
Two modules can each have their own `@@loop` without colliding.

Without local scope that collision is **silent**: the second module simply
jumps to the first module's label.

`@@` inside a comment or a string literal is not rewritten.

## Macros

```asm
    MACRO VDP_REG reg, value
    ld      a,value
    ld      b,reg
    call    VDP_SET_REG
    ENDM

    VDP_REG 7, 0F4h
```

Positional parameters. Each expansion suffixes the local labels in the body,
so two invocations never produce identical labels.

Restrictions, each with a clear error:

- a parameter named after a Z80 register or flag is rejected — a parameter
  called `a` would turn `ld a,n` into `ld 5,n`;
- an argument count different from the declaration is an error;
- a macro left open without `ENDM` is an error;
- redefining a macro is an error, citing both locations.

Substitution never happens inside a string literal or a comment.

> **Trap.** An argument that **starts with a parenthesis** changes the
> addressing mode of the expanded instruction. `VDP_REG 7, (15 * 16) + 4`
> turns `ld a,value` into `ld a,(240) + 4`, which the Z80 reads as a memory
> load — it assembles without error and loads the byte at address 240. Write
> `15 * 16 + 4` instead.

## `BSS` — RAM allocation

```asm
    BSS 0C000h
MUS_PTR:    DS 2        ; C000h
MUS_TICK:   DS 1        ; C002h
    ENDBSS
```

Reserves addresses without emitting bytes. The first block in the flattened
source declares the base; later blocks come bare (`BSS` with no argument) and
continue where the previous one stopped.

The assembler **refuses to assemble** when:

- two symbols share a name (the comparison ignores case);
- two ranges `[base, base+size)` overlap — partially included;
- an allocation runs past the RAM limit;
- a `BSS` symbol collides with a ROM label.

This replaces literal addresses scattered through the code. With modules, two
that both pick `0C020h` corrupt each other and nothing warns you.

## MegaROM

```asm
    MAPPER KONAMI, 2048K

    BANK 0                      ; resident, 4000h-5FFFh
    DB "AB"
    DW MAIN

    BANK 12 WINDOW 8000h
WORLD2:
    INCBIN "build/world2.bin"
```

| Layout | Bank | Windows | Resident | Maximum |
|---|---|---|---|---|
| `FLAT` | — | `4000h` | `4000h` | 1 |
| `KONAMI` | 8192 | `4000h` `6000h` `8000h` `A000h` | `4000h` | 256 (2 MB) |

Konami keeps `4000h–5FFFh` pinned to segment 0, which never pages. That is
where the header, the trampoline and the bank-switching routine must live —
code that pages cannot be paged out from under itself.

2 MB is the exact ceiling, not a round number: the bank register is 8 bits and
the emulator applies `value % numBanks`, giving 256 banks of 8 KB.

Symbols in the resident bank are visible from every bank. Between two paged
banks they are not — and assembly fails instead of emitting a wrong jump.

An `org` inside a paged bank that diverges from its `WINDOW` is an error: in
that syntax the window is authoritative.

### The filename hint is not decoration

In WebMSX, ASCII8 (priority 911), ASCII16 (912), Konami (913) and KonamiSCC
(914) share an **identical** detection condition, and the lower priority wins.
A 2 MB ROM loads as ASCII8, silently, with the wrong windows.

Name the ROM with the format in brackets — `mygame [Konami].rom` — and the
emulator picks correctly.

## Known limitations

- An `EQU` declared in the resident bank does **not** cross banks; only labels
  are seeded.
- There is no `FARCALL` validation. A `call` into a paged bank fails with
  "symbol does not exist" — the right message for the wrong reason.
- The bank map does not include `BSS` symbols.
- Macros do not expand recursively.
- A macro cannot be invoked on a line that already carries a label.
