# MSX2 Graphics Spec

**Languages:** [Português](msx2-spec-grafica.md) · [English](msx2-graphics-spec.en.md) · [Español](msx2-spec-grafica.es.md)

Architecture decisions document. Target: MSX2 (V9938), SCREEN 5.
Status: decisions settled in conversation, validated against existing code in §9.

---

## 1. Video mode and VRAM usage

**SCREEN 5 (Graphic 4)**, 256x212, 16 simultaneous colours from a palette of 512.
128 KB of VRAM split into 4 pages of 32 KB.

| Page | Use |
|------|-----|
| 0 | Visible buffer / double buffer A |
| 1 | Work buffer / double buffer B |
| 2 | Scenery tile bank |
| 3 | Character and boss animation frames |

The visible page is swapped through R#2, costing one register write, executed
during vblank.

**Watch the page's internal layout.** Sprite tables do not live on a separate
page: each 32 KB page has its own, at the BIOS default offsets (roughly
base+#7400 colours, base+#7600 attributes, base+#7800 patterns). Since pages 0
and 1 alternate as visible, the sprite tables of both must be kept in sync, or
you accept one frame of hitbox lag.

> **Corrected during validation — see §9.2.** The sync is not necessary. Sprite
> tables are addressed by R#5/R#11 and R#6, independent of R#2. Flipping the
> visible page does not move the tables: point both pages at a single set and
> the problem disappears, along with the frame of lag.

**Budget consequence:** with double buffering, 64 KB remain (pages 2 and 3) for
tiles and frames, not 96 KB.

---

## 2. Drawing characters (blitter)

Every character, boss and animated element is drawn by the V9938 command
engine. No hardware sprite is spent on visible drawing.

**Standard command:** `LMMM` with a transparent logical operation (`TIMP`),
copying the frame from the bank page to the work page.

Sequence per object:
1. Restore the background at the previous position (`HMMM` from the clean
   scenery page)
2. Copy the new frame (`LMMM` + `TIMP`)

Registers involved: R#32 through R#45 (SX, SY, DX, DY, NX, NY, CLR, ARG) and
R#46 (CMR, which fires the command). Before writing a new command, check the CE
bit in S#2.

**Cycle budget.** The blitter competes with screen refresh for VRAM access. It
is considerably faster with the display off or during vblank. The real number of
16x16 blits per frame must be measured on the target before committing to an
on-screen object density. Mark this as an instrumentation task (raster counter).

**H versus L commands.** The `H*` commands operate on whole bytes (faster,
2-pixel granularity in SCREEN 5). The `L*` commands operate pixel by pixel and
accept a logical operation. Use `H*` for aligned background restoration and `L*`
for drawing the object.

---

## 3. Collision

### 3.1 Object collision: transparent sprites

V9938 collision detection looks at pattern bits, not colour. A sprite with
colour 0 is not rendered but still collides. That allows invisible hitboxes.

**Project rule:** hitboxes cover weak points only, never the silhouette. A
64x48 boss spends 3 sprites (head, core, tail) instead of 12 to cover the whole
body. A technical and a gameplay win at once: the player has to aim.

**Configuration:**
- Sprite mode 2, colour 0 on hitboxes
- CC bit = 0 on hitboxes, on the player and on shots (they take part in
  collision)
- CC bit = 1 on any decorative sprite (does not take part)
- Magnification when the weak point is large: a magnified 16x16 sprite covers
  32x32 using a single slot. The 2-pixel granularity is irrelevant for a hitbox

**Per-frame reads:**
- S#0 bit 5 (C flag): a collision occurred. Reading S#0 clears the flag, so read
  it once per frame
- S#3/S#4 (X) and S#5/S#6 (Y): coordinates of the collision point

**Resolving the ambiguity.** The flag is global and does not say who collided.
Strategy: use the coordinate read to identify the weak point geometrically. If
the weak points sit in distinct Y bands, Y resolves it alone. If they coincide
in Y, X resolves it. Only when both coincide do you run a software bounding box,
and only on the objects near the coordinate read.

**Sprite budget.** Limit of 8 per scanline. Test the worst case: player pressed
against the boss firing multiple shots. With 3 weak points there is slack; from
5 upwards the test becomes mandatory.

**Correction about removing a hitbox.** To disable a destroyed weak point, move
the sprite off screen (Y >= 212). Do not use Y = 216 for this: in sprite mode 2
that value terminates processing of the entire list from that slot onward,
erasing the following sprites too.

### 3.2 Scenery collision

Collision map in RAM, indexed by tile. Never use `POINT` or VRAM reads for this;
the cost per query is far too high.

---

## 4. Palette

16 entries, 3 bits per channel (values 0 to 7). It is not continuous RGB: it is
8 discrete levels per component.

### 4.1 Partition

| Range | Use |
|-------|-----|
| 0 | Transparent |
| 1 to 5 | Scenery |
| 6 to 11 | Character and boss (6 entries) |
| 12 to 13 | Effects and accents |
| 14 to 15 | HUD, exclusive |

The character's sixth entry was taken from the scenery, not from the effects.
Rationale: large flat background areas absorb dithering far better than a small
moving object, which shimmers.

With 6 entries the character gets two 3-tone ramps (body and detail) or one
4-tone ramp plus 2 accents, instead of a single cramped ramp.

### 4.2 HUD

Entries 14 and 15 are exclusive and never touched by fade, flash or colour
cycling. Without that, the score flashes along with the damage effect.

If the HUD occupies a fixed band of the screen, it becomes a candidate for a
per-line palette split (R#19 + IE1), which returns those entries to the scenery
in the upper part of the screen.

### 4.3 Effects

Writing: set R#16 with the entry, then 2 writes to port #9A (one byte with R and
B, another with G). The whole palette takes 32 writes, which fits in vblank.

- **Fade:** precomputed table with a non-linear curve, more steps in the dark
  range. With 8 levels per channel, a linear fade is visibly stepped. Space the
  steps 2 or 3 frames apart
- **Colour cycling:** rotate 3 or 4 entries for water, lava, portals. Near-zero
  cost, high visual return
- **Boss damage flash:** prefer `LMMV` with a logical operation over the boss
  area for 2 frames, rather than touching the palette. Since character and boss
  share entries 6 to 11, a palette flash would flash both

---

## 5. Dithering

Used to compensate for the palette partition, mainly in the scenery.

**Mandatory rule:** the checker pattern is baked into the frame's bitmap,
anchored to the object's coordinates. Never generated at runtime anchored to the
screen. Anchored to the screen, the pattern "walks" under the moving object and
turns into static.

Choose pairs with a small luminance difference. On composite, horizontal
blending helps; on RGB, an overly contrasted pair shows up as a grid.

---

## 6. Animation data structure

Each animation frame carries, besides the bitmap:

```
frame:
  vram_src_x, vram_src_y     ; origin in the bank page
  width, height
  n_hitboxes
  hitbox[]:
    dx, dy                   ; offset relative to the object's anchor
    sprite_slot
    weak_point_id
```

Hitbox offsets come from the same table that defines the frame. If the sprite
coordinates are computed elsewhere, the hitbox drifts away from the drawing
during animation.

---

## 7. Open items

- [ ] Measure the real cost of a 16x16 `LMMM` with the display on, on the
      target, and settle the maximum number of objects per frame
- [ ] Test the worst case of 8 sprites per line (player pressed against the boss
      with multiple shots)
- [ ] Define the concrete palette (RGB values of the 16 entries)
- [ ] Decide whether the per-line palette split makes v1 or waits
- [x] Validate this spec against the code already in the repository — see §9

---

## 8. Notes on discarded alternatives

- **SCREEN 8:** 256 fixed colours, but loses the programmable palette (poor blue
  and green tones), drops to 2 pages, and the blitter gets slower per pixel.
  Discarded for a game with an animated boss
- **SCREEN 12 (YJK, MSX2+):** only if the target moves to MSX2+. Caveat: visible
  chroma artefacts on high-contrast edges
- **Hitbox covering the whole silhouette:** blows the 8-sprites-per-line budget
  with no gameplay gain

---

## 9. Validation against the code (§7, item 5)

Performed 2026-08-31 against WebMSX v6.0.8 (`4f4009e8`), the same commit pinned
in `vendor/webmsx`, and against `tools/build_pong.py` from Pong AI v24. Every
item below was read in the code, not assumed.

### 9.1 Y = 216 terminates the list — CONFIRMED

```js
// src/main/msx/video/VDP.js:1930
if (y === 216) break;    // Stop Sprite processing for the line, as per spec
```

The emulator implements exactly the behaviour described in §3.1. The rule of
hiding a hitbox with `Y >= 212` and never `216` is correct and should become a
runtime routine (`SPR_HIDE`), not a documented convention — conventions get
forgotten.

### 9.2 Sprite table sync between pages — UNNECESSARY

§1 concludes that the sprite tables of pages 0 and 1 must be kept in sync. The
premise is true (the BIOS default layout places a set of tables inside each
32 KB page), but the conclusion does not follow.

```js
// src/main/msx/video/VDP.js:362,471 — R#2 touches ONLY the layout table
case 2: if (mod & 0x7f) updateLayoutTableAddress();
    var add = ... (register[2] & 0x7f) << 10;

// src/main/msx/video/VDP.js:389,487 — sprites come from R#5/R#11 and R#6
spriteAttrTableAddress    = add & modeData.sprAttrTBase;   // R#5 / R#11
spritePatternTableAddress = ...                            // R#6
```

R#2 addresses the bitmap. Sprite tables are addressed by different registers.
**Flipping the visible page does not move the sprite tables.** Simply leave
R#5/R#11/R#6 pointing at a single set and both pages share it.

Consequences: the per-frame sync work disappears, the frame of hitbox lag
disappears, and the choice of which page hosts the tables becomes arbitrary. The
cost is 2 KB spent on one page; the equivalent region on the other page is free
for data, provided the packer knows it is not contiguous.

### 9.3 Blitter cost is NOT measurable in WebMSX — §7 item 1 blocked

```js
// src/main/msx/video/VDPCommandProcessor.js:3
// Commands perform all operation instantaneously at the first cycle.
// Duration is estimated and does not consider VRAM access slots
```

§2 wants to measure how many 16x16 blits fit in a frame, and correctly
identifies the cause: the blitter competes with screen refresh for VRAM. **That
competition is precisely what WebMSX does not model.** Duration is estimated by
a formula with a fixed correction factor (`COMMAND_PER_PIXEL_DURATION_FACTOR =
1.1`), and the command executes entirely on the first cycle.

The headless harness serves to prove blitter *correctness* — the right pixels in
the right place. It does not serve to settle a cycle budget. That number needs
real hardware or an emulator with more faithful VDP timing.

**Design consequence:** on-screen object density cannot be decided in the
emulator. The runtime should expose an instrumented raster counter from the
start, so the measurement can happen on target as soon as hardware is available,
without rework.

### 9.4 Relative cost estimates per command

Even though the absolute numbers do not hold (§9.3), the relative ordering comes
from the code and supports the "H* for background, L* for object" rule from §2:

| Command | Cycles per unit | Per line |
|---|---|---|
| `YMMM` | 40R + 24W = 64 | 0 |
| `HMMV` | 48W | 56 |
| `HMMM` | 64R + 24W = 88 | 64 |
| `LMMV` | 72R + 24W = 96 | 64 |
| `LMMM` | 64R + 32R + 24W = 120 | 64 |

`LMMM` costs about 1.4x `HMMM` per unit — and since in SCREEN 5 the `H*`
commands operate on 2-pixel bytes, the ratio per drawn area approaches 2.7x. The
§2 rule is right, and the gain is larger than "faster" suggests.

### 9.5 Pong does not use the command engine — THIS IS NEW CODE

A sweep of `tools/build_pong.py` for ports `#9B`, registers R#32 through R#46
and command names found no occurrences. Pong AI v24 draws entirely with hardware
sprites and direct VRAM writes.

There is nothing to extract for the blitter module. `blit.asm`, `page.asm`
(double buffering) and the VRAM frame packer are **new code written from
scratch**, not a refactor of proven code. It is the largest slice of technical
risk in the project, and deserves a target game of its own rather than riding
along with the Pong port.
