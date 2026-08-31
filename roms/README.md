# roms/

**Idiomas:** [Português](README.md) · [English](README.en.md) · [Español](README.es.md)

O que **efetivamente roda**. O `.gitignore` do projeto barra `*.rom` em todo
lugar justamente para que as dezenas de builds de teste não se misturem com as
ROMs jogáveis; este diretório é a exceção declarada.

| ROM | Tamanho | md5 | Máquina |
|---|---|---|---|
| `pong-ai-v24.rom` | 16 KB | `03324e8f4febc0e537c9c808c6c33c00` | MSX2 |

## Pong AI v24

O jogo de onde este projeto nasceu. MSX2 completo: tela de título, seleção de
chip de som (PSG, YM2413 ou sem música), música convertida de arquivos MIDI, IA
de raquete com três dificuldades, efeitos no modo ritmo do YM2413, logo
comprimido e partida de 10 pontos.

Rodar no WebMSX:

```
http://localhost:PORTA/?ROM=pong-ai-v24.rom&MACHINE=MSX2PE
```

Esta ROM é **byte a byte idêntica** a `tests/fixtures/pong-v24.rom`. As duas
cópias existem porque servem a coisas diferentes: a de `tests/fixtures/` é
contrato de teste, congelada para sempre — o assembler tem de continuar
produzindo esses bytes exatos depois de qualquer refatoração. Esta aqui é o
artefato jogável, e será substituída quando o port para a biblioteca ficar
pronto.

**Ela é a única coisa neste repositório que não dá para reconstruir a partir
daqui.** O fonte que a gera é `build_pong.py`, um script Python de 2.400 linhas
que vive no repositório antigo. É exatamente esse o problema que o projeto
existe para resolver — e é por isso que o binário fica versionado enquanto o
port não acontece.

## O que não está aqui, e por quê

**A ROM do exemplo** (`games/example/`) não está versionada de propósito: um
comando a reconstrói, e um binário rastreado envelheceria em silêncio ao lado
dos fontes que o produzem.

```sh
./games/example/build.sh
```

**ROMs de terceiros** não entram. O repositório é Apache-2.0 e não redistribui
trabalho de outras pessoas sem licença clara — a mesma razão pela qual o WebMSX
entra por submodule em vez de cópia. Ver [NOTICE](../NOTICE).
