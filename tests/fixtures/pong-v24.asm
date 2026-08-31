
    org 4000h
    db "AB"
    dw INIT
    dw 0
    dw 0
    dw 0
    ds 6,0

; ---------------------------------------------------------------- portas
V99 equ 99h
V98 equ 98h
V9A equ 9Ah
P0 equ 0A0h
P1 equ 0A1h
P2R equ 0A2h
F0 equ 7Ch
F1 equ 7Dh
PPIB equ 0A9h
PPIC equ 0AAh

; ------------------------------------------------------------ geometria
; Sprites 8x8 com MAG: cada celula do padrao vira 2x2 na tela.
;   raquete: celulas 2..5 -> X +4..+11  (PWID = 8)
;   bola:    celulas 2..6 -> X +4..+13  (SWID = 10)
SH equ 192
PH equ 32
PH2 equ 16
SVIS equ 4
SWID equ 10
PWID equ 8
BHALF equ 5
PCENT equ 80
P1X equ 8
P2X equ 232
PMAX equ 159
BYMAX equ 181
BXLP equ P1X+PWID
BXRP equ P2X-SWID
BOUTR equ 248
MAXPTS equ 10

; ---------------------------------------------------------------- audio
AUDPSG equ 0
AUDFM equ 1
AUDOFF equ 2
NOTAMIN equ 24
NNOTAS equ 84
NFONT equ 38
LOGOAD equ 15*128
LOGOSZ equ 84*128
LZBUF equ 0C100h

; posicoes no framebuffer do G4: endereco = y*128 + x/2
; rotulos em x=64, valores em x=136, cursor em x=48
LB0 equ 104*128+32
LB1 equ 116*128+32
LB2 equ 128*128+32
LB3 equ 144*128+32
CUR0 equ 104*128+24
CUR1 equ 116*128+24
CUR2 equ 128*128+24
CUR3 equ 144*128+24
VAL0 equ 104*128+68
VAL1 equ 116*128+68
VAL2 equ 128*128+68
TXPTS equ 164*128+24
TXHLP equ 176*128+24
NITENS equ 4

; ------------------------------------------------------------- VRAM (G3)
NAMT equ 1800h
PATT equ 0000h
COLT equ 2000h
SATT equ 1C00h
YPTT equ 1E00h
SPTT equ 3800h
SATC4 equ SATT+64
SC1A equ NAMT+44
SC2A equ NAMT+50

; -------------------------------------------------------------- RAM vars
BX equ 0C000h
BY equ 0C001h
BVX equ 0C002h
BVY equ 0C003h
P1Y equ 0C004h
P2Y equ 0C005h
P1V equ 0C006h
P2V equ 0C007h
S1 equ 0C008h
S2 equ 0C009h
P1M equ 0C00Ah
PAUSA equ 0C00Bh
SRV equ 0C00Eh
BPAST equ 0C00Fh
GIRO equ 0C010h
GIRT equ 0C011h
GIRF equ 0C012h
PISCA equ 0C013h
KLIN equ 0C014h
BEC equ 0C015h
AUDIO equ 0C016h
FIM equ 0C017h
MSEL equ 0C018h
BOT equ 0C019h
BOTA equ 0C01Ah
BOTE equ 0C01Bh
MVTMP equ 0C01Ch
MSONG equ 0C01Eh
; 6 vozes x 4 bytes (ponteiro, quadros restantes, volume) = 0C020..0C037
MVBASE equ 0C020h
NPLAY equ 0C038h
DIFF equ 0C039h
MDIRTY equ 0C03Ah
BOT2 equ 0C03Bh
BOT2A equ 0C03Ch
P2M equ 0C03Dh
SPRB equ 0C040h
TXY equ 0C05Ch
TXAD equ 0C05Dh
TXSTR equ 0C05Fh

; ================================================================== INIT
INIT:
    di
    ld sp, 0F380h
    call PG2
    in a, (V99)

    ld hl, VREG
    ld b, 12
    ld c, V99
    xor a
VLP:
    ld d, (hl)
    out (c), d
    ld e, a
    set 7, e
    out (c), e
    inc hl
    inc a
    djnz VLP

    call PSGI
    call FMI
    xor a
    ld (AUDIO), a
    ld (BOTA), a
    ld (BOT2A), a
    ld (NPLAY), a
    ld (P2M), a
    inc a
    ld (DIFF), a
    call AUDSET

MAIN:
    call TITULO
    call SETG3
    call GINIT
GLOOP:
    call WVB
    call INPUT
    call P1U
    ld a, (NPLAY)
    or a
    jr z, GIA
    call P2U
    jr GJOGA
GIA:
    call AIU
GJOGA:
    ld a, (PAUSA)
    or a
    jr nz, GPAUS
    call BALL
    call BSPIN
    jr GDRW
GPAUS:
    call MSAQUE
GDRW:
    call DRAW
    call MUSIC
    ld a, (FIM)
    or a
    jr z, GLOOP
    call FIMSCR
    jp MAIN

; ---- coloca a PAGINA 2 (8000h-BFFFh) no mesmo slot da pagina 1.
; A BIOS chama o INIT de um cartucho de 32 KB com a pagina 1 ja no slot do
; cartucho, mas deixa a PAGINA 2 na RAM. Sem este chaveamento tudo o que a ROM
; guarda acima de 0x8000 le lixo -- foi o que emudeceu a musica do jogo, cujas
; faixas caem inteiras nessa faixa. O cartucho fica no slot 1, nao expandido,
; entao copiar o slot primario da pagina 1 para a pagina 2 basta.
PG2:
    in a, (0A8h)
    ld b, a
    and 0Ch
    rlca
    rlca
    ld c, a
    ld a, b
    and 0CFh
    or c
    out (0A8h), a
    ret

; ---- escreve os 12 primeiros registradores do VDP a partir de HL
VREGS:
    ld b, 12
    ld c, V99
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

; ---- SCREEN 5 (G4) para a tela de abertura: bitmap, sem sprites, paleta neon
SETG4:
    ld hl, VREG5
    call VREGS
    ld hl, PALT
    call PALSET
    ld hl, 0
    call SETV
    ld bc, 6000h
    ld d, 22h
    call VFILL
    ld hl, LOGOCMP
    ld de, LZBUF
    call LZUN
    ld hl, LOGOAD
    call SETV
    ld hl, LZBUF
    ld bc, LOGOSZ
    call VWR
    ret

; ---- LZSS de janela 4 KB: HL = fluxo comprimido, DE = destino em RAM.
; Para quando HL alcanca LOGOFIM -- o tamanho da saida e implicito. O `ldir`
; faz a copia SOBREPOSTA, que e o que transforma uma referencia de distancia 1
; numa corrida de bytes iguais sem codigo extra.
; Os flags vivem no acumulador alternativo; a sentinela avisa quando os 8 bits
; acabaram. Nada de comentario na mesma linha de  ex af,af'  -- o apostrofo
; desliga o detector de comentario do montador.
LZUN:
    ld a, 1
    ex af, af'
LZ0:
    ex af, af'
    srl a
    jr nz, LZ1
    ld a, (hl)
    inc hl
    scf
    rra
LZ1:
    jr nc, LZM
    ex af, af'
    ld a, (hl)
    ld (de), a
    inc hl
    inc de
    jr LZTST
LZM:
    ex af, af'
    ld c, (hl)
    inc hl
    ld a, (hl)
    inc hl
    push hl
    push af
    and 0Fh
    ld b, a
    ld h, d
    ld l, e
    scf
    sbc hl, bc
    pop af
    rrca
    rrca
    rrca
    rrca
    and 0Fh
    add a, 3
    ld c, a
    ld b, 0
    ldir
    pop hl
LZTST:
    ld a, h
LZFH:
    cp LOGOFIM/256
    jr nz, LZ0
    ld a, l
LZFL:
    cp LOGOFIM%256
    jr nz, LZ0
    ret

; ---- SCREEN 4 (G3) para o jogo. O framebuffer do G4 ocupa 0000-5FFF, ou seja
; passou por cima das tabelas de padrao, cor, nome e sprites: todas precisam
; ser reconstruidas. Feito com o display apagado (R1 bit6 = 0 no VREG).
SETG3:
    ld hl, VREG
    call VREGS
    ld hl, PAL
    call PALSET
    call CLRBG
    call SCRINI
    call SPRUP
    call COLINIT
    call SATCLR
    ld a, 41h
    out (V99), a
    ld a, 81h
    out (V99), a
    ret

