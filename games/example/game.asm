; Exemplo minimo de cartucho MSX montado com msxasm.
;
; Pinta o fundo da tela de azul e conta quadros. Nao faz mais nada de
; proposito: o ponto e mostrar as quatro construcoes que o msxasm acrescenta
; ao Z80 -- INCLUDE, MACRO, BSS e labels locais @@ -- num programa pequeno o
; bastante para caber na cabeca de uma vez.
;
; Monta com:
;     msxasm games/example/game.asm -o build/example.rom --size 16K \
;            -I games/example
;
; Os modulos do runtime vem ANTES do codigo do jogo. Nao e estilo: o primeiro
; bloco BSS do fonte achatado e quem declara a base da RAM, e os blocos
; seguintes se concatenam a partir dela.

    org 4000h

    INCLUDE "rt/header.asm"
    INCLUDE "rt/vdp.asm"

; --- MACRO ---------------------------------------------------------------
; Escrever um registrador do VDP sao tres passos sempre iguais. A macro os
; nomeia. Cada expansao sufixa os labels locais do corpo, entao duas
; invocacoes nao colidem -- e, se colidissem, o assembler recusaria montar.

    MACRO VDP_REG reg, valor
    ld      a,valor
    ld      b,reg
    call    VDP_SET_REG
    ENDM

; --- constantes ----------------------------------------------------------

COR_FRENTE      EQU 15          ; branco
COR_FUNDO       EQU 4           ; azul escuro
REG_COR         EQU 7           ; R#7: cor de frente e de fundo

; --- estado em RAM -------------------------------------------------------
; BSS reserva endereco sem emitir byte. Aqui o bloco vem pelado: a base ja
; foi declarada por rt/vdp.asm, e este bloco continua de onde aquele parou.
; O assembler recusa montar se duas faixas se sobrepuserem -- que e o motivo
; de isto existir, em vez de se escrever 0C001h na mao e torcer.

    BSS
QUADROS:    DS 2                ; contador de quadros
    ENDBSS

; --- programa ------------------------------------------------------------

MAIN:
    ld      hl,0
    ld      (QUADROS),hl

; ATENCAO, armadilha real: um argumento de macro que COMECA com parentese
; muda o modo de enderecamento da instrucao expandida. Escrito como
; `(COR_FRENTE * 16) + COR_FUNDO`, o corpo `ld a,valor` vira
; `ld a,(240) + 4`, que o Z80 le como leitura de memoria -- monta sem erro e
; carrega o byte do endereco 240. Sem o parentese na frente, e imediato.
    VDP_REG REG_COR, COR_FRENTE * 16 + COR_FUNDO

; Um label local pertence ao ultimo label global acima dele. Outro modulo
; pode ter o seu proprio @@laco sem colidir com este.
@@laco:
    ld      hl,(QUADROS)
    inc     hl
    ld      (QUADROS),hl
    jr      @@laco
