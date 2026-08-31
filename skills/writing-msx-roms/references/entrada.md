# Teclado e joystick sem a BIOS

## PPI — as portas certas

| Porta | Função |
|---|---|
| `A8h` | PPI porta A — registrador de slot primário (2 bits por página) |
| `A9h` | PPI porta B — **leitura** da linha de teclado |
| `AAh` | PPI porta C — **seleção** da linha (bits 0–3) + CAPS, motor, clique |

Cuidado com a nomenclatura: é comum ver `A9h`/`AAh` descritos como "porta A" e
"porta B". A seleção é na `AAh`, a leitura na `A9h`.

## Ler uma linha

`0` significa **tecla pressionada**. Os bits altos da `AAh` controlam CAPS,
motor do gravador e clique da tecla — precisam ser preservados.

```asm
KROW:                ; B = linha (0..10), devolve a linha em A
    in a, (0AAh)
    and 0F0h         ; preserva CAPS / motor / clique
    or b
    out (0AAh), a
    in a, (0A9h)
    ret
```

## Linhas úteis

```
linha 8   bit0 ESPAÇO  bit1 HOME  bit2 INS  bit3 DEL
          bit4 ←       bit5 ↑     bit6 ↓    bit7 →

linha 2   bit6 A       (demais letras seguem a matriz padrão)
linha 5   bit7 Z
```

Para um segundo jogador no teclado, teclas em linhas diferentes custam uma
leitura de `KROW` cada.

## Joystick — pelo PSG

`R#15` seleciona a porta (bit 6) e habilita o pino 8 (bit 4 em zero); `R#14`
devolve o estado, lido em `A2h`, ativo em zero.

```asm
; B=0 porta 1, B=1 porta 2. Devolve em A: bit0 cima, bit1 baixo,
; bit2 esq, bit3 dir, bit4 gatilho — 1 = pressionado.
JOY:
    ld a, 15
    ld e, 8Fh
    bit 0, b
    jr z, JOY1
    ld e, 0CFh
JOY1:
    call PSGW
    ld a, 14
    out (0A0h), a
    in a, (0A2h)
    cpl
    and 1Fh
    ret
```

## Normalizar as duas fontes

Traga teclado e joystick para **o mesmo layout de bits** e combine com `or`.
Depois derive a borda de subida — é o que faz um menu andar um item por toque em
vez de varrer a lista inteira em meio segundo:

```
BOT   = teclado OR joystick        ; estado agora
BOTE  = BOT AND NOT BOTA           ; só o que ACABOU de ser pressionado
BOTA  = BOT                        ; guarda para o próximo quadro
```

Use `BOT` para movimento contínuo e `BOTE` para confirmações, navegação de menu
e saque.
