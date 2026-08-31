# msxasm — referência

**Idiomas:** [Português](referencia.md) · [English](reference.en.md) · [Español](referencia.es.md)

Assembler Z80 para cartuchos MSX. Duas passagens, sem dependências fora da
biblioteca padrão do Python.

```
msxasm FONTE -o SAÍDA [--org ENDEREÇO] [--size TAMANHO]
              [-I CAMINHO]... [--bank-map ARQUIVO]
```

| Opção | Significado | Padrão |
|---|---|---|
| `-o`, `--output` | ROM de saída | obrigatório |
| `--org` | Endereço de montagem, quando o fonte não declara `org` | `0x4000` |
| `--size` | Tamanho do cartucho | `16K` |
| `-I`, `--include-path` | Diretório extra para resolver `INCLUDE` e `INCBIN` | — |
| `--bank-map` | Grava o mapa símbolo → (banco, endereço) | — |

Erro de montagem sai como mensagem com `arquivo:linha`, código de saída 1, e
**nenhuma ROM é escrita**. ROM parcial em disco parece pronta.

## Grafia numérica

Uma gramática só, aceita em todo lugar — diretivas, expressões e argumentos de
linha de comando:

| Forma | Exemplo | Valor |
|---|---|---|
| Sufixo `K` / `M` | `16K`, `2M` | múltiplos de 1024 |
| Sufixo `H` (Intel) | `0C000h`, `4000h` | hexadecimal |
| Prefixo `0x` / `0b` / `0o` | `0x4000`, `0b1010` | estilo Python |
| Decimal | `49152` | — |

O sufixo é testado antes do prefixo: `0BEEFh` é hexadecimal terminado em `h`,
não binário começando em `0b`.

## Diretivas do Z80

`ORG`, `DB`, `DW`, `DS`, `INCBIN`, `EQU` — o conjunto tradicional.

`INCBIN "arquivo"` embute um binário. O caminho resolve relativo ao arquivo
**que contém a linha**, depois pelo `-I`. Arquivo ausente é erro, não silêncio.

Um label na própria linha do `ORG` (`INICIO: ORG 4000h`) resolve para o
endereço **depois** do `ORG`. As outras diretivas ligam o label ao endereço
anterior a elas, como de praxe.

## `INCLUDE`

```asm
    INCLUDE "rt/vdp.asm"
```

Resolve relativo ao arquivo incluidor, depois pelo `-I`. O mesmo arquivo
incluído duas vezes entra **uma vez só** — módulos de runtime dependem uns dos
outros e um guard manual em cada arquivo seria ruído repetido. Inclusão
circular é erro com a trilha completa, nunca recursão infinita.

Cada linha do fonte achatado guarda o arquivo e o número de origem. Um erro
dentro de `vdp.asm` aponta `vdp.asm:12`, não um deslocamento do achatado.

## Labels locais

```asm
PSG_ON:
@@laco:
    djnz @@laco
```

`@@nome` pertence ao último label global acima dele, virando `PSG_ON@@laco`.
Dois módulos podem ter cada um o seu `@@laco` sem colidir.

Sem escopo local, essa colisão é **silenciosa**: o segundo módulo simplesmente
salta para o label do primeiro.

`@@` dentro de comentário ou de string literal não é reescrito.

## Macros

```asm
    MACRO VDP_REG reg, valor
    ld      a,valor
    ld      b,reg
    call    VDP_SET_REG
    ENDM

    VDP_REG 7, 0F4h
```

Parâmetros posicionais. Cada expansão sufixa os labels locais do corpo, então
duas invocações não geram labels iguais.

Restrições, todas com erro claro:

- nome de parâmetro igual a registrador ou flag do Z80 é recusado — um
  parâmetro chamado `a` transformaria `ld a,n` em `ld 5,n`;
- número de argumentos diferente do declarado é erro;
- macro aberta sem `ENDM` é erro;
- redefinir uma macro é erro, com as duas localizações.

Substituição não acontece dentro de string literal nem de comentário.

> **Armadilha.** Um argumento que **começa com parêntese** muda o modo de
> endereçamento da instrução expandida. `VDP_REG 7, (15 * 16) + 4` faz
> `ld a,valor` virar `ld a,(240) + 4`, que o Z80 lê como leitura de memória —
> monta sem erro e carrega o byte do endereço 240. Escreva `15 * 16 + 4`.

## `BSS` — alocação de RAM

```asm
    BSS 0C000h
MUS_PTR:    DS 2        ; C000h
MUS_TICK:   DS 1        ; C002h
    ENDBSS
```

Reserva endereço sem emitir byte. O primeiro bloco do fonte achatado declara a
base; os seguintes vêm pelados (`BSS` sem argumento) e continuam de onde o
anterior parou.

O assembler **recusa montar** quando:

- dois símbolos têm o mesmo nome (a comparação ignora caixa);
- duas faixas `[base, base+tamanho)` se sobrepõem — inclusive parcialmente;
- a alocação ultrapassa o limite da RAM;
- um símbolo de `BSS` colide com um label de ROM.

Isto substitui endereços literais espalhados pelo código. Com módulos, dois
que escolham `0C020h` se corrompem mutuamente e nada avisa.

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

| Layout | Banco | Janelas | Residente | Máximo |
|---|---|---|---|---|
| `FLAT` | — | `4000h` | `4000h` | 1 |
| `KONAMI` | 8192 | `4000h` `6000h` `8000h` `A000h` | `4000h` | 256 (2 MB) |

O Konami mantém `4000h–5FFFh` fixo no segmento 0, que nunca pagina. É onde o
cabeçalho, o trampolim e a rotina de troca de banco precisam morar — código
que pagina não pode ser paginado embaixo de si mesmo.

2 MB é o teto exato, não um número redondo: o registrador de banco tem 8 bits
e o emulador aplica `value % numBanks`, logo 256 bancos de 8 KB.

Símbolos do banco residente são visíveis de todos os bancos. Entre dois bancos
paginados, não — e a montagem falha em vez de gerar salto errado.

Um `org` dentro de banco paginado que divirja da `WINDOW` é erro: nessa
sintaxe quem manda é a janela.

### O hint no nome do arquivo não é enfeite

No WebMSX, ASCII8 (prioridade 911), ASCII16 (912), Konami (913) e KonamiSCC
(914) têm condição de detecção **idêntica**, e vence a prioridade menor. Uma
ROM de 2 MB carrega como ASCII8, em silêncio, com as janelas erradas.

Nomeie a ROM com o formato entre colchetes — `meujogo [Konami].rom` — e o
emulador escolhe certo.

## Limitações conhecidas

- Um `EQU` declarado no banco residente **não** atravessa banco; só labels são
  semeados.
- Não existe validação de `FARCALL`. Um `call` para banco paginado falha com
  "símbolo não existe" — mensagem certa pelo motivo errado.
- O mapa de bancos não inclui símbolos de `BSS`.
- Macros não se expandem recursivamente.
- Uma macro não pode ser invocada numa linha que já tenha label.
