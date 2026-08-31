# Spec Gráfica — Projeto MSX2

**Idiomas:** [Português](msx2-spec-grafica.md) · [English](msx2-graphics-spec.en.md) · [Español](msx2-spec-grafica.es.md)

Documento de decisões de arquitetura gráfica. Alvo: MSX2 (V9938), SCREEN 5.
Status: decisões fechadas em conversa, pendente de validação contra o código existente.

---

## 1. Modo de vídeo e uso da VRAM

**SCREEN 5 (Graphic 4)**, 256x212, 16 cores simultâneas de uma paleta de 512.
VRAM de 128KB dividida em 4 páginas de 32KB.

| Página | Uso |
|--------|-----|
| 0 | Buffer visível / double buffer A |
| 1 | Buffer de trabalho / double buffer B |
| 2 | Banco de tiles do cenário |
| 3 | Frames de animação do personagem e do boss |

A troca de página visível é feita por R#2, custo de uma escrita de registrador, executada no vblank.

**Atenção ao layout interno da página.** As tabelas de sprite não vivem numa página separada: cada página de 32KB tem as suas, nos offsets padrão do BIOS (aproximadamente base+#7400 cores, base+#7600 atributos, base+#7800 padrões). Como as páginas 0 e 1 alternam como visíveis, as tabelas de sprite das duas precisam ser mantidas em sincronia, ou aceita-se um frame de atraso na hitbox.

> **Corrigido na validação — ver §9.2.** A sincronia não é necessária. As tabelas
> de sprite são endereçadas por R#5/R#11 e R#6, independentes de R#2. Virar a
> página visível não move as tabelas: aponta-se as duas páginas para um único
> conjunto e o problema desaparece, junto com o frame de atraso.

**Consequência de orçamento:** com double buffer, sobram 64KB (páginas 2 e 3) para tiles e frames, não 96KB.

---

## 2. Desenho de personagens (blitter)

Todo personagem, boss e elemento animado é desenhado pelo command engine do V9938. Nenhum sprite de hardware é gasto com o desenho visível.

**Comando padrão:** `LMMM` com operação lógica transparente (`TIMP`), copiando o frame da página de banco para a página de trabalho.

Sequência por objeto:
1. Restaurar o fundo na posição anterior (`HMMM` da página de cenário limpo)
2. Copiar o frame novo (`LMMM` + `TIMP`)

Registradores envolvidos: R#32 a R#45 (SX, SY, DX, DY, NX, NY, CLR, ARG) e R#46 (CMR, dispara o comando). Antes de escrever um novo comando, verificar o bit CE em S#2.

**Orçamento de ciclos.** O blitter disputa acesso à VRAM com o refresh de tela. É bem mais rápido com display desligado ou durante o vblank. O número real de blits de 16x16 por frame precisa ser medido no alvo antes de fechar a densidade de objetos em tela. Marcar isso como tarefa de instrumentação (contador de raster).

**Comandos H vs L.** Os `H*` operam em bytes inteiros (mais rápidos, granularidade de 2 pixels em SCREEN 5). Os `L*` operam pixel a pixel e aceitam operação lógica. Usar `H*` para restauração de fundo alinhada e `L*` para o desenho do objeto.

---

## 3. Colisão

### 3.1 Colisão entre objetos: sprites transparentes

A detecção de colisão do V9938 olha os bits do padrão, não a cor. Um sprite com cor 0 não é renderizado mas continua colidindo. Isso permite hitboxes invisíveis.

**Regra do projeto:** hitbox aplicada apenas aos pontos fracos, não à silhueta. Um boss de 64x48 gasta 3 sprites (cabeça, núcleo, cauda) em vez de 12 para cobrir o corpo inteiro. Ganho técnico e de gameplay ao mesmo tempo: o jogador precisa mirar.

**Configuração:**
- Sprite mode 2, cor 0 nas hitboxes
- Bit CC = 0 nas hitboxes, no jogador e nos tiros (participam da colisão)
- Bit CC = 1 em qualquer sprite decorativo (não participa)
- Magnificação ativa quando o ponto fraco for grande: um sprite de 16x16 magnificado cobre 32x32 gastando um slot só. A granularidade de 2 pixels é irrelevante para hitbox

**Leitura por frame:**
- S#0 bit 5 (flag C): houve colisão. A leitura de S#0 limpa a flag, então ler uma vez por frame
- S#3/S#4 (X) e S#5/S#6 (Y): coordenadas do ponto de colisão

**Resolução da ambiguidade.** A flag é global e não diz quem colidiu. Estratégia: usar a coordenada lida para identificar o ponto fraco por geometria. Se os pontos fracos estão em faixas Y distintas, o Y resolve sozinho. Se coincidem em Y, o X resolve. Só quando ambos coincidem é que se roda bounding box em software, e apenas nos objetos próximos da coordenada lida.

**Orçamento de sprites.** Limite de 8 por linha de varredura. Testar o pior caso: jogador colado no boss disparando tiro múltiplo. Com 3 pontos fracos há folga; a partir de 5 o teste passa a ser obrigatório.

**Correção sobre remover uma hitbox.** Para desativar um ponto fraco destruído, mover o sprite para fora da tela (Y >= 212). Não usar Y = 216 para isso: em sprite mode 2 esse valor encerra o processamento da lista inteira a partir daquele slot, apagando também os sprites seguintes.

### 3.2 Colisão com cenário

Mapa de colisão em RAM indexado por tile. Nunca usar `POINT` nem leitura de VRAM para isso, custo alto demais por consulta.

---

## 4. Paleta

16 entradas, cada canal com 3 bits (valores de 0 a 7). Não é RGB contínuo: são 8 níveis por componente, discretos.

### 4.1 Partição

| Faixa | Uso |
|-------|-----|
| 0 | Transparente |
| 1 a 5 | Cenário |
| 6 a 11 | Personagem e boss (6 entradas) |
| 12 a 13 | Efeitos e acentos |
| 14 a 15 | HUD, exclusivo |

A sexta entrada do personagem foi tirada do cenário, não dos efeitos. Justificativa: áreas grandes e chapadas de fundo absorvem dithering bem melhor que um objeto pequeno em movimento, que cintila.

Com 6 entradas o personagem ganha duas rampas de 3 tons (corpo e detalhe) ou uma rampa de 4 mais 2 acentos, em vez de uma rampa única espremida.

### 4.2 HUD

Entradas 14 e 15 são exclusivas e nunca tocadas por fade, flash ou ciclo de cores. Sem isso, o placar pisca junto com o efeito de dano.

Se o HUD ocupar uma faixa fixa da tela, ele é candidato a split de paleta por linha (R#19 + IE1), o que devolve essas entradas ao cenário na parte de cima da tela.

### 4.3 Efeitos

Escrita: setar R#16 com a entrada, depois 2 escritas na porta #9A (um byte com R e B, outro com G). Paleta inteira em 32 escritas, cabe no vblank.

- **Fade:** tabela pré-calculada com curva não linear, mais passos na faixa escura. Com 8 níveis por canal, fade linear fica visivelmente escadeado. Espaçar os passos em 2 ou 3 frames
- **Ciclo de cores:** rotacionar 3 ou 4 entradas para água, lava, portais. Custo quase zero, alto retorno visual
- **Flash de dano do boss:** preferir `LMMV` com operação lógica sobre a área do boss por 2 frames, em vez de mexer na paleta. Como personagem e boss compartilham as entradas 6 a 11, um flash por paleta piscaria os dois

---

## 5. Dithering

Usado para compensar a partição de paleta, principalmente no cenário.

**Regra obrigatória:** o padrão xadrez é gravado dentro do bitmap do frame, ancorado nas coordenadas do objeto. Nunca gerado em runtime ancorado na tela. Se ancorar na tela, o padrão "anda" sob o objeto em movimento e vira chuvisco.

Escolher pares com diferença pequena de luminância. Em composite a mistura horizontal ajuda; em RGB, par muito contrastado aparece como grade.

---

## 6. Estrutura de dados de animação

Cada frame de animação carrega, além do bitmap:

```
frame:
  vram_src_x, vram_src_y     ; origem na página de banco
  width, height
  n_hitboxes
  hitbox[]:
    dx, dy                   ; offset relativo à âncora do objeto
    sprite_slot
    weak_point_id
```

Os offsets das hitboxes saem da mesma tabela que define o frame. Se as coordenadas dos sprites forem calculadas em outro lugar, a hitbox descola do desenho durante a animação.

---

## 7. Pendências

- [ ] Medir custo real de `LMMM` 16x16 com display ligado no alvo, e fechar o número máximo de objetos por frame
- [ ] Testar pior caso de 8 sprites por linha (jogador colado no boss com tiro múltiplo)
- [ ] Definir a paleta concreta (valores RGB das 16 entradas)
- [ ] Decidir se o split de paleta por linha entra na v1 ou fica para depois
- [ ] Validar esta spec contra o código já existente no repositório

---

## 8. Notas de alternativas descartadas

- **SCREEN 8:** 256 cores fixas, mas perde a paleta programável (tons de azul e verde ruins), cai para 2 páginas e o blitter fica mais lento por pixel. Descartado para um jogo com boss animado
- **SCREEN 12 (YJK, MSX2+):** só se o alvo mudar para MSX2+. Ressalva: artefato de croma visível em bordas de alto contraste
- **Hitbox cobrindo a silhueta inteira:** estoura o orçamento de 8 sprites por linha sem ganho de gameplay

---

## 9. Validação contra o código (pendência §7, item 5)

Feita em 2026-08-31 contra o WebMSX v6.0.8 (`4f4009e8`), o mesmo commit fixado
em `vendor/webmsx`, e contra `tools/build_pong.py` do Pong AI v24. Cada item
abaixo foi lido no código, não presumido.

### 9.1 Y = 216 encerra a lista — CONFIRMADO

```js
// src/main/msx/video/VDP.js:1930
if (y === 216) break;    // Stop Sprite processing for the line, as per spec
```

O emulador implementa exatamente o comportamento descrito em §3.1. A regra de
esconder hitbox com `Y >= 212` e nunca `216` está correta e deve virar rotina do
runtime (`SPR_HIDE`), não convenção documentada — convenção se esquece.

### 9.2 Sincronia de tabelas de sprite entre páginas — DESNECESSÁRIA

A §1 conclui que as tabelas de sprite das páginas 0 e 1 precisam ser mantidas em
sincronia. A premissa é verdadeira (o layout padrão do BIOS coloca um conjunto
de tabelas dentro de cada página de 32KB), mas a conclusão não se sustenta.

```js
// src/main/msx/video/VDP.js:362,471 — R#2 mexe SO na tabela de layout
case 2: if (mod & 0x7f) updateLayoutTableAddress();
    var add = ... (register[2] & 0x7f) << 10;

// src/main/msx/video/VDP.js:389,487 — sprites vem de R#5/R#11 e R#6
spriteAttrTableAddress    = add & modeData.sprAttrTBase;   // R#5 / R#11
spritePatternTableAddress = ...                            // R#6
```

R#2 endereça o bitmap. As tabelas de sprite são endereçadas por registradores
distintos. **Virar a página visível não move as tabelas de sprite.** Basta deixar
R#5/R#11/R#6 apontando para um único conjunto e as duas páginas o compartilham.

Consequências: some o trabalho de sincronizar por frame, some o frame de atraso
na hitbox, e a escolha de qual página hospeda as tabelas vira arbitrária. O custo
é 2KB gastos numa página; a região equivalente na outra página fica livre para
dados, desde que o packer saiba que ela não é contígua.

### 9.3 Custo do blitter NÃO é mensurável no WebMSX — pendência §7 item 1 bloqueada

```js
// src/main/msx/video/VDPCommandProcessor.js:3
// Commands perform all operation instantaneously at the first cycle.
// Duration is estimated and does not consider VRAM access slots
```

A §2 quer medir quantos blits de 16x16 cabem num frame, e identifica
corretamente a causa: o blitter disputa acesso à VRAM com o refresh de tela.
**Essa disputa é justamente o que o WebMSX não modela.** A duração é estimada
por uma fórmula com fator de correção fixo (`COMMAND_PER_PIXEL_DURATION_FACTOR
= 1.1`), e o comando executa inteiro no primeiro ciclo.

O harness headless serve para provar *correção* do blitter — os pixels certos
no lugar certo. Não serve para fechar orçamento de ciclos. Esse número precisa
de hardware real ou de um emulador com timing de VDP mais fiel.

**Consequência de projeto:** a densidade de objetos em tela não pode ser decidida
no emulador. O runtime deve expor um contador de raster instrumentado desde o
início, para que a medição seja feita no alvo assim que houver hardware, sem
retrabalho.

### 9.4 Estimativas relativas de custo por comando

Ainda que os números absolutos não valham (§9.3), a ordem relativa vem do
código e sustenta a regra "H* para fundo, L* para objeto" da §2:

| Comando | Ciclos por unidade | Por linha |
|---|---|---|
| `YMMM` | 40R + 24W = 64 | 0 |
| `HMMV` | 48W | 56 |
| `HMMM` | 64R + 24W = 88 | 64 |
| `LMMV` | 72R + 24W = 96 | 64 |
| `LMMM` | 64R + 32R + 24W = 120 | 64 |

`LMMM` custa ~1,4x `HMMM` por unidade — e como em SCREEN 5 os `H*` operam sobre
bytes de 2 pixels, a razão por área desenhada aproxima-se de 2,7x. A regra da §2
está certa e o ganho é maior do que "mais rápido" sugere.

### 9.5 O Pong não usa o command engine — ISTO É CÓDIGO NOVO

Varredura em `tools/build_pong.py` por portas `#9B`, registradores R#32 a R#46 e
nomes de comando não encontrou nenhuma ocorrência. O Pong AI v24 desenha
inteiramente por sprites de hardware e escrita direta em VRAM.

Não há nada a extrair para o módulo de blitter. `blit.asm`, `page.asm` (double
buffer) e o packer de frames em VRAM são **código novo escrito do zero**, não
refatoração de código provado. É a maior fatia de risco técnico do projeto, e
merece um jogo-alvo próprio em vez de entrar de carona no port do Pong.
