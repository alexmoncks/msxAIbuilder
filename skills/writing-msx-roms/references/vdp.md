# V9938 — vídeo

## Portas

| Porta | Uso |
|---|---|
| `98h` | Dados de VRAM. O ponteiro auto-incrementa — por isso `otir` funciona |
| `99h` | Escrita: comando de dois bytes. Leitura: status `S#0` |
| `9Ah` | Paleta, dois bytes por entrada |
| `9Bh` | Escrita indireta de registrador |

### Protocolo da porta 99h

Toda escrita vem em par. O bit 7 do **segundo** byte decide a operação.

```asm
; escrever um registrador
    ld a, 04h        ; 1º byte: o valor
    out (99h), a
    ld a, 80h        ; 2º byte: bit7=1 -> registrador; bits 0-5 = número
    out (99h), a     ;          R#0 = 04h

; apontar a VRAM para 1E00h em modo escrita
    ld a, 00h        ; 1º byte: A0-A7
    out (99h), a
    ld a, 5Eh        ; 2º byte: bit7=0 -> endereço
    out (99h), a     ;          bit6=1 -> escrita
                     ;          bits 0-5 = A8-A13
```

O campo de endereço tem 14 bits. `A14–A16` vêm de `R#14` — ver armadilha 3.

Ler `99h` devolve `S#0` **e limpa o flag de VBlank**. É a base do sincronismo
por polling, que funciona com `di`:

```asm
WVB:
    in a, (99h)
    and 80h
    jr z, WVB
    ret
```

---

## Seleção de modo

```
modeBits = (R#1 & 18h) | ((R#0 & 0Eh) >> 1)
```

| Valor | Modo | Resolução | Cores | px/byte |
|---|---|---|---|---|
| `00h` | G1 | 256×192 | 16 | 8 |
| `01h` | G2 | 256×192 | 16 | 8 |
| `02h` | **G3** (SCREEN 4) | 256×192 | 16 por pixel | 8 (tiled) |
| `03h` | **G4** (SCREEN 5) | 256×212 | 16 por pixel | 2 (bitmap) |
| `04h` | G5 (SCREEN 6) | 512×212 | 4 | 4 |
| `05h` | G6 (SCREEN 7) | 512×212 | 16 | 2 |
| `07h` | G7 (SCREEN 8) | 256×212 | 256 | 1 |

G3 a G7 usam **sprite mode 2** (ver `sprites.md`).

---

## Os 12 registradores

Escritos em bloco. `C` aponta a porta, `A` conta o registrador:

```asm
VREGS:               ; HL = tabela de 12 bytes
    ld b, 12
    ld c, 99h
    xor a
VREGL:
    ld d, (hl)
    out (c), d
    ld e, a
    set 7, e
    out (c), e
    inc hl
    inc a
    djnz VREGL
    ret
```

| R# | Função | Notas |
|---|---|---|
| 0 | Modo (parte alta) | bits 1–3 entram em `modeBits` |
| 1 | Display / sprites | bit6 `BL` display · bit5 `IE0` · **bit1 `SI` 16×16** · **bit0 `MAG`** |
| 2 | Base **e máscara** da layout table | ver armadilha 2 |
| 3 | Color Table, bits baixos | combina com R#10 |
| 4 | Pattern Table | `R4 << 11`, mascarado |
| 5 | Tabela de sprites | `R5 << 7`, mascarado — ver armadilha 4 |
| 6 | Padrões de sprite | `R6 << 11` |
| 7 | Cor da borda | índice da paleta |
| 8 | Sprites / transparência | **bit1 `SPD`** 0 = ligados · **bit5 `TP`** |
| 9 | Altura e sincronismo | bit7 `LN` 0 = **192** linhas, 1 = 212 |
| 10 | Color Table, bits altos | |
| 11 | Tabela de sprites, bits altos | |
| 14 | `A14–A16` do ponteiro de VRAM | ver armadilha 3 |
| 16 | Índice inicial da paleta | auto-incrementa |

### Máscaras de base por modo

O valor do registrador **não é** o endereço: o VDP desloca e depois mascara.

| Modo | layTBase | colorTBase | patTBase | sprAttrTBase |
|---|---|---|---|---|
| G3 | `-1<<10` | `-1<<13` | `-1<<13` | `-1<<10` |
| G4 | `-1<<15` | 0 | 0 | `-1<<10` |
| G5 | `-1<<15` | 0 | 0 | `-1<<10` |
| G6 | `-1<<16` | 0 | 0 | `-1<<10` |

