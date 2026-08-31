# Sprite mode 2 (V9938 — G3 a G7)

## Duas tabelas, separadas por 512 bytes

`R#5` aponta uma região de 1 KB. Dentro dela existem **duas** tabelas:

```
SAT       = base      ; cores  — 16 bytes por sprite, UM POR LINHA
SAT + 512             ; atributos — 4 bytes por sprite
```

Cálculo do endereço:

```
add = (R11 << 15) | (R5 << 7)     ; 17 bits
SAT = add & sprAttrTBase          ; máscara do modo, -1<<10 em G3..G6
```

## Atributos, 4 bytes por sprite

```
byte 0   Y     posição vertical; 216 ENCERRA A LISTA
byte 1   X     posição horizontal
byte 2   PN    número do padrão
byte 3   —     não usado no modo 2
```

O VDP calcula `linhaDoSprite = linha − Y − 1`: escrever `Y = 0` desenha o sprite
a partir da linha 1.

## Cor, um byte por linha do sprite

```
bits 0-3   índice da paleta
bit  5     IC   ignora colisão
bit  6     CC   compõe com o sprite de maior prioridade
bit  7     EC   early clock: desloca X em -32
```

Ter uma cor por linha permite um sprite multicolorido sem gastar vários sprites.
A tabela é de tamanho fixo: você paga os 512 bytes usando ou não.

### `CC` — compor duas cores no mesmo pixel

Com `CC` ligado, o VDP compõe a cor deste sprite **por OR** com a do sprite de
maior prioridade já presente naquele pixel. É como se põe um detalhe *dentro* de
outro sprite em vez de tapá-lo.

```asm
BCOL:                ; 16 bytes por sprite
    db 0Ch,0Ch,0Ah,08h,08h,00h,00h,00h   ; sprite 4 — esfera sombreada
    db 00h,00h,00h,00h,00h,00h,00h,00h
    db 45h,45h,45h,45h,45h,00h,00h,00h   ; sprite 5 — 40h = CC, 05h = cor
    db 00h,00h,00h,00h,00h,00h,00h,00h
```

Com `MAG = 1` cada linha de padrão vira duas na tela, então cinco cores
diferentes já desenham um degradê que lê como volume.

### `EC` — sair pela esquerda

`X` tem 8 bits: não existe posição negativa. Com o bit 7 da cor ligado, o VDP
subtrai 32 do `X`. Somando 32 ao valor gravado, a soma e a subtração se
cancelam e o objeto ganha 32 pixels de percurso aparente antes de sumir.

```asm
CALCEC:
    xor a
    ld (BEC), a
    ld a, (SAINDO)
    or a
    ret z
    ld a, (VX)
    or a
    ret p            ; só quando vai para a esquerda
    ld a, 80h
    ld (BEC), a
    ret
```

## `MAG` e `SI`

```
R#1 bit0 MAG   cada pixel do padrão vira 2×2 na tela
R#1 bit1 SI    sprites de 16×16 em vez de 8×8
```

Com `SI = 1` o número do padrão é mascarado com `& 0FCh` — os padrões 0 a 3
viram todos o padrão 0.

`MAG = 1` com `SI = 0` dá objetos de 16×16 pixels com padrões de **8 bytes** e
números de padrão livres. É quase sempre o que se quer para peças simples.

Um objeto mais alto que 16 pixels são dois sprites empilhados, o segundo em
`Y + 16`.

## Limites

- **8 sprites por linha.** O nono some (ou dispara o flag de 5º/9º em `S#0`).
- **32 sprites**, mas a lista termina no primeiro `Y = 216`.
- Colisão só é reportada em `S#0`; nada é impedido pelo VDP.

## Montar em RAM, despejar de uma vez

Escrever a tabela de atributos direto na VRAM enquanto o VDP desenha faz o
quadro ler uma tabela pela metade. Monte em RAM e envie num `otir`:

```asm
    ld hl, 1E00h
    call SETV
    ld hl, SPRB
    ld b, 28         ; 7 entradas × 4 bytes
    ld c, 98h
    otir
```

## Geometria visível vs geometria do sprite

Um padrão raramente acende da coluna 0. Se a colisão usar a caixa do sprite em
vez da caixa **visível**, sobra folga entre os objetos. Guarde as medidas reais
como `equ` e derive os planos de contato delas:

```asm
SVIS  equ 4          ; primeira coluna acesa dentro do padrão, já com MAG
SWID  equ 10         ; largura visível
BXLP  equ P1X+PWID   ; plano de contato à esquerda
BXRP  equ P2X-SWID   ; plano de contato à direita
```
