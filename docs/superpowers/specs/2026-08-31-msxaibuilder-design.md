# msxAIbuilder — construtor universal de ROMs MSX

Design aprovado em 2026-08-31.

## 1. Objetivo

Extrair o conhecimento acumulado no Pong AI v24 — hoje preso em
`tools/build_pong.py`, um script Python de 2.400 linhas que gera todo o Z80 como
string — e transformá-lo numa biblioteca capaz de construir jogos MSX de gêneros
variados.

**Critério de sucesso da v1:** o Pong v24 reescrito em cima da biblioteca,
provado equivalente ao original por comparação de traço de execução.

Uma segunda trilha, de composite por blitter do V9938 para jogos mais
elaborados, está especificada em [`docs/msx2-spec-grafica.md`](../../msx2-spec-grafica.md)
e resumida na seção 6.2. Ela **não** faz parte da v1 — ver seções 10 e 11.

## 2. Decisões

| Decisão | Escolha | Razão |
|---|---|---|
| Repositório | Novo e separado, `msxAIbuilder` | O diretório atual é clone do `ppeccin/WebMSX`; qualquer push carregaria o histórico do emulador |
| Alvo | Engine genérica, peças combináveis | O usuário pretende gêneros diferentes, não só arcade de tela única |
| Autoria | Híbrido `.asm` + Python para dados | ASM legível e navegável; Python só onde há cálculo (tabelas, música, arte) |
| Organização | INCLUDEs granulares | Previsível e depurável; sem tree-shaking, que quebra com jump table e código automodificante |
| Assembler | INCLUDE + macros + mapper/bancos | Escolha explícita do usuário |
| MegaROM na v1 | Assembler e runtime sim; Pong fica flat 16KB | Trocar mapper e biblioteca ao mesmo tempo confunde a causa de qualquer regressão |
| Licença | Apache-2.0 | Permissiva com concessão de patente; não alcança os jogos de terceiros |
| Visibilidade | Público | |
| WebMSX | Submodule apontando para fork próprio | Permite ganchos de teste no emulador sem depender do upstream |

## 3. Layout

```
msxAIbuilder/
├── msxasm/                    # assembler Z80 — não sabe o que é um sprite
│   ├── lexer.py  parser.py  encoder.py
│   ├── include.py             # resolução de INCLUDE
│   ├── macro.py               # expansão de macros
│   ├── sections.py            # bancos de ROM + BSS
│   └── errors.py              # erro com arquivo:linha + pilha de includes
├── msxbuild/                  # assets e projeto — não sabe codificar Z80
│   ├── project.py
│   ├── assets/  bmp.py  midi.py  lz.py  font.py
│   └── rt/                    # runtime Z80, versionado como .asm
│       ├── header.asm  mapper.asm  vdp.asm   screen.asm
│       ├── sprite.asm  text.asm    draw.asm  lz.asm
│       ├── psg.asm     ym2413.asm  music.asm sfx.asm
│       ├── input.asm
│       └── (pós-v1) blit.asm  page.asm  palette.asm
│                    collide.asm  anim.asm
├── games/
│   ├── pong/      game.asm  build.py  art/  midi/
│   └── example/
├── vendor/webmsx/             # submodule (apenas testes)
├── tests/
└── docs/
```

A fronteira entre `msxasm` e `msxbuild` é um diretório de arquivos gerados.
Cada pacote é testável sozinho.

**Nenhum caminho absoluto.** O `build_pong.py` atual embute
`/home/alexmarra/projects/WebMSX` em `sys.path` e no caminho de saída; o projeto
novo resolve tudo relativo à raiz do repositório.

## 4. `msxasm` — o assembler

Hoje `tools/minz80asm.py` reconhece apenas `ORG DB DW DS INCBIN EQU`.

### 4.1 INCLUDE

Resolve relativo ao arquivo incluidor, depois por search path (`-I`). Guarda
contra inclusão dupla. Inclusão circular é erro, não recursão infinita. O erro
reporta a pilha de includes.

### 4.2 Macros

`MACRO nome arg1,arg2` … `ENDM`. Labels locais (`@@loop`) são renomeados por
expansão para não colidir entre invocações.

### 4.3 BSS — alocação de RAM

**O problema que resolve:** o Pong atual grava endereços de RAM literais no
código — `0C000h`, `0C001h`, `0C020h`, `0C05Ch` — espalhados, sem nomes
simbólicos. Numa biblioteca modular isso é corrupção silenciosa: se `music.asm`
usa `0C020h` e o jogo também, nada avisa.

