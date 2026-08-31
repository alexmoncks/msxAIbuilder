# msxasm — referencia

**Idiomas:** [Português](referencia.md) · [English](reference.en.md) · [Español](referencia.es.md)

Ensamblador Z80 para cartuchos MSX. Dos pasadas, sin dependencias fuera de la
biblioteca estándar de Python.

```
msxasm FUENTE -o SALIDA [--org DIRECCIÓN] [--size TAMAÑO]
               [-I RUTA]... [--bank-map ARCHIVO]
```

| Opción | Significado | Por defecto |
|---|---|---|
| `-o`, `--output` | ROM de salida | obligatorio |
| `--org` | Dirección de ensamblado, cuando la fuente no declara `org` | `0x4000` |
| `--size` | Tamaño del cartucho | `16K` |
| `-I`, `--include-path` | Directorio adicional para resolver `INCLUDE` e `INCBIN` | — |
| `--bank-map` | Escribe el mapa símbolo → (banco, dirección) | — |

Un error de ensamblado se informa con `archivo:línea`, sale con estado 1 y
**no se escribe ninguna ROM**. Una ROM parcial en disco parece terminada.

## Escritura numérica

Una sola gramática, aceptada en todas partes — directivas, expresiones y
argumentos de línea de comandos:

| Forma | Ejemplo | Valor |
|---|---|---|
| Sufijo `K` / `M` | `16K`, `2M` | múltiplos de 1024 |
| Sufijo `H` (Intel) | `0C000h`, `4000h` | hexadecimal |
| Prefijo `0x` / `0b` / `0o` | `0x4000`, `0b1010` | estilo Python |
| Decimal | `49152` | — |

El sufijo se prueba antes que el prefijo: `0BEEFh` es un hexadecimal terminado
en `h`, no un binario que empieza por `0b`.

## Directivas del Z80

`ORG`, `DB`, `DW`, `DS`, `INCBIN`, `EQU` — el conjunto tradicional.

`INCBIN "archivo"` incrusta un binario. La ruta se resuelve relativa al
archivo **que contiene la línea**, luego mediante `-I`. Un archivo ausente es
un error, no silencio.

Una etiqueta en la propia línea del `ORG` (`INICIO: ORG 4000h`) se resuelve a
la dirección **posterior** al `ORG`. Las demás directivas ligan la etiqueta a
la dirección anterior a ellas, como es habitual.

## `INCLUDE`

```asm
    INCLUDE "rt/vdp.asm"
```

Se resuelve relativo al archivo que incluye, luego mediante `-I`. El mismo
archivo incluido dos veces entra **una sola vez** — los módulos del runtime
dependen unos de otros y una guarda manual en cada archivo sería ruido
repetido. La inclusión circular es un error con el rastro completo, nunca
recursión infinita.

Cada línea de la fuente aplanada conserva su archivo y número de origen. Un
error dentro de `vdp.asm` informa `vdp.asm:12`, no un desplazamiento dentro
del texto aplanado.

## Etiquetas locales

```asm
PSG_ON:
@@bucle:
    djnz @@bucle
```

`@@nombre` pertenece a la última etiqueta global por encima de ella,
convirtiéndose en `PSG_ON@@bucle`. Dos módulos pueden tener cada uno su propio
`@@bucle` sin colisionar.

Sin ámbito local esa colisión es **silenciosa**: el segundo módulo simplemente
salta a la etiqueta del primero.

`@@` dentro de un comentario o de una cadena literal no se reescribe.

## Macros

```asm
    MACRO VDP_REG reg, valor
    ld      a,valor
    ld      b,reg
    call    VDP_SET_REG
    ENDM

    VDP_REG 7, 0F4h
```

Parámetros posicionales. Cada expansión añade un sufijo a las etiquetas
locales del cuerpo, de modo que dos invocaciones nunca producen etiquetas
idénticas.

Restricciones, todas con error claro:

