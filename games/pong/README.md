# Pong AI v24 — port pendente

Este diretorio esta vazio de proposito.

O **Pong AI v24** e o jogo de onde este projeto nasceu: um MSX2 completo, com
tela de titulo, selecao de chip de som, musica convertida de MIDI, IA de
raquete, efeitos no modo ritmo do YM2413 e logo comprimido. Ele existe e
funciona — mas construido por um script Python unico de 2.400 linhas que gera
todo o Z80 como string, com enderecos de RAM literais (`0C000h`, `0C020h`,
`0C05Ch`) espalhados pelo codigo.

Portar esse jogo para a biblioteca e o **teste de regressao** do projeto, e tem
plano proprio. A ROM dele ja esta neste repositorio como
`tests/fixtures/pong-v24.rom`, congelada, servindo de golden file: o assembler
tem de continuar produzindo esses 16384 bytes exatos
(`md5 03324e8f4febc0e537c9c808c6c33c00`) depois de qualquer refatoracao.

O port so comeca depois do harness de regressao existir. A ordem importa: o
primeiro teste do harness e provar que a v24 e equivalente a si mesma. Se ele
nao provar isso, nao prova nada sobre o port.