```asm
    BSS 0C000h
MUS_PTR:    DS 2        ; assembler atribui C000h
MUS_TICK:   DS 1        ;                   C002h
MUS_VOZ:    DS 6
    ENDBSS
```

Aloca endereços sem emitir bytes. Cada módulo declara seu bloco; o assembler
concatena na ordem de inclusão e **falha se dois símbolos colidirem ou se a RAM
estourar**.

### 4.4 Mapper e bancos

```asm
    MAPPER KONAMI, 2048K        ; define janelas, valida tamanho final

    BANK 0                      ; residente — 4000h-5FFFh
    ORG 4000h
        DB "AB"
        DW INIT
    INCLUDE "msxbuild/rt/mapper.asm"

    BANK 12  WINDOW 8000h
MUNDO2_TILES:
        INCBIN "build/mundo2.bin"
```

Símbolo deixa de ser endereço e passa a ser **(banco, endereço)**. Com isso o
assembler pode:

- **rejeitar `call` direto** para símbolo em banco não-residente fora da janela
  corrente, exigindo `FARCALL` — hoje isso montaria em silêncio e quebraria em
  runtime;
- validar que cada banco cabe no tamanho da janela;
- validar que a janela declarada existe no mapper escolhido;
- emitir mapa de bancos para depuração.

### 4.5 Erros

`arquivo:linha` mais pilha de includes. Hoje um erro no meio de 2.400 linhas
geradas não diz onde ocorreu.

## 5. MegaROM — fatos verificados no WebMSX

Tudo nesta seção foi lido do código do emulador em `src/main/msx/slots/`, não
presumido.

### 5.1 Escolha do mapper: Konami

```js
// CartridgeKonami.js — read()
case 0x4000: return bytes[address - 0x4000];   // FIXO no segmento 0
case 0x6000: return bytes[bank2Offset + address];
case 0x8000: return bytes[bank3Offset + address];
case 0xa000: return bytes[bank4Offset + address];
```

O Konami mantém `4000h–5FFFh` permanentemente no segmento 0 da ROM. Isso dá
**8KB residentes de graça** — exatamente onde header, trampolim, ISR e a rotina
de paginação precisam morar, já que código que troca banco não pode ser paginado
embaixo de si mesmo. Nos demais mappers todas as janelas comutam e a residência
vira disciplina manual.

Bônus decisivo: no `reset()` o Konami mapeia os segmentos 0,1,2,3 linearmente em
`4000h–BFFFh`. **Os primeiros 32KB de uma MegaROM Konami se comportam byte a
byte como uma ROM flat de 32KB** — e o Pong v24 ocupa apenas 16KB
(`CART = 16 * 1024` em `build_pong.py`; o `pong-ai.rom` publicado tem 16384
bytes), portanto cabe folgado no primeiro segmento. O port não precisa de
adaptação, só ganha os bancos seguintes.

### 5.2 Aritmética de 2MB

| Mapper | Banco | Bancos em 2MB | Registrador | Teto |
|---|---|---|---|---|
| Konami / ASCII8 | 8KB | 256 | 8 bits (`value % numBanks`) | **2MB — exatamente o teto** |
| ASCII16 | 16KB | 128 | 7 bits usados | 4MB |

2MB é o limite superior do Konami/ASCII8, não um ponto confortável. Passar disso
obriga ASCII16, com janelas de 16KB e menos granularidade.

### 5.3 A armadilha da detecção automática

Em `SlotFormats.js`, ASCII8 (911), ASCII16 (912), Konami (913) e KonamiSCC (914)
têm **condição de detecção idêntica**: conteúdo múltiplo de 8K/16K começando com
`"AB"`. Em `SlotCreator.js`, `getFormatOptions` ordena por
`a.prioritySelected - b.prioritySelected` e devolve `options[0]` — vence a
prioridade **menor**.

Consequência: uma ROM de 2MB nossa seria carregada como **ASCII8**, em silêncio,
com as janelas erradas.

Solução verificada: `HINTS_PREFIX_REGEX = "\\["` e
`FORMAT_FORCE_PRIORITY_BOOST = 5000` fazem o nome do arquivo forçar o formato. O
builder emite **`meujogo [Konami].rom`** — o colchete não é enfeite, é o que faz
o WebMSX escolher certo.

### 5.4 A armadilha estrutural