- un parámetro con nombre de registro o bandera del Z80 se rechaza — un
  parámetro llamado `a` convertiría `ld a,n` en `ld 5,n`;
- un número de argumentos distinto al declarado es error;
- una macro abierta sin `ENDM` es error;
- redefinir una macro es error, citando ambas ubicaciones.

La sustitución nunca ocurre dentro de una cadena literal ni de un comentario.

> **Trampa.** Un argumento que **empieza con paréntesis** cambia el modo de
> direccionamiento de la instrucción expandida. `VDP_REG 7, (15 * 16) + 4`
> convierte `ld a,valor` en `ld a,(240) + 4`, que el Z80 lee como lectura de
> memoria — ensambla sin error y carga el byte de la dirección 240. Escriba
> `15 * 16 + 4`.

## `BSS` — asignación de RAM

```asm
    BSS 0C000h
MUS_PTR:    DS 2        ; C000h
MUS_TICK:   DS 1        ; C002h
    ENDBSS
```

Reserva direcciones sin emitir bytes. El primer bloque de la fuente aplanada
declara la base; los siguientes vienen desnudos (`BSS` sin argumento) y
continúan donde se detuvo el anterior.

El ensamblador **se niega a ensamblar** cuando:

- dos símbolos comparten nombre (la comparación ignora mayúsculas);
- dos rangos `[base, base+tamaño)` se solapan — incluso parcialmente;
- una asignación sobrepasa el límite de la RAM;
- un símbolo de `BSS` colisiona con una etiqueta de ROM.

Esto sustituye las direcciones literales esparcidas por el código. Con
módulos, dos que elijan `0C020h` se corrompen mutuamente y nada avisa.

## MegaROM

```asm
    MAPPER KONAMI, 2048K

    BANK 0                      ; residente, 4000h-5FFFh
    DB "AB"
    DW MAIN

    BANK 12 WINDOW 8000h
MUNDO2:
    INCBIN "build/mundo2.bin"
```

| Layout | Banco | Ventanas | Residente | Máximo |
|---|---|---|---|---|
| `FLAT` | — | `4000h` | `4000h` | 1 |
| `KONAMI` | 8192 | `4000h` `6000h` `8000h` `A000h` | `4000h` | 256 (2 MB) |

Konami mantiene `4000h–5FFFh` fijo en el segmento 0, que nunca pagina. Ahí es
donde deben vivir la cabecera, el trampolín y la rutina de conmutación de
banco — el código que pagina no puede ser paginado bajo sus propios pies.

2 MB es el techo exacto, no un número redondo: el registro de banco tiene 8
bits y el emulador aplica `value % numBanks`, lo que da 256 bancos de 8 KB.

Los símbolos del banco residente son visibles desde todos los bancos. Entre
dos bancos paginados no lo son — y el ensamblado falla en lugar de emitir un
salto equivocado.

Un `org` dentro de un banco paginado que difiera de su `WINDOW` es error: en
esa sintaxis manda la ventana.

### La pista en el nombre del archivo no es decoración

En WebMSX, ASCII8 (prioridad 911), ASCII16 (912), Konami (913) y KonamiSCC
(914) comparten una condición de detección **idéntica**, y gana la prioridad
menor. Una ROM de 2 MB se carga como ASCII8, en silencio, con las ventanas
equivocadas.

Nombre la ROM con el formato entre corchetes — `mijuego [Konami].rom` — y el
emulador elige correctamente.

## Limitaciones conocidas

- Un `EQU` declarado en el banco residente **no** cruza bancos; solo se
  siembran las etiquetas.
- No existe validación de `FARCALL`. Un `call` a un banco paginado falla con
  "el símbolo no existe" — el mensaje correcto por el motivo equivocado.
- El mapa de bancos no incluye símbolos de `BSS`.
- Las macros no se expanden recursivamente.
- Una macro no puede invocarse en una línea que ya lleve etiqueta.
