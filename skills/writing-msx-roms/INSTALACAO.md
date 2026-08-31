# Instalação

Copie a pasta `writing-msx-roms/` para o diretório de skills do seu runtime:

| Runtime | Diretório |
|---|---|
| Claude Code | `~/.claude/skills/` |
| Codex · Copilot CLI · Gemini CLI | `~/.agents/skills/` |

```bash
cp -r skills/writing-msx-roms ~/.claude/skills/
```

A skill é reconhecida na próxima sessão. Nada mais é necessário — não há
dependências, scripts nem configuração.

## Conteúdo

```
writing-msx-roms/
  SKILL.md                    ponto de entrada e índice de sintomas
  references/armadilhas.md    as falhas silenciosas, com causa e correção
  references/vdp.md           V9938: modos, registradores, máscaras, VRAM, paleta
  references/sprites.md       sprite mode 2: cor por linha, CC, EC, MAG
  references/audio.md         PSG, YM2413 melódico e modo ritmo, tocador de música
  references/entrada.md       matriz de teclado e joystick pelo PSG
  references/toolchain.md     montador, asserções de build, harnesses de teste
```

## Escopo

MSX / MSX2 em assembly Z80, cartucho de 16 ou 32 KB, verificado contra o
WebMSX 6.0.8 (`src/main/msx/video/VDP.js` e `src/main/msx/cpu/CPU.js`).

Fora de escopo: MSX BASIC, disco/BDOS, turbo R, e emuladores cujo comportamento
de VDP difira do WebMSX.

## Versão

v1 — extraída de um projeto real de cartucho MSX2 (jogo completo em G3 + G4,
PSG/YM2413, dois jogadores). Cada armadilha documentada corresponde a uma falha
que de fato aconteceu e custou tempo.

Este é o mesmo projeto que deu origem ao repositório onde a skill agora vive: o
Pong AI v24, cuja ROM está em [`roms/`](../../roms/) e cujo montador foi
refatorado como o pacote [`msxasm`](../../docs/referencia.md).

Vale notar que várias armadilhas aqui documentadas foram **redescobertas do
zero** durante essa refatoração, porque o conhecimento estava fora do alcance de
quem trabalhava — entre elas `armadilhas.md` item 8 (parênteses em imediato) e
`toolchain.md` (silenciar exceções no avaliador). É o argumento para a skill
morar junto do código.