As janelas de troca de banco ficam **dentro** da região lida como ROM. Um
`ld (hl),a` com `HL` corrompido apontando para `8000h` não escreve em lugar
nenhum — **troca o banco embaixo do PC em execução**, e o jogo salta para o
nada. É uma classe de bug que não existe em ROM flat.

Mitigação: `trace_rom.js` reporta qualquer escrita em faixa de mapper que não
venha da rotina de paginação.

### 5.5 Espelho de banco em RAM

Os registradores de mapper são **write-only**: o código não consegue perguntar ao
hardware qual banco está ativo. O runtime mantém `PG_CUR_B/C/D` em `BSS`, e
`FARCALL` salva/restaura a partir desse espelho.

## 6. Runtime Z80 (`msxbuild/rt/`)

### 6.1 Inventário extraído do Pong v24

| Módulo | Rotinas de origem |
|---|---|
| `vdp` | `VREG` `VREGS` `VREGL` `SETV` `VWR` `VFILL` `WVB` `PALSET` |
| `screen` | `SETG4` (SCREEN 5) `SETG3` (SCREEN 2) `CLRBG` `CLRNAM` `SCRINI` |
| `sprite` | `SPRUP` `SATCLR` `SPRPAT` `COLINIT` `CHMSP` |
| `text` | `FNTW` `FNTC` `PRSTR` `PRSTR5` — fonte 5x7 |
| `draw` | `PIX8` `CHMAP` |
| `lz` | `LZUN` `LZ0..LZFL` — par de `tools/lz.py` |
| `psg` | `PSGW` `PSGI` `PSGON` `PSGOFF` |
| `ym2413` | `FMW` `FMI` `FMSEQ` `FMINI` `FMON` `FMOFF` `INSTAB` |
| `music` | `MUSIC` `MVOZ` `MVNEXT` `MVPLAY` `MTRK` `MDECAY` `AUDSET` — player RLE 3 vozes |
| `sfx` | `SFXW` `SFXH` `SFXS` — modo ritmo do YM2413 |
| `input` | `GINIT` `KROW` `JOY` `INPUT` — matriz PPI + joystick |
| `mapper` | novo — `PG_SET_B/C/D` `FARCALL` `PG_PUSH` `PG_POP` |

Fica em `games/pong/`, fora da biblioteca: game loop, raquete, IA, bola, placar,
telas de título e fim, tabela de dificuldade.

Convenções do runtime, uniformes entre módulos: prefixo por módulo nos símbolos
públicos, `@@` para labels internos, registradores destruídos documentados no
cabeçalho de cada rotina, variáveis exclusivamente em blocos `BSS`.

### 6.2 Trilha de composite por blitter (pós-v1)

Especificada em [`docs/msx2-spec-grafica.md`](../../msx2-spec-grafica.md):
desenhar personagens e bosses pelo command engine do V9938 em vez de sprites de
hardware, com double buffer em páginas de VRAM e sprites usados apenas como
hitboxes invisíveis.

Módulos adicionais que essa trilha exige. **Nenhum é extração — o Pong v24 não
toca no command engine** (validado em `msx2-spec-grafica.md` §9.5):

| Módulo | Responsabilidade |
|---|---|
| `blit` | Driver do command engine. R#32–R#45, disparo por R#46, espera do bit CE em S#2. `LMMM`+`TIMP` para objeto, `HMMM` para restaurar fundo, `LMMV`/`HMMV` para preenchimento |
| `page` | Páginas de VRAM e double buffer. Troca da página visível por R#2 no vblank |
| `palette` | Partição de paleta, fade por tabela pré-calculada, ciclo de cores. R#16 mais duas escritas na porta `#9A` |
| `collide` | Hitboxes invisíveis (cor 0, `CC=0`). Leitura de S#0 bit 5 uma vez por frame, coordenadas em S#3–S#6, desambiguação por geometria. `SPR_HIDE` usando `Y >= 212` e nunca `216` |
| `anim` | Tabela de frames com hitboxes embutidas, emitida junto com o bitmap |

Duas regras da spec gráfica viram **rotina do runtime, não convenção
documentada**, porque convenção se esquece e o bug resultante é silencioso:

- esconder hitbox com `Y >= 212`; `Y = 216` encerra o processamento da lista
  inteira a partir daquele slot, apagando os sprites seguintes (confirmado em
  `VDP.js:1930`);
- contador de raster instrumentado desde o primeiro dia, porque o orçamento de
  blits por frame **não é mensurável no emulador** (§9.3) e terá de ser fechado
  no alvo real.

