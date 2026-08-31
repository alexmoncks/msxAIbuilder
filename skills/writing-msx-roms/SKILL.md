---
name: writing-msx-roms
description: Use when writing or debugging Z80 assembly for MSX/MSX2 cartridge ROMs — VDP/V9938 video setup, sprites, PSG or YM2413 audio, keyboard and joystick input — or when an MSX screen comes out blank, garbled or entirely in the background color, sprites collapse into a single shape, a ROM larger than 16 KB reads garbage, or music goes silent.
---

# Escrevendo ROMs para MSX

## Visão geral

**No MSX quase toda falha é silenciosa.** O VDP não recusa uma configuração
errada — ele desenha outra coisa. O montador não recusa um operando ambíguo —
ele monta outro programa. A BIOS não avisa que metade do seu cartucho não está
mapeada — ela devolve lixo.

Princípio central: **quando a tela ou o som está errado, suspeite primeiro da
configuração de hardware, não da sua lógica.** A lógica falha alto; o hardware
falha calado.

**Não use para:** BASIC do MSX, disco/BDOS, turbo R, ou emuladores que não sejam
o WebMSX — as referências a `VDP.js` e `CPU.js` são específicas dele.

## O caminho mínimo de um cartucho de 32 KB

A ordem importa. Trocar dois passos quebra o resultado.

1. Cabeçalho em `4000h`: `"AB"`, `dw INIT`, e 12 bytes zerados
2. `di` e pilha própria (`ld sp, 0F380h`) — a BIOS não volta a rodar
3. **Mapear a página 2** no slot do cartucho (ver `references/armadilhas.md`)
4. `in a, (99h)` para zerar o latch de dois bytes do VDP
5. Escrever os 12 registradores **com o display apagado** (R#1 bit 6 = 0)
6. Paleta, e só então limpar todas as tabelas de VRAM que o modo exige
7. Silenciar PSG e YM2413 — eles bootam com lixo
8. Só agora ligar o display (R#1 bit 6 = 1)

O laço de quadro sincroniza por polling de `S#0` bit 7 (`in a,(99h)`), que
funciona com as interrupções mascaradas.

## Índice de sintomas

Leia `references/armadilhas.md` antes de depurar. Índice rápido:

| Sintoma | Suspeite de |
|---|---|
| Tela inteira na cor de fundo, VRAM correta | `R#2` — ele define a **máscara** de leitura, não só a base |
| Tiles coloridos aleatórios no boot | Display ligado antes de limpar as tabelas |
| Todos os sprites viram o mesmo desenho | `R#1` bit 1 ligou modo 16×16; o `PN` é mascarado com `0FCh` |
| Sprites somem ou saem em cima do padrão | `R#5` — a máscara do modo zerou a base da SAT |
| Escrita de VRAM cai 16 KB adiante | `R#14` não foi reescrito depois de cruzar `4000h` |
| Dados acima de `8000h` leem lixo | Página 2 ainda está na RAM, não no cartucho |
| Música muda, efeitos funcionam | Mesma causa: as faixas estão acima de `8000h` |
| Constante hexadecimal virou outro número | Montador confundindo literal binário com hex terminado em `0B`/`1B` |
| `ld hl,(VAR)` carregou o endereço | Regra do imediato avaliada antes da do indireto |

## A regra dos dois harnesses

Um modelo funcional do VDP valida lógica de jogo e geometria. Ele **não** valida
modo de vídeo, endereçamento, slots nem paleta — aí ele mostra a imagem certa
enquanto a máquina real mostra tela vazia. Para qualquer mudança de modo, de
registrador de vídeo ou de mapeamento, rode contra o `VDP.js` e o `CPU.js` reais
(`references/toolchain.md`).

**Quando um recurso parece quebrado, confira primeiro se o harness sabe
exercitá-lo** — um teste que só lê a linha 8 do teclado faz o modo dois jogadores
parecer defeituoso quando o defeito é do teste.

## Referências

| Arquivo | Conteúdo |
|---|---|
| `references/armadilhas.md` | As falhas silenciosas, com causa e correção |
| `references/vdp.md` | Modos, 12 registradores, máscaras de base, VRAM, paleta, texto |
| `references/sprites.md` | Sprite mode 2: duas tabelas, cor por linha, CC, EC, MAG |
| `references/audio.md` | PSG, YM2413 melódico e modo ritmo, tabelas de nota |
| `references/entrada.md` | Matriz de teclado e joystick pelo PSG |
| `references/toolchain.md` | Montador caseiro, asserções de build, harnesses de teste |
