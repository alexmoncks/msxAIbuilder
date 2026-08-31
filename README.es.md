# msxAIbuilder

**Idiomas:** [Português](README.md) · [English](README.en.md) · [Español](README.es.md)

Constructor de ROMs para MSX y MSX2: un ensamblador Z80 en Python, una capa de
conversión de recursos y un runtime modular en ensamblador, para escribir juegos
de cartucho.

> **Estado: el ensamblador existe y funciona.** 160 pruebas, y la ROM de Pong AI
> v24 se sigue produciendo byte a byte. Falta la capa de recursos, el runtime Z80
> compartido y el port de Pong.
>
> Referencia del ensamblador: [`docs/referencia.es.md`](docs/referencia.es.md).
> Diseño completo: [`docs/superpowers/specs/2026-08-31-msxaibuilder-design.md`](docs/superpowers/specs/2026-08-31-msxaibuilder-design.md) (portugués).

## De dónde viene esto

El proyecto nació de **Pong AI v24**, un juego MSX2 completo — pantalla de
título, selección de chip de sonido, música convertida de MIDI, IA de paleta,
efectos en modo ritmo del YM2413, logo comprimido — construido por un único
script de Python de 2.400 líneas que genera todo el Z80 como cadena de texto.

El juego funciona. El script no escala a un segundo juego.

msxAIbuilder separa lo que era reutilizable de aquel trabajo (VDP, sprites,
texto, PSG, YM2413, reproductor de música, entrada, descompresión LZ) de lo que
era Pong.

## Cómo funciona

El código del juego es ensamblador de verdad, en archivos `.asm`:

```asm
    INCLUDE "rt/vdp.asm"
    INCLUDE "rt/sprite.asm"
    INCLUDE "rt/input.asm"

MAIN:
    call VDP_INIT_SCREEN5
LOOP:
    call INPUT_READ
    call SPR_FLUSH
    jr   LOOP
```

Python entra solo donde hay cálculo — convertir BMP en patrones de sprite, MIDI
en datos de música, generar tablas de frecuencia por chip:

```python
from msxbuild import Project

p = Project("mijuego", mapper="konami", size="2048K")
p.image("art/logo.bmp", compress="lz")
p.music("midi/tema.mid", chip=("psg", "ym2413"))
p.build("game.asm")
```

## Componentes

| Paquete | Responsabilidad |
|---|---|
| `msxasm` | Ensamblador Z80. `INCLUDE`, macros, `BSS` con asignación de RAM, bancos de MegaROM. No sabe qué es un sprite. |
| `msxbuild` | Conversión de recursos, montaje del proyecto, runtime `.asm`. No sabe codificar Z80. |
| `games/` | Los cartuchos. [`example/`](games/example/) ensambla y funciona hoy; `pong/` espera el port. |
| [`roms/`](roms/) | Las ROMs jugables. Hoy: Pong AI v24, 16 KB, MSX2. |
| [`skills/`](skills/) | Conocimiento de hardware MSX empaquetado como skill de agente. |

## Documentacion

| Documento | Que cubre |
|---|---|
| [Referencia de msxasm](docs/referencia.es.md) | Sintaxis del ensamblador: CLI, directivas, INCLUDE, macros, BSS, MegaROM |
| [Manual de desarrollo MSX](docs/manual.es.md) | Hardware: V9938, sprites, PSG, YM2413, trampas, pipeline de musica |
| [Spec grafica MSX2](docs/msx2-spec-grafica.es.md) | Decisiones de arquitectura para composite por blitter |
| [skills/writing-msx-roms](skills/) | El mismo hardware como referencia rapida, instalable en agentes (portugues) |

## MegaROM

Soporte para cartuchos de hasta 2 MB con paginación. El mapper por defecto es
**Konami**, por un motivo concreto: mantiene `4000h-5FFFh` fijo en el segmento 0
de la ROM, lo que da 8 KB residentes donde debe vivir el trampolín de
conmutación de banco — el código que pagina no puede ser paginado bajo sus
propios pies.

El detalle que muerde, y que la referencia documenta: los cuatro mappers
compatibles comparten una regla de detección idéntica en WebMSX, y gana la
prioridad menor. Una ROM de 2 MB se cargaría como ASCII8 en silencio, con las
ventanas equivocadas. Por eso el constructor emite el nombre con la pista de
formato — `mijuego [Konami].rom`.

## Primeros pasos

```sh
git clone --recurse-submodules https://github.com/alexmoncks/msxAIbuilder.git
cd msxAIbuilder
python3 -m venv .venv && .venv/bin/pip install pytest

./games/example/build.sh      # -> games/example/build/example.rom
```

El ejemplo es un cartucho MSX de 16 KB que ensambla, con cabecera válida y
vector de entrada correcto. Existe para mostrar `INCLUDE`, `MACRO`, `BSS` y
etiquetas locales `@@` en un programa que cabe en la cabeza de una vez.

## Pruebas

WebMSX entra como submódulo en `vendor/webmsx` y ejecuta las ROMs sin interfaz:
el Z80 y el VDP reales del emulador ejecutan el cartucho, con entrada
programada, y las pruebas verifican el estado resultante.

¿Ya clonaste sin los submódulos?

```sh
git submodule update --init --depth 1
```

## Licencia

[Apache-2.0](LICENSE). El runtime en ensamblador está bajo la misma licencia —
usarlo en un juego no obliga a abrir el código del juego.

WebMSX (Copyright Paulo Augusto Peccin) es una dependencia de pruebas
referenciada por submódulo, no redistribuida por este repositorio. Ver
[NOTICE](NOTICE).
