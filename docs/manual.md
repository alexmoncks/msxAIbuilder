# Manual de Desenvolvimento MSX — WebMSX

**Idiomas:** [Português](manual.md) · [English](manual.en.md) · [Español](manual.es.md)

## Sumário
1. [Arquitetura do MSX](#1-arquitetura-do-msx)
2. [VDP V9938 — Modos de Vídeo](#2-vdp-v9938)
3. [Screen 4 (G3) — Tiled com Sprites](#3-screen-4-g3)
4. [Screen 5 (G4) — Bitmap com Sprites](#4-screen-5-g4)
5. [Sistema de Sprites (spriteMode 2)](#5-sistema-de-sprites)
6. [Paleta V9938](#6-paleta-v9938)
7. [Registradores VDP](#7-registradores-vdp)
8. [Som PSG AY-3-8910](#8-som-psg)
9. [Música YM2413 (OPLL)](#9-musica-ym2413)
10. [Análise Birdy Flap](#10-analise-birdy-flap)
11. [Pong AI — Código de Referência](#11-pong-ai)
12. [Expansões de Memória](#12-expansoes-memoria)

---

## 1. Arquitetura do MSX

### Mapa de Memória
```
0000-3FFF  BIOS/ROM do sistema (somente leitura)
4000-7FFF  Slot do cartucho (página 1)
8000-BFFF  Slot do cartucho (página 2, mirror 16KB)
C000-FFFF  RAM principal (64KB)
  C000-DFFF  Livre para programas
  E000-F37F  Área de trabalho do sistema
  F380-FFFF  Pilha e variáveis do sistema
```

### Mapa de I/O (portas relevantes)
```
98h    VDP — dados VRAM (leitura/escrita)
99h    VDP — endereço VRAM / registrador
9Ah    VDP — escrita de paleta (V9938+)
9Bh    VDP — registrador indireto (V9938+)
A0h    PSG — seleção de registrador
A1h    PSG — dados do registrador
A9h    PPI — porta A (teclado, linha)
AAh    PPI — porta B (teclado, coluna)
7Ch    YM2413 — seleção de registrador (FMI)
7Dh    YM2413 — dados (FMD)
```

---

## 2. VDP V9938

### Modos de Vídeo (Screen Modes)
O modo é selecionado pelos bits M2-M5 nos registradores R#0 e R#1:

```
modeBits = (R1 & 0x18) | ((R0 & 0x0e) >> 1)

Valor  Nome    Descrição                 Resolução  Cores  ppb
0x00   G1      Graphics 1 (TMS9918)      256×192    16     8
0x01   G2      Graphics 2 (TMS9918)      256×192    16     8
0x02   G3      Graphics 3 (Screen 4)     256×192    16     8 **
0x03   G4      Graphics 4 (Screen 5)     256×212    16     2
0x04   G5      Graphics 5 (Screen 6)     512×212    4      2
0x05   G6      Graphics 6 (Screen 7)     512×212    16     2
0x07   G7      Graphics 7 (Screen 8)     256×212    256    1
```

** ppb = pixels por byte

### Screen 4 (G3) — Tiled
- 256×192 pixels, 16 cores por pixel
- Tiled: Name Table + Pattern Table + Color Table
- 32×24 tiles de 8×8 pixels
- Sprites: spriteMode 2 (mesmo do G4/G5/G6/G7)

### Screen 5 (G4) — Bitmap
- 256×212 pixels, 16 cores por pixel
- 2 pixels por byte (4 bits cada)
- Framebuffer direto: 128 bytes por linha
- Sprites: spriteMode 2 (idêntico ao G3)

### Máscaras de Base (sprAttrTBase)
Cada modo define máscaras diferentes para as tabelas:

| Modo | layTBase | colorTBase | patTBase | sprAttrTBase |
|------|----------|------------|----------|-------------|
| G3   | -1<<10   | -1<<13     | -1<<13   | -1<<10      |
| G4   | -1<<15   | 0          | 0        | -1<<10      |
| G5   | -1<<15   | 0          | 0        | -1<<10      |
| G6   | -1<<16   | 0          | 0        | -1<<10      |

**Importante**: A máscara `-1<<10` exige que o endereço SAT tenha bit 10 ou superior setado.
- R5=4 → (4<<7)=0x200 → mascarado para 0 (inválido!)
- R5=8 → (8<<7)=0x400 → sobrevive à máscara → SAT=0x400 ✓
- R5=0x3F → (0x3F<<7)=0x1F80 → sobrevive → SAT=0x1C00 ✓

### Cálculo do Endereço SAT (spriteMode 2)
```
add = (R11 << 15) | (R5 << 7)   // limitado a 17 bits (0x1FFFF)
SAT = add & sprAttrTBase          // aplica máscara do modo
YPT = SAT + 512                   // Tabela Y,X,PN (spriteMode 2)
ColorTable = SAT                  // Tabela de cores (16 bytes/sprite)
```

---

## 3. Screen 4 (G3)

### Registradores Essenciais (12 registros)
```
R0=04  R1=E2  R2=nn  R3=nn  R4=nn  R5=nn
R6=nn  R7=nn  R8=nn  R9=00  R10=00 R11=00
```

### Tabelas de Tile em G3
- **Name Table** em R2 × 0x400 (768 bytes: 32×24 tiles)
- **Pattern Table** (256 chars × 8 bytes = 2048 bytes) em R4 × 0x800, mascarado por -1<<13
- **Color Table** (1 byte por tile) em (R10<<14)|(R3<<6), mascarado por -1<<13

### Exemplo Birdy Flap (G3 funcional)
```
R0=04 R1=A2→E2 R2=06 R3=FF R4=03 R5=3F
R6=07 R7=01 R8=00 R9=00 R10=00 R11=00

Name Table:  0x1800  (R2=6 × 0x400)
Pattern:     0x0000  (R4=3, mascarado)
Color:       0x0000  (R3=0xFF, mascarado)
SAT:         0x1C00  (R5=0x3F<<7 & -1<<10)
YPT:         0x1E00  (SAT+512)
Spr Pat:     0x3800  (R6=7 × 0x800)
```

---

## 4. Screen 5 (G4)

### Diferenças do G3
- **Sem Name Table**: framebuffer bitmap diretamente na VRAM
- **128 bytes/linha**: cada byte = 2 pixels (nibble high = pixel esquerdo, low = direito)
- **Altura**: 212 linhas (PAL) em vez de 192 (NTSC)
- **Sprites**: MESMO spriteMode 2 do G3 (renderSpritesLineMode2)
- **R2**: controla base do framebuffer (mascarado por -1<<15)

### Limitação do SETV
Endereços VRAM ≥ 0x8000 NÃO podem ser escritos via SETV normal (porta 0x99), pois o byte alto com bit 7=1 é interpretado como "escrita de registrador". Use R#14/R#15 para endereçar VRAM acima de 32KB.

### VRAM Layout em G4 (com framebuffer em 0)
```
0000-69FF  Framebuffer (128 bytes × 212 linhas = 27.136 bytes)
6A00-FFFF  Livre para SAT, padrões, etc.
```

---

## 5. Sistema de Sprites (spriteMode 2)

### Formato da Tabela Y-X-PN (em YPT = SAT + 512)
4 bytes por sprite, 32 sprites máx:
```
Byte 0: Y position (216 = terminador)
Byte 1: X position
Byte 2: Pattern number (PN)
Byte 3: (não utilizado)
```

### Formato da Tabela de Cores (em SAT)
16 bytes por sprite (1 por scanline), 32 sprites × 16 = 512 bytes:
```
Byte s: cor para scanline s do sprite i
  bits 0-3: índice da paleta (0-15)
  bit 5: IC (Internal Collision)
  bit 6: CC (Complementary Color)
  bit 7: EC (Early Clock, X -= 32)
```

### Duas ou mais cores na MESMA linha: o bit CC
Uma cor por linha ja vem de graca (a tabela acima). Para ter **mais de uma cor
na mesma linha**, use o bit **CC (bit 6)** da cor: um sprite com CC=1 nao
substitui o sprite de mesma prioridade que estiver embaixo — as duas cores sao
combinadas por **OR**.

```
sprite N   (CC=0, cor A)  -> desenha A
sprite N+1 (CC=1, cor B)  -> onde so ele tem pixel: B
                             onde os dois tem pixel: A OR B
```

Regras que importam na pratica (`renderSpritesLineMode2Tiled` em VDP.js):

- O sprite com CC=1 tem de vir **depois** (numero maior) do sprite CC=0, e na
  mesma linha. Se nenhum sprite CC=0 foi processado antes naquela linha, o
  sprite CC=1 e simplesmente **descartado**.
- Sem CC o sprite de numero maior seria descartado em cima do de numero menor
  (prioridade), entao CC e a unica forma de sobrepor cor dentro do mesmo objeto.
- Como o resultado e um **OR**, escolha as cores pensando em bits. Exemplo do
  Pong: corpo da bola em 12/10/8 e marca em 5 →
  `12|5=13`, `10|5=15`, `8|5=13` — logo as paletas **13 e 15 tem de receber o
  mesmo tom**, senao o brilho muda de cor conforme a linha do corpo.
- Vale a pena definir tambem a paleta da cor isolada (5, no exemplo), para o
  caso de o sprite CC passar do contorno do de baixo.

### Magnificacao e a tabela de cores
Com MAG (`R1` bit0=1), o VDP faz `spriteLine >>= 1` **antes** de indexar a cor.
Ou seja, com sprites 8x8 magnificados so as **8 primeiras** entradas de cor de
cada sprite sao lidas — uma por linha do padrao, nao por linha de tela.

### Registrador R#1 para Sprites
```
bit 0:  0 = sprite 8×8, 1 = sprite 16×16
bit 1:  0 = tamanho normal, 1 = magnificação 2×
```

### Exemplos:
- R1=0xE2: bit1=1 → sprites 8×8 renderizados como 16×16 (mag 2x)
- R1=0xE0: bit1=0 → sprites 8×8 sem magnificação

### R#8 — Controle de Sprites
```
bit 2 (SPD): 0 = sprites habilitados, 1 = desabilitados
bit 5 (TP):  0 = cor 0 sólida, 1 = cor 0 transparente
```

---

## 6. Paleta V9938

### Formato de Escrita
Cada entrada de paleta tem 2 bytes escritos via porta 0x9A:
```
Byte baixo: (R << 4) | B    (R, G, B cada 0-7)
Byte alto:  G
Valor 16-bit: (G << 8) | (R << 4) | B
```

### Conversão para 8-bit (por canal)
```
valor_3bit -> valor_8bit
0 -> 0, 1 -> 36, 2 -> 73, 3 -> 109
4 -> 146, 5 -> 182, 6 -> 219, 7 -> 255
```

### Exemplo de Paleta (16 entradas)
```asm
PAL:
    ; 0: black      db 00h, 00h
    ; 1: blue       db 07h, 00h    (R=0,G=0,B=7)
    ; 2: green      db 00h, 07h    (R=0,G=7,B=0)
    ; 3: cyan       db 07h, 07h    (R=0,G=7,B=7)
    ; 4: red        db 70h, 00h    (R=7,G=0,B=0)
    ; 5: white      db 77h, 07h    (R=7,G=7,B=7)
    ; ...total 32 bytes
    db 00h,00h, 07h,00h, 00h,07h, 07h,07h
    db 70h,00h, 77h,07h, 00h,00h, 00h,00h
    db 00h,00h, 00h,00h, 00h,00h, 00h,00h
    db 00h,00h, 00h,00h, 00h,00h, 00h,00h
```

## 7. Registradores VDP

### Protocolo de Escrita (porta 0x99)
Dois bytes para cada operação:
```
1º byte: valor (dado do registrador OU low byte do endereço VRAM)
2º byte: controle
  bit 7 = 1 → escrita de registrador (bits 0-5 = nº do registrador)
  bit 7 = 0 → endereço VRAM
    bit 6 = 1 → modo escrita
    bit 6 = 0 → modo leitura
    bits 0-5 = high byte do endereço (A13-A8)
```

**IMPORTANTE**: O bit 7 do 2º byte NUNCA pode ser 1 para endereços VRAM. Isso limita endereços diretos a < 0x8000. Para VRAM > 32KB, use R#14/R#15.

### Tabela de Registradores VDP (V9938)
```
R#   Nome  Função
0    MODE  Bits M4,M5 do modo de vídeo
1    DISP  Display/Mode (bits M2,M3, IE, BL, SI, SPR)
2    BASE  Base da Name Table (×0x400) ou Framebuffer
3    BASE  Base da Color Table (×0x40)
4    BASE  Base da Pattern Table (×0x800)
5    SAT   Base da Sprite Attribute Table (×0x80)
6    SPT   Base da Sprite Pattern Table (×0x800)
7    BD    Cor da borda (índice da paleta)
8    TP    Transparent Pen / Sprite Disable
9    YAE   YJK/YAE mode / PAL NTSC
10   BASE  High bits da Color Table
11   BASE  High bits da SAT
12-13       Reservado
14   RV    High bits do ponteiro VRAM
15   ST    Status index
16   PAL   Índice da paleta para escrita via 0x9A
17   ADJ   Ajuste indireto de registrador
```

### Registrador R#0 (Modo)
```
bits 1-3: M4, M5 (combinados com R1 bits 3-4)
0x04 = Screen 4 (G3)
0x06 = Screen 5 (G4)
```

### Registrador R#1 (Display)
```
bit 0:  0=sprites 8×8, 1=sprites 16×16
bit 1:  0=normal, 1=magnificação 2×
bit 2:  reservado
bit 3-4: M2, M3 (modo)
bit 5:  IE (interrupção VBlank)
bit 6:  BL (display enable no WebMSX)
bit 7:  reservado (manter 0)
```

Valores comuns:
- 0xE2: display on, VBlank IE, spr mag 2x, sprites 8×8
- 0xE0: display on, VBlank IE, spr normal, sprites 8×8
- 0xA2: display off (bit6=0), spr mag 2x (usado init Birdy Flap)

---

## 8. Som PSG (AY-3-8910)

### Portas
```
A0h: seleção de registrador PSG
A1h: dados do registrador PSG
```

### Registradores PSG
```
R0:  Canal A — tom (fine)
R1:  Canal A — tom (coarse)
R2:  Canal B — tom (fine)
R3:  Canal B — tom (coarse)
R4:  Canal C — tom (fine)
R5:  Canal C — tom (coarse)
R6:  Ruído — período
R7:  Mixer (I/O também)
R8:  Canal A — volume
R9:  Canal B — volume
R10: Canal C — volume
R11: Envelope — período (fine)
R12: Envelope — período (coarse)
R13: Envelope — forma
R14: Joystick (somente leitura, porta 0A2h)
R15: I/O port B — bit6 = porta do joystick, bit4/5 = pino 8
```

### Joystick
Ler o gatilho 1 da porta 1:
```asm
    ld a, 15
    out (0A0h), a
    ld a, 8Fh        ; bit6=0 -> porta 1 ; bit4=0 -> pino 8 em nivel baixo
    out (0A1h), a
    ld a, 14
    out (0A0h), a
    in a, (0A2h)     ; bit0..3 = direcoes, bit4 = gatilho A, bit5 = gatilho B
    and 10h          ; zero = gatilho A pressionado
```
`R15` bit4 (pino 8) precisa estar em **0**, senao o WebMSX devolve 0x3Fh fixo
(`DOMJoykeysControls.readLocalControllerPort`). O valor de reset ja e 8Fh.

### Teclado — linha 8
```
bit0 = SPACE   bit1 = HOME   bit2 = INS   bit3 = DEL
bit4 = LEFT    bit5 = UP     bit6 = DOWN  bit7 = RIGHT
```
Todos ativos em **0**. Selecione a linha em PPI porta C (0AAh) bits 0-3 e leia
em PPI porta B (0A9h).

---

## 9. Música YM2413 (OPLL)

### Portas
```
7Ch: seleção de registrador (F0)
7Dh: dados (F1)
```

### Inicialização
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

### Percussão / Ruído (modo ritmo)

O YM2413 tem um setor de ritmo que reaproveita os canais 6, 7 e 8. É aqui que
moram os **instrumentos de ruído**: HH (chimbau), SD (caixa) e TCY (prato).
BD e TOM são afinados, não ruidosos.

```
reg 0Eh   bit5 = liga o modo ritmo
          bit4 = BD   bit3 = SD   bit2 = TOM   bit1 = TCY   bit0 = HH
```

Volumes (0 = máximo, 15 = mudo):
```
reg 36h   bits 3-0 = BD          (o nibble alto NÃO é volume: BD tem modulador)
reg 37h   bits 7-4 = HH   bits 3-0 = SD
reg 38h   bits 7-4 = TOM  bits 3-0 = TCY
```

Frequências padrão dos canais de percussão (MSX-MUSIC):
```
ch6 (BD)       reg 16h = 20h   reg 26h = 05h
ch7 (HH/SD)    reg 17h = 50h   reg 27h = 05h
ch8 (TOM/TCY)  reg 18h = C0h   reg 28h = 01h
```

**Ordem importa**: ligue o modo ritmo (0Eh = 20h) **antes** de escrever
36h/37h/38h. Fora do modo ritmo esses três registradores são o
*instrumento* dos canais 6/7/8, não o volume.

**Re-disparo**: a percussão só ataca quando o bit de key-on vai de 0 para 1.
Para tocar o mesmo som duas vezes seguidas é preciso desligar antes:

```asm
    ld a, 0Eh
    ld e, 20h       ; key-off de tudo, modo ritmo mantido
    call FMW
    ld a, 0Eh
    ld e, 21h       ; key-on do HH
    call FMW
```

**Escrita que não muda o registrador é ignorada** (tanto no chip quanto no
WebMSX, que compara `register[reg] ^ val`). Para garantir que um volume seja
aplicado no boot, escreva um valor diferente antes: `37h = FFh`, depois
`37h = 02h`.

### Tempo de escrita
O chip exige ≥12 ciclos após o byte de endereço (porta 7Ch) e ≥84 ciclos após
o byte de dado (porta 7Dh). Um laço `ld a,n / dec a / jr nz` de 2 e 6 voltas
cobre os dois casos.

---

## 9b. Chips de som disponíveis no WebMSX

| Chip | Canais | Como chega | Situação |
|------|--------|-----------|----------|
| **PSG** AY-3-8910 | 3 tom + 1 ruído | embutido em todo MSX | sempre disponível |
| **FM / MSX-MUSIC** YM2413 (OPLL) | 9 melódicos, ou 6 + 5 percussão | `_MSX2BASE` já inclui `MSXMUSIC` | sempre disponível no MSX2/2+ |
| **SCC / SCC+** | 5 wavetable | extensão, `PRESETS=SCC` na URL | disponível, desligado por padrão |
| **Double PSG** | +3 tom | extensão, `PRESETS=DOUBLEPSG` | disponível, desligado por padrão |
| **OPL4 / MoonSound** | 18 FM + wavetable | extensão, `PRESETS=OPL4` | disponível, desligado por padrão |
| **MSX-Audio** Y8950 | 9 FM + ADPCM | — | **não emulado** |

`src/main/msx/rom/SlotFormatsNotSupported.js` lista literalmente
`"MSXAUDIO": 0, // Make Support?`. O ROM database reconhece os cartuchos
(Panasonic FS-CA1 etc.) mas o formato não é implementado.

### Notas do PSG
`periodo = (3579545/2) / (16 * frequencia)`, 12 bits. A nota mais grave que
cabe é ~C1 (período 3420). O PSG não tem envoltória por nota utilizável para
melodia (a envoltória é global), então o decaimento vem por software.

### Notas do YM2413
`f = F * 49716 * 2^block / 2^19`. Escolha o `block` que deixa `F` entre 256 e
511 — é onde a resolução é melhor. O byte do registrador `20h+canal` é
`10h (key-on) | block<<1 | F bit8`.

---

## 10. Análise Birdy Flap

### VREG (12 registros em 0x40DC)
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

### Pós-Init: R1 muda para 0xE2
```asm
    ld a, 0E2h
    out (0x99), a
    ld a, 81h      ; R1 = 0xE2 (display on, IE, spr mag 2x)
    out (0x99), a
```

### Display Toggle
Birdy Flap inicializa com display blanked (R1 bit6=0), configura TUDO, e SÓ ENTÃO ativa o display. Evita artefatos.

---

## 11. Pong AI — Código de Referência

### Arquivos
- `tools/build_pong.py` — Código fonte Z80 + script de build (v24)
- `tools/minz80asm.py` — Montador Z80 2-pass — hoje refatorado como o pacote
  [`msxasm`](referencia.md) deste repositório
- `roms/pong-ai-v24.rom` — ROM publicada, **16384 bytes**
  (`md5 03324e8f4febc0e537c9c808c6c33c00`)

> **Correção.** Versões anteriores deste manual diziam 32 KB. A v24 tem
> `CART = 16 * 1024` em `build_pong.py`, e a ROM publicada tem 16384 bytes —
> conferido em 2026-08-31. As ROMs de 32 KB em `release/` são builds antigos.

### Geometria dos sprites com MAG
Os sprites são 8×8 com magnificação (R1 bit0=1), então cada pixel do padrão
vira 2×2 na tela. Bola e raquete desenham nas **colunas 2..5** do padrão, o
que na tela vira o intervalo **+4..+11** a partir do X do sprite:

```
raquete P1 (X=8)    ocupa X =  12..19
raquete P2 (X=232)  ocupa X = 236..243
bola                ocupa X = BX+4..BX+11
```

Por isso a colisão não pode usar o X do sprite direto: para a bola *encostar*
na raquete, `BXLP = P1X+8 = 16` e `BXRP = P2X-8 = 224`. Usar o X cru deixa
folga de um lado e sobreposição do outro.

O VDP também desenha o sprite na linha **Y+1**, então os limites verticais são
`PMAX = 192-32-1 = 159` e `BYMAX = 192-8-1 = 183`.

### Configuração VDP (G3 funcional)
```
R0=04  R1=E0  R2=00  R3=01  R4=02
R5=08  R6=04  R7=00  R8=20  (TP=1)

SAT = 0x400  (R5=8 → 8<<7=0x400)
YPT = 0x600  (SAT+512)
Spr Pat = 0x2000 (R6=4)
Color Table = 0x400 (SAT base)
```

---

## 12. Armadilhas Comuns

### SAT Address Masking
Verifique R5 mín=8 em G3/G4/G5 (máscara `-1<<10` zera valores < 0x400).

### VRAM Address Bit 7
Nunca use SETV com endereços ≥ 0x8000 (bit7 causa registro write).

### Constante hex terminada em 0B/1B (minz80asm)
O `_eval` converte hex antes de binario. Depois da conversao, `0C00Bh` ja e
`0x0C00B`, e o regex de literal binario `([01]+)B\b` casava com o `00B` final:

```
0C00Bh -> 192   (0x00C0)      0Bh -> 0
```

Sem nenhum aviso. `PAUSA equ 0C00Bh` virou um endereco dentro da ROM da BIOS,
entao a escrita era descartada e a leitura devolvia lixo. **Corrigido** com um
lookbehind (`(?<![0-9A-Fx])`), e `_eval` agora avisa quando uma expressao nao
avalia em vez de devolver 0 calado.

O `build_pong.py` tambem confere, a cada build, que todo equate de variavel
esta em `0xC000..0xC0FF` e todo equate de VRAM em `0x0000..0x3FFF`.

### VBlank Sync
Com `ei`, a BIOS lê S#0 e limpa o flag VBlank. O loop `in a,(99h); rlca; jr nc` pode falhar. Use `di` para polling direto.

### Inicialização do Display
Sempre configure tudo ANTES de ativar o display. Técnica Birdy Flap: init com R1 bit6=0, depois mude para bit6=1.

---

## 12a. Cartucho de 32 KB: a página 2 não vem de graça

A BIOS chama o `INIT` de um cartucho de 32 KB com a **página 1** (4000h-7FFFh)
já no slot do cartucho, mas deixa a **página 2** (8000h-BFFFh) na RAM. Tudo que
a ROM guardar acima de 0x8000 lê lixo até o próprio cartucho chavear a página.

Sintoma real: a música do título tocava e a do jogo não — as faixas do jogo
eram justamente as que caíam acima de 0x8000.

```asm
; copia o slot primario da pagina 1 para a pagina 2
PG2:
    in a, (0A8h)
    ld b, a
    and 0Ch          ; slot da pagina 1 (bits 2-3)
    rlca
    rlca             ; para os bits 4-5 (pagina 2)
    ld c, a
    ld a, b
    and 0CFh         ; zera os bits da pagina 2
    or c
    out (0A8h), a
    ret
```

Vale para slot **não expandido** (é o caso: o WebMSX põe o cartucho no slot 1,
`CARTRIDGE1_SLOT: [1]`). Em slot expandido seria preciso mexer também no
registrador de subslot em 0FFFFh.

**Um harness que mapeia a ROM inteira em 4000h-BFFFh nunca vê esse bug.**
`tools/emu_test.js` tem um modelo de slots: página 0 = BIOS, 1 = cartucho,
2 e 3 = RAM, com a porta 0A8h implementada — e reproduziu o problema na hora.

---

## 12b. Imagem: por que a abertura saiu do G3 e foi para o G4

A primeira tentativa foi tiled (SCREEN 4). Deu artefato e a causa é estrutural:
o G3 aceita **duas cores por segmento de 8×1 pixels**, e num logo com contorno
o par vira contorno+banda ou contorno+fundo — sempre sobra cor de fora. Dá para
mitigar (testar todos os pares de cada linha em vez de pegar as duas mais
frequentes ajuda bastante), mas não some.

No **SCREEN 5 (G4)** não existe essa restrição: framebuffer de 4 bits por pixel,
2 pixels por byte, nibble alto = pixel da esquerda, 128 bytes por linha.
`tools/bmp2msx.py` tem os dois conversores; `converter_g4` é o usado.

### Largura 256, não 240
Com 256 px a linha ocupa exatamente 128 bytes e a imagem inteira vira **um bloco
contíguo**: uma escrita sequencial só, sem recalcular endereço por linha. Custa
672 bytes de padding e economiza código e tempo.

### Ponteiro de VRAM de 17 bits
A porta 99h carrega só **14 bits** do endereço; os de cima vêm de **R#14**. O
framebuffer do G4 passa de 0x3FFF, então R#14 tem de ser escrito sempre —
inclusive **zerado**, porque o VDP incrementa R#14 sozinho ao cruzar cada 16 KB
(`checkVRAMPointerWrap` em VDP.js). Um `SETV` que só escreve os 14 bits baixos
funciona no G3 e falha no G4 assim que alguma escrita anterior cruzou a
fronteira.

### R#2 no G4 tem de ser 1Fh, não 00h
Este é o erro que deixa a tela **inteira na cor de fundo** com o framebuffer
perfeitamente escrito — e o mais difícil de enxergar, porque a VRAM está certa.

`R#2` não define só a base: no VDP ele define **também a máscara de leitura**
(`updateLayoutTableAddress` em VDP.js):

```
add                     = (R2 & 0x7F) << 10
layoutTableAddress      = add & layTBase        ; layTBase do G4 = -1<<15
layoutTableAddressMask  = add | 0x3FF           ; base fixa para todos os modos
```

e o desenho lê `vram[pos & layoutTableAddressMask]`. Com `R2=00`:

```
base    = 0        (parece certo)
máscara = 0x3FF    (o VDP lê só o primeiro 1 KB da VRAM)
```

Com `R2=1Fh`:

```
base    = 0x7C00 & (-1<<15) = 0        (framebuffer em 0, como se quer)
máscara = 0x7C00 | 0x3FF    = 0x7FFF   (os 32 KB da página)
```

Confira no G3 pela mesma fórmula: `R2=06` → base `0x1800`, máscara `0x1BFF`,
que cobre os 768 bytes da Name Table.

### Trocar de modo custa reconstruir a VRAM
O framebuffer do G4 ocupa 0x0000–0x5FFF, que é exatamente onde moram as tabelas
de padrão, cor, nome e sprites do G3. Voltar para o jogo exige refazer todas
elas (`CLRBG` + `SCRINI` + `SPRUP` + `COLINIT` + `SATCLR`), com o display
apagado. São ~35 KB de escrita em VRAM, cerca de 0,4 s.

### Custo de desenhar texto no bitmap
No G3 escrever texto é 1 byte por caractere na Name Table. No G4 é **32 bytes
por caractere** (8 linhas × 4 bytes). Redesenhar o menu inteiro a cada quadro
custava ~66 mil T-states — **mais que um frame** —, o que derrubava a taxa de
quadros e junto o andamento da música. Redesenhe só quando o conteúdo muda.

### Fundo preto = transparente
Pixels com luminância abaixo do limiar viram o índice do fundo. No logo do Pong
o limiar 95 também elimina o eco escuro que a arte tem no topo.

---

## 12c. Testar com o VDP de verdade

`tools/emu_test.js` roda a ROM com o **VDP.js e o CPU.js reais** do WebMSX,
com stubs só para canvas, áudio e monitor, e grava o quadro renderizado em PPM:

```bash
node tools/emu_test.js release/pong-ai.rom 120 /tmp/quadro.ppm '[[200,206,"baixo"],[240,246,"ok"]]'
```

Ele também imprime o estado interno do VDP (`vdp.eval(...)`): `modeData.name`,
`layoutTableAddress`, `layoutTableAddressMask`, `videoDisplayed`, os
registradores, o ponteiro de VRAM.

**Um modelo simplificado do VDP não serve para validar mudança de modo.** Um
harness que só acumula as escritas de VRAM num array e redesenha por fora mostra
a imagem certa mesmo quando a máquina real mostra tela vazia — foi exatamente o
que aconteceu com o `R#2` acima. Para geometria e lógica de jogo o modelo
simples basta; para modo de vídeo, endereçamento e paleta, use o VDP real.

---

## 13. Pipeline de música a partir de .mid

```
midi/*.mid  ->  tools/mid2pong.py  ->  tools/music_data.py  ->  build_pong.py
```

`tools/midparse.py` lê Standard MIDI File (formato 0 e 1), incluindo o mapa de
tempo, e devolve as notas em ticks. `mid2pong.py` converte ticks para quadros
(**60 Hz**: com `R9` bit1 = 0 o VDP fica em NTSC) e reduz a polifonia para as
3 vozes disponíveis:

```
voz 0 = nota mais aguda soando   (melodia)
voz 1 = segunda mais aguda       (contracanto)
voz 2 = nota mais grave          (baixo)
```

A linha do tempo é montada quadro a quadro e comprimida por RLE. **O RLE
precisa quebrar também em ataque novo**, senão duas colcheias iguais seguidas
viram uma semínima só.

Formato na ROM: pares `(nota, duração)`, nota 0 = silêncio, 255 = fim (volta ao
início). Duração em 1 byte, então nota mais longa que 255 quadros é dividida.

### 6 vozes, não 3
O YM2413 em modo ritmo deixa os canais **0..5** livres para melodia (6/7/8 ficam
com a percussão dos efeitos); o PSG só tem 3. Por isso o conversor gera 6 faixas
ordenadas por **importância**, não por altura:

```
voz 0 = mais aguda (melodia)   voz 1 = segunda mais aguda   voz 2 = mais grave (baixo)
voz 3..5 = as do meio, da mais aguda para a mais grave
```

Quem toca só 3 canais usa 0/1/2 e já fica com o essencial — o mesmo dado serve
para os dois chips. Passar de 3 para 6 vozes custou só **+1742 bytes** nas duas
músicas juntas: as vozes 4 e 5 ficam quase sempre em silêncio, e o RLE colapsa
isso.

### Custo em ROM
O tamanho depende da densidade, não da duração. Referências medidas:

| Música | notas | duração | polifonia | bytes |
|---|---|---|---|---|
| Animal Crossing – Load Game | 290 | 77 s | 5 | 983 |
| Animal Crossing – 100 PM | 524 | 131 s | 3 | 1965 |
| Pokémon HGSS – Game Corner | 1728 | 127 s | 8 | 5393 |
| Pokémon RBY – Game Corner | 827 | 73 s | 4 | 2419 |

A ROM **tem de caber no tamanho declarado**: passar disso não deixa o arquivo só
maior, muda a regra de mapeamento que o WebMSX escolhe (`SlotFormats.js` trata
cada faixa de tamanho como formato diferente). O `build_pong.py` falha o build se
o último símbolo chegar a `0xC000`.

O `msxasm` deste repositório generaliza isso: binário maior que o `--size`
declarado é erro, nunca truncamento, e ROMs acima de 32 KB passam a ser
possíveis via `MAPPER KONAMI` — com o hint de formato no nome do arquivo, porque
quatro mappers têm detecção idêntica no WebMSX. Ver [`referencia.md`](referencia.md).

*Manual gerado em 22/05/2026, atualizado em 22/08/2026 — WebMSX 6.0.8 — MSX2 V9938*