## 7. `msxbuild` — camada Python

```python
# games/pong/build.py
from msxbuild import Project

p = Project("pong", mapper="flat16k")

p.font("art/font5x7.png")
p.image("art/logo.bmp", compress="lz")
p.music("midi/animal-100pm.mid", chip=("psg", "ym2413"), voices=3)
p.notes_table("psg", "ym2413")

p.build("game.asm", out="release/")
```

Cada chamada devolve um handle com os símbolos gerados (`logo.symbol`,
`logo.size_bytes`), então o `.asm` referencia nomes que o Python provou existir,
em vez de o autor escrever `LOGO_DATA` na mão e descobrir o erro de digitação no
assembler.

Com mapper, `p.image("mundo2.bmp", bank="auto")` aloca o banco e emite a
constante do banco junto com o símbolo, para `FARCALL`/`PG_SET` receberem o
número certo sem contagem manual.

Conversores derivados do que já existe: `bmp2msx.py`, `lz.py`, `midparse.py` e
`mid2pong.py` — este último generalizado, pois hoje codifica escolhas do Pong
(3 vozes fixas, seleção da mais aguda e da mais grave).

Na saída, o nome do arquivo carrega o hint de formato quando há mapper
(seção 5.3).

### 7.1 O que a trilha de blitter acrescenta à camada Python

A spec gráfica empurra trabalho decisivo para o lado Python, e isso é o
argumento mais forte a favor da escolha híbrida da seção 2:

- **Packer de frames em VRAM.** Empacotar frames de animação nas páginas 2 e 3 e
  emitir `(src_x, src_y, w, h)` por frame. É bin-packing 2D com orçamento duro:
  com double buffer sobram 64KB, não 96KB. O packer **falha no build** quando não
  cabe, em vez de o jogo corromper VRAM em runtime.
- **Dithering gravado no bitmap.** A spec exige o padrão ancorado nas coordenadas
  do objeto, nunca gerado em runtime ancorado na tela — senão o padrão "anda" sob
  o objeto e vira chuvisco. Isso é conversão de asset, e é exatamente o tipo de
  trabalho que não cabe em assembly.
- **Hitbox emitida da mesma fonte que o frame.** A spec avisa que, se as
  coordenadas de sprite forem calculadas em outro lugar, a hitbox descola do
  desenho durante a animação. O gerador emite bitmap e tabela de hitbox da mesma
  passagem, tornando o descolamento impossível por construção em vez de por
  disciplina.
- **Validador de partição de paleta.** As entradas 14 e 15 são exclusivas do HUD
  e nunca podem ser tocadas por fade ou ciclo de cores. O build recusa um efeito
  declarado sobre faixa reservada.
- **Tabelas de fade.** Curva não linear com mais passos na faixa escura — com 8
  níveis por canal, fade linear fica visivelmente escadeado.

## 8. Testes

### Nível 1 — unidade, Python puro

`msxasm` testado sem MSX nenhum: cada opcode codifica para o byte correto,
`INCLUDE` circular é detectado, macro com label local não colide entre
expansões, `BSS` acusa colisão de símbolo, banco estourando a janela falha,
`call` cruzando banco sem `FARCALL` é rejeitado. Roda em milissegundos e é onde
a maior parte dos bugs do assembler morre.

### Nível 2 — ROM headless

`trace_rom.js` já executa a ROM no Z80 real do WebMSX. Vira teste: roda N frames
com input roteirizado e afirma sobre estado (VRAM, registradores VDP, RAM). Ganha
também o detector de escrita indevida em faixa de mapper (seção 5.4).

### Nível 3 — o gate de regressão do Pong

**"Byte-compatível no comportamento" não pode ser comparação de binário.** A
biblioteca vai reordenar código, mudar endereços de RAM (justamente por causa do
`BSS`) e realocar rotinas. Os dois `.rom` serão diferentes byte a byte e ambos
corretos.

O que se compara: as duas ROMs rodam sob o mesmo harness com a **mesma sequência
roteirizada de input**, e se comparam os **traços de escrita no VDP e nos chips
de som, quadro a quadro**. Traços idênticos significam comportamento idêntico —
inclusive música, IA e placar. Divergência aponta o quadro exato e o que mudou.

Isso é viável porque **o Pong é determinístico**: uma varredura por fontes de
aleatoriedade (`ld a,r`, seed, RNG) em `build_pong.py` não encontrou nenhuma.

