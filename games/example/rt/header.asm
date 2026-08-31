; Cabecalho de cartucho MSX. Tem de ficar no inicio da ROM (4000h).
;
; O MSX varre os slots procurando a assinatura "AB" no inicio de uma pagina.
; Achando, chama o endereco em INIT. Os outros vetores sao para extensoes de
; BASIC e drivers de dispositivo; um jogo de cartucho deixa em zero.

    DB "AB"
    DW MAIN         ; INIT   -- ponto de entrada
    DW 0            ; STATEMENT
    DW 0            ; DEVICE
    DW 0            ; TEXT
    DW 0, 0, 0      ; reservado
