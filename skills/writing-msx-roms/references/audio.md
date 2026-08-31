# Som — PSG e YM2413

## Chips disponíveis no WebMSX

| Chip | Canais | Como chega | Situação |
|---|---|---|---|
| **PSG** AY-3-8910 | 3 tom + 1 ruído | embutido em todo MSX | sempre |
| **MSX-MUSIC** YM2413 (OPLL) | 9 melódicos, ou 6 + 5 percussão | `_MSX2BASE` já inclui `MSXMUSIC` | sempre no MSX2/2+ |
| SCC / SCC+ | 5 wavetable | `PRESETS=SCC` na URL | desligado por padrão |
| Double PSG | +3 tom | `PRESETS=DOUBLEPSG` | desligado por padrão |
| OPL4 / MoonSound | 18 FM + wavetable | `PRESETS=OPL4` | desligado por padrão |
| MSX-Audio Y8950 | 9 FM + ADPCM | — | **não emulado** |

`SlotFormatsNotSupported.js` traz literalmente `"MSXAUDIO": 0`.

---

## PSG (AY-3-8910)

Registrador em `A0h`, dado em `A1h`.

```asm
PSGW:                ; A = registrador, E = valor
    out (0A0h), a
    ld a, e
    out (0A1h), a
    ret
```

| Reg | Função |
|---|---|
| 0,1 | período do canal A — 12 bits |
| 2,3 | canal B |
| 4,5 | canal C |
| 6 | período do ruído |
| **7** | mixer — **bit em zero LIGA** |
| 8,9,10 | volume dos canais A, B, C — 0 a 15 |
| 11,12,13 | envoltória |
| 14,15 | portas de I/O — joystick |

```
R7 = 0BFh   1011 1111   silêncio total
R7 = 0B8h   1011 1000   tons A, B e C ligados, ruídos desligados
R7 = 0BEh   1011 1110   só o tom do canal A
```

Período: `periodo = (3579545/2) / (16 * frequencia)`. A nota mais grave que cabe
em 12 bits é ~C1.

**O PSG não tem envoltória por nota utilizável** para uma melodia comum: faça o
decaimento por software, um contador por voz decrementado a cada quadro e
escrito em `R(8+canal)`.

---

## YM2413 (OPLL / MSX-MUSIC)

Registrador em `7Ch`, dado em `7Dh`. O chip exige ≥12 ciclos após o byte de
endereço e ≥84 após o byte de dado. Dois laços curtos cobrem os dois casos:

```asm
FMW:                 ; A = registrador, E = valor
    out (7Ch), a
    ld a, 2
FMW1:
    dec a
    jr nz, FMW1
    ld a, e
    out (7Dh), a
    ld a, 6
FMW2:
    dec a
    jr nz, FMW2
    ret
```

### Canais melódicos

```
10h + canal   F-Number, bits 0-7
20h + canal   bit4 key-on | bloco << 1 | F-Number bit 8
30h + canal   instrumento << 4 | volume    (volume: 0 = máximo, 15 = mudo)
```

Faixas de 16: trocar `10h` por `20h` é um erro que **não faz barulho nenhum**,
literalmente.

Instrumentos: 1 violino, 2 guitarra, 3 piano, 4 flauta, 5 clarinete, 6 oboé,
7 trompete, 8 órgão, 9 trompa, 10 sintetizador, 11 cravo, 12 vibrafone,
13 baixo sintetizado, 14 baixo acústico, 15 guitarra elétrica.

### Modo ritmo — percussão

Reaproveita os canais 6, 7 e 8, e deixa **0 a 5 livres para melodia**. É onde
moram os instrumentos de ruído: HH (chimbau), SD (caixa) e TCY (prato); BD e TOM
são afinados.

```
reg 0Eh   bit5 = liga o modo ritmo
          bit4 BD | bit3 SD | bit2 TOM | bit1 TCY | bit0 HH
```

Volumes (0 = máximo):

```
reg 36h   bits 3-0 = BD     (o nibble alto NÃO é volume: BD tem modulador)
reg 37h   bits 7-4 = HH     bits 3-0 = SD
reg 38h   bits 7-4 = TOM    bits 3-0 = TCY
```

Frequências padrão da percussão (MSX-MUSIC):

```
ch6 (BD)       reg 16h = 20h   reg 26h = 05h
ch7 (HH/SD)    reg 17h = 50h   reg 27h = 05h
ch8 (TOM/TCY)  reg 18h = C0h   reg 28h = 01h
```

**A ordem importa:** ligue o modo ritmo (`0Eh = 20h`) **antes** de escrever
`36h/37h/38h`. Fora do modo ritmo esses três registradores são o *instrumento*
dos canais 6/7/8, não o volume.

Um efeito de impacto vira duas escritas e nenhum custo por quadro — o chip
apaga a nota sozinho:

```asm
RHIT:                ; E = máscara dos instrumentos
    push de
    ld a, 0Eh
    ld e, 20h        ; modo ritmo, tudo em key-off
    call FMW
    pop de
    ld a, e
    or 20h
    ld e, a
    ld a, 0Eh
    call FMW
    ret

; E = 01h  chimbau        E = 09h  caixa + chimbau
; E = 0Ah  caixa + prato
```

---

## Um tocador de música que serve aos dois chips

O PSG tem 3 canais; o OPLL em modo ritmo tem 6. Para um único conjunto de dados
servir aos dois, **ordene as vozes por importância, não por altura**:

```
voz 0 = nota mais aguda soando no instante   (melodia)
voz 1 = segunda mais aguda                   (contracanto)
voz 2 = nota mais grave                      (baixo)
voz 3..5 = as do meio, da mais aguda para a mais grave
```

Quem toca 3 vozes pega 0/1/2 e já fica com o essencial. O laço muda só o
contador:

```asm
    ld b, 3          ; PSG
    or a
    jr z, MUS0
    ld b, 6          ; FM
MUS0:
```

### Formato de faixa

Uma lista de pares `(nota, duração em quadros)` comprimida por RLE, terminada
por um sentinela (`255`). Ao encontrar o sentinela, recarregue o ponteiro do
início e a música dá a volta.

**O RLE tem de quebrar também num novo ataque da mesma nota** — sem isso duas
colcheias iguais viram uma mínima.

### Estado por voz

4 bytes: ponteiro na faixa (2), quadros restantes da nota (1), contador de
decaimento (1). O decaimento só é usado no PSG; no OPLL a rotina retorna na
primeira instrução.

### Custo

Converter uma trilha de MIDI para 6 vozes em vez de 3 custa da ordem de
+1,7 KB de ROM por par de músicas. Vozes 3–5 costumam ser esparsas mas são o que
torna a versão FM mais cheia que a do PSG.