**E o build também é determinístico**, o que dá um segundo ponto de apoio:
`build_pong.py` executado duas vezes produz bytes idênticos, e o resultado bate
com o `pong-ai.rom` publicado — 16384 bytes, `md5 03324e8f4febc0e537c9c808c6c33c00`.

Esse hash é o **golden file** do projeto. Ele permite refatorar o assembler
existente com rede: qualquer mudança em `msxasm` que ainda produza exatamente
esses 16384 bytes a partir do mesmo fonte preservou a codificação de opcodes.
Sem isso, reescrever um assembler que já monta um jogo real seria trocar código
provado por código novo sem forma de comparar.

Requer capacidade que hoje não existe: **input roteirizado** — o harness precisa
injetar teclado e joystick por script.

## 9. Repositório

- Nome: `msxAIbuilder`, conta `alexmoncks`, público.
- Licença: Apache-2.0, com `NOTICE`.
- Branch principal: `main`.

`.gitignore`:

```gitignore
*.rom
*.zip
build/
release/
__pycache__/
*.pyc
.idea/
node_modules/
```

**WebMSX como submodule em `vendor/webmsx`.** O Git guarda apenas o ponteiro de
commit, não os arquivos. O clone atual **não tem arquivo de licença**
(`git ls-files` não encontra nenhum), embora os fontes tragam cabeçalho de
copyright do autor; referenciar por submodule evita redistribuir código de
terceiros sem licença clara.

**Pré-requisito:** o fork `alexmoncks/WebMSX` ainda não existe e precisa ser
criado antes de configurar o submodule.

Sobe para o repositório: `msxasm/`, `msxbuild/` (incluindo o runtime `.asm`),
`games/*/` (fontes, arte-fonte, MIDI), `tests/`, `docs/` (o `MANUAL_DEV_MSX.md`
e a anatomia da ROM têm valor direto aqui), `Dockerfile` e `run.sh`.

## 10. Fora de escopo da v1

- Tree-shaking de rotinas não usadas — quebra com jump table e código
  automodificante, que o Pong já usa.
- Suporte a ASCII8, ASCII16, KonamiSCC e demais mappers além de Konami e flat
  flat. A arquitetura de `MAPPER` os acomoda; a v1 não os implementa.
- ROMs acima de 2MB.
- Port do Pong para MegaROM. Ele permanece flat 16KB na v1.
- Scroll, mapas de tile e sistema de colisão genérico — entram quando um jogo
  concreto pedir.
- **A trilha inteira de composite por blitter** (seção 6.2 e
  `docs/msx2-spec-grafica.md`): `blit`, `page`, `palette`, `collide`, `anim`, o
  packer de frames em VRAM e o dithering na conversão de asset. Motivo na seção
  11.

## 11. Riscos

**O port do Pong é a maior fatia de trabalho, não a biblioteca.** São 2.400
linhas com endereços de RAM literais que precisam virar símbolos `BSS`, um a um.
É trabalho mecânico e de alto risco de erro por digitação — o gate de regressão
existe exatamente para pegar isso.

**Validação de `call` entre bancos é heurística.** O assembler enxerga `call
SIMBOLO` mas não enxerga `ld hl,SIMBOLO` seguido de `jp (hl)`. A validação pega o
caso comum, não todos.

**A trilha de blitter é código novo, não extração — e não pode ser validada
como o resto.** O Pong v24 não toca no command engine (`msx2-spec-grafica.md`
§9.5), então não há código provado de onde extrair `blit.asm`, `page.asm` ou o
packer de frames. Some a rede de segurança que justifica a v1 inteira: o gate de
regressão do Pong prova que a extração não quebrou nada, mas não prova nada
sobre código que nunca existiu.

Agrava isso o fato de que **o orçamento de ciclos do blitter não é mensurável no
emulador** (§9.3): o WebMSX estima a duração dos comandos e explicitamente não
modela a disputa por slots de acesso à VRAM, que é justamente a variável que
decide quantos objetos cabem em tela. Um design de jogo fechado sobre um número
saído do emulador pode não caber no hardware.

Por isso a trilha fica fora da v1 e pede um jogo-alvo próprio, com o contador de
raster instrumentado desde o primeiro dia e medição no alvo real antes de fechar
densidade de objetos.

**O harness de teste depende de `src/main/**` do WebMSX** carregado via
`vm.runInContext`. Uma mudança na estrutura interna do emulador quebra os testes;
o submodule fixado em commit protege contra isso até o momento em que se decidir
atualizar.
