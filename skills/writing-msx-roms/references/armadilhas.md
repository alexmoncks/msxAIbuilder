# Armadilhas silenciosas do MSX

Todas produzem um programa que roda. Nenhuma emite erro. Estão em ordem de
quanto tempo custam quando você não sabe delas.

---

## 1. A página 2 de um cartucho de 32 KB não vem mapeada

**Sintoma:** tudo abaixo de `8000h` funciona; tudo acima lê lixo. Costuma
aparecer como música muda, tabela de dados corrompida ou salto para o nada.

A BIOS chama o `INIT` de um cartucho de 32 KB com a **página 1** já no slot do
cartucho, mas deixa a **página 2 na RAM**. O registrador de slot primário na
porta `A8h` vem tipicamente com `F4h`:

```
pág. 0 = slot 0 (BIOS)   pág. 1 = slot 1 (cartucho)
pág. 2 = slot 3 (RAM)    pág. 3 = slot 3 (RAM)
```

**Correção** — copiar os 2 bits da página 1 para os da página 2, logo no início
do `INIT`. Vale para cartucho em slot **não expandido**; em slot expandido é
preciso mexer também no registrador secundário em `FFFFh`.

```asm
PG2:
    in a, (0A8h)
    ld b, a
    and 0Ch          ; bits da página 1
    rlca
    rlca             ; para a posição da página 2
    ld c, a
    ld a, b
    and 0CFh         ; zera os bits da página 2
    or c
    out (0A8h), a
    ret
```

**Por que passa despercebido:** um emulador de teste que mapeia a ROM inteira
linearmente lê os bytes certos e o bug não aparece.

---

## 2. `R#2` define a máscara de leitura, não só a base

**Sintoma:** tela **inteira na cor de fundo**, com o framebuffer perfeitamente
escrito na VRAM. É o erro mais difícil de enxergar, porque tudo o que você
inspeciona está certo.

No V9938 (`updateLayoutTableAddress`, em `VDP.js`):

```
add   = (R2 & 7Fh) << 10
base  = add & layTBase          ; layTBase depende do modo
mask  = add | 3FFh              ; e o desenho lê vram[pos & mask]
```

Em G4, `layTBase = -1<<15`:

| R#2 | base | máscara | resultado |
|---|---|---|---|
| `00h` | 0 | `3FFh` | o VDP lê só o **primeiro 1 KB** da VRAM, repetido |
| `1Fh` | 0 | `7FFFh` | framebuffer em 0 e os 32 KB da página visíveis |

Em G3 confira pela mesma fórmula: `R#2 = 06h` → base `1800h`, máscara `1BFFh`,
que cobre exatamente os 768 bytes da Name Table.

**Regra:** escolha `R#2` pela máscara que você precisa, e depois verifique que a
base ainda cai onde você quer.

---

## 3. `R#14` precisa ser reescrito mesmo quando é zero

**Sintoma:** as primeiras escritas de VRAM acertam o alvo; depois de encher mais
de 16 KB, todas caem 16 KB adiante.

A porta `99h` carrega só **14 bits** de endereço (`A0–A13`). `A14–A16` vêm de
`R#14` — e o VDP **incrementa `R#14` sozinho** quando o ponteiro cruza uma
fronteira de 16 KB (`checkVRAMPointerWrap`).

Uma rotina de posicionamento que só escreve os 14 bits baixos funciona em G3
(tudo cabe abaixo de `4000h`) e passa a errar em G4 assim que uma escrita
anterior atravessou `4000h`.

```asm
SETV:                ; aponta a VRAM para HL, modo escrita
    ld a, h
    rlca
    rlca
    and 3
    out (99h), a
    ld a, 8Eh        ; R#14
    out (99h), a
    ld a, l
    out (99h), a
    ld a, h
    and 3Fh
    or 40h           ; bit6 = escrita
    out (99h), a
    ret
```

---

## 4. `R#5` some com a tabela de sprites