Exemplo em G3 com `R#3 = FFh`: `FFh << 6 = 3FC0h`, e a máscara `-1<<13` corta
tudo abaixo do bit 13 → `2000h`. Qualquer valor entre `80h` e `FFh` daria a
mesma tabela. O registrador tem mais resolução do que o modo usa.

---

## G3 (SCREEN 4) — tiled

Três blocos de 64 linhas, cada um com seu banco de 2 048 bytes de padrões **e**
de cores. Um tile de mesmo número desenha coisas diferentes em blocos
diferentes. A Color Table guarda **um byte por linha de padrão**, não um por
tile: cada fileira de 8 pixels tem sua própria dupla de cores.

```
bit = (pattern >> (7 - (x & 7))) & 1
cor = bit ? (color >> 4) : (color & 0Fh)
```

Layout típico (`R#2=06h R#3=FFh R#4=03h R#5=3Fh R#6=07h`):

| Faixa | Bytes | Conteúdo |
|---|---|---|
| `0000–17FF` | 6 144 | Pattern Table — 3 blocos de 2 048 |
| `1800–1AFF` | 768 | Name Table — 32×24 |
| `1C00–1DFF` | 512 | Cores de sprite |
| `1E00–1FFF` | 512 | Atributos de sprite |
| `2000–37FF` | 6 144 | Color Table — 3 blocos |
| `3800–3FFF` | 2 048 | Padrões de sprite |

**Campo de cor única:** Pattern = `00h`, Color = `XYh` (frente X, fundo Y),
Name = `00h`. Nenhum bit ligado, então todo pixel usa o nibble de fundo.

**Texto em G3 custa 1 byte por caractere** (o número do tile na Name Table) — mas
a fonte precisa ser instalada nos **três** bancos de padrões se o texto aparece
em qualquer altura da tela.

---

## G4 (SCREEN 5) — bitmap

4 bits por pixel, 2 pixels por byte, **nibble alto = pixel da esquerda**,
128 bytes por linha.

```
endereço = y * 128 + x/2
```

Com largura 256 a imagem inteira é um bloco contíguo: uma escrita sequencial só,
sem recalcular endereço por linha.

**Texto em G4 custa 32 bytes por caractere** (8 linhas × 4 bytes). Redesenhar uma
tela de menu a cada quadro passa de 66 000 T-states — mais do que o quadro
inteiro oferece: a 3,58 MHz um quadro de 60 Hz são ~59 700. Redesenhe só quando
o conteúdo muda, com um flag de sujeira.

Escrever um glifo **linha a linha** em vez de caractere a caractere reduz os
reposicionamentos do ponteiro de VRAM de 8 por caractere para 8 por string.

---

## Paleta

16 entradas, 3 bits por canal, 512 cores. Escrita pela porta `9Ah` em pares,
depois de apontar o índice em `R#16`; o índice auto-incrementa.

```asm
    xor a            ; índice inicial 0
    out (99h), a
    ld a, 90h        ; bit7=1, registrador 10h = R#16
    out (99h), a
    ld hl, PAL
    ld bc, 209Ah     ; B=32 bytes, C=porta 9Ah
    otir
```

Formato de cada entrada:

```
1º byte   bits 4-6 = R    bits 0-2 = B     -> (R<<4) | B
2º byte   bits 0-2 = G
```

O verde vem sozinho no segundo byte. Escala de 3 para 8 bits:
`0, 36, 73, 109, 146, 182, 219, 255`.

**Escreva as 16 entradas**, mesmo as que você não usa. Entradas não escritas
guardam a paleta padrão do V9938, e um índice encostado por acidente pinta a
tela de uma cor que não está em lugar nenhum do fonte.

---

## Tempo de escrita de VRAM

O V9938 exige ~29 ciclos entre acessos consecutivos à VRAM. Um laço de
preenchimento simples fica em ~40 ciclos por byte e é seguro em hardware real:

```asm
VFILL:               ; preenche BC bytes com D, a partir do ponteiro atual
    ld a, d
    out (98h), a
    dec bc
    ld a, b
    or c
    jr nz, VFILL
    ret
```
