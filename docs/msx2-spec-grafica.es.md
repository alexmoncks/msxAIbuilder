# Spec Gráfica — Proyecto MSX2

**Idiomas:** [Português](msx2-spec-grafica.md) · [English](msx2-graphics-spec.en.md) · [Español](msx2-spec-grafica.es.md)

Documento de decisiones de arquitectura gráfica. Objetivo: MSX2 (V9938),
SCREEN 5. Estado: decisiones cerradas en conversación, validadas contra el
código existente en §9.

---

## 1. Modo de vídeo y uso de la VRAM

**SCREEN 5 (Graphic 4)**, 256x212, 16 colores simultáneos de una paleta de 512.
128 KB de VRAM divididos en 4 páginas de 32 KB.

| Página | Uso |
|--------|-----|
| 0 | Búfer visible / doble búfer A |
| 1 | Búfer de trabajo / doble búfer B |
| 2 | Banco de tiles del escenario |
| 3 | Fotogramas de animación del personaje y del jefe |

El cambio de página visible se hace por R#2, con un coste de una escritura de
registro, ejecutada en el vblank.

**Atención al diseño interno de la página.** Las tablas de sprites no viven en
una página aparte: cada página de 32 KB tiene las suyas, en los desplazamientos
por defecto de la BIOS (aproximadamente base+#7400 colores, base+#7600
atributos, base+#7800 patrones). Como las páginas 0 y 1 se alternan como
visibles, las tablas de sprites de ambas deben mantenerse sincronizadas, o se
acepta un fotograma de retraso en la hitbox.

> **Corregido en la validación — ver §9.2.** La sincronización no es necesaria.
> Las tablas de sprites se direccionan por R#5/R#11 y R#6, independientes de
> R#2. Cambiar la página visible no mueve las tablas: se apuntan ambas páginas a
> un único conjunto y el problema desaparece, junto con el fotograma de retraso.

**Consecuencia de presupuesto:** con doble búfer quedan 64 KB (páginas 2 y 3)
para tiles y fotogramas, no 96 KB.

---

## 2. Dibujo de personajes (blitter)

Todo personaje, jefe y elemento animado se dibuja mediante el command engine del
V9938. No se gasta ningún sprite de hardware en el dibujo visible.

**Comando estándar:** `LMMM` con operación lógica transparente (`TIMP`),
copiando el fotograma de la página de banco a la página de trabajo.

Secuencia por objeto:
1. Restaurar el fondo en la posición anterior (`HMMM` desde la página de
   escenario limpio)
2. Copiar el fotograma nuevo (`LMMM` + `TIMP`)

Registros implicados: R#32 a R#45 (SX, SY, DX, DY, NX, NY, CLR, ARG) y R#46
(CMR, que dispara el comando). Antes de escribir un nuevo comando, comprobar el
bit CE en S#2.

**Presupuesto de ciclos.** El blitter compite con el refresco de pantalla por el
acceso a la VRAM. Es bastante más rápido con la pantalla apagada o durante el
vblank. El número real de blits de 16x16 por fotograma debe medirse en el
objetivo antes de cerrar la densidad de objetos en pantalla. Marcar esto como
tarea de instrumentación (contador de ráster).

**Comandos H frente a L.** Los `H*` operan sobre bytes enteros (más rápidos,
granularidad de 2 píxeles en SCREEN 5). Los `L*` operan píxel a píxel y aceptan
operación lógica. Usar `H*` para la restauración de fondo alineada y `L*` para
el dibujo del objeto.

---

## 3. Colisión

### 3.1 Colisión entre objetos: sprites transparentes

La detección de colisión del V9938 mira los bits del patrón, no el color. Un
sprite con color 0 no se renderiza pero sigue colisionando. Eso permite hitboxes
invisibles.

**Regla del proyecto:** hitbox aplicada solo a los puntos débiles, nunca a la
silueta. Un jefe de 64x48 gasta 3 sprites (cabeza, núcleo, cola) en lugar de 12
para cubrir el cuerpo entero. Ganancia técnica y de jugabilidad a la vez: el
jugador tiene que apuntar.

**Configuración:**
- Sprite mode 2, color 0 en las hitboxes
- Bit CC = 0 en las hitboxes, en el jugador y en los disparos (participan en la
  colisión)
- Bit CC = 1 en cualquier sprite decorativo (no participa)
- Magnificación activa cuando el punto débil sea grande: un sprite de 16x16
  magnificado cubre 32x32 gastando una sola ranura. La granularidad de 2 píxeles
  es irrelevante para una hitbox

**Lectura por fotograma:**
- S#0 bit 5 (flag C): hubo colisión. Leer S#0 borra el flag, así que léelo una
  vez por fotograma
- S#3/S#4 (X) y S#5/S#6 (Y): coordenadas del punto de colisión

**Resolución de la ambigüedad.** El flag es global y no dice quién colisionó.
Estrategia: usar la coordenada leída para identificar el punto débil por
geometría. Si los puntos débiles están en franjas Y distintas, Y lo resuelve
solo. Si coinciden en Y, X lo resuelve. Solo cuando ambos coinciden se ejecuta
bounding box por software, y únicamente sobre los objetos cercanos a la
coordenada leída.

**Presupuesto de sprites.** Límite de 8 por línea de barrido. Probar el peor
caso: jugador pegado al jefe disparando tiro múltiple. Con 3 puntos débiles hay
holgura; a partir de 5 la prueba pasa a ser obligatoria.

**Corrección sobre eliminar una hitbox.** Para desactivar un punto débil
destruido, mover el sprite fuera de la pantalla (Y >= 212). No usar Y = 216 para
esto: en sprite mode 2 ese valor termina el procesamiento de la lista entera a
partir de esa ranura, borrando también los sprites siguientes.

### 3.2 Colisión con el escenario

Mapa de colisión en RAM indexado por tile. Nunca usar `POINT` ni lectura de VRAM
para esto; el coste por consulta es demasiado alto.

---

## 4. Paleta

16 entradas, cada canal con 3 bits (valores de 0 a 7). No es RGB continuo: son 8
niveles discretos por componente.

### 4.1 Partición

| Franja | Uso |
|--------|-----|
| 0 | Transparente |
| 1 a 5 | Escenario |
| 6 a 11 | Personaje y jefe (6 entradas) |
| 12 a 13 | Efectos y acentos |
| 14 a 15 | HUD, exclusivo |

La sexta entrada del personaje se tomó del escenario, no de los efectos.
Justificación: las áreas grandes y planas de fondo absorben el dithering mucho
mejor que un objeto pequeño en movimiento, que centellea.

Con 6 entradas el personaje gana dos rampas de 3 tonos (cuerpo y detalle) o una
rampa de 4 más 2 acentos, en lugar de una rampa única apretada.

### 4.2 HUD

Las entradas 14 y 15 son exclusivas y nunca las tocan el fade, el flash o el
ciclo de colores. Sin eso, el marcador parpadea junto con el efecto de daño.

Si el HUD ocupa una franja fija de la pantalla, es candidato a división de
paleta por línea (R#19 + IE1), lo que devuelve esas entradas al escenario en la
parte superior de la pantalla.

### 4.3 Efectos

Escritura: fijar R#16 con la entrada, luego 2 escrituras en el puerto #9A (un
byte con R y B, otro con G). La paleta entera son 32 escrituras, que caben en el
vblank.

- **Fade:** tabla precalculada con curva no lineal, más pasos en la franja
  oscura. Con 8 niveles por canal, un fade lineal queda visiblemente escalonado.
  Espaciar los pasos 2 o 3 fotogramas
- **Ciclo de colores:** rotar 3 o 4 entradas para agua, lava, portales. Coste
  casi nulo, alto retorno visual
- **Flash de daño del jefe:** preferir `LMMV` con operación lógica sobre el área
  del jefe durante 2 fotogramas, en lugar de tocar la paleta. Como personaje y
  jefe comparten las entradas 6 a 11, un flash por paleta haría parpadear a los
  dos

---

## 5. Dithering

Usado para compensar la partición de paleta, principalmente en el escenario.

**Regla obligatoria:** el patrón de damero se graba dentro del bitmap del
fotograma, anclado a las coordenadas del objeto. Nunca generado en tiempo de
ejecución anclado a la pantalla. Si se ancla a la pantalla, el patrón "camina"
bajo el objeto en movimiento y se convierte en ruido.

Elegir pares con diferencia pequeña de luminancia. En compuesto la mezcla
horizontal ayuda; en RGB, un par demasiado contrastado aparece como rejilla.

---

## 6. Estructura de datos de animación

Cada fotograma de animación lleva, además del bitmap:

```
frame:
  vram_src_x, vram_src_y     ; origen en la página de banco
  width, height
  n_hitboxes
  hitbox[]:
    dx, dy                   ; desplazamiento relativo al ancla del objeto
    sprite_slot
    weak_point_id
```

Los desplazamientos de las hitboxes salen de la misma tabla que define el
fotograma. Si las coordenadas de los sprites se calculan en otro sitio, la
hitbox se despega del dibujo durante la animación.

---

## 7. Pendientes

- [ ] Medir el coste real de `LMMM` 16x16 con la pantalla encendida en el
      objetivo, y cerrar el número máximo de objetos por fotograma
- [ ] Probar el peor caso de 8 sprites por línea (jugador pegado al jefe con
      tiro múltiple)
- [ ] Definir la paleta concreta (valores RGB de las 16 entradas)
- [ ] Decidir si la división de paleta por línea entra en la v1 o espera
- [x] Validar esta spec contra el código ya existente en el repositorio — ver §9

---

## 8. Notas sobre alternativas descartadas

- **SCREEN 8:** 256 colores fijos, pero pierde la paleta programable (tonos de
  azul y verde malos), baja a 2 páginas y el blitter se vuelve más lento por
  píxel. Descartado para un juego con jefe animado
- **SCREEN 12 (YJK, MSX2+):** solo si el objetivo cambia a MSX2+. Salvedad:
  artefacto de croma visible en bordes de alto contraste
- **Hitbox cubriendo la silueta entera:** revienta el presupuesto de 8 sprites
  por línea sin ganancia de jugabilidad

---

## 9. Validación contra el código (§7, punto 5)

Realizada el 2026-08-31 contra WebMSX v6.0.8 (`4f4009e8`), el mismo commit
fijado en `vendor/webmsx`, y contra `tools/build_pong.py` de Pong AI v24. Cada
punto de abajo fue leído en el código, no supuesto.

### 9.1 Y = 216 termina la lista — CONFIRMADO

```js
// src/main/msx/video/VDP.js:1930
if (y === 216) break;    // Stop Sprite processing for the line, as per spec
```

El emulador implementa exactamente el comportamiento descrito en §3.1. La regla
de esconder la hitbox con `Y >= 212` y nunca `216` es correcta y debe convertirse
en rutina del runtime (`SPR_HIDE`), no en convención documentada — las
convenciones se olvidan.

### 9.2 Sincronización de tablas de sprites entre páginas — INNECESARIA

§1 concluye que las tablas de sprites de las páginas 0 y 1 deben mantenerse
sincronizadas. La premisa es verdadera (el diseño por defecto de la BIOS coloca
un conjunto de tablas dentro de cada página de 32 KB), pero la conclusión no se
sostiene.

```js
// src/main/msx/video/VDP.js:362,471 — R#2 toca SOLO la tabla de layout
case 2: if (mod & 0x7f) updateLayoutTableAddress();
    var add = ... (register[2] & 0x7f) << 10;

// src/main/msx/video/VDP.js:389,487 — los sprites vienen de R#5/R#11 y R#6
spriteAttrTableAddress    = add & modeData.sprAttrTBase;   // R#5 / R#11
spritePatternTableAddress = ...                            // R#6
```

R#2 direcciona el bitmap. Las tablas de sprites se direccionan por registros
distintos. **Cambiar la página visible no mueve las tablas de sprites.** Basta
dejar R#5/R#11/R#6 apuntando a un único conjunto y ambas páginas lo comparten.

Consecuencias: desaparece el trabajo de sincronizar por fotograma, desaparece el
fotograma de retraso en la hitbox, y la elección de qué página hospeda las
tablas se vuelve arbitraria. El coste son 2 KB gastados en una página; la región
equivalente en la otra queda libre para datos, siempre que el packer sepa que no
es contigua.

### 9.3 El coste del blitter NO es medible en WebMSX — §7 punto 1 bloqueado

```js
// src/main/msx/video/VDPCommandProcessor.js:3
// Commands perform all operation instantaneously at the first cycle.
// Duration is estimated and does not consider VRAM access slots
```

§2 quiere medir cuántos blits de 16x16 caben en un fotograma, e identifica
correctamente la causa: el blitter compite con el refresco de pantalla por la
VRAM. **Esa competencia es justamente lo que WebMSX no modela.** La duración se
estima con una fórmula con factor de corrección fijo
(`COMMAND_PER_PIXEL_DURATION_FACTOR = 1.1`), y el comando se ejecuta entero en el
primer ciclo.

El harness sin interfaz sirve para probar la *corrección* del blitter — los
píxeles correctos en el lugar correcto. No sirve para cerrar un presupuesto de
ciclos. Ese número necesita hardware real o un emulador con temporización de VDP
más fiel.

**Consecuencia de diseño:** la densidad de objetos en pantalla no puede decidirse
en el emulador. El runtime debe exponer un contador de ráster instrumentado desde
el principio, para que la medición se haga en el objetivo en cuanto haya
hardware, sin retrabajo.

### 9.4 Estimaciones relativas de coste por comando

Aunque los números absolutos no valgan (§9.3), el orden relativo viene del código
y sostiene la regla "H* para el fondo, L* para el objeto" de §2:

| Comando | Ciclos por unidad | Por línea |
|---|---|---|
| `YMMM` | 40R + 24W = 64 | 0 |
| `HMMV` | 48W | 56 |
| `HMMM` | 64R + 24W = 88 | 64 |
| `LMMV` | 72R + 24W = 96 | 64 |
| `LMMM` | 64R + 32R + 24W = 120 | 64 |

`LMMM` cuesta unas 1,4 veces `HMMM` por unidad — y como en SCREEN 5 los `H*`
operan sobre bytes de 2 píxeles, la razón por área dibujada se acerca a 2,7x. La
regla de §2 es correcta y la ganancia es mayor de lo que "más rápido" sugiere.

### 9.5 Pong no usa el command engine — ESTO ES CÓDIGO NUEVO

Un barrido de `tools/build_pong.py` buscando los puertos `#9B`, los registros
R#32 a R#46 y los nombres de comando no encontró ninguna aparición. Pong AI v24
dibuja enteramente con sprites de hardware y escritura directa en VRAM.

No hay nada que extraer para el módulo de blitter. `blit.asm`, `page.asm` (doble
búfer) y el packer de fotogramas en VRAM son **código nuevo escrito desde cero**,
no una refactorización de código probado. Es la mayor porción de riesgo técnico
del proyecto, y merece un juego objetivo propio en lugar de ir de polizón en el
port de Pong.
