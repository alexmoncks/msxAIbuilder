# MSX Development Manual — WebMSX

**Languages:** [Português](manual.md) · [English](manual.en.md) · [Español](manual.es.md)

## Contents
1. [MSX architecture](#1-msx-architecture)
2. [V9938 VDP — video modes](#2-v9938-vdp)
3. [Screen 4 (G3) — tiled with sprites](#3-screen-4-g3)
4. [Screen 5 (G4) — bitmap with sprites](#4-screen-5-g4)
5. [Sprite system (spriteMode 2)](#5-sprite-system)
6. [V9938 palette](#6-v9938-palette)
7. [VDP registers](#7-vdp-registers)
8. [PSG AY-3-8910 sound](#8-psg-sound)
9. [YM2413 (OPLL) music](#9-ym2413-music)
10. [Birdy Flap analysis](#10-birdy-flap-analysis)
11. [Pong AI — reference code](#11-pong-ai)
12. [Common traps](#12-common-traps)
13. [Music pipeline from .mid](#13-music-pipeline)

---

## 1. MSX architecture

### Memory map
```
0000-3FFF  System BIOS/ROM (read only)
4000-7FFF  Cartridge slot (page 1)
8000-BFFF  Cartridge slot (page 2, 16 KB mirror)
C000-FFFF  Main RAM (64 KB)
  C000-DFFF  Free for programs
  E000-F37F  System work area
  F380-FFFF  Stack and system variables
```

### I/O map (relevant ports)
```
98h    VDP — VRAM data (read/write)
99h    VDP — VRAM address / register
9Ah    VDP — palette write (V9938+)
9Bh    VDP — indirect register (V9938+)
A0h    PSG — register select
A1h    PSG — register data
A9h    PPI — port A (keyboard, row)
AAh    PPI — port B (keyboard, column)
7Ch    YM2413 — register select (FMI)
7Dh    YM2413 — data (FMD)
```

---

## 2. V9938 VDP

### Video modes (screen modes)
The mode is selected by bits M2-M5 in registers R#0 and R#1:

```
modeBits = (R1 & 0x18) | ((R0 & 0x0e) >> 1)

Value  Name    Description               Resolution  Colours  ppb
0x00   G1      Graphics 1 (TMS9918)      256×192     16       8
0x01   G2      Graphics 2 (TMS9918)      256×192     16       8
0x02   G3      Graphics 3 (Screen 4)     256×192     16       8 **
0x03   G4      Graphics 4 (Screen 5)     256×212     16       2
0x04   G5      Graphics 5 (Screen 6)     512×212     4        2
0x05   G6      Graphics 6 (Screen 7)     512×212     16       2
0x07   G7      Graphics 7 (Screen 8)     256×212     256      1
```

** ppb = pixels per byte

### Screen 4 (G3) — tiled
- 256×192 pixels, 16 colours per pixel
- Tiled: Name Table + Pattern Table + Colour Table
- 32×24 tiles of 8×8 pixels
- Sprites: spriteMode 2 (same as G4/G5/G6/G7)

### Screen 5 (G4) — bitmap
- 256×212 pixels, 16 colours per pixel
- 2 pixels per byte (4 bits each)
- Direct framebuffer: 128 bytes per line
- Sprites: spriteMode 2 (identical to G3)

### Base masks (sprAttrTBase)
Each mode defines different masks for the tables:

| Mode | layTBase | colorTBase | patTBase | sprAttrTBase |
|------|----------|------------|----------|-------------|
| G3   | -1<<10   | -1<<13     | -1<<13   | -1<<10      |
| G4   | -1<<15   | 0          | 0        | -1<<10      |
| G5   | -1<<15   | 0          | 0        | -1<<10      |
| G6   | -1<<16   | 0          | 0        | -1<<10      |

**Important**: the `-1<<10` mask requires the SAT address to have bit 10 or
higher set.
- R5=4 → (4<<7)=0x200 → masked to 0 (invalid!)
- R5=8 → (8<<7)=0x400 → survives the mask → SAT=0x400 ✓
- R5=0x3F → (0x3F<<7)=0x1F80 → survives → SAT=0x1C00 ✓

### SAT address calculation (spriteMode 2)
```
add = (R11 << 15) | (R5 << 7)   // limited to 17 bits (0x1FFFF)
SAT = add & sprAttrTBase          // applies the mode's mask
YPT = SAT + 512                   // Y,X,PN table (spriteMode 2)
ColorTable = SAT                  // Colour table (16 bytes/sprite)
```

---

## 3. Screen 4 (G3)

### Essential registers (12 registers)
```
R0=04  R1=E2  R2=nn  R3=nn  R4=nn  R5=nn
R6=nn  R7=nn  R8=nn  R9=00  R10=00 R11=00
```

### Tile tables in G3
- **Name Table** at R2 × 0x400 (768 bytes: 32×24 tiles)
- **Pattern Table** (256 chars × 8 bytes = 2048 bytes) at R4 × 0x800, masked by -1<<13
- **Colour Table** (1 byte per tile) at (R10<<14)|(R3<<6), masked by -1<<13

### Birdy Flap example (working G3)
```
R0=04 R1=A2→E2 R2=06 R3=FF R4=03 R5=3F
R6=07 R7=01 R8=00 R9=00 R10=00 R11=00

Name Table:  0x1800  (R2=6 × 0x400)
Pattern:     0x0000  (R4=3, masked)
Colour:      0x0000  (R3=0xFF, masked)
SAT:         0x1C00  (R5=0x3F<<7 & -1<<10)
YPT:         0x1E00  (SAT+512)
Spr Pat:     0x3800  (R6=7 × 0x800)
```

---

## 4. Screen 5 (G4)

### Differences from G3
- **No Name Table**: bitmap framebuffer directly in VRAM
- **128 bytes/line**: each byte = 2 pixels (high nibble = left pixel, low = right)
- **Height**: 212 lines (PAL) instead of 192 (NTSC)
- **Sprites**: the SAME spriteMode 2 as G3 (renderSpritesLineMode2)
- **R2**: controls the framebuffer base (masked by -1<<15)

### The SETV limitation
VRAM addresses ≥ 0x8000 CANNOT be written through a normal SETV (port 0x99),
because a high byte with bit 7=1 is interpreted as "register write". Use
R#14/R#15 to address VRAM above 32 KB.

### VRAM layout in G4 (framebuffer at 0)
```
0000-69FF  Framebuffer (128 bytes × 212 lines = 27,136 bytes)
6A00-FFFF  Free for SAT, patterns, etc.
```

---

## 5. Sprite system (spriteMode 2)

### Y-X-PN table format (at YPT = SAT + 512)
4 bytes per sprite, 32 sprites max:
```
Byte 0: Y position (216 = terminator)
Byte 1: X position
Byte 2: Pattern number (PN)
Byte 3: (unused)
```

### Colour table format (at SAT)
16 bytes per sprite (1 per scanline), 32 sprites × 16 = 512 bytes:
```
Byte s: colour for scanline s of sprite i
  bits 0-3: palette index (0-15)
  bit 5: IC (Internal Collision)
  bit 6: CC (Complementary Color)
  bit 7: EC (Early Clock, X -= 32)
```

### Two or more colours on the SAME line: the CC bit
One colour per line comes for free (the table above). To get **more than one
colour on the same line**, use the colour's **CC bit (bit 6)**: a sprite with
CC=1 does not replace the same-priority sprite underneath it — the two colours
are combined with **OR**.

```
sprite N   (CC=0, colour A)  -> draws A
sprite N+1 (CC=1, colour B)  -> where only it has a pixel: B
                                where both have a pixel: A OR B
```

Rules that matter in practice (`renderSpritesLineMode2Tiled` in VDP.js):

- The CC=1 sprite must come **after** (higher number than) the CC=0 sprite, on
  the same line. If no CC=0 sprite was processed earlier on that line, the CC=1
  sprite is simply **discarded**.
- Without CC, the higher-numbered sprite would be discarded on top of the
  lower-numbered one (priority), so CC is the only way to overlay colour within
  the same object.
- Since the result is an **OR**, choose colours thinking in bits. Example from
  Pong: ball body at 12/10/8 and highlight at 5 → `12|5=13`, `10|5=15`,
  `8|5=13` — so palettes **13 and 15 must get the same tone**, otherwise the
  highlight changes colour depending on the body line.
- It is worth defining the isolated colour's palette entry too (5, in the
  example), in case the CC sprite extends past the outline of the one below.

### Magnification and the colour table
With MAG (`R1` bit0=1), the VDP does `spriteLine >>= 1` **before** indexing the
colour. That is, with magnified 8x8 sprites only the **first 8** colour entries
of each sprite are read — one per pattern line, not per screen line.

### Register R#1 for sprites
```
bit 0:  0 = 8×8 sprite, 1 = 16×16 sprite
bit 1:  0 = normal size, 1 = 2× magnification
```

### Examples:
- R1=0xE2: bit1=1 → 8×8 sprites rendered as 16×16 (mag 2x)
- R1=0xE0: bit1=0 → 8×8 sprites without magnification

### R#8 — sprite control
```
bit 2 (SPD): 0 = sprites enabled, 1 = disabled
bit 5 (TP):  0 = colour 0 solid, 1 = colour 0 transparent
```

---

## 6. V9938 palette

### Write format
Each palette entry is 2 bytes written through port 0x9A:
```
Low byte:  (R << 4) | B    (R, G, B each 0-7)
High byte: G
16-bit value: (G << 8) | (R << 4) | B
```

### Conversion to 8-bit (per channel)
```
3-bit value -> 8-bit value
0 -> 0, 1 -> 36, 2 -> 73, 3 -> 109
4 -> 146, 5 -> 182, 6 -> 219, 7 -> 255
```

### Palette example (16 entries)
```asm
PAL:
    ; 0: black      db 00h, 00h
    ; 1: blue       db 07h, 00h    (R=0,G=0,B=7)
    ; 2: green      db 00h, 07h    (R=0,G=7,B=0)
    ; 3: cyan       db 07h, 07h    (R=0,G=7,B=7)
    ; 4: red        db 70h, 00h    (R=7,G=0,B=0)
    ; 5: white      db 77h, 07h    (R=7,G=7,B=7)
    ; ...32 bytes total
    db 00h,00h, 07h,00h, 00h,07h, 07h,07h
    db 70h,00h, 77h,07h, 00h,00h, 00h,00h
    db 00h,00h, 00h,00h, 00h,00h, 00h,00h
    db 00h,00h, 00h,00h, 00h,00h, 00h,00h
```

## 7. VDP registers

### Write protocol (port 0x99)
Two bytes for every operation:
```
1st byte: value (register data OR low byte of the VRAM address)
2nd byte: control
  bit 7 = 1 → register write (bits 0-5 = register number)
  bit 7 = 0 → VRAM address
    bit 6 = 1 → write mode
    bit 6 = 0 → read mode
    bits 0-5 = high byte of the address (A13-A8)
```

**IMPORTANT**: bit 7 of the 2nd byte can NEVER be 1 for VRAM addresses. That
limits direct addresses to < 0x8000. For VRAM > 32 KB, use R#14/R#15.

### VDP register table (V9938)
```
R#   Name  Function
0    MODE  Video mode bits M4, M5
1    DISP  Display/Mode (bits M2, M3, IE, BL, SI, SPR)
2    BASE  Name Table base (×0x400) or framebuffer
3    BASE  Colour Table base (×0x40)
4    BASE  Pattern Table base (×0x800)
5    SAT   Sprite Attribute Table base (×0x80)
6    SPT   Sprite Pattern Table base (×0x800)
7    BD    Border colour (palette index)
8    TP    Transparent Pen / Sprite Disable
9    YAE   YJK/YAE mode / PAL NTSC
10   BASE  Colour Table high bits
11   BASE  SAT high bits
12-13      Reserved
14   RV    VRAM pointer high bits
15   ST    Status index
16   PAL   Palette index for writes through 0x9A
17   ADJ   Indirect register adjustment
```

### Register R#0 (mode)
```
bits 1-3: M4, M5 (combined with R1 bits 3-4)
0x04 = Screen 4 (G3)
0x06 = Screen 5 (G4)
```

### Register R#1 (display)
```
bit 0:  0=8×8 sprites, 1=16×16 sprites
bit 1:  0=normal, 1=2× magnification
bit 2:  reserved
bit 3-4: M2, M3 (mode)
bit 5:  IE (VBlank interrupt)
bit 6:  BL (display enable in WebMSX)
bit 7:  reserved (keep 0)
```

Common values:
- 0xE2: display on, VBlank IE, spr mag 2x, 8×8 sprites
- 0xE0: display on, VBlank IE, spr normal, 8×8 sprites
- 0xA2: display off (bit6=0), spr mag 2x (used in Birdy Flap init)

---

## 8. PSG sound (AY-3-8910)

### Ports
```
A0h: PSG register select
A1h: PSG register data
```

### PSG registers
```
R0:  Channel A — tone (fine)
R1:  Channel A — tone (coarse)
R2:  Channel B — tone (fine)
R3:  Channel B — tone (coarse)
R4:  Channel C — tone (fine)
R5:  Channel C — tone (coarse)
R6:  Noise — period
R7:  Mixer (also I/O)
R8:  Channel A — volume
R9:  Channel B — volume
R10: Channel C — volume
R11: Envelope — period (fine)
R12: Envelope — period (coarse)
R13: Envelope — shape
R14: Joystick (read only, port 0A2h)
R15: I/O port B — bit6 = joystick port, bit4/5 = pin 8
```

### Joystick
Reading trigger 1 on port 1:
```asm
    ld a, 15
    out (0A0h), a
    ld a, 8Fh        ; bit6=0 -> port 1 ; bit4=0 -> pin 8 low
    out (0A1h), a
    ld a, 14
    out (0A0h), a
    in a, (0A2h)     ; bit0..3 = directions, bit4 = trigger A, bit5 = trigger B
    and 10h          ; zero = trigger A pressed
```
`R15` bit4 (pin 8) must be **0**, otherwise WebMSX returns a fixed 0x3Fh
(`DOMJoykeysControls.readLocalControllerPort`). The reset value is already 8Fh.

### Keyboard — row 8
```
bit0 = SPACE   bit1 = HOME   bit2 = INS   bit3 = DEL
bit4 = LEFT    bit5 = UP     bit6 = DOWN  bit7 = RIGHT
```
All active **low**. Select the row on PPI port C (0AAh) bits 0-3 and read on PPI
port B (0A9h).

---

## 9. YM2413 (OPLL) music

### Ports
```
7Ch: register select (F0)
7Dh: data (F1)
```

### Initialisation
```asm
    ld a, 10h
    out (F0), a
    xor a
    out (F1), a
    ld b, 9
    ld a, 20h
loop:
    push af
    out (F0), a
    xor a
    out (F1), a
    pop af
    inc a
    djnz loop
```

---

### Percussion / noise (rhythm mode)

The YM2413 has a rhythm section that reuses channels 6, 7 and 8. This is where
the **noise instruments** live: HH (hi-hat), SD (snare) and TCY (top cymbal).
BD and TOM are pitched, not noisy.

```
reg 0Eh   bit5 = enables rhythm mode
          bit4 = BD   bit3 = SD   bit2 = TOM   bit1 = TCY   bit0 = HH
```

Volumes (0 = maximum, 15 = mute):
```
reg 36h   bits 3-0 = BD          (the high nibble is NOT volume: BD has a modulator)
reg 37h   bits 7-4 = HH   bits 3-0 = SD
reg 38h   bits 7-4 = TOM  bits 3-0 = TCY
```

Standard frequencies for the percussion channels (MSX-MUSIC):
```
ch6 (BD)       reg 16h = 20h   reg 26h = 05h
ch7 (HH/SD)    reg 17h = 50h   reg 27h = 05h
ch8 (TOM/TCY)  reg 18h = C0h   reg 28h = 01h
```

**Order matters**: enable rhythm mode (0Eh = 20h) **before** writing
36h/37h/38h. Outside rhythm mode those three registers are the *instrument* of
channels 6/7/8, not the volume.

**Re-triggering**: percussion only attacks when the key-on bit goes from 0 to 1.
To play the same sound twice in a row you have to switch it off first:

```asm
    ld a, 0Eh
    ld e, 20h       ; key-off everything, rhythm mode kept
    call FMW
    ld a, 0Eh
    ld e, 21h       ; key-on for HH
    call FMW
```

**A write that does not change the register is ignored** (both on the chip and
in WebMSX, which compares `register[reg] ^ val`). To make sure a volume is
applied at boot, write a different value first: `37h = FFh`, then `37h = 02h`.

### Write timing
The chip requires ≥12 cycles after the address byte (port 7Ch) and ≥84 cycles
after the data byte (port 7Dh). An `ld a,n / dec a / jr nz` loop of 2 and 6
iterations covers both cases.

---

## 9b. Sound chips available in WebMSX

| Chip | Channels | How it arrives | Status |
|------|----------|----------------|--------|
| **PSG** AY-3-8910 | 3 tone + 1 noise | built into every MSX | always available |
| **FM / MSX-MUSIC** YM2413 (OPLL) | 9 melodic, or 6 + 5 percussion | `_MSX2BASE` already includes `MSXMUSIC` | always available on MSX2/2+ |
| **SCC / SCC+** | 5 wavetable | extension, `PRESETS=SCC` in the URL | available, off by default |
| **Double PSG** | +3 tone | extension, `PRESETS=DOUBLEPSG` | available, off by default |
| **OPL4 / MoonSound** | 18 FM + wavetable | extension, `PRESETS=OPL4` | available, off by default |
| **MSX-Audio** Y8950 | 9 FM + ADPCM | — | **not emulated** |

`src/main/msx/rom/SlotFormatsNotSupported.js` literally lists
`"MSXAUDIO": 0, // Make Support?`. The ROM database recognises the cartridges
(Panasonic FS-CA1 and others) but the format is not implemented.

### PSG notes
`period = (3579545/2) / (16 * frequency)`, 12 bits. The lowest note that fits is
about C1 (period 3420). The PSG has no per-note envelope usable for melody (the
envelope is global), so decay has to come from software.

### YM2413 notes
`f = F * 49716 * 2^block / 2^19`. Pick the `block` that leaves `F` between 256
and 511 — that is where resolution is best. The byte for register `20h+channel`
is `10h (key-on) | block<<1 | F bit8`.

---

## 10. Birdy Flap analysis

### VREG (12 registers at 0x40DC)
```
R0=04  (G3)
R1=A2  (init: bit6=0 → display blanked)
R2=06  (name table ×0x400 = 0x1800)
R3=FF  R4=03
R5=3F  (SAT = 0x3F<<7 = 0x1F80 → masked = 0x1C00)
R6=07  (sprite patterns ×0x800 = 0x3800)
R7=01  (border = palette 1)
R8=00  (TP=0, SPD=0)
R9=00  R10=00 R11=00
```

### After init: R1 changes to 0xE2
```asm
    ld a, 0E2h
    out (0x99), a
    ld a, 81h      ; R1 = 0xE2 (display on, IE, spr mag 2x)
    out (0x99), a
```

### Display toggle
Birdy Flap initialises with the display blanked (R1 bit6=0), configures
EVERYTHING, and ONLY THEN enables the display. Avoids artefacts.

---

## 11. Pong AI — reference code

### Files
- `tools/build_pong.py` — Z80 source + build script (v24)
- `tools/minz80asm.py` — 2-pass Z80 assembler — now refactored as this
  repository's [`msxasm`](reference.en.md) package
- `roms/pong-ai-v24.rom` — published ROM, **16384 bytes**
  (`md5 03324e8f4febc0e537c9c808c6c33c00`)

> **Correction.** Earlier versions of this manual said 32 KB. v24 has
> `CART = 16 * 1024` in `build_pong.py`, and the published ROM is 16384 bytes —
> verified 2026-08-31. The 32 KB ROMs in `release/` are older builds.

### Sprite geometry with MAG
The sprites are 8×8 with magnification (R1 bit0=1), so each pattern pixel
becomes 2×2 on screen. Ball and paddle draw in pattern **columns 2..5**, which
on screen becomes the range **+4..+11** from the sprite's X:

```
paddle P1 (X=8)     occupies X =  12..19
paddle P2 (X=232)   occupies X = 236..243
ball                occupies X = BX+4..BX+11
```

That is why collision cannot use the sprite's X directly: for the ball to
*touch* the paddle, `BXLP = P1X+8 = 16` and `BXRP = P2X-8 = 224`. Using the raw
X leaves a gap on one side and overlap on the other.

The VDP also draws the sprite on line **Y+1**, so the vertical limits are
`PMAX = 192-32-1 = 159` and `BYMAX = 192-8-1 = 183`.

### VDP configuration (working G3)
```
R0=04  R1=E0  R2=00  R3=01  R4=02
R5=08  R6=04  R7=00  R8=20  (TP=1)

SAT = 0x400  (R5=8 → 8<<7=0x400)
YPT = 0x600  (SAT+512)
Spr Pat = 0x2000 (R6=4)
Colour Table = 0x400 (SAT base)
```

---

## 12. Common traps

### SAT address masking
Check that R5 ≥ 8 in G3/G4/G5 (the `-1<<10` mask zeroes values below 0x400).

### VRAM address bit 7
Never use SETV with addresses ≥ 0x8000 (bit 7 causes a register write).

### Hex constant ending in 0B/1B (minz80asm)
`_eval` converts hex before binary. After conversion, `0C00Bh` is already
`0x0C00B`, and the binary literal regex `([01]+)B\b` matched the trailing `00B`:

```
0C00Bh -> 192   (0x00C0)      0Bh -> 0
```

With no warning at all. `PAUSA equ 0C00Bh` became an address inside the BIOS
ROM, so the write was discarded and the read returned garbage. **Fixed** with a
lookbehind (`(?<![0-9A-Fx])`), and `_eval` now warns when an expression fails to
evaluate instead of quietly returning 0.

`build_pong.py` also checks, on every build, that every variable equate sits in
`0xC000..0xC0FF` and every VRAM equate in `0x0000..0x3FFF`.

> In this repository's `msxasm`, an unresolved expression is no longer a warning
> at all: it is a hard error with `file:line`. A warning in a 3,355-line build
> gets lost, and the result was a ROM that assembled cleanly and hung the
> machine.

### VBlank sync
With `ei`, the BIOS reads S#0 and clears the VBlank flag. The
`in a,(99h); rlca; jr nc` loop can fail. Use `di` for direct polling.

### Display initialisation
Always configure everything BEFORE enabling the display. Birdy Flap technique:
init with R1 bit6=0, then switch to bit6=1.

---

## 12a. A 32 KB cartridge: page 2 does not come for free

The BIOS calls a 32 KB cartridge's `INIT` with **page 1** (4000h-7FFFh) already
in the cartridge slot, but leaves **page 2** (8000h-BFFFh) on RAM. Anything the
ROM stores above 0x8000 reads garbage until the cartridge itself switches the
page.

Real symptom: the title music played and the in-game music did not — the
in-game tracks were exactly the ones that landed above 0x8000.

```asm
; copies page 1's primary slot into page 2
PG2:
    in a, (0A8h)
    ld b, a
    and 0Ch          ; page 1 slot (bits 2-3)
    rlca
    rlca             ; into bits 4-5 (page 2)
    ld c, a
    ld a, b
    and 0CFh         ; clears the page 2 bits
    or c
    out (0A8h), a
    ret
```

Valid for a **non-expanded** slot (which is the case: WebMSX puts the cartridge
in slot 1, `CARTRIDGE1_SLOT: [1]`). On an expanded slot you would also have to
touch the subslot register at 0FFFFh.

**A harness that maps the whole ROM into 4000h-BFFFh never sees this bug.**
`tools/emu_test.js` has a slot model: page 0 = BIOS, 1 = cartridge, 2 and 3 =
RAM, with port 0A8h implemented — and it reproduced the problem immediately.

---

## 12b. Imagery: why the intro moved from G3 to G4

The first attempt was tiled (SCREEN 4). It produced artefacts and the cause is
structural: G3 accepts **two colours per 8×1 pixel segment**, and in a logo with
an outline the pair becomes outline+band or outline+background — a colour always
gets left out. You can mitigate it (testing every pair on each line, rather than
taking the two most frequent, helps a lot), but it does not go away.

In **SCREEN 5 (G4)** that restriction does not exist: a 4-bits-per-pixel
framebuffer, 2 pixels per byte, high nibble = left pixel, 128 bytes per line.
`tools/bmp2msx.py` has both converters; `converter_g4` is the one used.

### Width 256, not 240
At 256 px a line occupies exactly 128 bytes and the whole image becomes **one
contiguous block**: a single sequential write, with no per-line address
recalculation. It costs 672 bytes of padding and saves code and time.

### 17-bit VRAM pointer
Port 99h carries only **14 bits** of the address; the upper ones come from
**R#14**. The G4 framebuffer goes past 0x3FFF, so R#14 must always be written —
**including when it is zero**, because the VDP increments R#14 by itself when
crossing each 16 KB boundary (`checkVRAMPointerWrap` in VDP.js). A `SETV` that
writes only the low 14 bits works in G3 and fails in G4 as soon as an earlier
write crossed the boundary.

### R#2 in G4 must be 1Fh, not 00h
This is the mistake that leaves the **entire screen in the background colour**
with the framebuffer perfectly written — and the hardest one to see, because
VRAM is correct.

`R#2` does not only define the base: in the VDP it **also** defines the read
mask (`updateLayoutTableAddress` in VDP.js):

```
add                     = (R2 & 0x7F) << 10
layoutTableAddress      = add & layTBase        ; G4's layTBase = -1<<15
layoutTableAddressMask  = add | 0x3FF           ; fixed base for every mode
```

and drawing reads `vram[pos & layoutTableAddressMask]`. With `R2=00`:

```
base = 0        (looks right)
mask = 0x3FF    (the VDP reads only the first 1 KB of VRAM)
```

With `R2=1Fh`:

```
base = 0x7C00 & (-1<<15) = 0        (framebuffer at 0, as intended)
mask = 0x7C00 | 0x3FF    = 0x7FFF   (the page's full 32 KB)
```

Check G3 with the same formula: `R2=06` → base `0x1800`, mask `0x1BFF`, which
covers the Name Table's 768 bytes.

### Switching modes costs a VRAM rebuild
The G4 framebuffer occupies 0x0000–0x5FFF, which is exactly where G3's pattern,
colour, name and sprite tables live. Going back to the game requires rebuilding
all of them (`CLRBG` + `SCRINI` + `SPRUP` + `COLINIT` + `SATCLR`), with the
display off. That is ~35 KB of VRAM writes, about 0.4 s.

### The cost of drawing text on the bitmap
In G3, writing text is 1 byte per character in the Name Table. In G4 it is
**32 bytes per character** (8 lines × 4 bytes). Redrawing the whole menu every
frame cost ~66,000 T-states — **more than one frame** — which dropped the frame
rate and took the music's tempo down with it. Redraw only when the content
changes.

### Black background = transparent
Pixels with luminance below the threshold become the background index. In the
Pong logo, threshold 95 also removes the dark echo the artwork has at the top.

---

## 12c. Testing with the real VDP

`tools/emu_test.js` runs the ROM with WebMSX's **real VDP.js and CPU.js**, with
stubs only for canvas, audio and monitor, and writes the rendered frame as PPM:

```bash
node tools/emu_test.js release/pong-ai.rom 120 /tmp/frame.ppm '[[200,206,"low"],[240,246,"ok"]]'
```

It also prints the VDP's internal state (`vdp.eval(...)`): `modeData.name`,
`layoutTableAddress`, `layoutTableAddressMask`, `videoDisplayed`, the registers,
the VRAM pointer.

**A simplified VDP model is no good for validating a mode change.** A harness
that merely accumulates VRAM writes into an array and redraws externally shows
the right image even when the real machine shows an empty screen — which is
exactly what happened with `R#2` above. For geometry and game logic the simple
model is enough; for video mode, addressing and palette, use the real VDP.

---

## 13. Music pipeline from .mid

```
midi/*.mid  ->  tools/mid2pong.py  ->  tools/music_data.py  ->  build_pong.py
```

`tools/midparse.py` reads a Standard MIDI File (format 0 and 1), including the
tempo map, and returns the notes in ticks. `mid2pong.py` converts ticks into
frames (**60 Hz**: with `R9` bit1 = 0 the VDP stays in NTSC) and reduces
polyphony to the 3 available voices:

```
voice 0 = highest sounding note   (melody)
voice 1 = second highest          (counter-melody)
voice 2 = lowest note             (bass)
```

The timeline is built frame by frame and compressed with RLE. **The RLE must
also break on a new attack**, otherwise two identical consecutive eighth notes
turn into a single quarter note.

ROM format: `(note, duration)` pairs, note 0 = silence, 255 = end (loops back to
the start). Duration in 1 byte, so a note longer than 255 frames gets split.

### 6 voices, not 3
The YM2413 in rhythm mode leaves channels **0..5** free for melody (6/7/8 are
taken by the effects' percussion); the PSG only has 3. So the converter
generates 6 tracks ordered by **importance**, not by pitch:

```
voice 0 = highest (melody)   voice 1 = second highest   voice 2 = lowest (bass)
voices 3..5 = the middle ones, from highest to lowest
```

Anything playing only 3 channels uses 0/1/2 and still gets the essentials — the
same data serves both chips. Going from 3 to 6 voices cost only **+1742 bytes**
across both tracks: voices 4 and 5 are silent almost all the time, and the RLE
collapses that.

### ROM cost
Size depends on density, not duration. Measured references:

| Track | notes | duration | polyphony | bytes |
|---|---|---|---|---|
| Animal Crossing – Load Game | 290 | 77 s | 5 | 983 |
| Animal Crossing – 100 PM | 524 | 131 s | 3 | 1965 |
| Pokémon HGSS – Game Corner | 1728 | 127 s | 8 | 5393 |
| Pokémon RBY – Game Corner | 827 | 73 s | 4 | 2419 |

The ROM **must fit the declared size**: going past it does not merely make the
file bigger, it changes the mapping rule WebMSX picks (`SlotFormats.js` treats
each size range as a different format). `build_pong.py` fails the build if the
last symbol reaches `0xC000`.

This repository's `msxasm` generalises that: a binary larger than the declared
`--size` is an error, never truncation, and ROMs above 32 KB become possible via
`MAPPER KONAMI` — with the format hint in the filename, because four mappers
share an identical detection rule in WebMSX. See [`reference.en.md`](reference.en.md).

*Manual generated 2026-05-22, updated 2026-08-22 — WebMSX 6.0.8 — MSX2 V9938.
Corrections and cross-references to msxasm added 2026-08-31.*
