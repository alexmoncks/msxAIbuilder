# roms/

**Idiomas:** [Português](README.md) · [English](README.en.md) · [Español](README.es.md)

Lo que **efectivamente funciona**. El `.gitignore` del proyecto bloquea `*.rom`
en todas partes precisamente para que las decenas de compilaciones de prueba no
se mezclen con las ROMs jugables; este directorio es la excepción declarada.

| ROM | Tamaño | md5 | Máquina |
|---|---|---|---|
| `pong-ai-v24.rom` | 16 KB | `03324e8f4febc0e537c9c808c6c33c00` | MSX2 |

## Pong AI v24

El juego del que nació este proyecto. Un MSX2 completo: pantalla de título,
selección de chip de sonido (PSG, YM2413 o sin música), música convertida de
archivos MIDI, IA de paleta con tres dificultades, efectos en modo ritmo del
YM2413, logo comprimido y partida a 10 puntos.

Ejecutarlo en WebMSX:

```
http://localhost:PUERTO/?ROM=pong-ai-v24.rom&MACHINE=MSX2PE
```

Esta ROM es **byte a byte idéntica** a `tests/fixtures/pong-v24.rom`. Ambas
copias existen porque sirven a cosas distintas: la de `tests/fixtures/` es un
contrato de prueba, congelada para siempre — el ensamblador debe seguir
produciendo esos bytes exactos tras cualquier refactorización. Esta es el
artefacto jugable, y será sustituida cuando el port a la biblioteca esté listo.

**Es lo único en este repositorio que no se puede reconstruir desde aquí.** La
fuente que la genera es `build_pong.py`, un script de Python de 2.400 líneas que
vive en el repositorio antiguo. Ese es precisamente el problema que este
proyecto existe para resolver — y por eso el binario queda versionado mientras
el port no ocurra.

## Lo que no está aquí, y por qué

**La ROM del ejemplo** (`games/example/`) no está versionada a propósito: un
comando la reconstruye, y un binario rastreado envejecería en silencio junto a
las fuentes que lo producen.

```sh
./games/example/build.sh
```

**ROMs de terceros** no entran. El repositorio es Apache-2.0 y no redistribuye
trabajo de otras personas sin licencia clara — la misma razón por la que WebMSX
entra como submódulo en lugar de copia. Ver [NOTICE](../NOTICE).
