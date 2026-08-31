# games/

**Idiomas:** [Português](README.md) · [English](README.en.md) · [Español](README.es.md)

Cada subdirectorio es un cartucho. El repositorio versiona lo que **produce** la
ROM — fuentes `.asm`, arte, MIDI, scripts de compilación — nunca el binario. Una
ROM en git envejece en silencio: nadie sabe de qué commit de las fuentes salió.

## `example/`

Cartucho mínimo que ensambla y funciona. Pinta el fondo de azul y cuenta
fotogramas.

```sh
./games/example/build.sh
# -> games/example/build/example.rom (16 KB) + example.map
```

No hace nada más a propósito. El objetivo es mostrar las cuatro construcciones
que msxasm añade al Z80 — `INCLUDE`, `MACRO`, `BSS` y etiquetas locales `@@` —
en un programa lo bastante pequeño para caber en la cabeza de una vez.

```
example/
├── game.asm          el juego
├── rt/
│   ├── header.asm    cabecera de cartucho MSX
│   └── vdp.asm       escritura en registro del VDP
└── build.sh
```

Los módulos del runtime van **antes** del código del juego en la fuente. No es
estilo: el primer bloque `BSS` de la fuente aplanada es el que declara la base
de la RAM, y los bloques siguientes se concatenan a partir de ella.

El archivo lleva un comentario sobre una trampa real que solo aparece
escribiendo código: un argumento de macro que empieza con paréntesis cambia el
modo de direccionamiento de la instrucción expandida, y la ROM sale mal sin
error de ensamblado.

## `pong/`

Vacío a propósito — ver [`pong/README.md`](pong/README.md). Pong AI v24 es el
juego del que nació este proyecto, y portarlo a la biblioteca es la prueba de
regresión del proyecto, con plan propio.

## Referencia

La sintaxis completa del ensamblador está en
[`docs/referencia.es.md`](../docs/referencia.es.md).
