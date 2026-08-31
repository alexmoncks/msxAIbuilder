# games/

**Idiomas:** [Português](README.md) · [English](README.en.md) · [Español](README.es.md)

Cada subdiretório é um cartucho. O repositório versiona o que **produz** a ROM
— fontes `.asm`, arte, MIDI, scripts de build — nunca o binário. Uma ROM no git
envelhece em silêncio: ninguém sabe de qual commit dos fontes ela saiu.

## `example/`

Cartucho mínimo que monta e roda. Pinta o fundo de azul e conta quadros.

```sh
./games/example/build.sh
# -> games/example/build/example.rom (16 KB) + example.map
```

Não faz mais nada de propósito. O ponto é mostrar as quatro construções que o
msxasm acrescenta ao Z80 — `INCLUDE`, `MACRO`, `BSS` e labels locais `@@` — num
programa pequeno o bastante para caber na cabeça de uma vez.

```
example/
├── game.asm          o jogo
├── rt/
│   ├── header.asm    cabeçalho de cartucho MSX
│   └── vdp.asm       escrita em registrador do VDP
└── build.sh
```

Os módulos do runtime vêm **antes** do código do jogo no fonte. Não é estilo: o
primeiro bloco `BSS` do fonte achatado é quem declara a base da RAM, e os
blocos seguintes se concatenam a partir dela.

O arquivo carrega um comentário sobre uma armadilha real que só aparece
escrevendo: um argumento de macro que começa com parêntese muda o modo de
endereçamento da instrução expandida, e a ROM sai errada sem erro de montagem.

## `pong/`

Vazio de propósito — ver [`pong/README.md`](pong/README.md). O Pong AI v24 é o
jogo de onde este projeto nasceu, e portá-lo para a biblioteca é o teste de
regressão do projeto, com plano próprio.

## Referência

A sintaxe completa do assembler está em
[`docs/referencia.md`](../docs/referencia.md).