; ---------------------------------------------- espera VBlank (S#0 bit7)
WVB:
    in a, (V99)
    and 80h
    jr z, WVB
    ret

; -------------------- aponta o ponteiro de VRAM para HL (16 bits, modo escrita)
; A porta 99h so carrega 14 bits do endereco; os de cima vem de R#14. O
; framebuffer do G4 passa de 0x3FFF, entao R#14 tem de ser escrito sempre --
; inclusive zerado, porque o VDP incrementa R#14 sozinho ao cruzar 16 KB.
SETV:
    ld a, h
    rlca
    rlca
    and 3
    out (V99), a
    ld a, 8Eh
    out (V99), a
    ld a, l
    out (V99), a
    ld a, h
    and 3Fh
    or 40h
    out (V99), a
    ret

; --------------------------- preenche BC bytes com D a partir do ponteiro
VFILL:
    ld a, d
    out (V98), a
    dec bc
    ld a, b
    or c
    jr nz, VFILL
    ret

; ------------------------- copia BC bytes de HL para a VRAM (16 bits, ao
; contrario do OTIR, que so conta ate 255)
VWR:
    ld a, (hl)
    out (V98), a
    inc hl
    dec bc
    ld a, b
    or c
    jr nz, VWR
    ret

; ------------------------------------------- carrega a paleta (32 bytes)
; HL = tabela de 32 bytes da paleta
PALSET:
    xor a
    out (V99), a
    ld a, 90h
    out (V99), a
    ld bc, 209Ah
    otir
    ret

; ------------------------------- limpa o plano de tiles (campo uniforme)
CLRBG:
    ld hl, PATT
    call SETV
    ld bc, 1800h
    ld d, 0
    call VFILL

    ld hl, COLT
    call SETV
    ld bc, 1800h
    ld d, 22h
    call VFILL

CLRNAM:
    ld hl, NAMT
    call SETV
    ld bc, 0300h
    ld d, 0
    call VFILL
    ret

; ------------------------------------------------------- fonte (38 chars)
; O G3 tem TRES bancos de padroes (linhas 0-7, 8-15, 16-23 da tela) e o
; numero do char e relativo ao banco. Como a tela inicial usa a altura toda,
; a fonte precisa ser instalada nos tres.
SCRINI:
    ld hl, PATT+8
    call SETV
    call FNTW
    ld hl, PATT+800h+8
    call SETV
    call FNTW
    ld hl, PATT+1000h+8
    call SETV
    call FNTW
    ld hl, COLT+8
    call SETV
    call FNTC
    ld hl, COLT+800h+8
    call SETV
    call FNTC
    ld hl, COLT+1000h+8
    call SETV
    call FNTC
    ret
FNTW:
    ld hl, FONT
    ld bc, NFONT*8
    call VWR
    ret
FNTC:
    ld bc, NFONT*8
    ld d, 42h
    call VFILL
    ret

; ------------------------------------ padroes de sprite (7 x 8 bytes) ->
SPRUP:
    ld hl, SPTT
    call SETV
    ld hl, SPRPAT
    ld b, 56
    ld c, V98
    otir
    ret

; As cores dos 4 sprites de raquete sao 64 bytes de uma constante so cada --
; gerar com dois lacos custa menos ROM do que guardar a tabela.
COLINIT:
    ld hl, SATT
    call SETV
    ld b, 32
    ld a, 4
CIN1:
    out (V98), a
    djnz CIN1
    ld b, 32
    ld a, 7
CIN2:
    out (V98), a
    djnz CIN2
    ld hl, BCOL
    ld b, 32
    ld c, V98
    otir
    ret

SATCLR:
    ld hl, YPTT
    call SETV
    ld bc, 0200h
    ld d, 216
    call VFILL
    ret

; ================================================================== texto
; A = caractere ASCII -> A = numero do char na Pattern Table
;   ' ' -> 0   '0'..'9' -> 1..10   'A'..'Z' -> 11..36   ':' -> 37   '>' -> 38
CHMAP:
    cp 30h
    jr c, CHMSP
    cp 3Ah
    jr nc, CHM1
    sub 2Fh
    ret
CHM1:
    cp 3Ah
    jr nz, CHM2
    ld a, 37
    ret
CHM2:
    cp 3Eh
    jr nz, CHM3
    ld a, 38
    ret
CHM3:
    cp 41h
    jr c, CHMSP
    cp 5Bh
    jr nc, CHMSP
    sub 36h
    ret
CHMSP:
    xor a
    ret

; ---- escreve 8 pixels no framebuffer do G4 a partir do padrao em H.
; Branco (4) onde o bit e 1, cor de fundo (2) onde e 0. 2 pixels por byte.
PIX8:
    ld b, 4
PIX8L:
    sla h
    ld a, 2
    jr nc, PX1
    ld a, 4
PX1:
    rlca
    rlca
    rlca
    rlca
    ld c, a
    sla h
    ld a, 2
    jr nc, PX2
    ld a, 4
PX2:
    or c
    out (V98), a
    djnz PIX8L
    ret

; ---- escreve a string HL no framebuffer do G4, canto superior esquerdo em DE
; (endereco = y*128 + x/2). Percorre uma LINHA do glifo por vez: assim sao 8
; reposicionamentos por string, e nao 8 por caractere.
PRSTR5:
    ld (TXSTR), hl
    ld (TXAD), de
    xor a
    ld (TXY), a
PS5L:
    ld hl, (TXAD)
    call SETV
    ld hl, (TXSTR)
PS5C:
    ld a, (hl)
    or a
    jr z, PS5E
    push hl
    call CHMAP
    or a
    jr z, PS5B
    dec a
    ld l, a
    ld h, 0
    add hl, hl
    add hl, hl
    add hl, hl
    ld de, FONT
    add hl, de
    ld a, (TXY)
    ld e, a
    ld d, 0
    add hl, de
    ld a, (hl)
    jr PS5W
PS5B:
    xor a
PS5W:
    ld h, a
    call PIX8
    pop hl
    inc hl
    jr PS5C
PS5E:
    ld hl, (TXAD)
    ld de, 128
    add hl, de
    ld (TXAD), hl
    ld hl, TXY
    inc (hl)
    ld a, (hl)
    cp 8
    jr c, PS5L
    ret

; HL = string ASCII terminada em 0, DE = endereco na Name Table
PRSTR:
    ex de, hl
    call SETV
    ex de, hl
PRS1:
    ld a, (hl)
    or a
    ret z
    call CHMAP
    out (V98), a
    inc hl
    jr PRS1

; ================================================================= placar
SCDRW:
    ld a, (S1)
    ld hl, SC1A
    call SCD2
    ld a, (S2)
    ld hl, SC2A
    call SCD2
    ret

; A = valor 0..99, HL = endereco VRAM do digito das dezenas
SCD2:
    ld c, a
    call SETV
    ld a, c
    ld b, 0
SCD2L:
    cp 10
    jr c, SCD2D
    sub 10
    inc b
    jr SCD2L
SCD2D:
    ld c, a
    ld a, b
    inc a
    out (V98), a
    ld a, c
    inc a
    out (V98), a
    ret

; ============================================================ tela inicial
TITULO:
    call SETG4
    ld hl, TS0
    ld de, LB0
    call PRSTR5
    ld hl, TS1
    ld de, LB1
    call PRSTR5
    ld hl, TS2
    ld de, LB2
    call PRSTR5
    ld hl, TS3
    ld de, LB3
    call PRSTR5
    ld hl, TS4
    ld de, TXPTS
    call PRSTR5
    ld hl, TS5
    ld de, TXHLP
    call PRSTR5
    xor a
    ld (MSEL), a
    ld (MSONG), a
    call MARCA
    call MRESET
    ld a, 40h
    out (V99), a
    ld a, 81h
    out (V99), a
TL1:
    call WVB
    call INPUT
    call TDRAW
    call MUSIC
    ld a, (BOTE)
    bit 0, a
    jr z, TL2
    ld a, (MSEL)
    or a
    jr z, TL2
    dec a
    ld (MSEL), a
    call MARCA
TL2:
    ld a, (BOTE)
    bit 1, a
    jr z, TL3
    ld a, (MSEL)
    cp NITENS-1
    jr nc, TL3
    inc a
    ld (MSEL), a
    call MARCA
TL3:
    ld a, (BOTE)
    bit 2, a
    jr z, TL4
    ld a, -1
    call MVAL
TL4:
    ld a, (BOTE)
    bit 3, a
    jr z, TL5
    ld a, 1
    call MVAL
TL5:
    ld a, (BOTE)
    bit 4, a
    jr z, TL1
    ld a, (MSEL)
    cp NITENS-1
    jr z, TL6
    ld a, 1
    call MVAL
    jr TL1
TL6:
    call MSIL
    ld a, 1
    ld (MSONG), a
    call MRESET
    ret

; marca o menu para ser redesenhado no proximo quadro
MARCA:
    ld a, 1
    ld (MDIRTY), a
    ret

; A = +1 ou -1: muda o valor do item selecionado, com volta no fim
MVAL:
    ld c, a
    ld a, (MSEL)
    or a
    jr nz, MV1
    ld hl, AUDIO
    ld b, 3
    jr MVGO
MV1:
    cp 1
    jr nz, MV2
    ld hl, NPLAY
    ld b, 2
    jr MVGO
MV2:
    cp 2
    ret nz
    ld hl, DIFF
    ld b, 3
MVGO:
    ld a, (hl)
    add a, c
    jp p, MVG1
    ld a, b
    dec a
MVG1:
    cp b
    jr c, MVG2
    xor a
MVG2:
    ld (hl), a
    call MARCA
    ld a, (MSEL)
    or a
    ret nz
    call MSIL
    jp AUDSET

; Redesenha o menu SO quando algo muda. Cada caractere no G4 custa 32 bytes de
; VRAM; redesenhar tudo a cada quadro passava de um frame inteiro de CPU.
TDRAW:
    ld a, (MDIRTY)
    or a
    ret z
    xor a
    ld (MDIRTY), a
    ld hl, CURTAB
    ld b, NITENS
TD0:
    push bc
    push hl
    ld e, (hl)
    inc hl
    ld d, (hl)
    ld hl, TSBL
    call PRSTR5
    pop hl
    inc hl
    inc hl
    pop bc
    djnz TD0
    ld a, (MSEL)
    add a, a
    ld e, a
    ld d, 0
    ld hl, CURTAB
    add hl, de
    ld e, (hl)
    inc hl
    ld d, (hl)
    ld hl, TSCUR
    call PRSTR5
    ld a, (AUDIO)
    ld hl, AUDPT
    ld de, VAL0
    call TDVAL
    ld a, (NPLAY)
    ld hl, PLPT
    ld de, VAL1
    call TDVAL
    ld a, (DIFF)
    ld hl, DIFPT
    ld de, VAL2
    call TDVAL
    ret

; A = indice, HL = tabela de ponteiros de string, DE = destino
TDVAL:
    push de
    add a, a
    ld e, a
    ld d, 0
    add hl, de
    ld e, (hl)
    inc hl
    ld d, (hl)
    ex de, hl
    pop de
    call PRSTR5
    ret

; ============================================================== fim de jogo
FIMSCR:
    call SATCLR
    call CLRNAM
    ld a, (S1)
    cp MAXPTS
    jr nc, FSW1
    ld hl, FS2
    ld de, NAMT+8*32+12
    ld a, (NPLAY)
    or a
    jr z, FSW2
    ld hl, FS4
    ld de, NAMT+8*32+9
    jr FSW2
FSW1:
    ld hl, FS1
    ld de, NAMT+8*32+10
FSW2:
    call PRSTR
    ld a, (S1)
    ld hl, NAMT+12*32+13
    call SCD2
    ld hl, FSX
    ld de, NAMT+12*32+16
    call PRSTR
    ld a, (S2)
    ld hl, NAMT+12*32+18
    call SCD2
    ld hl, FS3
    ld de, NAMT+17*32+2
    call PRSTR
FSL1:
    call WVB
    call INPUT
    call MUSIC
    ld a, (BOTE)
    and 10h
    jr z, FSL1
    call MSIL
    ret

; ================================================================== PSG
PSGW:
    out (P0), a
    ld a, e
    out (P1), a
    ret

PSGI:
    ld a, 7
    ld e, 0BFh
    call PSGW
    ld a, 8
    ld e, 0
    call PSGW
    ld a, 9
    ld e, 0
    call PSGW
    ld a, 10
    ld e, 0
    call PSGW
    ld a, 15
    ld e, 8Fh
    call PSGW
    ret

; ================================================================ YM2413
; escreve E no registrador A, respeitando o tempo de escrita do chip
FMW:
    out (F0), a
    ld a, 2
FMW1:
    dec a
    jr nz, FMW1
    ld a, e
    out (F1), a
    ld a, 6
FMW2:
    dec a
    jr nz, FMW2
    ret

FMI:
    ld a, 0Eh
    ld e, 0
    call FMW
    ld b, 9
    ld a, 20h
FV:
    push af
    ld e, 0
    call FMW
    pop af
    inc a
    djnz FV

; O resto da inicializacao e uma lista de (registrador, valor). Escrever como
; tabela custa 2 bytes por par em vez dos 7 de  ld a,n / ld e,n / call FMW.
    ld hl, FMINI
FMSEQ:
    ld a, (hl)
    cp 0FFh
    ret z
    inc hl
    ld e, (hl)
    inc hl
    call FMW
    jr FMSEQ

FMINI:
; frequencias padrao dos canais de percussao (6=BD, 7=HH/SD, 8=TOM/TCY)
    db 16h, 20h
    db 26h, 05h
    db 17h, 50h
    db 27h, 05h
    db 18h, 0C0h
    db 28h, 01h
; modo ritmo (bit5) ANTES dos volumes: fora dele 36h/37h/38h sao registradores
; de INSTRUMENTO dos canais 6/7/8, nao de volume
    db 0Eh, 20h
; cada volume e escrito duas vezes com valores diferentes porque o chip ignora
; escrita que nao muda o registrador -- a primeira so garante a transicao
    db 36h, 0F0h
    db 36h, 00Fh
    db 37h, 0FFh
    db 37h, 002h
    db 38h, 00Fh
    db 38h, 0F0h
    db 0FFh

; ================================================================== musica
; 3 vozes. Cada faixa e uma lista de pares (nota, duracao em quadros);
; nota 0 = silencio, 255 = fim (volta ao inicio).
; Estado por voz em MVBASE + 4*voz: ponteiro(2), quadros restantes(1), volume(1)
; O PSG tem 3 canais; o YM2413 em modo ritmo deixa 0..5 livres (6/7/8 sao a
; percussao dos efeitos). Entao o PSG toca as vozes 0..2 e o FM toca as 6.
MUSIC:
    ld a, (AUDIO)
    cp AUDOFF
    ret nc
    ld b, 3
    or a
    jr z, MUS0
    ld b, 6
MUS0:
    ld c, 0
MUS1:
    push bc
    call MVOZ
    pop bc
    inc c
    ld a, c
    cp b
    jr c, MUS1
    ret

MVOZ:
    ld a, c
    add a, a
    add a, a
    ld e, a
    ld d, 0
    ld hl, MVBASE
    add hl, de
    ld (MVTMP), hl
    inc hl
    inc hl
    dec (hl)
    jp z, MVNEXT
    jp MDECAY

MVNEXT:
    ld hl, (MVTMP)
    ld e, (hl)
    inc hl
    ld d, (hl)
    ld a, (de)
    inc a
    jr nz, MVPLAY
    call MTRK
MVPLAY:
; um token por evento: indice no dicionario, ou 254 seguido do par literal
    ld a, (de)
    inc de
    cp 254
    jr z, MVLIT
    push de
    ld l, a
    ld h, 0
    add hl, hl
    ld de, MDICT
    add hl, de
    ld b, (hl)
    inc hl
    ld a, (hl)
    pop de
    jr MVGRV
MVLIT:
    ld a, (de)
    ld b, a
    inc de
    ld a, (de)
    inc de
MVGRV:
    ld hl, (MVTMP)
    ld (hl), e
    inc hl
    ld (hl), d
    inc hl
    ld (hl), a
    inc hl
    ld (hl), 60
    ld a, (AUDIO)
    or a
    ld a, b
    jp nz, FMON
    jp PSGON

; DE = inicio da faixa C da musica MSONG
MTRK:
    ld a, (MSONG)
    add a, a
    ld e, a
    ld d, 0
    ld hl, SONGS
    add hl, de
    ld e, (hl)
    inc hl
    ld d, (hl)
    ex de, hl
    ld a, c
    add a, a
    ld e, a
    ld d, 0
    add hl, de
    ld e, (hl)
    inc hl
    ld d, (hl)
    ret

; decaimento do volume no PSG (o OPLL tem envoltoria propria)
MDECAY:
    ld a, (AUDIO)
    or a
    ret nz
    ld hl, (MVTMP)
    inc hl
    inc hl
    inc hl
    ld a, (hl)
    or a
    ret z
    dec (hl)
    ld a, (hl)
    srl a
    srl a
    ld e, a
    ld a, 8
    add a, c
    call PSGW
    ret

; recarrega as 3 vozes no inicio da musica MSONG
MRESET:
    ld a, (MSONG)
    add a, a
    ld e, a
    ld d, 0
    ld hl, SONGS
    add hl, de
    ld e, (hl)
    inc hl
    ld d, (hl)
    ex de, hl
    ld de, MVBASE
    ld b, 6
MRS1:
    ld a, (hl)
    ld (de), a
    inc hl
    inc de
    ld a, (hl)
    ld (de), a
    inc hl
    inc de
    ld a, 1
    ld (de), a
    inc de
    xor a
    ld (de), a
    inc de
    djnz MRS1
    ret

; mixer do PSG: so liga os tres canais de tom quando a musica e do PSG
AUDSET:
    ld a, (AUDIO)
    cp AUDPSG
    ld e, 0BFh
    jr nz, AUDS1
    ld e, 0B8h
AUDS1:
    ld a, 7
    call PSGW
    ret

; corta qualquer nota pendurada nos dois chips
MSIL:
    ld c, 0
MSIL1:
    ld a, c
    cp 3
    jr nc, MSIL2
    ld a, 8
    add a, c
    ld e, 0
    call PSGW
MSIL2:
    ld a, 20h
    add a, c
    ld e, 0
    call FMW
    inc c
    ld a, c
    cp 6
    jr c, MSIL1
    ret

; A = nota (0 = silencio), C = canal 0..2
PSGON:
    or a
    jr z, PSGOFF
    sub NOTAMIN
    jr nc, PSGN1
    xor a
PSGN1:
    cp NNOTAS
    jr c, PSGN2
    ld a, NNOTAS-1
PSGN2:
    add a, a
    ld e, a
    ld d, 0
    ld hl, PSGTAB
    add hl, de
    ld e, (hl)
    inc hl
    ld d, (hl)
    ld a, c
    add a, a
    call PSGW
    ld e, d
    ld a, c
    add a, a
    inc a
    call PSGW
    ld a, c
    add a, 8
    ld e, 15
    call PSGW
    ret
PSGOFF:
    ld a, c
    add a, 8
    ld e, 0
    call PSGW
    ret

FMON:
    or a
    jr z, FMOFF
    sub NOTAMIN
    jr nc, FMN1
    xor a
FMN1:
    cp NNOTAS
    jr c, FMN2
    ld a, NNOTAS-1
FMN2:
; A = indice da nota (0..NNOTAS-1). Separa oitava e semitom por subtracao
; sucessiva: o F baixo vem da tabela de 12, o byte alto sai da oitava.
    add a, FMDESL
    ld b, 0
FMOC:
    cp 12
    jr c, FMOK
    sub 12
    inc b
    jr FMOC
FMOK:
    ld e, a
    ld d, 0
    ld hl, FBASE
    add hl, de
    ld e, (hl)
    ld a, b
    add a, a
    or 11h
    ld d, a
    push de
    ld hl, INSTAB
    ld e, c
    ld d, 0
    add hl, de
    ld e, (hl)
    ld a, 30h
    add a, c
    call FMW
    pop de
    ld a, 10h
    add a, c
    call FMW
    ld a, 20h
    add a, c
    ld e, d
    call FMW
    ret
FMOFF:
    ld a, 20h
    add a, c
    ld e, 0
    call FMW
    ret

; =========================================================== estado inicial
GINIT:
    xor a
    ld (S1), a
    ld (S2), a
    ld (PAUSA), a
    ld (FIM), a
    ld a, 2
    ld (SRV), a
GRI:
    ld a, 123
    ld (BX), a
    ld a, 91
    ld (BY), a
    ld a, 2
    ld (BVX), a
    ld a, (SRV)
    neg
    ld (SRV), a
    ld (BVY), a
    ld a, PCENT
    ld (P1Y), a
    ld (P2Y), a
    xor a
    ld (P1V), a
    ld (P2V), a
    ld (P1M), a
    ld (BPAST), a
    ld (GIRO), a
    ld (GIRF), a
    ld (PISCA), a
    ld (BEC), a
    ld a, 1
    ld (GIRT), a
    call SCDRW
    ret

; ========================================================= teclado/joystick
; BOT: bit0=CIMA bit1=BAIXO bit2=ESQ bit3=DIR bit4=OK (1 = pressionado)
; BOTE: so os que ACABARAM de ser pressionados neste quadro
; ---- le a linha B do teclado (PPI porta C bits 0-3) -> A
KROW:
    in a, (PPIC)
    and 0F0h
    or b
    out (PPIC), a
    in a, (PPIB)
    ret

; ---- le o joystick: B=0 porta 1, B=1 porta 2. Devolve em A ja no layout do
; BOT (bit0 cima, bit1 baixo, bit2 esq, bit3 dir, bit4 gatilho), 1 = apertado.
; O R15 do PSG seleciona a porta no bit6 e habilita o pino 8 com o bit4 em 0.
JOY:
    ld a, 15
    ld e, 8Fh
    bit 0, b
    jr z, JOY1
    ld e, 0CFh
JOY1:
    call PSGW
    ld a, 14
    out (P0), a
    in a, (P2R)
    cpl
    and 1Fh
    ret

; BOT: bit0=CIMA bit1=BAIXO bit2=ESQ bit3=DIR bit4=OK (1 = pressionado)
; BOTE: so os que ACABARAM de ser pressionados neste quadro
INPUT:
    ld b, 8
    call KROW
    ld (KLIN), a
    cpl
    ld b, a
    xor a
    bit 5, b
    jr z, LB1K
    or 01h
LB1K:
    bit 6, b
    jr z, LB2K
    or 02h
LB2K:
    bit 4, b
    jr z, LB3K
    or 04h
LB3K:
    bit 7, b
    jr z, LB4K
    or 08h
LB4K:
    bit 0, b
    jr z, LB5K
    or 10h
LB5K:
    ld c, a
    ld b, 0
    call JOY
    or c
    ld (BOT), a
    ld b, a
    ld a, (BOTA)
    cpl
    and b
    ld (BOTE), a
    ld a, b
    ld (BOTA), a

; --- jogador 2: teclas A (linha 2 bit6) e Z (linha 5 bit7), ou joystick 2
    ld b, 2
    call KROW
    cpl
    ld c, 0
    bit 6, a
    jr z, IN2A
    ld c, 01h
IN2A:
    ld b, 5
    call KROW
    cpl
    bit 7, a
    jr z, IN2B
    ld a, c
    or 02h
    ld c, a
IN2B:
    ld b, 1
    call JOY
    or c
    ld (BOT2), a
    ld b, a
    ld a, (BOT2A)
    cpl
    and b
    ld a, b
    ld (BOT2A), a

; --- movimento das raquetes a partir dos botoes
    ld a, (BOT)
    ld hl, P1M
    call MOVDIR
    ld a, (BOT2)
    ld hl, P2M
    call MOVDIR
    ret

; A = botoes, HL = variavel de movimento (-1 cima, +1 baixo, 0 parado)
MOVDIR:
    bit 0, a
    jr z, MD1
    ld (hl), -1
    ret
MD1:
    bit 1, a
    jr z, MD2
    ld (hl), 1
    ret
MD2:
    ld (hl), 0
    ret

MSAQUE:
    ld a, (BOTE)
    and 10h
    ret z
    xor a
    ld (PAUSA), a
    ret

; ============================================ raquetes humanas (P1 e P2)
; HL = P1M/P2M (direcao), DE = P1Y/P2Y, BC = P1V/P2V
P1U:
    ld hl, P1M
    ld de, P1Y
    ld bc, P1V
    jp PADU
P2U:
    ld hl, P2M
    ld de, P2Y
    ld bc, P2V
PADU:
    ld a, (hl)
    or a
    jr z, PADSTOP
    jp m, PADUP
    ld a, (de)
    add a, 3
    cp PMAX+1
    jr c, PADSET
    ld a, PMAX
PADSET:
    ld (de), a
    ld a, 3
PADV:
    ld h, b
    ld l, c
    ld (hl), a
    ret
PADUP:
    ld a, (de)
    sub 3
    jr nc, PADSET2
    xor a
PADSET2:
    ld (de), a
    ld a, -3
    jr PADV
PADSTOP:
    xor a
    jr PADV

; ====================================================== raquete da IA (P2)
; A velocidade da IA e o seletor de dificuldade: 1, 2 ou 3 pixels por quadro.
AIU:
    ld a, (DIFF)
    ld e, a
    ld d, 0
    ld hl, AISPD
    add hl, de
    ld b, (hl)
    ld a, (BY)
    add a, BHALF
    ld d, a
    ld a, (P2Y)
    add a, PH2
    cp d
    jr z, AISTOP
    jr c, AIDOWN
    ld a, (P2Y)
    sub b
    jr nc, AISET
    xor a
AISET:
    ld (P2Y), a
    ld a, b
    neg
    ld (P2V), a
    ret
AIDOWN:
    ld a, (P2Y)
    add a, b
    cp PMAX+1
    jr c, AISET2
    ld a, PMAX
AISET2:
    ld (P2Y), a
    ld a, b
    ld (P2V), a
    ret
AISTOP:
    xor a
    ld (P2V), a
    ret

; ------------------------------ clampa A (com sinal) no intervalo -6..+6
CLV:
    ld b, a
    add a, 6
    cp 13
    ld a, b
    ret c
    bit 7, b
    ld a, 6
    ret z
    ld a, -6
    ret

; ==================================================================== bola
BALL:
    ld hl, BY
    ld a, (BVY)
    add a, (hl)
    ld (hl), a

    ld a, (BVY)
    or a
    jp m, BYUP
    ld a, (BY)
    cp BYMAX+1
    jr c, BYOK
    ld a, BYMAX
    ld (BY), a
    call BNEGY
    jr BYOK
BYUP:
    ld a, (BY)
    cp BYMAX+1
    jr c, BYOK
    xor a
    ld (BY), a
    call BNEGY
BYOK:
    ld hl, BX
    ld a, (BVX)
    add a, (hl)
    ld (hl), a

    ld a, (BVX)
    or a
    jp m, BGOL

    ld a, (BPAST)
    or a
    jr nz, BDOUT
    ld a, (BX)
    cp BXRP
    ret c
; AABB vertical: colide se BY+SWID-1-P2Y couber em 0..PH+SWID-2 (sem sinal)
    ld a, (P2Y)
    ld e, a
    ld a, (BY)
    add a, SWID-1
    sub e
    cp PH+SWID-1
    jr nc, BMISS
    ld a, (BVX)
    neg
    dec a
    cp 0FAh
    jr nc, BR1
    ld a, -6
BR1:
    ld (BVX), a
    ld a, (P2V)
    ld hl, BVY
    add a, (hl)
    call CLV
    ld (hl), a
    ld a, (P2V)
    call SETGIR
    ld a, BXRP
    ld (BX), a
    jp SFXH

BDOUT:
    ld a, (BX)
    cp BOUTR
    jp nc, SCP1
    ret

BGOL:
    ld a, (BPAST)
    or a
    jr nz, BEOUT
    ld a, (BX)
    cp BXLP+1
    ret nc
    ld a, (P1Y)
    ld e, a
    ld a, (BY)
    add a, SWID-1
    sub e
    cp PH+SWID-1
    jr nc, BMISS
    ld a, (BVX)
    neg
    inc a
    cp 7
    jr c, BL1
    ld a, 6
BL1:
    ld (BVX), a
    ld a, (P1V)
    ld hl, BVY
    add a, (hl)
    call CLV
    ld (hl), a
    ld a, (P1V)
    neg
    call SETGIR
    ld a, BXLP
    ld (BX), a
    jp SFXH

; ja passou pela raquete de P1: BX lido COM SINAL ate a bola sumir na esquerda
BEOUT:
    ld a, (BX)
    add a, SVIS+SWID-1
    jp m, SCP2
    ret

BMISS:
    ld a, 1
    ld (BPAST), a
    ret

BNEGY:
    ld a, (BVY)
    neg
    ld (BVY), a
    jp SFXW

SCP1:
    ld hl, S1
    inc (hl)
    call SFXS
    call GRI
    ld a, (S1)
    cp MAXPTS
    ret c
    ld a, 1
    ld (FIM), a
    ret
SCP2:
    ld hl, S2
    inc (hl)
    call SFXS
    call GRI
    ld a, -2
    ld (BVX), a
    ld a, (S2)
    cp MAXPTS
    jr c, SCP2B
    ld a, 1
    ld (FIM), a
    ret
SCP2B:
    ld a, 1
    ld (PAUSA), a
    ret

; ================================================================== giro
;   raquete de P1 bate no lado ESQUERDO da bola -> GIRO = -P1V
;   raquete de P2 bate no lado DIREITO da bola  -> GIRO = +P2V
SETGIR:
    ld (GIRO), a
    or a
    ret z
    ld a, 1
    ld (GIRT), a
    ret

BSPIN:
    ld a, (GIRO)
    or a
    ret z
    ld hl, GIRT
    dec (hl)
    ret nz
    ld a, (GIRO)
    ld b, a
    or a
    jp p, BSP1
    neg
BSP1:
    cp 7
    jr c, BSP2
    ld a, 6
BSP2:
    ld e, a
    ld d, 0
    ld hl, GIRP
    add hl, de
    ld a, (hl)
    ld (GIRT), a
    ld a, (GIRF)
    bit 7, b
    jr nz, BSP3
    inc a
    jr BSP4
BSP3:
    dec a
BSP4:
    and 3
    ld (GIRF), a
    ret

; =================================================================== DRAW
;   0,1 = raquete P1 (PN 5,6)   2,3 = raquete P2   4 = corpo da bola (CC=0)
;   5 = marca do giro (CC=1, mistura por OR com o corpo)   6 = fim da lista
DRAW:
    call CALCEC
    ld hl, SPRB
    ld a, (P1Y)
    ld (hl), a
    inc hl
    ld (hl), P1X
    inc hl
    ld (hl), 5
    inc hl
    ld (hl), 0
    inc hl
    ld a, (P1Y)
    add a, 16
    ld (hl), a
    inc hl
    ld (hl), P1X
    inc hl
    ld (hl), 6
    inc hl
    ld (hl), 0
    inc hl
    ld a, (P2Y)
    ld (hl), a
    inc hl
    ld (hl), P2X
    inc hl
    ld (hl), 5
    inc hl
    ld (hl), 0
    inc hl
    ld a, (P2Y)
    add a, 16
    ld (hl), a
    inc hl
    ld (hl), P2X
    inc hl
    ld (hl), 6
    inc hl
    ld (hl), 0
    inc hl

    call BYVIS
    ld c, a
    ld a, (BX)
    ld e, a
    ld a, (BEC)
    or a
    ld a, e
    jr z, DRX
    add a, 32
DRX:
    ld e, a
    ld (hl), c
    inc hl
    ld (hl), e
    inc hl
    ld (hl), 0
    inc hl
    ld (hl), 0
    inc hl
    ld (hl), c
    inc hl
    ld (hl), e
    inc hl
    ld a, (GIRF)
    inc a
    ld (hl), a
    inc hl
    ld (hl), 0
    inc hl
    ld (hl), 216
    inc hl
    ld (hl), 0
    inc hl
    ld (hl), 0
    inc hl
    ld (hl), 0

    ld hl, YPTT
    call SETV
    ld hl, SPRB
    ld b, 28
    ld c, V98
    otir

; cores dos sprites 4 e 5 (uma por linha do padrao) com o Early Clock
    ld hl, SATC4
    call SETV
    ld hl, BCOL
    ld a, (BEC)
    ld c, a
    ld b, 32
DRC1:
    ld a, (hl)
    or c
    out (V98), a
    inc hl
    djnz DRC1
    ret

CALCEC:
    xor a
    ld (BEC), a
    ld a, (BPAST)
    or a
    ret z
    ld a, (BVX)
    or a
    ret p
    ld a, 80h
    ld (BEC), a
    ret

BYVIS:
    ld a, (PAUSA)
    or a
    jr z, BYV1
    ld a, (PISCA)
    inc a
    ld (PISCA), a
    and 10h
    jr z, BYV1
    ld a, 212
    ret
BYV1:
    ld a, (BY)
    ret

; ============================================================== efeitos
; Setor de ritmo do YM2413: bit5=modo, bit4=BD bit3=SD bit2=TOM bit1=TCY bit0=HH
RHIT:
    push de
    ld a, 0Eh
    ld e, 20h
    call FMW
    pop de
    ld a, e
    or 20h
    ld e, a
    ld a, 0Eh
    call FMW
    ret

SFXW:
    ld e, 01h
    jp RHIT
SFXH:
    ld e, 09h
    jp RHIT
SFXS:
    ld e, 0Ah
    jp RHIT

; ============================================================== dados
VREG:
    db 04h, 01h, 06h, 0FFh, 03h, 3Fh, 07h, 02h, 00h, 00h, 00h, 00h

; SCREEN 5 (G4): R0=06 modo, R1=00 display apagado,
; R7=02 borda na cor do fundo, R8=02 SPD=1 (sprites desligados na abertura)
;
; R2=1Fh e OBRIGATORIO, nao 00h. O R#2 nao define so a base: no VDP a mascara
; de leitura e  ((R2 & 7Fh) << 10) | 3FFh  (VDP.js, updateLayoutTableAddress).
; Com R2=00 a mascara fica 3FFh e o VDP le apenas o primeiro 1 KB da VRAM --
; a tela inteira sai na cor de fundo, por mais correto que o framebuffer esteja.
; Com R2=1Fh:  base = 7C00h & (-1<<15) = 0  (framebuffer em 0, como se quer)
;              mascara = 7C00h | 3FFh = 7FFFh (os 32 KB da pagina)
VREG5:
    db 06h, 00h, 1Fh, 00h, 00h, 08h, 04h, 02h, 02h, 00h, 00h, 00h

; paleta V9938: byte baixo = R<<4|B, byte alto = G
PAL:
    db 00h,00h
    db 00h,00h
    db 02h,00h
    db 00h,00h
    db 77h,07h
    db 74h,07h
    db 00h,00h
    db 70h,07h
    db 40h,00h
    db 00h,00h
    db 70h,00h
    db 00h,00h
    db 74h,04h
    db 74h,07h
    db 00h,00h
    db 74h,07h

SPRPAT:
; PN0: corpo da bola (disco 5x5)
    db 00011100b
    db 00111110b
    db 00111110b
    db 00111110b
    db 00011100b
    db 00000000b
    db 00000000b
    db 00000000b
; PN1: ponteiro para CIMA
    db 00001000b
    db 00001000b
    db 00001000b
    db 00000000b
    db 00000000b
    db 00000000b
    db 00000000b
    db 00000000b
; PN2: ponteiro para a DIREITA
    db 00000000b
    db 00000000b
    db 00001110b
    db 00000000b
    db 00000000b
    db 00000000b
    db 00000000b
    db 00000000b
; PN3: ponteiro para BAIXO
    db 00000000b
    db 00000000b
    db 00001000b
    db 00001000b
    db 00001000b
    db 00000000b
    db 00000000b
    db 00000000b
; PN4: ponteiro para a ESQUERDA
    db 00000000b
    db 00000000b
    db 00111000b
    db 00000000b
    db 00000000b
    db 00000000b
    db 00000000b
    db 00000000b
; PN5: raquete (metade de cima)
    db 00111100b
    db 00111100b
    db 00111100b
    db 00111100b
    db 00111100b
    db 00111100b
    db 00111100b
    db 00111100b
; PN6: raquete (metade de baixo)
    db 00111100b
    db 00111100b
    db 00111100b
    db 00111100b
    db 00111100b
    db 00111100b
    db 00111100b
    db 00111100b

BCOL:
    db 0Ch,0Ch,0Ah,08h,08h,00h,00h,00h
    db 00h,00h,00h,00h,00h,00h,00h,00h
    db 45h,45h,45h,45h,45h,00h,00h,00h
    db 00h,00h,00h,00h,00h,00h,00h,00h

GIRP:
    db 0, 10, 6, 4, 3, 3, 2

; instrumento<<4 | volume do YM2413 por voz (6 canais melodicos)
; piano, vibrafone, baixo acustico, clarinete, flauta, guitarra
INSTAB:
    db 32h, 0C4h, 0E3h, 55h, 46h, 26h

TSBL:
    db " ", 0
TSCUR:
    db ">", 0
TS0:
    db "AUDIO", 0
TS1:
    db "PLAYERS", 0
TS2:
    db "LEVEL", 0
TS3:
    db "PLAY GAME", 0
TS4:
    db "PARTIDA DE 10 PONTOS", 0
TS5:
    db "P2 = A E Z OU JOYSTICK 2", 0
CURTAB:
    dw CUR0
    dw CUR1
    dw CUR2
    dw CUR3
FS1:
    db "PLAYER WINS", 0
FS2:
    db "CPU WINS", 0
FSX:
    db "X", 0
FS3:
    db "ESPACO OU GATILHO PARA VOLTAR", 0
FS4:
    db "PLAYER 2 WINS", 0
APSG:
    db "PSG 3 CANAIS", 0
AFM:
    db "FM 6 CANAIS ", 0
AOFF:
    db "SEM MUSICA  ", 0
AUDPT:
    dw APSG
    dw AFM
    dw AOFF
PL1:
    db "1 PLAYER    ", 0
PL2:
    db "2 PLAYERS   ", 0
PLPT:
    dw PL1
    dw PL2
DIF0:
    db "FACIL       ", 0
DIF1:
    db "NORMAL      ", 0
DIF2:
    db "DIFICIL     ", 0
DIFPT:
    dw DIF0
    dw DIF1
    dw DIF2

; velocidade da raquete da IA por nivel de dificuldade
AISPD:
    db 1, 2, 3

LOGOCMP:
    db 113,34,0,240,0,240,0,240,34,43,17,0,160,132,32,240
    db 0,240,187,18,240,0,240,0,240,119,192,187,110,0,32,136
    db 136,0,0,160,136,139,23,48,129,178,49,240,0,240,0,240
    db 0,240,0,240,0,48,176,86,117,144,24,136,0,0,129,17
    db 144,11,49,240,112,0,240,0,240,0,240,0,240,34,34,32
    db 243,176,87,0,0,130,21,16,33,15,112,16,5,32,1,2
    db 57,240,0,240,0,240,0,240,240,209,94,48,98,129,173,176
    db 3,0,177,18,15,112,40,32,32,1,0,14,242,0,240,0
    db 240,0,240,0,144,240,65,226,1,103,16,233,139,16,65,0
    db 1,176,238,160,187,187,177,6,14,34,136,136,9,242,0,240
    db 0,240,0,240,253,64,100,238,65,119,64,8,239,64,123,0
    db 129,130,227,178,11,43,136,170,48,130,68,240,0,240,0,240
    db 0,240,222,116,50,1,17,16,1,82,32,40,1,190,127,112
    db 34,2,34,33,8,41,160,16,0,246,32,144,3,135,17,72
    db 240,0,240,0,240,0,224,81,33,175,18,34,32,11,227,65
    db 2,127,0,38,165,102,0,0,98,127,0,14,2,150,10,0
    db 105,8,1,82,142,80,43,18,17,131,241,0,240,0,240,0
    db 176,215,40,136,16,201,48,32,77,64,128,8,252,244,0,127
    db 32,105,34,11,40,11,34,251,41,86,10,0,101,153,149,89
    db 153,43,153,85,142,145,40,176,17,139,80,240,0,240,92,0
    db 240,110,132,128,0,1,69,48,32,87,96,125,130,255,96,8
    db 128,130,34,37,10,16,174,0,64,82,34,40,1,100,43,25
    db 20,1,96,244,244,0,240,0,240,242,147,77,83,32,34,116
    db 64,31,16,8,32,8,37,10,48,25,17,126,128,19,102,101
    db 251,1,116,113,40,6,18,131,241,0,240,84,0,240,197,113
    db 1,127,34,178,127,128,33,127,0,139,34,86,127,80,150,127
    db 144,29,16,112,144,40,144,48,196,0,240,0,240,0,112,184
    db 72,3,9,48,33,251,24,130,127,80,101,146,34,129,16,82
    db 127,96,130,253,33,0,145,33,110,176,33,5,18,120,90,240
    db 0,240,0,240,187,16,0,8,190,65,167,43,16,11,127,80
    db 227,17,0,127,48,105,124,127,0,136,33,101,153,153,153,149
    db 128,48,21,146,127,192,43,144,20,139,2,241,0,240,114,244
    db 87,1,17,27,131,115,178,127,80,101,2,35,26,127,160,89
    db 33,0,41,85,0,16,127,224,131,1,65,129,189,19,0,240
    db 0,240,240,212,202,66,38,114,16,19,0,8,127,80,118,1
    db 32,127,112,118,32,53,96,137,41,127,240,74,48,27,97,240
    db 0,240,180,144,17,182,180,96,85,86,115,17,34,136,255,96
    db 85,10,244,20,149,118,0,82,127,224,240,17,107,241,74,17
    db 113,24,143,245,0,240,48,112,177,0,11,75,56,243,153,153
    db 105,36,116,2,128,130,41,102,93,102,100,33,34,43,24,127
    db 192,43,122,120,224,127,224,25,16,74,130,0,240,0,240,34
    db 128,0,148,175,80,215,66,105,18,0,11,116,1,127,32,146
    db 76,102,6,127,176,32,0,46,97,127,208,43,74,32,0,68
    db 85,0,240,0,240,236,1,180,83,92,99,127,48,125,32,35
    db 85,85,110,18,127,240,244,70,177,127,227,187,104,136,153,241
    db 0,240,251,49,8,110,8,99,16,215,115,82,193,43,127,112
    db 120,0,127,208,118,54,122,24,16,178,138,193,196,2,138,100
    db 17,6,243,0,240,251,33,178,31,34,177,11,34,153,90,116
    db 107,0,127,144,237,89,127,32,90,162,127,0,43,170,170,131
    db 170,172,127,80,129,26,37,24,130,133,251,19,153,5,146,28
    db 32,0,3,242,0,240,108,21,176,17,199,6,248,123,96,242
    db 2,127,160,83,57,34,34,147,111,51,51,140,194,127,0,44
    db 204,0,0,24,16,120,58,18,238,147,176,8,148,19,157,55
    db 3,242,132,0,240,251,97,136,54,0,110,84,117,18,127,144
    db 172,7,204,194,34,118,16,127,160,14,16,142,122,129,80,32
    db 157,25,33,22,198,88,155,250,0,192,33,163,48,225,3,5
    db 150,108,68,34,118,32,127,96,111,16,107,0,127,240,36,23
    db 48,16,41,32,127,89,44,25,85,52,68,141,33,67,1,24
    db 114,240,114,166,121,3,127,32,130,214,136,61,37,242,33,176
    db 11,34,172,108,32,127,240,10,127,112,204,144,73,176,44,58
    db 127,0,30,88,4,34,16,136,4,140,246,123,146,112,7,24
    db 73,20,197,3,125,18,145,146,127,96,227,34,108,48,44,127
    db 240,127,144,27,252,53,57,59,7,187,34,40,27,34,149,140
    db 155,120,95,0,8,16,152,250,114,182,65,3,1,136,127,16
    db 108,37,16,34,178,127,64,212,1,127,96,204,156,127,240,127
    db 80,178,37,89,76,32,46,12,130,250,198,0,149,27,136,34
    db 177,2,177,16,169,8,119,240,236,120,11,169,51,8,127,48
    db 101,12,12,32,127,16,89,204,127,112,128,96,127,240,255,17
    db 84,46,32,78,48,130,59,16,86,29,153,8,96,82,152,0
    db 240,58,19,67,85,1,128,127,16,244,0,40,35,129,1,80
    db 16,99,32,127,96,34,127,240,212,16,158,151,33,34,128,178
    db 44,27,4,237,33,40,105,130,59,49,120,0,86,130,65,1
    db 178,101,0,220,148,250,124,33,184,0,8,56,68,43,128,169
    db 0,127,0,244,49,139,236,12,156,99,16,40,201,16,127,96
    db 105,16,202,120,4,127,0,42,170,248,7,16,255,51,146,48
    db 178,44,200,136,131,174,1,33,40,27,8,59,50,146,133,65
    db 105,166,86,20,187,176,134,244,121,67,27,112,38,98,54,110
    db 40,37,101,127,16,33,11,195,18,217,48,254,127,176,167,119
    db 119,119,114,16,130,21,39,6,0,119,127,48,42,127,80,156
    db 0,157,37,202,42,28,37,159,71,85,29,73,251,0,33,16
    db 25,0,125,240,120,20,18,34,116,52,110,40,225,69,144,127
    db 240,27,19,116,16,127,16,40,127,80,240,19,39,157,119,127
    db 96,204,204,200,245,0,127,16,85,10,31,88,86,127,48,8
    db 231,33,166,255,242,0,26,16,217,149,167,65,127,96,1,178
    db 127,112,1,34,66,246,16,178,97,23,127,192,40,27,10,32
    db 114,16,29,82,160,66,162,125,36,174,54,34,6,53,89,87
    db 5,108,255,16,5,244,187,16,116,6,34,153,109,87,253,176
    db 127,48,89,34,177,130,43,129,5,178,127,64,0,108,6,98
    db 0,67,17,127,208,127,24,72,127,112,139,66,127,16,136,127
    db 32,82,20,41,89,33,159,129,178,34,32,139,142,8,139,215
    db 0,71,17,130,34,242,85,69,27,57,50,92,195,2,220,195
    db 21,111,18,34,129,0,118,32,114,33,37,1,127,208,114,66
    db 32,127,64,130,127,80,185,49,65,133,127,16,244,35,127,48
    db 200,27,74,0,11,244,214,83,139,34,95,90,119,19,33,186
    db 33,60,195,0,78,127,96,114,43,0,98,48,27,16,39,127
    db 160,105,119,127,144,95,68,44,127,64,204,197,127,0,25,32
    db 133,24,127,32,128,18,70,0,103,21,5,164,39,17,16,2
    db 237,120,48,34,128,127,0,67,65,18,127,16,202,90,0,127
    db 112,1,129,66,127,96,0,96,72,127,0,246,126,187,0,44
    db 39,52,10,3,34,137,20,150,127,16,129,18,151,56,18,38
    db 157,81,0,41,166,123,50,149,101,176,35,127,0,136,127,64
    db 43,239,2,34,170,167,127,144,1,176,139,52,0,49,127,0
    db 34,127,240,0,136,246,78,107,1,232,167,68,32,2,207,17
    db 86,127,17,128,18,34,181,153,232,6,0,135,133,128,8,125
    db 81,101,155,89,34,224,56,177,2,231,54,135,25,11,166,247
    db 49,43,128,127,64,255,29,43,127,80,39,230,127,192,8,136
    db 103,8,91,48,1,178,44,145,204,128,96,79,34,127,16,129
    db 71,11,129,17,1,138,169,143,2,233,90,105,109,87,236,0
    db 90,53,177,56,129,22,229,67,108,48,33,8,33,127,96,138
    db 98,78,0,64,34,34,2,2,57,95,18,11,170,118,200,31
    db 93,27,0,89,40,82,113,2,1,98,17,1,228,117,16,35
    db 87,37,110,72,127,64,176,17,17,16,110,66,127,80,195,3
    db 67,1,39,127,80,0,161,240,40,164,242,44,187,13,2,40
    db 86,71,16,41,87,49,128,242,59,62,101,155,56,123,67,139
    db 34,41,150,25,102,110,104,39,0,156,194,127,112,65,26,127
    db 64,45,130,127,80,40,8,57,81,130,249,82,254,64,86,127
    db 48,34,187,223,1,136,55,2,172,171,103,85,41,8,54,128
    db 50,79,146,127,144,178,108,57,75,105,146,127,64,51,199,54
    db 127,32,40,205,26,104,127,64,8,50,127,0,43,193,69,40
    db 24,199,51,216,253,97,115,18,194,54,136,129,155,0,119,122
    db 66,128,96,202,136,53,217,38,234,32,127,144,37,161,104,149
    db 32,119,3,83,210,135,114,95,112,127,64,114,250,127,144,130
    db 200,148,39,114,34,33,1,68,84,131,55,16,124,171,74,7
    db 20,87,36,0,102,68,87,146,40,17,127,192,105,46,76,92
    db 177,34,18,127,32,202,218,36,220,80,32,180,68,188,5,10
    db 64,80,225,40,70,165,127,160,54,33,162,47,88,195,136,4
    db 2,187,20,86,12,57,127,144,127,33,157,1,227,23,90,75
    db 138,127,16,199,62,0,178,220,81,127,3,127,128,1,157,136
    db 0,16,0,24,128,103,10,209,121,40,213,11,122,140,18,182
    db 65,34,144,86,200,82,171,34,129,104,4,85,127,48,129,54
    db 96,129,138,236,42,101,158,0,176,129,24,47,51,129,6,42
    db 120,227,39,127,112,180,85,129,187,187,176,240,77,170,0,32
    db 11,247,28,187,84,24,128,92,138,184,74,155,68,34,128,112
    db 146,157,21,136,2,86,127,18,20,136,122,9,2,149,127,16
    db 85,188,42,118,50,65,3,9,18,90,180,38,0,11,97,140
    db 0,0,171,10,174,26,80,14,80,82,147,202,17,27,150,34
    db 5,68,0,185,47,237,86,217,26,1,178,127,128,34,102,101
    db 176,39,72,174,67,127,208,80,16,18,27,195,44,0,96,112
    db 112,142,160,0,0,127,240,56,0,128,18,127,96,213,176,234
    db 1,149,17,58,32,10,141,177,130,116,99,45,40,24,44,168
    db 64,177,2,40,127,128,46,5,35,24,34,17,91,21,0,73
    db 255,80,54,105,0,250,37,85,97,27,254,65,40,16,221,21
    db 74,127,96,41,65,79,176,127,128,11,0,149,127,144,222,201
    db 17,2,43,27,34,127,160,43,24,61,187,97,16,8,136,187
    db 136,195,252,113,4,178,142,2,129,12,50,127,176,32,1,183
    db 2,42,165,172,76,38,128,144,74,157,10,128,195,128,177,42
    db 39,74,82,125,81,34,167,55,39,253,128,227,41,128,158,12
    db 195,255,71,135,14,2,29,97,190,48,181,3,24,48,74,3
    db 7,4,203,20,125,3,41,85,155,74,182,163,114,227,60,88
    db 126,96,97,22,0,34,34,125,176,17,0,59,253,197,251,25
    db 98,27,54,37,144,25,127,16,147,119,122,127,64,27,91,1
    db 127,176,128,17,92,20,126,96,48,41,32,65,32,114,216,48
    db 222,1,56,253,228,0,240,170,64,17,181,39,62,48,0,187
    db 16,38,67,36,172,194,232,38,8,37,34,253,131,128,33,133
    db 139,127,16,140,171,87,138,12,50,2,212,27,43,140,212,48
    db 245,2,1,187,116,242,0,240,45,32,187,214,95,10,139,187
    db 204,92,11,200,65,122,162,80,29,37,154,43,254,7,127,160
    db 40,23,18,88,43,104,215,33,1,129,64,37,18,152,109,1
    db 136,193,27,104,240,0,240,0,80,253,30,172,65,43,2,99
    db 43,8,45,73,253,19,223,18,53,89,148,2,8,205,160,41
    db 44,125,97,176,106,65,167,76,242,19,123,241,64,0,240,142
    db 227,91,67,202,9,27,72,230,1,44,135,53,237,32,206,192
    db 176,2,170,121,40,16,2,140,75,82,148,27,17,0,177,254
    db 0,240,0,240,16,224,5,34,200,3,202,3,127,96,94,52
    db 194,43,16,104,204,193,35,1,170,106,129,27,97,187,16,93
    db 6,192,249,1,47,254,0,240,16,244,55,1,40,4,129,178
    db 149,129,194,54,114,253,19,124,93,85,253,237,178,2,127,80
    db 176,28,141,80,20,43,253,0,240,0,240,71,17,74,44,5
    db 130,44,7,136,172,91,228,1,122,100,48,67,40,24,127,240
    db 127,64,140,58,23,98,0,14,144,96,0,240,0,240,213,188
    db 57,18,127,144,119,172,202,61,6,72,228,33,24,0,34,82
    db 58,69,146,114,244,0,240,154,0,240,34,155,118,8,24,136
    db 68,191,14,39,70,134,20,204,34,127,240,240,20,0,1,199
    db 38,0,130,195,119,43,69,3,250,241,0,240,0,240,4,114
    db 177,7,0,1,8,136,84,127,16,0,17,126,241,93,22,2
    db 127,16,167,38,0,152,102,133,4,251,241,0,240,0,240,166
    db 4,162,129,0,136,36,190,24,24,136,17,122,240,91,25,255
    db 255,165,23,229,29,119,34,33,2,66,71,101,1,116,244,0
    db 240,0,240,0,176,17,198,68,147,32,0,16,56,135,5,32
    db 87,240,127,16,199,132,47,56,191,70,128,251,241,0,240,0
    db 240,0,240,128,12,189,52,127,80,122,194,125,243,1,52,37
    db 85,127,32,0,60,3,240,245,0,240,0,240,89,240,198,49
    db 61,76,225,0,49,177,254,240,129,19,127,80,129,178,18,63
    db 251,241,144,0,240,0,240,0,240,202,16,187,209,47,77,72
    db 128,216,67,248,107,19,166,68,34,40,127,16,128,1,0,163
    db 242,0,240,0,240,0,240,198,20,136,4,253,35,224,49,5
    db 129,215,241,34,110,39,39,68,127,0,118,244,0,240,136,0
    db 240,0,240,18,120,0,127,96,253,242,127,208,40,1,17,240
    db 246,0,240,0,240,0,240,72,197,70,173,1,228,28,128,33
    db 127,17,177,0,8,123,242,0,240,0,240,16,0,240,136,100
    db 127,32,7,37,176,126,241,129,83,158,33,0,84,14,101,250
    db 0,240,0,240,0,240,3,146,61,45,70,45,4,28,240,127
    db 112,114,43,33,253,240,0,240,0,240,0,240,2,129,177,130
    db 0,17,123,247,128,97,159,5,8,35,110,248,32,0,240,0
    db 240,0,240,224,211,85,49,177,91,241,39,84,1,34,123,106
    db 0,240,0,240,0,240,0,240,228,170,212,50,0,253,243,128
    db 97,120,68,125,241,0,240,0,240,0,240,223,208,17,16,208
    db 37,253,243,129,99,11,242,39,249,243,0,240,144,0,240,0
    db 240,142,248,0,17,33,217,243,127,128,43,1,17,116,246,0
    db 240,0,240,0,240,0,240,91,17,174,15,0,127,240,1,116
    db 65,14,30,240,0,240,0,240,0,240,0,240,24,5,52,223
    db 240,41,151,0,24,30,240,0,240,0,240,96,0,240,0,240
    db 152,60,213,246,35,132,17,17,126,240,0,0,240,0,240,0
    db 240,0,240,0,240,0,16
LOGOFIM:

PALT:
    db  87,  7
    db  86,  6
    db   2,  0
    db  54,  6
    db 119,  7
    db  23,  6
    db   7,  7
    db 113,  4
    db  69,  5
    db  37,  4
    db 101,  2
    db  52,  3
    db 102,  1
    db   0,  0
    db   0,  0
    db   0,  0


FONT:
; 0
    db 00111000b
    db 01000100b
    db 01001100b
    db 01010100b
    db 01100100b
    db 01000100b
    db 00111000b
    db 00000000b
; 1
    db 00010000b
    db 00110000b
    db 00010000b
    db 00010000b
    db 00010000b
    db 00010000b
    db 00111000b
    db 00000000b
; 2
    db 00111000b
    db 01000100b
    db 00000100b
    db 00001000b
    db 00010000b
    db 00100000b
    db 01111100b
    db 00000000b
; 3
    db 01111100b
    db 00001000b
    db 00010000b
    db 00001000b
    db 00000100b
    db 01000100b
    db 00111000b
    db 00000000b
; 4
    db 00001000b
    db 00011000b
    db 00101000b
    db 01001000b
    db 01111100b
    db 00001000b
    db 00001000b
    db 00000000b
; 5
    db 01111100b
    db 01000000b
    db 01111000b
    db 00000100b
    db 00000100b
    db 01000100b
    db 00111000b
    db 00000000b
; 6
    db 00011000b
    db 00100000b
    db 01000000b
    db 01111000b
    db 01000100b
    db 01000100b
    db 00111000b
    db 00000000b
; 7
    db 01111100b
    db 00000100b
    db 00001000b
    db 00010000b
    db 00100000b
    db 00100000b
    db 00100000b
    db 00000000b
; 8
    db 00111000b
    db 01000100b
    db 01000100b
    db 00111000b
    db 01000100b
    db 01000100b
    db 00111000b
    db 00000000b
; 9
    db 00111000b
    db 01000100b
    db 01000100b
    db 00111100b
    db 00000100b
    db 00001000b
    db 00110000b
    db 00000000b
; A
    db 00111000b
    db 01000100b
    db 01000100b
    db 01111100b
    db 01000100b
    db 01000100b
    db 01000100b
    db 00000000b
; B
    db 01111000b
    db 01000100b
    db 01000100b
    db 01111000b
    db 01000100b
    db 01000100b
    db 01111000b
    db 00000000b
; C
    db 00111000b
    db 01000100b
    db 01000000b
    db 01000000b
    db 01000000b
    db 01000100b
    db 00111000b
    db 00000000b
; D
    db 01111000b
    db 01000100b
    db 01000100b
    db 01000100b
    db 01000100b
    db 01000100b
    db 01111000b
    db 00000000b
; E
    db 01111100b
    db 01000000b
    db 01000000b
    db 01111000b
    db 01000000b
    db 01000000b
    db 01111100b
    db 00000000b
; F
    db 01111100b
    db 01000000b
    db 01000000b
    db 01111000b
    db 01000000b
    db 01000000b
    db 01000000b
    db 00000000b
; G
    db 00111000b
    db 01000100b
    db 01000000b
    db 01011100b
    db 01000100b
    db 01000100b
    db 00111100b
    db 00000000b
; H
    db 01000100b
    db 01000100b
    db 01000100b
    db 01111100b
    db 01000100b
    db 01000100b
    db 01000100b
    db 00000000b
; I
    db 00111000b
    db 00010000b
    db 00010000b
    db 00010000b
    db 00010000b
    db 00010000b
    db 00111000b
    db 00000000b
; J
    db 00011100b
    db 00001000b
    db 00001000b
    db 00001000b
    db 00001000b
    db 01001000b
    db 00110000b
    db 00000000b
; K
    db 01000100b
    db 01001000b
    db 01010000b
    db 01100000b
    db 01010000b
    db 01001000b
    db 01000100b
    db 00000000b
; L
    db 01000000b
    db 01000000b
    db 01000000b
    db 01000000b
    db 01000000b
    db 01000000b
    db 01111100b
    db 00000000b
; M
    db 01000100b
    db 01101100b
    db 01010100b
    db 01010100b
    db 01000100b
    db 01000100b
    db 01000100b
    db 00000000b
; N
    db 01000100b
    db 01100100b
    db 01010100b
    db 01001100b
    db 01000100b
    db 01000100b
    db 01000100b
    db 00000000b
; O
    db 00111000b
    db 01000100b
    db 01000100b
    db 01000100b
    db 01000100b
    db 01000100b
    db 00111000b
    db 00000000b
; P
    db 01111000b
    db 01000100b
    db 01000100b
    db 01111000b
    db 01000000b
    db 01000000b
    db 01000000b
    db 00000000b
; Q
    db 00111000b
    db 01000100b
    db 01000100b
    db 01000100b
    db 01010100b
    db 01001000b
    db 00110100b
    db 00000000b
; R
    db 01111000b
    db 01000100b
    db 01000100b
    db 01111000b
    db 01010000b
    db 01001000b
    db 01000100b
    db 00000000b
; S
    db 00111100b
    db 01000000b
    db 01000000b
    db 00111000b
    db 00000100b
    db 00000100b
    db 01111000b
    db 00000000b
; T
    db 01111100b
    db 00010000b
    db 00010000b
    db 00010000b
    db 00010000b
    db 00010000b
    db 00010000b
    db 00000000b
; U
    db 01000100b
    db 01000100b
    db 01000100b
    db 01000100b
    db 01000100b
    db 01000100b
    db 00111000b
    db 00000000b
; V
    db 01000100b
    db 01000100b
    db 01000100b
    db 01000100b
    db 01000100b
    db 00101000b
    db 00010000b
    db 00000000b
; W
    db 01000100b
    db 01000100b
    db 01000100b
    db 01010100b
    db 01010100b
    db 01101100b
    db 01000100b
    db 00000000b
; X
    db 01000100b
    db 01000100b
    db 00101000b
    db 00010000b
    db 00101000b
    db 01000100b
    db 01000100b
    db 00000000b
; Y
    db 01000100b
    db 01000100b
    db 00101000b
    db 00010000b
    db 00010000b
    db 00010000b
    db 00010000b
    db 00000000b
; Z
    db 01111100b
    db 00000100b
    db 00001000b
    db 00010000b
    db 00100000b
    db 01000000b
    db 01111100b
    db 00000000b
; :
    db 00000000b
    db 00010000b
    db 00010000b
    db 00000000b
    db 00010000b
    db 00010000b
    db 00000000b
    db 00000000b
; >
    db 01000000b
    db 01100000b
    db 01110000b
    db 01111000b
    db 01110000b
    db 01100000b
    db 01000000b
    db 00000000b

PSGTAB:
    dw  3420          ; nota 24
    dw  3229          ; nota 25
    dw  3047          ; nota 26
    dw  2876          ; nota 27
    dw  2715          ; nota 28
    dw  2562          ; nota 29
    dw  2419          ; nota 30
    dw  2283          ; nota 31
    dw  2155          ; nota 32
    dw  2034          ; nota 33
    dw  1920          ; nota 34
    dw  1812          ; nota 35
    dw  1710          ; nota 36
    dw  1614          ; nota 37
    dw  1524          ; nota 38
    dw  1438          ; nota 39
    dw  1357          ; nota 40
    dw  1281          ; nota 41
    dw  1209          ; nota 42
    dw  1141          ; nota 43
    dw  1077          ; nota 44
    dw  1017          ; nota 45
    dw   960          ; nota 46
    dw   906          ; nota 47
    dw   855          ; nota 48
    dw   807          ; nota 49
    dw   762          ; nota 50
    dw   719          ; nota 51
    dw   679          ; nota 52
    dw   641          ; nota 53
    dw   605          ; nota 54
    dw   571          ; nota 55
    dw   539          ; nota 56
    dw   508          ; nota 57
    dw   480          ; nota 58
    dw   453          ; nota 59
    dw   428          ; nota 60
    dw   404          ; nota 61
    dw   381          ; nota 62
    dw   360          ; nota 63
    dw   339          ; nota 64
    dw   320          ; nota 65
    dw   302          ; nota 66
    dw   285          ; nota 67
    dw   269          ; nota 68
    dw   254          ; nota 69
    dw   240          ; nota 70
    dw   226          ; nota 71
    dw   214          ; nota 72
    dw   202          ; nota 73
    dw   190          ; nota 74
    dw   180          ; nota 75
    dw   170          ; nota 76
    dw   160          ; nota 77
    dw   151          ; nota 78
    dw   143          ; nota 79
    dw   135          ; nota 80
    dw   127          ; nota 81
    dw   120          ; nota 82
    dw   113          ; nota 83
    dw   107          ; nota 84
    dw   101          ; nota 85
    dw    95          ; nota 86
    dw    90          ; nota 87
    dw    85          ; nota 88
    dw    80          ; nota 89
    dw    76          ; nota 90
    dw    71          ; nota 91
    dw    67          ; nota 92
    dw    64          ; nota 93
    dw    60          ; nota 94
    dw    57          ; nota 95
    dw    53          ; nota 96
    dw    50          ; nota 97
    dw    48          ; nota 98
    dw    45          ; nota 99
    dw    42          ; nota 100
    dw    40          ; nota 101
    dw    38          ; nota 102
    dw    36          ; nota 103
    dw    34          ; nota 104
    dw    32          ; nota 105
    dw    30          ; nota 106
    dw    28          ; nota 107

FMDESL equ 5
FBASE:
    db   2, 18, 34, 51, 70, 89,109,131,154,179,204,232

SONGS:
    dw SNGT
    dw SNGG

SNGT:
    dw TV0
    dw TV1
    dw TV2
    dw TV3
    dw TV4
    dw TV5

SNGG:
    dw GV0
    dw GV1
    dw GV2
    dw GV3
    dw GV4
    dw GV5

MDICT:
    db   0,  9
    db   0,  1
    db   0, 10
    db   0, 16
    db   0,  8
    db   0,255
    db  65,  7
    db  60,  6
    db  55,  7
    db  63,  7
    db  67,  7
    db  60,  7
    db   0,  7
    db  67,  1
    db  55,  6
    db  42,  1
    db  47,  1
    db  44,  1
    db  35,  1
    db  36,  7
    db  40,  1
    db  69,  7
    db   0,  2
    db  65,  1
    db  67,  6
    db  77,  7
    db  63,  1
    db  45,  1
    db  42, 10
    db  65,  6
    db  79,  7
    db   0, 14
    db  36,  1
    db  44, 10
    db   0, 31
    db  39,  1
    db  75,  6
    db  35, 11
    db  60,  8
    db  67,  8
    db  65,  8
    db  68,  7
    db   0, 21
    db  72,  7
    db  63,  6
    db  67,  5
    db  60,  5
    db  82,  8
    db  70,  7
    db  45, 10
    db  82,  7
    db  35, 12
    db  84,  8
    db  35, 10
    db   0, 15
    db  71, 10
    db  64, 10
    db  68,  1
    db   0,  6
    db  39, 12
    db  62,  1
    db  75, 11
    db  73, 10
    db  40, 11
    db  47, 10
    db  74,  6
    db  36,  6
    db  80,  7
    db  60,  1
    db  37,  1
    db  86,  6
    db  69,  9
    db  86,  8
    db  65, 14
    db  82,  6
    db  69,  6
    db  82,  1
    db  55,  5
    db  75,  5
    db   0, 32
    db  84,  7
    db  79,  8
    db  84,  1
    db  39, 11
    db  68,  8
    db  65,  9
    db  80,  1
    db  47,  9
    db  77,  8
    db  36,  5
    db  79,  1
    db  63, 10
    db  75, 14
    db  86,  7
    db  76, 11
    db  42, 11
    db  40, 10
    db   0, 11
    db  40, 12
    db   0, 20
    db  72,  6
    db  70,  5
    db  68, 10
    db  42, 12
    db  79,  6
    db  72,  5
    db  77, 22
    db  75,  7
    db   0, 17
    db  36, 14
    db   0, 23
    db   0, 29
    db  73, 11
    db  63, 21
    db  75, 10
    db  64,  1
    db  39, 10
    db  44, 11
    db  72,  1
    db  68,  6
    db  77,  1
    db  86,  1
    db  57,  1
    db  69, 11
    db  68,  5
    db  69, 15
    db  78,  7
    db  36,  9
    db  91,  9
    db  74,  7
    db  79,  5
    db  67,  2
    db  70,  6
    db  63,  2
    db  66,  7
    db  63,  5
    db   0, 24
    db  71, 11
    db  64, 22
    db  59, 22
    db  76, 10
    db  66, 22
    db  69, 10
    db  35,  9
    db  89,  8
    db  75, 22
    db  67, 21
    db  63, 14
    db  70,  8
    db   0, 30
    db  71, 22
    db  61, 10
    db  66, 10
    db  80,  8
    db  81,  7
    db  65,  5
    db  67, 14
    db  62, 14
    db  75,  1
    db  57, 14
    db  55,  8
    db   0,189
    db   0,190
    db  66, 11
    db  71,  1
    db  76,  5
    db  59, 10
    db  39,  9
    db  70,  1
    db  75,  8
    db  83,  8
    db  62,  8
    db  74,  1
    db  62,  6
    db  74,  8
    db  68, 11
    db  64, 11
    db  71,  5
    db  37,  9
    db  79, 29
    db  82, 22
    db  84, 21
    db  36,  8
    db  69,  8
    db  79, 30
    db  72, 21
    db  67, 23
    db  62,  7
    db   0, 39
    db   0, 25
    db  62, 30
    db  68, 22
    db  58,  1
    db  71, 75
    db  69, 87
    db  69, 22
    db  66, 21
    db  73,  1
    db  78, 33
    db  59, 21
    db  63, 22
    db  80, 10
    db  74, 10
    db  62, 10
    db  63, 11
    db  78, 22
    db  61, 22
    db  64, 21
    db  68, 43
    db  66, 44
    db  69, 43
    db  69, 21
    db  44, 12
    db  40, 13
    db  45, 11
    db  44,  9
    db  75, 23
    db  89,  9
    db  83,  7
    db  71,  7
    db   0, 59
    db  77,  6
    db  67,  9
    db  60, 22
    db  58,  7
    db  81,  1
    db  60, 21
    db  67, 29
    db  65, 22
    db   0, 53
    db  41,  6
    db  63, 46
    db  62, 45
    db  56, 30
    db  58, 45
    db  60, 45
    db  58, 46
    db   0, 54
    db  37, 11
    db  37, 10
    db   0, 42
    db  81, 13
    db  72,  8
    db  77, 16
    db  75, 15
    db  79, 23
    db  77, 45
    db  89, 10
    db  91,  8
    db  86,  9
    db  87,  8
    db  84,  9
    db  81,  8
    db  81, 14

TV0:
    db 11,32,4,10,38,12,39,7,0,10,7,0,21,7,0,125
    db 11,32,4,10,38,12,39,7,0,48,8,1,21,9,39,21
    db 43,88,11,32,4,10,38,12,39,7,0,10,7,0,21,7
    db 0,125,11,32,4,10,38,12,39,7,0,48,8,1,21,9
    db 39,21,43,88,11,0,70,13,38,12,47,7,0,104,13,7
    db 22,105,22,21,65,0,36,71,25,0,36,57,40,25,92,1
    db 106,1,179,126,88,11,0,70,13,38,12,47,7,0,104,13
    db 7,22,105,22,21,65,0,36,71,6,22,25,92,23,30,107
    db 57,29,1,180,1,241,1,50,168,181,118,11,0,70,13,38
    db 12,47,7,0,104,13,7,22,105,22,21,65,0,36,71,25
    db 0,36,57,40,25,92,1,106,1,179,126,88,11,0,70,13
    db 38,12,47,7,0,104,13,7,22,105,22,21,65,0,36,71
    db 3,43,84,12,242,12,216,254,74,5,0,169,106,11,127,10
    db 38,66,1,39,7,1,182,10,7,22,89,22,21,7,22,19
    db 125,11,127,10,38,32,58,39,7,1,182,48,8,32,21,9
    db 39,21,43,88,11,127,10,38,66,1,39,7,1,182,10,7
    db 22,89,22,21,7,22,19,125,11,127,10,38,32,58,39,7
    db 1,182,48,8,32,21,9,39,21,43,88,11,0,70,13,38
    db 12,47,7,0,104,13,7,22,105,22,21,65,0,36,71,25
    db 0,36,57,40,25,92,1,106,1,179,126,88,11,0,70,13
    db 38,12,47,7,0,104,13,7,22,105,22,21,65,0,36,71
    db 6,22,25,92,23,30,107,57,29,1,180,1,241,1,50,168
    db 181,118,11,0,70,13,38,12,47,7,0,104,13,7,22,105
    db 22,21,65,0,36,71,25,0,36,57,40,25,92,1,106,1
    db 179,126,88,11,0,70,13,38,12,47,7,0,104,13,7,22
    db 105,22,21,65,0,36,71,243,244,25,169,12,245,246,247,80
    db 67,52,67,25,153,80,144,52,254,80,6,52,153,25,67,52
    db 128,93,50,72,50,30,47,93,248,72,50,72,50,30,50,249
    db 52,81,107,81,107,43,107,52,81,107,30,52,250,80,25,47
    db 251,154,25,252,88,43,25,80,144,144,80,154,52,154,88,43
    db 217,80,67,52,153,25,67,80,217,80,67,52,67,25,67,52
    db 128,93,50,72,47,30,50,93,128,93,50,72,50,30,50,72
    db 128,93,218,72,170,30,218,72,170,30,129,81,10,219,129,81
    db 254,79,9,30,30,54,47,12,47,220,11,32,4,10,38,12
    db 39,46,2,10,7,0,21,7,0,125,11,32,4,10,38,12
    db 39,46,2,48,8,183,9,39,21,43,25,1,11,32,4,10
    db 38,12,39,46,2,10,7,0,21,7,0,125,11,32,4,10
    db 38,12,39,46,2,48,8,183,9,39,21,43,25,1,11,0
    db 70,13,38,12,47,46,2,130,131,7,1,100,22,21,65,0
    db 36,71,25,0,36,57,40,25,92,1,106,184,126,25,57,11
    db 0,70,13,38,12,47,46,2,130,131,7,1,100,22,21,65
    db 0,36,71,6,22,221,1,92,23,30,107,57,155,22,180,253
    db 1,50,168,181,118,11,0,70,13,38,12,47,46,2,130,131
    db 7,1,100,22,21,65,0,36,71,25,0,36,57,40,25,92
    db 1,106,184,126,25,57,11,0,70,13,38,12,47,46,2,130
    db 131,7,1,100,22,21,65,0,36,71,3,43,84,12,242,12
    db 145,65,0,169,106,11,127,10,38,66,1,39,46,22,19,1
    db 10,7,1,66,22,21,7,22,19,125,11,127,10,38,32,58
    db 39,46,22,19,1,48,8,183,9,39,21,43,25,32,11,127
    db 10,38,66,1,39,46,22,19,1,10,7,1,66,22,21,7
    db 22,19,125,11,127,10,38,32,58,39,46,22,19,1,48,8
    db 183,9,39,21,43,25,32,11,0,70,13,38,12,47,46,2
    db 130,131,7,1,100,22,21,65,0,36,71,25,0,36,57,40
    db 25,92,1,106,184,126,25,57,11,0,70,13,38,12,47,46
    db 2,130,131,7,1,100,22,21,65,0,36,71,6,22,221,1
    db 92,23,30,107,57,155,22,180,253,1,50,168,181,118,11,0
    db 70,13,38,12,47,46,2,130,131,7,1,100,22,21,65,0
    db 36,71,25,0,36,57,40,25,92,1,106,184,126,25,57,11
    db 0,70,13,38,12,47,46,2,130,131,7,1,100,22,21,65
    db 0,36,71,243,244,25,169,12,245,246,247,80,67,52,67,25
    db 67,52,144,80,67,52,153,25,67,52,128,93,50,72,50,30
    db 50,72,248,93,50,72,47,30,50,249,52,81,36,81,169,43
    db 107,52,81,107,30,52,250,80,25,47,251,154,25,252,88,100
    db 88,80,144,144,80,154,52,154,88,43,217,80,67,52,153,221
    db 153,80,144,52,67,52,67,25,67,52,128,93,50,72,47,104
    db 47,93,128,93,50,72,50,30,50,72,128,93,218,72,170,104
    db 170,72,170,30,129,81,10,219,129,81,81,81,30,54,50,90
    db 12,47,255

TV1:
    db 8,0,9,8,4,9,1,14,0,9,14,0,6,14,0,73
    db 1,8,0,9,8,4,9,1,14,0,10,4,29,4,40,6
    db 54,8,0,9,8,4,9,1,14,0,9,14,0,6,14,0
    db 73,1,8,0,9,8,4,9,1,14,0,10,4,29,4,40
    db 6,254,43,6,0,8,0,74,26,8,4,30,13,14,0,36
    db 26,14,0,6,7,0,75,85,6,0,119,23,11,4,84,29
    db 0,132,0,48,43,4,48,21,84,8,0,74,26,8,4,30
    db 13,14,0,36,26,14,0,6,7,0,75,85,11,0,41,6
    db 4,41,23,7,0,132,0,105,0,48,13,185,1,8,0,74
    db 26,8,4,30,13,14,0,36,26,14,0,6,7,0,75,85
    db 6,0,119,23,11,4,84,29,0,132,0,48,43,4,48,21
    db 84,8,0,74,26,8,4,30,13,14,0,36,26,14,0,6
    db 7,0,75,40,108,41,6,4,41,4,254,72,22,1,101,0
    db 43,1,254,74,21,1,8,0,9,8,32,12,9,1,14,0
    db 9,14,0,6,14,0,73,32,8,0,9,8,32,12,9,32
    db 14,0,10,19,1,29,4,40,6,254,36,15,8,0,9,8
    db 32,12,9,1,14,0,9,14,0,6,14,0,73,32,8,0
    db 9,8,32,12,9,32,14,0,10,19,1,29,4,40,6,254
    db 36,15,8,0,74,26,8,4,30,13,14,0,36,26,14,0
    db 6,7,0,75,85,6,0,119,23,11,4,84,29,0,132,0
    db 48,43,4,48,21,84,8,0,74,26,8,4,30,13,14,0
    db 36,26,14,0,6,7,0,75,85,11,0,41,6,4,41,23
    db 7,0,132,0,105,0,48,13,185,1,8,0,74,26,8,4
    db 30,13,14,0,36,26,14,0,6,7,0,75,85,6,0,119
    db 23,11,4,84,29,0,132,0,48,43,4,48,21,84,8,0
    db 74,26,8,4,30,13,14,0,36,26,14,0,6,7,0,75
    db 85,254,72,16,254,72,15,43,43,57,12,145,57,254,74,45
    db 222,82,146,86,156,120,73,82,73,86,29,86,6,11,120,223
    db 171,121,254,62,21,76,157,90,147,121,147,76,147,76,73,90
    db 29,76,6,82,254,62,15,158,157,158,157,11,158,254,60,29
    db 90,11,224,82,254,58,14,120,224,254,57,23,120,159,118,254
    db 57,21,82,159,82,159,225,31,9,118,6,186,86,156,120,10
    db 73,82,6,82,29,86,73,86,226,86,11,254,62,23,76,157
    db 90,187,147,121,9,121,44,76,147,76,254,65,21,76,6,186
    db 254,83,1,156,90,227,90,24,172,254,67,15,146,172,10,254
    db 74,9,129,129,54,81,12,81,220,8,0,9,8,4,9,1
    db 77,2,9,14,0,6,14,0,73,1,8,0,9,8,4,9
    db 1,77,2,10,12,6,4,40,6,54,8,0,9,8,4,9
    db 1,77,2,9,14,0,6,14,0,73,1,8,0,9,8,4
    db 9,1,77,2,10,12,6,4,40,6,254,43,6,0,8,0
    db 74,26,8,4,30,13,77,2,78,133,14,0,6,7,0,75
    db 85,6,0,119,23,11,4,84,155,2,101,0,148,43,4,48
    db 21,41,1,8,0,74,26,8,4,30,13,77,2,78,133,14
    db 0,6,7,0,75,85,11,0,41,6,4,41,23,46,2,101
    db 0,100,0,48,13,185,1,8,0,74,26,8,4,30,13,77
    db 2,78,133,14,0,6,7,0,75,85,6,0,119,23,11,4
    db 84,155,2,101,0,148,43,4,48,21,41,1,8,0,74,26
    db 8,4,30,13,77,2,78,133,14,0,6,7,0,75,40,108
    db 41,6,4,41,4,254,72,22,132,0,43,1,254,74,21,1
    db 8,0,9,8,32,12,9,1,77,2,9,14,0,6,14,0
    db 73,32,8,0,9,8,32,12,9,32,77,2,10,19,6,4
    db 40,6,109,1,8,0,9,8,32,12,9,1,77,2,9,14
    db 0,6,14,0,73,32,8,0,9,8,32,12,9,32,77,2
    db 10,19,6,4,40,6,109,1,8,0,74,26,8,4,30,13
    db 77,2,78,133,14,0,6,7,0,75,85,6,0,119,23,11
    db 4,84,155,2,101,0,148,43,4,48,21,41,1,8,0,74
    db 26,8,4,30,13,77,2,78,133,14,0,6,7,0,75,85
    db 11,0,41,6,4,41,23,46,2,101,0,100,0,48,13,185
    db 1,8,0,74,26,8,4,30,13,77,2,78,133,14,0,6
    db 7,0,75,85,6,0,119,23,11,4,84,155,2,101,0,148
    db 43,4,48,21,41,1,8,0,74,26,8,4,30,13,77,2
    db 78,133,14,0,6,7,0,75,85,254,72,16,254,72,15,43
    db 43,57,12,145,57,254,74,45,222,82,24,86,156,86,156,120
    db 29,86,254,65,29,86,6,11,120,226,1,171,121,173,76,157
    db 76,157,90,44,76,254,63,29,76,9,228,76,6,82,254,62
    db 15,158,173,158,254,62,22,223,158,223,224,82,254,58,22,254
    db 57,8,225,254,57,29,118,254,57,6,118,159,82,159,82,159
    db 225,31,9,118,6,39,82,227,120,24,120,73,82,73,86,73
    db 86,226,86,11,171,121,254,62,29,90,173,90,147,121,9,121
    db 44,76,147,76,254,65,21,76,6,39,121,227,90,24,90,156
    db 254,83,1,10,90,24,172,254,67,15,146,172,10,174,174,129
    db 54,30,172,12,81,255

TV2:
    db 19,3,19,3,66,0,66,229,19,3,19,3,66,0,66,68
    db 4,7,4,9,110,19,3,19,3,66,0,66,229,19,3,19
    db 3,66,0,230,68,4,254,39,5,68,4,230,26,188,44,3
    db 9,3,44,110,14,0,29,0,11,0,29,3,40,7,0,24
    db 0,24,1,41,4,10,134,40,3,44,3,9,3,44,110,14
    db 0,29,189,6,11,4,6,3,24,0,45,0,10,1,146,108
    db 44,3,9,3,44,110,14,0,29,0,11,0,29,3,40,7
    db 0,24,0,24,1,41,4,10,134,40,3,44,3,9,3,44
    db 110,14,0,29,254,0,129,19,0,109,34,66,254,0,38,19
    db 19,1,19,0,109,4,19,3,19,4,89,68,4,9,1,19
    db 54,19,0,109,34,66,254,0,38,19,19,1,19,0,109,4
    db 19,3,19,4,89,68,4,9,1,19,34,44,3,9,3,44
    db 110,14,0,29,0,11,0,29,3,40,7,0,24,0,24,1
    db 41,4,10,134,40,3,44,3,9,3,44,110,14,0,29,189
    db 6,11,4,6,3,24,0,45,0,10,1,146,108,44,3,9
    db 3,44,110,14,0,29,0,11,0,29,3,40,7,0,24,0
    db 24,1,41,4,10,134,40,3,44,3,9,3,44,110,14,0
    db 29,0,254,60,15,23,6,11,23,12,6,4,228,1,45,2
    db 6,186,231,232,233,234,235,190,236,254,55,45,254,55,30,254
    db 53,90,54,11,187,1,231,254,62,44,233,236,254,60,44,190
    db 254,62,120,254,55,9,8,8,54,160,12,160,220,19,3,19
    db 3,89,2,89,237,19,3,19,3,89,2,89,254,60,2,12
    db 11,4,9,110,19,3,19,3,89,2,89,237,19,3,19,3
    db 89,2,254,41,5,254,60,2,12,254,39,6,68,4,230,26
    db 188,44,3,9,3,135,136,14,0,29,0,11,0,29,3,40
    db 46,2,45,0,10,1,41,4,10,134,6,108,44,3,9,3
    db 135,136,14,0,29,189,6,11,4,6,3,45,0,24,0,10
    db 1,146,108,44,3,9,3,135,136,14,0,29,0,11,0,29
    db 3,40,46,2,45,0,10,1,41,4,10,134,6,108,44,3
    db 9,3,135,136,14,0,29,254,0,129,19,0,109,34,89,188
    db 19,19,1,19,0,109,4,19,3,19,12,66,68,4,9,1
    db 19,54,19,0,109,34,89,188,19,19,1,19,0,109,4,19
    db 3,19,12,66,68,4,9,1,19,34,44,3,9,3,135,136
    db 14,0,29,0,11,0,29,3,40,46,2,45,0,10,1,41
    db 4,10,134,6,108,44,3,9,3,135,136,14,0,29,189,6
    db 11,4,6,3,45,0,24,0,10,1,146,108,44,3,9,3
    db 135,136,14,0,29,0,11,0,29,3,40,46,2,45,0,10
    db 1,41,4,10,134,6,108,44,3,9,3,135,136,14,0,29
    db 0,254,60,15,23,6,11,23,12,6,4,228,1,45,2,6
    db 186,231,232,254,56,29,1,234,235,190,236,254,55,45,254,55
    db 30,254,53,90,54,11,187,1,254,63,45,232,233,234,235,190
    db 254,62,120,160,160,8,54,160,12,160,255

TV3:
    db 254,0,181,7,254,0,234,7,0,46,0,44,254,0,40,24
    db 3,10,3,24,161,24,3,10,3,24,161,24,3,10,3,24
    db 161,24,3,10,3,24,5,254,0,99,11,4,46,254,0,220
    db 11,4,46,254,0,55,24,3,10,3,24,161,24,3,10,3
    db 24,161,24,3,10,3,24,161,24,3,10,3,24,229,254,65
    db 15,1,41,6,4,41,4,191,1,101,2,41,254,70,23,0
    db 13,42,13,31,23,31,23,31,23,58,23,31,68,149,60,42
    db 60,31,26,31,26,31,26,31,23,31,23,58,23,12,60,54
    db 60,31,60,42,68,111,68,31,192,31,192,149,122,31,122,42
    db 122,31,122,254,0,36,23,149,13,31,13,42,23,12,23,58
    db 23,31,68,42,68,149,60,31,60,42,26,12,26,58,26,31
    db 23,42,23,149,13,31,13,111,13,58,13,31,13,42,13,12
    db 254,71,9,219,254,71,6,13,54,174,12,174,254,0,240,46
    db 254,0,235,46,0,7,0,44,254,0,40,24,3,10,3,45
    db 162,24,3,10,3,45,162,24,3,10,3,45,162,24,3,10
    db 3,45,5,254,0,100,11,12,7,254,0,220,11,12,7,254
    db 0,55,24,3,10,3,45,162,24,3,10,3,45,162,24,3
    db 10,3,45,162,24,3,10,3,45,237,254,65,15,1,41,6
    db 4,41,4,191,1,101,2,41,254,70,23,0,13,58,13,31
    db 13,31,23,58,23,111,23,31,68,149,60,58,60,31,60,31
    db 26,58,26,111,26,111,23,12,60,54,60,58,60,254,0,44
    db 68,111,192,149,122,111,122,58,122,31,122,31,122,254,0,36
    db 23,54,13,111,13,58,23,31,23,31,23,31,68,42,68,54
    db 60,111,60,58,26,31,26,12,26,58,26,31,23,42,23,54
    db 13,111,13,58,13,31,13,12,13,58,13,31,13,42,13,12
    db 254,71,8,254,71,8,254,71,6,13,54,129,168,12,174,255

TV4:
    db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,254,0
    db 153,222,10,24,60,54,148,12,148,5,5,5,5,5,5,5
    db 5,5,5,5,5,5,5,254,0,212,39,39,24,60,54,48
    db 60,12,148,255

TV5:
    db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,254,0
    db 153,254,62,9,187,173,3,39,12,39,5,5,5,5,5,5
    db 5,5,5,5,5,5,5,5,254,0,212,171,171,173,3,10
    db 192,12,39,255

GV0:
    db 254,73,33,137,123,175,163,176,163,26,177,132,177,101,1,177
    db 101,150,238,83,138,139,254,68,21,138,112,20,193,164,254,76
    db 33,61,112,55,123,175,194,254,66,23,113,195,196,15,114,35
    db 254,73,43,94,114,197,140,197,198,94,61,62,137,254,70,11
    db 254,71,87,254,64,23,199,191,138,112,20,193,254,76,34,114
    db 112,137,123,175,194,141,200,195,196,61,35,254,73,75,35,198
    db 140,16,114,140,16,254,78,10,18,201,16,94,165,115,78,165
    db 164,78,165,78,164,140,115,55,112,202,115,61,35,166,254,61
    db 11,203,15,91,35,55,15,62,61,94,20,166,17,151,204,176
    db 55,17,62,18,61,205,145,150,254,81,21,254,80,17,254,81
    db 5,17,201,254,78,11,94,55,115,62,15,202,20,61,166,15
    db 151,18,203,15,91,35,55,62,18,114,15,94,254,59,11,151
    db 18,91,17,56,20,55,17,62,61,254,78,23,254,75,21,254
    db 81,22,254,78,21,254,83,12,124,45,17,124,45,18,124,45
    db 254,68,44,138,139,254,68,21,138,112,20,193,164,254,76,33
    db 61,112,55,123,175,194,254,66,23,113,195,196,15,114,35,254
    db 73,43,94,114,197,140,197,198,94,61,62,137,254,70,11,254
    db 71,87,254,64,23,199,191,138,112,20,193,254,76,34,114,112
    db 137,123,175,194,141,200,195,196,61,35,254,73,75,35,198,140
    db 16,114,140,16,254,78,10,18,201,16,94,165,115,78,165,164
    db 78,165,78,164,140,115,55,112,202,115,61,35,166,254,61,11
    db 203,15,91,35,55,15,62,61,94,20,166,17,151,204,176,55
    db 17,62,18,61,205,145,150,254,81,21,254,80,17,254,81,5
    db 17,201,254,78,11,94,55,115,62,15,202,20,61,166,15,151
    db 18,203,15,91,137,62,18,114,15,94,254,59,11,151,18,91
    db 17,56,20,55,17,62,61,254,78,23,254,75,21,254,81,22
    db 254,78,21,254,83,12,124,45,17,124,45,18,124,45,254,68
    db 44,255

GV1:
    db 254,69,33,102,1,152,1,56,1,91,254,46,1,151,1,204
    db 16,204,79,51,42,206,254,56,22,207,139,123,1,208,102,18
    db 142,69,55,35,254,68,33,56,16,152,20,56,91,18,56,16
    db 209,254,63,43,254,63,23,199,141,113,1,55,1,210,254,73
    db 21,69,62,35,254,75,33,62,16,91,15,56,163,254,67,10
    db 16,254,68,12,124,45,27,124,45,102,27,254,66,43,254,61
    db 23,254,56,21,138,139,123,1,208,102,18,142,69,55,254,68
    db 34,56,163,56,16,91,18,56,16,209,113,206,200,139,141,113
    db 137,1,210,152,32,102,69,142,1,150,211,1,55,142,1,102
    db 1,152,1,254,64,16,20,254,64,5,177,18,254,71,15,18
    db 56,20,176,2,56,20,115,116,1,95,53,28,1,15,167,1
    db 28,1,53,103,96,1,33,1,53,212,96,33,1,17,143,1
    db 117,145,150,141,113,254,76,17,78,1,62,61,207,254,44,2
    db 254,42,9,1,96,1,83,28,1,15,143,1,28,1,116,1
    db 95,143,1,28,1,63,212,143,1,33,1,17,254,40,9,1
    db 33,1,53,117,216,254,71,21,205,211,254,80,11,20,33,1
    db 53,1,117,63,53,238,83,206,254,56,22,207,139,123,1,208
    db 102,18,142,69,55,35,254,68,33,56,16,152,20,56,91,18
    db 56,16,209,254,63,43,254,63,23,199,141,113,1,55,1,210
    db 254,73,21,69,62,35,254,75,33,62,16,91,15,56,163,254
    db 67,10,16,254,68,12,124,45,119,45,102,27,254,66,43,254
    db 61,23,254,56,21,138,139,123,1,208,102,18,142,69,55,254
    db 68,34,56,163,56,16,91,18,56,16,209,113,206,200,139,141
    db 113,137,1,210,152,32,102,69,142,1,150,211,1,55,142,1
    db 102,1,152,1,254,64,16,20,254,64,5,177,18,254,71,15
    db 18,56,20,176,2,56,20,115,116,1,95,53,28,1,15,167
    db 1,28,1,53,103,96,1,33,1,53,212,96,33,1,17,143
    db 1,117,145,150,141,113,254,76,17,78,1,62,61,207,254,44
    db 2,254,42,9,1,96,1,83,28,1,15,143,1,28,1,116
    db 103,143,1,28,1,63,212,143,1,33,1,17,254,40,9,1
    db 33,1,53,117,216,254,71,21,205,211,254,80,11,20,33,1
    db 53,1,117,63,53,238,83,255

GV2:
    db 254,49,22,97,28,1,33,1,49,1,254,46,10,1,254,46
    db 10,1,254,47,11,1,254,47,11,254,0,65,98,33,51,33
    db 63,33,51,33,63,1,20,33,37,33,63,53,1,18,178,1
    db 69,167,1,98,64,51,87,1,96,1,64,53,1,18,87,1
    db 59,49,51,49,59,49,37,49,254,39,13,28,37,28,59,28
    db 37,28,1,116,1,35,28,37,95,116,51,178,1,69,167,1
    db 103,64,51,87,1,28,1,64,51,87,1,59,49,1,37,254
    db 45,9,1,59,49,117,28,213,33,37,33,98,33,51,33,63
    db 1,117,37,33,63,53,1,239,1,83,98,64,37,64,98,87
    db 1,53,1,64,1,59,49,37,214,83,49,51,49,59,28,51
    db 28,83,95,37,28,83,1,95,37,28,83,254,36,10,1,32
    db 178,1,116,1,103,64,37,64,1,95,87,1,53,1,18,87
    db 1,254,40,16,1,254,40,5,254,35,5,1,254,35,15,1
    db 96,1,63,2,96,1,35,42,18,2,18,2,35,2,35,99
    db 18,2,20,97,20,99,18,2,20,2,20,2,18,2,18,2
    db 59,28,51,28,59,28,37,28,213,215,1,37,33,98,215,1
    db 15,79,35,2,18,240,18,2,18,42,20,2,18,2,18,2
    db 20,34,18,2,103,214,37,49,103,49,37,49,63,1,20,34
    db 20,2,18,2,18,42,98,33,51,33,63,33,51,33,63,1
    db 20,33,37,33,63,53,1,18,178,1,69,167,1,98,64,51
    db 87,1,96,1,64,53,1,18,87,1,59,49,51,49,59,49
    db 37,49,59,95,37,28,59,28,37,28,1,116,1,35,28,37
    db 95,116,51,178,1,69,167,1,103,64,51,87,1,28,1,64
    db 51,87,1,59,49,51,254,45,9,1,59,49,117,28,213,33
    db 37,33,98,33,51,33,63,1,117,37,33,63,53,1,239,1
    db 83,98,64,37,64,98,87,1,53,1,64,1,59,49,37,214
    db 83,49,51,49,59,28,51,28,83,95,37,28,83,1,95,37
    db 28,83,254,36,10,1,239,1,116,1,103,64,37,64,1,95
    db 87,1,53,1,18,87,1,254,40,16,1,254,40,5,254,35
    db 5,1,254,35,15,1,96,1,63,2,96,1,35,42,18,2
    db 18,2,35,2,35,99,18,2,20,97,20,99,18,2,20,2
    db 20,2,18,2,18,2,59,28,51,28,59,28,37,28,213,215
    db 1,37,33,98,215,1,15,79,35,2,18,34,35,2,18,2
    db 18,42,20,2,18,2,18,2,20,34,18,2,103,214,37,49
    db 103,49,37,49,63,1,20,34,20,2,18,2,18,42,255

GV3:
    db 254,0,187,17,2,17,2,17,34,17,2,17,2,17,97,17
    db 2,17,99,17,2,20,2,69,2,35,42,16,2,16,2,16
    db 34,16,2,16,2,16,42,27,2,27,2,27,2,27,99,27
    db 2,27,97,15,99,15,2,15,2,15,2,15,79,15,2,15
    db 34,35,2,69,2,35,42,16,2,16,2,16,34,16,2,16
    db 2,16,79,27,2,27,2,27,34,15,97,17,34,17,2,17
    db 2,17,2,17,2,17,79,17,2,17,2,20,34,20,97,16
    db 34,16,2,16,2,16,79,27,2,27,240,27,2,27,2,27
    db 42,15,2,15,2,15,34,15,2,15,79,15,2,15,2,35
    db 2,69,79,16,2,16,34,16,2,16,2,16,254,0,97,20
    db 254,0,174,17,42,15,2,15,2,15,2,15,99,15,2,15
    db 97,17,99,17,2,17,2,17,254,0,206,17,79,27,2,27
    db 2,27,34,27,254,0,98,17,2,17,2,17,34,17,2,17
    db 2,17,97,17,34,17,2,20,2,69,2,35,42,16,2,16
    db 2,16,34,16,2,16,2,16,42,27,2,27,2,27,2,27
    db 99,27,2,27,79,15,2,15,2,15,2,15,79,15,2,15
    db 34,35,2,69,2,35,42,16,2,16,2,16,34,16,2,16
    db 2,16,42,27,2,27,2,27,2,27,34,15,97,17,34,17
    db 2,17,2,17,2,17,2,17,79,17,2,17,2,20,34,20
    db 97,16,34,16,2,16,2,16,79,27,2,27,240,27,2,27
    db 2,27,42,15,2,15,2,15,34,15,2,15,79,15,2,15
    db 2,35,254,0,43,16,2,16,34,16,2,16,2,16,254,0
    db 97,20,254,0,174,17,42,15,2,15,2,15,2,15,99,15
    db 2,15,97,17,99,17,2,17,2,17,254,0,206,17,79,27
    db 2,27,2,27,34,27,254,0,87,255

GV4:
    db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
    db 5,254,0,33,255

GV5:
    db 5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5
    db 5,254,0,33,255
