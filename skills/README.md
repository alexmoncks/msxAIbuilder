# skills/

Conhecimento de hardware MSX empacotado como skill de agente, instalável em
Claude Code, Codex, Copilot CLI e Gemini CLI.

## `writing-msx-roms`

Seis arquivos de referência extraídos de um cartucho MSX2 real — o mesmo Pong
AI v24 que deu origem a este repositório. Cada armadilha documentada corresponde
a uma falha que aconteceu e custou tempo.

| Arquivo | Conteúdo |
|---|---|
| `SKILL.md` | Ponto de entrada, caminho mínimo de um cartucho, índice de sintomas |
| `references/armadilhas.md` | 10 falhas silenciosas com causa e correção, checklist de tela em branco |
| `references/vdp.md` | V9938: portas, modos, os 12 registradores, máscaras de base, paleta |
| `references/sprites.md` | Sprite mode 2: cor por linha, `CC`, `EC`, `MAG`, limites |
| `references/audio.md` | PSG, YM2413 melódico e modo ritmo, um tocador para os dois chips |
| `references/entrada.md` | Matriz de teclado pelo PPI e joystick pelo PSG |
| `references/toolchain.md` | Onde os bugs de montador nascem, asserções de build, a regra dos dois harnesses |

Instalação em [`writing-msx-roms/INSTALACAO.md`](writing-msx-roms/INSTALACAO.md).

## Relação com o resto do repositório

A skill é **referência de hardware**: o que o V9938 e os chips de som fazem, e
como falham em silêncio. O [manual](../docs/manual.md) cobre o mesmo terreno em
prosa mais longa, com análise de dois jogos reais. A
[referência do msxasm](../docs/referencia.md) é outra coisa — sintaxe do
montador deste repositório, não hardware.

Está em português. Traduzir foi deixado para depois; o manual, que cobre o mesmo
material, existe nos três idiomas.