**Sintoma:** sprites não aparecem, ou aparecem em cima da Pattern Table.

A máscara de `sprAttrTBase` é `-1<<10` em G3/G4/G5/G6: o endereço precisa ter o
bit 10 ligado para sobreviver.

| R#5 | `R5<<7` | após a máscara |
|---|---|---|
| `04h` | `200h` | **`0000h`** — em cima da Pattern Table |
| `08h` | `400h` | `400h` — menor valor útil |
| `3Fh` | `1F80h` | `1C00h` |

---

## 5. Os bits de sprite do `R#1` são fáceis de inverter

**Sintoma:** todos os sprites viram o mesmo desenho.

```
R#1  bit6 BL  display     bit5 IE0 interrupção
     bit1 SI  sprite 16×16 (não é o bit 0)
     bit0 MAG magnificação (não é o bit 1)
```

No `VDP.js`: `spritesSize = (R1 & 0x02) ? 16 : 8` e `spritesMag = R1 & 0x01`.

Ligar o bit 1 por engano põe o VDP em 16×16, e nesse modo o número do padrão é
mascarado com `& 0FCh` — os padrões 0, 1, 2 e 3 viram todos o padrão 0.

O mesmo vale para o `R#8`: `SPD` é o **bit 1** (0 = sprites ligados), e o `TP` é
o **bit 5** com o sentido invertido do que se espera —
`color0Solid = (R8 & 0x20) !== 0`.

---

## 6. Ligar o display antes de limpar a VRAM

**Sintoma:** tela de tiles coloridos aleatórios no boot, por uma fração de
segundo ou permanentemente.

O VDP começa a desenhar sobre tabelas que ainda contêm o que a BIOS deixou.
Escreva os 12 registradores com `R#1` bit 6 = **0**, limpe todas as tabelas que
o modo exige, e só então ligue o display.

Vale também para **troca de modo**: o framebuffer do G4 ocupa `0000h–5FFFh`,
exatamente onde moram as tabelas de padrão, cor, nome e sprites do G3. Voltar do
G4 para o G3 exige reconstruir todas elas, com o display apagado.

---

## 7. `;` é comentário, não separador de instruções

```asm
    ld a, 7; ld e, 5; call PSGW     ; monta APENAS  ld a, 7
```

Uma instrução por linha. Sempre.

---

## 8. Parênteses em imediato viram endereçamento indireto

```asm
    ld a, (SH-PH)/2      ; NÃO carrega 80 — monta  ld a, (00A0h)
```

Pré-calcule constantes derivadas como `equ`: `PCENT equ 80`.

---

## 9. Efeitos do YM2413 que só tocam uma vez

A percussão do modo ritmo ataca na **borda** do bit de key-on. Para repetir o
mesmo som é preciso desligar antes:

```asm
    ld a, 0Eh
    ld e, 20h        ; modo ritmo mantido, tudo em key-off
    call FMW
    ld a, 0Eh
    ld e, 21h        ; agora dispara o chimbau
    call FMW
```

E uma escrita que não muda o valor do registrador é **ignorada** (o chip e o
WebMSX comparam `register[reg] ^ val`). Para garantir que um volume entre no
boot, escreva um valor diferente antes.

---

## 10. O mixer do PSG tem lógica invertida

`R#7`: **bit em zero LIGA** o canal.

```
0BFh   1011 1111   silêncio total
0B8h   1011 1000   tons A, B e C ligados, ruídos desligados
```

---

## Checklist de tela em branco

Na ordem, do mais provável ao menos:

1. O display foi ligado? (`R#1` bit 6)
2. `R#2` produz a máscara certa para o modo?
3. As tabelas que o modo exige foram todas escritas?
4. `R#14` está correto para o endereço que você acha que escreveu?
5. `R#9` bit 7 bate com a altura que você desenhou (192 vs 212)?
6. A paleta foi carregada? Entradas não escritas guardam a paleta padrão.
