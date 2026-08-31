# Montador, build e verificação

## O montador é onde os bugs mais caros nascem

Montadores caseiros (e alguns famosos) resolvem ambiguidades por **ordem de
regras**. Quando a ordem está errada, o resultado não é um erro: é outro
programa.

### Ordem de conversão de literais

Converter hexadecimal antes de binário sem lookbehind destrói constantes:

```
'0C00Bh'  --hex-->  '0x0C00B'
'([01]+)B\b' casa com o '00B' final  -->  '0x0C0'  =  192
```

Qualquer constante terminada em `0B` ou `1B` cai nisso, e `0Bh` vira zero.
A correção é exigir que o caractere anterior não seja hexadecimal nem o `x` de
`0x`:

```python
e = re.sub(r'(?<![0-9A-Fx])([01]+)B\b', lambda m: str(int(m.group(1), 2)), e)
```

### Ordem imediato vs indireto

A regra do imediato de 16 bits testada antes da do endereçamento indireto faz
`ld hl, (VAR)` virar `ld hl, VAR`: carrega o **endereço** em vez do conteúdo.
Teste `ld rr,(nn)` e `ld (nn),rr` **primeiro**.

### Saltos relativos truncados

`jr` alcança `−128…+127`. Sem verificação o deslocamento é truncado em silêncio
e o programa pula para o lugar errado. Emita erro:

```python
if diff < -128 or diff > 127:
    print(f"ASM ERRO: salto relativo fora de alcance ({diff}) — use JP", file=sys.stderr)
```

### Silenciar exceções no avaliador

Um `try/except` largo no avaliador de expressões esconde exatamente a classe de
bug acima. No último passe, deixe a exceção falar.

---

## Asserções de build

Como quase toda falha é silenciosa, transforme cada uma que você já pagou numa
asserção que roda **antes** de o binário existir. Monte o fonte uma vez só para
ler os `equ` e confira:

- Cada variável de RAM cai na faixa esperada (`C000h–C0FFh`, por exemplo)
- Blocos vizinhos não se invadem — um buffer de N bytes contra a variável
  seguinte
- Símbolos que o código percorre com `inc hl` continuam **consecutivos**
- Constantes derivadas ainda batem com a fórmula
  (`BXLP == P1X + PWID`, `BYMAX == SH - SWID - 1`)
- Posições de texto caem na linha que dizem cair e não colidem com a imagem
- Tabelas geradas em Python e `equ` do assembly concordam no tamanho

E depois de montar, o tamanho:

```python
if fim_rom >= 0xC000:
    raise SystemExit(f'ROM estourou 32 KB: último símbolo 0x{fim_rom:04X}')
```

Passar de 32 KB não deixa a ROM só maior — **muda o formato detectado pelo
emulador**, e o mapeamento vira outro.

---

## Dois harnesses, dois propósitos

### Modelo funcional

Carrega o `CPU.js` real com um modelo mínimo do barramento e das portas do VDP.
Rápido, e serve para:

- A CPU escapa da faixa do cartucho?
- Quais faixas de VRAM foram efetivamente escritas, e as tabelas do modo estão
  cobertas?
- Estado das variáveis de jogo, estatísticas de movimento
- Renderizar um quadro *por fora*, a partir da VRAM capturada

### Máquina real

Carrega o `CPU.js` **e o `VDP.js`** reais, com stubs só para canvas, áudio e
monitor, e modela os slots. Mais lento, e é o único que valida:

- Modo de vídeo, `layoutTableAddress` e `layoutTableAddressMask`
- Mapeamento de páginas e slots
- Paleta e o que a tela de fato mostra

```bash
node tools/emu_test.js rom.rom 600 /tmp/tela.png \
     '[[60,64,"BAIXO"],[90,94,"DIREITA"],[150,154,"GATILHO"]]'
```

Aceitar uma lista de teclas com faixas de quadros permite navegar menu, escolher
opções e jogar uma partida inteira sem interação.

### A regra

> Um modelo simplificado valida lógica. Só o VDP real valida vídeo.

O bug do mapeamento da página 2 é invisível num harness que mapeia a ROM
linearmente. O bug do `R#2` é invisível em qualquer coisa que não seja o `VDP.js`
real. Os dois sobrevivem meses justamente porque o teste mais rápido diz que
está tudo certo.

### E o inverso

**Quando um recurso parece quebrado, confira se o harness sabe exercitá-lo antes
de mexer no código de produção.** Um harness de teclado que só responde à linha
8 faz um modo de dois jogadores parecer defeituoso quando o defeito é do teste.

---

## Build reprodutível

O build deve produzir o mesmo binário byte a byte a cada execução, e publicar
copiando o arquivo — não regerando. Um `cmp` contra a ROM publicada é a
verificação mais barata que existe de que o que está rodando é o que está no
fonte.
