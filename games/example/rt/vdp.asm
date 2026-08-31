; Escrita em registrador do VDP.
;
; Dois bytes na porta 099h: primeiro o valor, depois o numero do registrador
; com o bit 7 ligado. A ordem importa e a sequencia nao pode ser interrompida,
; por isso o `di`/`ei` em volta.

VDP_PORTA_REG   EQU 099h

    BSS 0C000h
VDP_ULTIMO_REG: DS 1        ; ultimo registrador escrito, para depuracao
    ENDBSS

; Entrada: A = valor, B = numero do registrador (0..27)
; Destroi: A
VDP_SET_REG:
    ld      (VDP_ULTIMO_REG),a
    di
    out     (VDP_PORTA_REG),a
    ld      a,b
    or      080h
    out     (VDP_PORTA_REG),a
    ei
    ret
