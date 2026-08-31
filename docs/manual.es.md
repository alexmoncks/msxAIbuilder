# Manual de Desarrollo MSX — WebMSX

**Idiomas:** [Português](manual.md) · [English](manual.en.md) · [Español](manual.es.md)

## Índice
1. [Arquitectura del MSX](#1-arquitectura-del-msx)
2. [VDP V9938 — modos de vídeo](#2-vdp-v9938)
3. [Screen 4 (G3) — mosaico con sprites](#3-screen-4-g3)
4. [Screen 5 (G4) — bitmap con sprites](#4-screen-5-g4)
5. [Sistema de sprites (spriteMode 2)](#5-sistema-de-sprites)
6. [Paleta V9938](#6-paleta-v9938)
7. [Registros del VDP](#7-registros-del-vdp)
8. [Sonido PSG AY-3-8910](#8-sonido-psg)
9. [Música YM2413 (OPLL)](#9-musica-ym2413)
10. [Análisis de Birdy Flap](#10-analisis-birdy-flap)
11. [Pong AI — código de referencia](#11-pong-ai)
12. [Trampas comunes](#12-trampas-comunes)
13. [Pipeline de música desde .mid](#13-pipeline-de-musica)

---

## 1. Arquitectura del MSX

### Mapa de memoria
```
0000-3FFF  BIOS/ROM del sistema (solo lectura)
4000-7FFF  Ranura del cartucho (página 1)
8000-BFFF  Ranura del cartucho (página 2, espejo de 16 KB)
C000-FFFF  RAM principal (64 KB)
  C000-DFFF  Libre para programas
  E000-F37F  Área de trabajo del sistema
  F380-FFFF  Pila y variables del sistema
```

### Mapa de E/S (puertos relevantes)
```
98h    VDP — datos de VRAM (lectura/escritura)
99h    VDP — dirección de VRAM / registro
9Ah    VDP — escritura de paleta (V9938+)
9Bh    VDP — registro indirecto (V9938+)
A0h    PSG — selección de registro
A1h    PSG — datos del registro
A9h    PPI — puerto A (teclado, fila)
AAh    PPI — puerto B (teclado, columna)
7Ch    YM2413 — selección de registro (FMI)
7Dh    YM2413 — datos (FMD)
```

---

## 2. VDP V9938

### Modos de vídeo (screen modes)
El modo se selecciona con los bits M2-M5 de los registros R#0 y R#1:

```
modeBits = (R1 & 0x18) | ((R0 & 0x0e) >> 1)

Valor  Nombre  Descripción               Resolución  Colores  ppb
0x00   G1      Graphics 1 (TMS9918)      256×192     16       8
0x01   G2      Graphics 2 (TMS9918)      256×192     16       8
0x02   G3      Graphics 3 (Screen 4)     256×192     16       8 **
0x03   G4      Graphics 4 (Screen 5)     256×212     16       2
0x04   G5      Graphics 5 (Screen 6)     512×212     4        2
0x05   G6      Graphics 6 (Screen 7)     512×212     16       2
0x07   G7      Graphics 7 (Screen 8)     256×212     256      1
```

** ppb = píxeles por byte

### Screen 4 (G3) — mosaico
- 256×192 píxeles, 16 colores por píxel
- Mosaico: Name Table + Pattern Table + Color Table
- 32×24 tiles de 8×8 píxeles
- Sprites: spriteMode 2 (el mismo de G4/G5/G6/G7)

### Screen 5 (G4) — bitmap
- 256×212 píxeles, 16 colores por píxel
- 2 píxeles por byte (4 bits cada uno)
- Framebuffer directo: 128 bytes por línea
- Sprites: spriteMode 2 (idéntico a G3)

### Máscaras de base (sprAttrTBase)
Cada modo define máscaras distintas para las tablas:

| Modo | layTBase | colorTBase | patTBase | sprAttrTBase |
|------|----------|------------|----------|-------------|
| G3   | -1<<10   | -1<<13     | -1<<13   | -1<<10      |
| G4   | -1<<15   | 0          | 0        | -1<<10      |
| G5   | -1<<15   | 0          | 0        | -1<<10      |
| G6   | -1<<16   | 0          | 0        | -1<<10      |

**Importante**: la máscara `-1<<10` exige que la dirección de la SAT tenga el
bit 10 o superior activado.
- R5=4 → (4<<7)=0x200 → enmascarado a 0 (¡inválido!)
- R5=8 → (8<<7)=0x400 → sobrevive a la máscara → SAT=0x400 ✓
- R5=0x3F → (0x3F<<7)=0x1F80 → sobrevive → SAT=0x1C00 ✓

### Cálculo de la dirección SAT (spriteMode 2)
```
add = (R11 << 15) | (R5 << 7)   // limitado a 17 bits (0x1FFFF)
SAT = add & sprAttrTBase          // aplica la máscara del modo
YPT = SAT + 512                   // Tabla Y,X,PN (spriteMode 2)
ColorTable = SAT                  // Tabla de colores (16 bytes/sprite)
```

---

## 3. Screen 4 (G3)

### Registros esenciales (12 registros)
```
R0=04  R1=E2  R2=nn  R3=nn  R4=nn  R5=nn
R6=nn  R7=nn  R8=nn  R9=00  R10=00 R11=00
```

### Tablas de tiles en G3
- **Name Table** en R2 × 0x400 (768 bytes: 32×24 tiles)
- **Pattern Table** (256 chars × 8 bytes = 2048 bytes) en R4 × 0x800, enmascarada por -1<<13
- **Color Table** (1 byte por tile) en (R10<<14)|(R3<<6), enmascarada por -1<<13

### Ejemplo Birdy Flap (G3 funcional)
```
R0=04 R1=A2→E2 R2=06 R3=FF R4=03 R5=3F
R6=07 R7=01 R8=00 R9=00 R10=00 R11=00

Name Table:  0x1800  (R2=6 × 0x400)
Pattern:     0x0000  (R4=3, enmascarado)
Color:       0x0000  (R3=0xFF, enmascarado)
SAT:         0x1C00  (R5=0x3F<<7 & -1<<10)
YPT:         0x1E00  (SAT+512)
Spr Pat:     0x3800  (R6=7 × 0x800)
```

---

## 4. Screen 5 (G4)

### Diferencias con G3
- **Sin Name Table**: framebuffer bitmap directamente en la VRAM
- **128 bytes/línea**: cada byte = 2 píxeles (nibble alto = píxel izquierdo, bajo = derecho)
- **Altura**: 212 líneas (PAL) en lugar de 192 (NTSC)
- **Sprites**: el MISMO spriteMode 2 de G3 (renderSpritesLineMode2)
- **R2**: controla la base del framebuffer (enmascarado por -1<<15)

### La limitación de SETV
Las direcciones de VRAM ≥ 0x8000 NO pueden escribirse mediante un SETV normal
(puerto 0x99), porque un byte alto con el bit 7=1 se interpreta como «escritura
de registro». Usa R#14/R#15 para direccionar VRAM por encima de 32 KB.

### Disposición de la VRAM en G4 (framebuffer en 0)
```
0000-69FF  Framebuffer (128 bytes × 212 líneas = 27.136 bytes)
6A00-FFFF  Libre para SAT, patrones, etc.
```

---

## 5. Sistema de sprites (spriteMode 2)

### Formato de la tabla Y-X-PN (en YPT = SAT + 512)
4 bytes por sprite, 32 sprites máx.:
```
Byte 0: posición Y (216 = terminador)
Byte 1: posición X
Byte 2: número de patrón (PN)
Byte 3: (sin usar)
```

### Formato de la tabla de colores (en SAT)
16 bytes por sprite (1 por línea de barrido), 32 sprites × 16 = 512 bytes:
```
Byte s: color para la línea s del sprite i
  bits 0-3: índice de la paleta (0-15)
  bit 5: IC (Internal Collision)
  bit 6: CC (Complementary Color)
  bit 7: EC (Early Clock, X -= 32)
```

### Dos o más colores en la MISMA línea: el bit CC
Un color por línea ya viene gratis (la tabla de arriba). Para tener **más de un
color en la misma línea**, usa el bit **CC (bit 6)** del color: un sprite con
CC=1 no sustituye al sprite de la misma prioridad que esté debajo — los dos
colores se combinan mediante **OR**.

```
sprite N   (CC=0, color A)  -> dibuja A
sprite N+1 (CC=1, color B)  -> donde solo él tiene píxel: B
                               donde ambos tienen píxel: A OR B
```

Reglas que importan en la práctica (`renderSpritesLineMode2Tiled` en VDP.js):

- El sprite con CC=1 tiene que ir **después** (número mayor) del sprite CC=0, y
  en la misma línea. Si ningún sprite CC=0 se procesó antes en esa línea, el
  sprite CC=1 simplemente se **descarta**.
- Sin CC, el sprite de número mayor se descartaría encima del de número menor
  (prioridad), así que CC es la única forma de superponer color dentro del mismo
  objeto.
- Como el resultado es un **OR**, elige los colores pensando en bits. Ejemplo de
  Pong: cuerpo de la pelota en 12/10/8 y brillo en 5 → `12|5=13`, `10|5=15`,
  `8|5=13` — así que las paletas **13 y 15 tienen que recibir el mismo tono**, o
  el brillo cambia de color según la línea del cuerpo.
- Merece la pena definir también la paleta del color aislado (5, en el ejemplo),
  por si el sprite CC sobrepasa el contorno del de abajo.

### Magnificación y la tabla de colores
Con MAG (`R1` bit0=1), el VDP hace `spriteLine >>= 1` **antes** de indexar el
color. Es decir, con sprites 8x8 magnificados solo se leen las **8 primeras**
entradas de color de cada sprite — una por línea del patrón, no por línea de
pantalla.

### Registro R#1 para sprites
```
bit 0:  0 = sprite 8×8, 1 = sprite 16×16
bit 1:  0 = tamaño normal, 1 = magnificación 2×
```

### Ejemplos:
- R1=0xE2: bit1=1 → sprites 8×8 renderizados como 16×16 (mag 2x)
- R1=0xE0: bit1=0 → sprites 8×8 sin magnificación

### R#8 — control de sprites
```
bit 2 (SPD): 0 = sprites habilitados, 1 = deshabilitados
bit 5 (TP):  0 = color 0 sólido, 1 = color 0 transparente
```

---

## 6. Paleta V9938

### Formato de escritura
Cada entrada de paleta son 2 bytes escritos por el puerto 0x9A:
```
Byte bajo: (R << 4) | B    (R, G, B cada uno 0-7)
Byte alto: G
Valor de 16 bits: (G << 8) | (R << 4) | B
```

### Conversión a 8 bits (por canal)
```
valor de 3 bits -> valor de 8 bits
0 -> 0, 1 -> 36, 2 -> 73, 3 -> 109
4 -> 146, 5 -> 182, 6 -> 219, 7 -> 255
```

### Ejemplo de paleta (16 entradas)
```asm
PAL:
    ; 0: negro      db 00h, 00h
    ; 1: azul       db 07h, 00h    (R=0,G=0,B=7)
    ; 2: verde      db 00h, 07h    (R=0,G=7,B=0)
    ; 3: cian       db 07h, 07h    (R=0,G=7,B=7)
    ; 4: rojo       db 70h, 00h    (R=7,G=0,B=0)
    ; 5: blanco     db 77h, 07h    (R=7,G=7,B=7)
    ; ...32 bytes en total
    db 00h,00h, 07h,00h, 00h,07h, 07h,07h
    db 70h,00h, 77h,07h, 00h,00h, 00h,00h
    db 00h,00h, 00h,00h, 00h,00h, 00h,00h
    db 00h,00h, 00h,00h, 00h,00h, 00h,00h
```

## 7. Registros del VDP

### Protocolo de escritura (puerto 0x99)
Dos bytes para cada operación:
```
1.er byte: valor (dato del registro O byte bajo de la dirección de VRAM)
2.º byte: control
  bit 7 = 1 → escritura de registro (bits 0-5 = nº de registro)
  bit 7 = 0 → dirección de VRAM
    bit 6 = 1 → modo escritura
    bit 6 = 0 → modo lectura
    bits 0-5 = byte alto de la dirección (A13-A8)
```

**IMPORTANTE**: el bit 7 del 2.º byte NUNCA puede ser 1 para direcciones de
VRAM. Eso limita las direcciones directas a < 0x8000. Para VRAM > 32 KB, usa
R#14/R#15.

### Tabla de registros del VDP (V9938)
```
R#   Nombre  Función
0    MODE    Bits M4, M5 del modo de vídeo
1    DISP    Display/Modo (bits M2, M3, IE, BL, SI, SPR)
2    BASE    Base de la Name Table (×0x400) o framebuffer
3    BASE    Base de la Color Table (×0x40)
4    BASE    Base de la Pattern Table (×0x800)
5    SAT     Base de la Sprite Attribute Table (×0x80)
6    SPT     Base de la Sprite Pattern Table (×0x800)
7    BD      Color del borde (índice de la paleta)
8    TP      Transparent Pen / Sprite Disable
9    YAE     Modo YJK/YAE / PAL NTSC
10   BASE    Bits altos de la Color Table
11   BASE    Bits altos de la SAT
12-13        Reservado
14   RV      Bits altos del puntero de VRAM
15   ST      Índice de estado
16   PAL     Índice de paleta para escrituras por 0x9A
17   ADJ     Ajuste indirecto de registro
```

### Registro R#0 (modo)
```
bits 1-3: M4, M5 (combinados con R1 bits 3-4)
0x04 = Screen 4 (G3)
0x06 = Screen 5 (G4)
```

### Registro R#1 (display)
```
bit 0:  0=sprites 8×8, 1=sprites 16×16
bit 1:  0=normal, 1=magnificación 2×
bit 2:  reservado
bit 3-4: M2, M3 (modo)
bit 5:  IE (interrupción de VBlank)
bit 6:  BL (display enable en WebMSX)
bit 7:  reservado (mantener en 0)
```

Valores comunes:
- 0xE2: display encendido, VBlank IE, spr mag 2x, sprites 8×8
- 0xE0: display encendido, VBlank IE, spr normal, sprites 8×8
- 0xA2: display apagado (bit6=0), spr mag 2x (usado en el init de Birdy Flap)

---

## 8. Sonido PSG (AY-3-8910)

### Puertos
```
A0h: selección de registro del PSG
A1h: datos del registro del PSG
```

### Registros del PSG
```
R0:  Canal A — tono (fino)
R1:  Canal A — tono (grueso)
R2:  Canal B — tono (fino)
R3:  Canal B — tono (grueso)
R4:  Canal C — tono (fino)
R5:  Canal C — tono (grueso)
R6:  Ruido — periodo
R7:  Mezclador (también E/S)
R8:  Canal A — volumen
R9:  Canal B — volumen
R10: Canal C — volumen
R11: Envolvente — periodo (fino)
R12: Envolvente — periodo (grueso)
R13: Envolvente — forma
R14: Joystick (solo lectura, puerto 0A2h)
R15: Puerto E/S B — bit6 = puerto del joystick, bit4/5 = pin 8
```

### Joystick
Leer el gatillo 1 del puerto 1:
```asm
    ld a, 15
    out (0A0h), a
    ld a, 8Fh        ; bit6=0 -> puerto 1 ; bit4=0 -> pin 8 en nivel bajo
    out (0A1h), a
    ld a, 14
    out (0A0h), a
    in a, (0A2h)     ; bit0..3 = direcciones, bit4 = gatillo A, bit5 = gatillo B
    and 10h          ; cero = gatillo A pulsado
```
El bit4 de `R15` (pin 8) tiene que estar en **0**, si no WebMSX devuelve un
0x3Fh fijo (`DOMJoykeysControls.readLocalControllerPort`). El valor de reinicio
ya es 8Fh.

### Teclado — fila 8
```
bit0 = SPACE   bit1 = HOME   bit2 = INS   bit3 = DEL
bit4 = LEFT    bit5 = UP     bit6 = DOWN  bit7 = RIGHT
```
Todos activos en **0**. Selecciona la fila en el puerto C del PPI (0AAh) bits
0-3 y lee en el puerto B del PPI (0A9h).

---

## 9. Música YM2413 (OPLL)

### Puertos
```
7Ch: selección de registro (F0)
7Dh: datos (F1)
```

### Inicialización
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

### Percusión / ruido (modo ritmo)

El YM2413 tiene un sector de ritmo que reaprovecha los canales 6, 7 y 8. Ahí es
donde viven los **instrumentos de ruido**: HH (charles), SD (caja) y TCY
(platillo). BD y TOM son afinados, no ruidosos.

```
reg 0Eh   bit5 = activa el modo ritmo
          bit4 = BD   bit3 = SD   bit2 = TOM   bit1 = TCY   bit0 = HH
```

Volúmenes (0 = máximo, 15 = mudo):
```
reg 36h   bits 3-0 = BD          (el nibble alto NO es volumen: BD tiene modulador)
reg 37h   bits 7-4 = HH   bits 3-0 = SD
reg 38h   bits 7-4 = TOM  bits 3-0 = TCY
```

Frecuencias estándar de los canales de percusión (MSX-MUSIC):
```
ch6 (BD)       reg 16h = 20h   reg 26h = 05h
ch7 (HH/SD)    reg 17h = 50h   reg 27h = 05h
ch8 (TOM/TCY)  reg 18h = C0h   reg 28h = 01h
```

**El orden importa**: activa el modo ritmo (0Eh = 20h) **antes** de escribir
36h/37h/38h. Fuera del modo ritmo, esos tres registros son el *instrumento* de
los canales 6/7/8, no el volumen.

**Redisparo**: la percusión solo ataca cuando el bit de key-on pasa de 0 a 1.
Para tocar el mismo sonido dos veces seguidas hay que apagarlo antes:

```asm
    ld a, 0Eh
    ld e, 20h       ; key-off de todo, modo ritmo mantenido
    call FMW
    ld a, 0Eh
    ld e, 21h       ; key-on del HH
    call FMW
```

**Una escritura que no cambia el registro se ignora** (tanto en el chip como en
WebMSX, que compara `register[reg] ^ val`). Para garantizar que un volumen se
aplique en el arranque, escribe antes un valor distinto: `37h = FFh`, luego
`37h = 02h`.

### Tiempo de escritura
El chip exige ≥12 ciclos tras el byte de dirección (puerto 7Ch) y ≥84 ciclos
tras el byte de dato (puerto 7Dh). Un bucle `ld a,n / dec a / jr nz` de 2 y 6
vueltas cubre ambos casos.

---

## 9b. Chips de sonido disponibles en WebMSX

| Chip | Canales | Cómo llega | Situación |
|------|---------|-----------|-----------|
| **PSG** AY-3-8910 | 3 tono + 1 ruido | integrado en todo MSX | siempre disponible |
| **FM / MSX-MUSIC** YM2413 (OPLL) | 9 melódicos, o 6 + 5 percusión | `_MSX2BASE` ya incluye `MSXMUSIC` | siempre disponible en MSX2/2+ |
| **SCC / SCC+** | 5 wavetable | extensión, `PRESETS=SCC` en la URL | disponible, apagado por defecto |
| **Double PSG** | +3 tono | extensión, `PRESETS=DOUBLEPSG` | disponible, apagado por defecto |
| **OPL4 / MoonSound** | 18 FM + wavetable | extensión, `PRESETS=OPL4` | disponible, apagado por defecto |
| **MSX-Audio** Y8950 | 9 FM + ADPCM | — | **no emulado** |

`src/main/msx/rom/SlotFormatsNotSupported.js` lista literalmente
`"MSXAUDIO": 0, // Make Support?`. La base de datos de ROMs reconoce los
cartuchos (Panasonic FS-CA1 y otros) pero el formato no está implementado.

### Notas del PSG
`periodo = (3579545/2) / (16 * frecuencia)`, 12 bits. La nota más grave que cabe
es ~C1 (periodo 3420). El PSG no tiene envolvente por nota utilizable para
melodía (la envolvente es global), así que el decaimiento viene por software.

### Notas del YM2413
`f = F * 49716 * 2^block / 2^19`. Elige el `block` que deje `F` entre 256 y 511
— ahí es donde la resolución es mejor. El byte del registro `20h+canal` es
`10h (key-on) | block<<1 | F bit8`.

---

## 10. Análisis de Birdy Flap

### VREG (12 registros en 0x40DC)
```
R0=04  (G3)
R1=A2  (init: bit6=0 → display en blanco)
R2=06  (name table ×0x400 = 0x1800)
R3=FF  R4=03
R5=3F  (SAT = 0x3F<<7 = 0x1F80 → enmascarado = 0x1C00)
R6=07  (patrones de sprite ×0x800 = 0x3800)
R7=01  (borde = paleta 1)
R8=00  (TP=0, SPD=0)
R9=00  R10=00 R11=00
```

### Tras el init: R1 cambia a 0xE2
```asm
    ld a, 0E2h
    out (0x99), a
    ld a, 81h      ; R1 = 0xE2 (display encendido, IE, spr mag 2x)
    out (0x99), a
```

### Conmutación del display
Birdy Flap inicializa con el display en blanco (R1 bit6=0), configura TODO, y
SOLO ENTONCES activa el display. Evita artefactos.

---

## 11. Pong AI — código de referencia

### Archivos
- `tools/build_pong.py` — código fuente Z80 + script de compilación (v24)
- `tools/minz80asm.py` — ensamblador Z80 de 2 pasadas — hoy refactorizado como
  el paquete [`msxasm`](referencia.es.md) de este repositorio
- `roms/pong-ai-v24.rom` — ROM publicada, **16384 bytes**
  (`md5 03324e8f4febc0e537c9c808c6c33c00`)

> **Corrección.** Versiones anteriores de este manual decían 32 KB. La v24 tiene
> `CART = 16 * 1024` en `build_pong.py`, y la ROM publicada tiene 16384 bytes —
> comprobado el 2026-08-31. Las ROMs de 32 KB en `release/` son builds antiguos.

### Geometría de los sprites con MAG
Los sprites son 8×8 con magnificación (R1 bit0=1), así que cada píxel del patrón
se convierte en 2×2 en pantalla. Pelota y paleta dibujan en las **columnas 2..5**
del patrón, lo que en pantalla se convierte en el intervalo **+4..+11** desde la
X del sprite:

```
paleta P1 (X=8)     ocupa X =  12..19
paleta P2 (X=232)   ocupa X = 236..243
pelota              ocupa X = BX+4..BX+11
```

Por eso la colisión no puede usar la X del sprite directamente: para que la
pelota *toque* la paleta, `BXLP = P1X+8 = 16` y `BXRP = P2X-8 = 224`. Usar la X
en bruto deja holgura de un lado y solapamiento del otro.

El VDP además dibuja el sprite en la línea **Y+1**, así que los límites
verticales son `PMAX = 192-32-1 = 159` y `BYMAX = 192-8-1 = 183`.

### Configuración del VDP (G3 funcional)
```
R0=04  R1=E0  R2=00  R3=01  R4=02
R5=08  R6=04  R7=00  R8=20  (TP=1)

SAT = 0x400  (R5=8 → 8<<7=0x400)
YPT = 0x600  (SAT+512)
Spr Pat = 0x2000 (R6=4)
Color Table = 0x400 (base de la SAT)
```

---

## 12. Trampas comunes

### Enmascaramiento de la dirección SAT
Comprueba que R5 ≥ 8 en G3/G4/G5 (la máscara `-1<<10` pone a cero los valores
por debajo de 0x400).

### Bit 7 de la dirección de VRAM
Nunca uses SETV con direcciones ≥ 0x8000 (el bit 7 provoca una escritura de
registro).

### Constante hexadecimal terminada en 0B/1B (minz80asm)
`_eval` convierte hexadecimal antes que binario. Tras la conversión, `0C00Bh` ya
es `0x0C00B`, y la expresión regular de literal binario `([01]+)B\b` casaba con
el `00B` final:

```
0C00Bh -> 192   (0x00C0)      0Bh -> 0
```

Sin ningún aviso. `PAUSA equ 0C00Bh` se convirtió en una dirección dentro de la
ROM de la BIOS, de modo que la escritura se descartaba y la lectura devolvía
basura. **Corregido** con un lookbehind (`(?<![0-9A-Fx])`), y `_eval` ahora avisa
cuando una expresión no evalúa, en lugar de devolver 0 en silencio.

`build_pong.py` además comprueba, en cada build, que todo equate de variable
está en `0xC000..0xC0FF` y todo equate de VRAM en `0x0000..0x3FFF`.

> En el `msxasm` de este repositorio, una expresión sin resolver ya no es un
> aviso: es un error duro con `archivo:línea`. Un aviso en un build de 3.355
> líneas se pierde, y el resultado era una ROM que ensamblaba limpiamente y
> colgaba la máquina.

### Sincronización de VBlank
Con `ei`, la BIOS lee S#0 y borra el flag de VBlank. El bucle
`in a,(99h); rlca; jr nc` puede fallar. Usa `di` para sondeo directo.

### Inicialización del display
Configura siempre todo ANTES de activar el display. Técnica de Birdy Flap: init
con R1 bit6=0, luego cambiar a bit6=1.

---

## 12a. Cartucho de 32 KB: la página 2 no viene gratis

La BIOS llama al `INIT` de un cartucho de 32 KB con la **página 1**
(4000h-7FFFh) ya en la ranura del cartucho, pero deja la **página 2**
(8000h-BFFFh) en la RAM. Todo lo que la ROM guarde por encima de 0x8000 lee
basura hasta que el propio cartucho conmute la página.

Síntoma real: la música del título sonaba y la del juego no — las pistas del
juego eran justamente las que caían por encima de 0x8000.

```asm
; copia la ranura primaria de la página 1 a la página 2
PG2:
    in a, (0A8h)
    ld b, a
    and 0Ch          ; ranura de la página 1 (bits 2-3)
    rlca
    rlca             ; hacia los bits 4-5 (página 2)
    ld c, a
    ld a, b
    and 0CFh         ; pone a cero los bits de la página 2
    or c
    out (0A8h), a
    ret
```

Vale para ranura **no expandida** (que es el caso: WebMSX pone el cartucho en la
ranura 1, `CARTRIDGE1_SLOT: [1]`). En ranura expandida habría que tocar también
el registro de subranura en 0FFFFh.

**Un harness que mapea la ROM entera en 4000h-BFFFh nunca ve este fallo.**
`tools/emu_test.js` tiene un modelo de ranuras: página 0 = BIOS, 1 = cartucho,
2 y 3 = RAM, con el puerto 0A8h implementado — y reprodujo el problema al
instante.

---

## 12b. Imagen: por qué la apertura salió del G3 y fue al G4

El primer intento fue con mosaico (SCREEN 4). Dio artefactos y la causa es
estructural: el G3 acepta **dos colores por segmento de 8×1 píxeles**, y en un
logo con contorno el par se convierte en contorno+banda o contorno+fondo —
siempre sobra algún color. Se puede mitigar (probar todos los pares de cada
línea en vez de tomar los dos más frecuentes ayuda bastante), pero no
desaparece.

En **SCREEN 5 (G4)** no existe esa restricción: framebuffer de 4 bits por píxel,
2 píxeles por byte, nibble alto = píxel izquierdo, 128 bytes por línea.
`tools/bmp2msx.py` tiene ambos conversores; `converter_g4` es el usado.

### Ancho 256, no 240
Con 256 px la línea ocupa exactamente 128 bytes y la imagen entera se convierte
en **un bloque contiguo**: una sola escritura secuencial, sin recalcular la
dirección por línea. Cuesta 672 bytes de relleno y ahorra código y tiempo.

### Puntero de VRAM de 17 bits
El puerto 99h carga solo **14 bits** de la dirección; los de arriba vienen de
**R#14**. El framebuffer del G4 pasa de 0x3FFF, así que R#14 tiene que
escribirse siempre — **incluso puesto a cero**, porque el VDP incrementa R#14
por su cuenta al cruzar cada frontera de 16 KB (`checkVRAMPointerWrap` en
VDP.js). Un `SETV` que solo escribe los 14 bits bajos funciona en G3 y falla en
G4 en cuanto alguna escritura anterior cruzó la frontera.

### R#2 en G4 tiene que ser 1Fh, no 00h
Este es el error que deja la pantalla **entera del color de fondo** con el
framebuffer perfectamente escrito — y el más difícil de ver, porque la VRAM está
correcta.

`R#2` no define solo la base: en el VDP define **también** la máscara de lectura
(`updateLayoutTableAddress` en VDP.js):

```
add                     = (R2 & 0x7F) << 10
layoutTableAddress      = add & layTBase        ; layTBase del G4 = -1<<15
layoutTableAddressMask  = add | 0x3FF           ; base fija para todos los modos
```

y el dibujado lee `vram[pos & layoutTableAddressMask]`. Con `R2=00`:

```
base    = 0        (parece correcto)
máscara = 0x3FF    (el VDP lee solo el primer 1 KB de la VRAM)
```

Con `R2=1Fh`:

```
base    = 0x7C00 & (-1<<15) = 0        (framebuffer en 0, como se quiere)
máscara = 0x7C00 | 0x3FF    = 0x7FFF   (los 32 KB de la página)
```

Compruébalo en G3 con la misma fórmula: `R2=06` → base `0x1800`, máscara
`0x1BFF`, que cubre los 768 bytes de la Name Table.

### Cambiar de modo cuesta reconstruir la VRAM
El framebuffer del G4 ocupa 0x0000–0x5FFF, que es exactamente donde viven las
tablas de patrón, color, nombre y sprites del G3. Volver al juego exige rehacer
todas ellas (`CLRBG` + `SCRINI` + `SPRUP` + `COLINIT` + `SATCLR`), con el
display apagado. Son ~35 KB de escritura en VRAM, unos 0,4 s.

### Coste de dibujar texto en el bitmap
En G3, escribir texto es 1 byte por carácter en la Name Table. En G4 son **32
bytes por carácter** (8 líneas × 4 bytes). Redibujar el menú entero en cada
fotograma costaba ~66.000 T-states — **más que un fotograma** —, lo que hundía la
tasa de fotogramas y con ella el tempo de la música. Redibuja solo cuando el
contenido cambia.

### Fondo negro = transparente
Los píxeles con luminancia por debajo del umbral pasan al índice del fondo. En el
logo de Pong, el umbral 95 elimina además el eco oscuro que el arte tiene arriba.

---

## 12c. Probar con el VDP de verdad

`tools/emu_test.js` ejecuta la ROM con el **VDP.js y el CPU.js reales** de
WebMSX, con stubs solo para canvas, audio y monitor, y graba el fotograma
renderizado en PPM:

```bash
node tools/emu_test.js release/pong-ai.rom 120 /tmp/fotograma.ppm '[[200,206,"bajo"],[240,246,"ok"]]'
```

También imprime el estado interno del VDP (`vdp.eval(...)`): `modeData.name`,
`layoutTableAddress`, `layoutTableAddressMask`, `videoDisplayed`, los registros,
el puntero de VRAM.

**Un modelo simplificado del VDP no sirve para validar un cambio de modo.** Un
harness que solo acumula las escrituras de VRAM en un array y redibuja por fuera
muestra la imagen correcta incluso cuando la máquina real muestra pantalla vacía
— que es exactamente lo que pasó con el `R#2` de arriba. Para geometría y lógica
de juego el modelo simple basta; para modo de vídeo, direccionamiento y paleta,
usa el VDP real.

---

## 13. Pipeline de música desde .mid

```
midi/*.mid  ->  tools/mid2pong.py  ->  tools/music_data.py  ->  build_pong.py
```

`tools/midparse.py` lee un Standard MIDI File (formatos 0 y 1), incluido el mapa
de tempo, y devuelve las notas en ticks. `mid2pong.py` convierte ticks a
fotogramas (**60 Hz**: con `R9` bit1 = 0 el VDP se queda en NTSC) y reduce la
polifonía a las 3 voces disponibles:

```
voz 0 = nota más aguda sonando   (melodía)
voz 1 = segunda más aguda        (contracanto)
voz 2 = nota más grave           (bajo)
```

La línea de tiempo se monta fotograma a fotograma y se comprime por RLE. **El
RLE tiene que romper también en ataque nuevo**, si no dos corcheas iguales
seguidas se convierten en una sola negra.

Formato en la ROM: pares `(nota, duración)`, nota 0 = silencio, 255 = fin (vuelve
al inicio). Duración en 1 byte, así que una nota más larga que 255 fotogramas se
divide.

### 6 voces, no 3
El YM2413 en modo ritmo deja los canales **0..5** libres para melodía (6/7/8 se
quedan con la percusión de los efectos); el PSG solo tiene 3. Por eso el
conversor genera 6 pistas ordenadas por **importancia**, no por altura:

```
voz 0 = más aguda (melodía)   voz 1 = segunda más aguda   voz 2 = más grave (bajo)
voces 3..5 = las del medio, de la más aguda a la más grave
```

Quien toca solo 3 canales usa 0/1/2 y ya se queda con lo esencial — el mismo dato
sirve para ambos chips. Pasar de 3 a 6 voces costó solo **+1742 bytes** en las
dos músicas juntas: las voces 4 y 5 están casi siempre en silencio, y el RLE lo
colapsa.

### Coste en ROM
El tamaño depende de la densidad, no de la duración. Referencias medidas:

| Música | notas | duración | polifonía | bytes |
|---|---|---|---|---|
| Animal Crossing – Load Game | 290 | 77 s | 5 | 983 |
| Animal Crossing – 100 PM | 524 | 131 s | 3 | 1965 |
| Pokémon HGSS – Game Corner | 1728 | 127 s | 8 | 5393 |
| Pokémon RBY – Game Corner | 827 | 73 s | 4 | 2419 |

La ROM **tiene que caber en el tamaño declarado**: pasarse no deja el archivo
solo más grande, cambia la regla de mapeo que WebMSX elige (`SlotFormats.js`
trata cada franja de tamaño como un formato distinto). `build_pong.py` falla el
build si el último símbolo llega a `0xC000`.

El `msxasm` de este repositorio lo generaliza: un binario mayor que el `--size`
declarado es error, nunca truncamiento, y las ROMs por encima de 32 KB pasan a
ser posibles mediante `MAPPER KONAMI` — con la pista de formato en el nombre del
archivo, porque cuatro mappers comparten una detección idéntica en WebMSX. Ver
[`referencia.es.md`](referencia.es.md).

*Manual generado el 22/05/2026, actualizado el 22/08/2026 — WebMSX 6.0.8 —
MSX2 V9938. Correcciones y referencias cruzadas a msxasm añadidas el
2026-08-31.*
