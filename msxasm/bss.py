# msxasm/bss.py
"""Alocacao de variaveis em RAM.

Um bloco BSS reserva enderecos sem emitir bytes. Cada modulo declara o seu; o
assembler concatena na ordem de inclusao e recusa montar se dois simbolos
colidirem ou se a RAM estourar.

O que isto substitui: enderecos literais espalhados pelo codigo (0C000h,
0C020h, 0C05Ch). Com um runtime modular, dois modulos que escolham o mesmo
endereco se corrompem mutuamente e nada avisa.
"""
import re
from dataclasses import dataclass

from msxasm.errors import MontagemError
from msxasm.numero import parse as _numero
from msxasm.source import Linha
from msxasm.texto import corta_comentario

_BSS = re.compile(r"^\s*BSS\s*(\S+)?\s*$", re.IGNORECASE)
_ENDBSS = re.compile(r"^\s*ENDBSS\s*$", re.IGNORECASE)
_RESERVA = re.compile(
    r"^\s*([A-Za-z_][A-Za-z_0-9@]*)\s*:\s*DS\s+(\S+)\s*$", re.IGNORECASE
)


@dataclass(frozen=True)
class Simbolo:
    """Um simbolo de RAM alocado por um bloco BSS.

    Carrega a PROCEDENCIA REAL (arquivo e numero da linha `NOME: DS n` que
    o declarou), nao um indice sintetico. A Tarefa 7 gerava as linhas EQU
    com `arquivo="<bss>"` e um contador, e isso foi deferido como
    cosmetico -- deixou de ser: quando o EQU sintetico falha ao montar, o
    erro apontava para `<bss>:1` e nao havia caminho de volta ao fonte que
    a pessoa escreveu.
    """
    nome: str
    endereco: int
    tamanho: int
    arquivo: str
    numero: int

    @property
    def origem(self) -> str:
        return f"{self.arquivo}:{self.numero}"


def extrair(linhas: list[Linha],
            limite: int = 0xFFFF) -> tuple[list[Linha], dict[str, Simbolo]]:
    resto: list[Linha] = []
    mapa: dict[str, Simbolo] = {}
    # Chave normalizada em maiuscula -> Simbolo da primeira declaracao. A
    # comparacao de duplicata usa esta chave, nao o nome como escrito -- a
    # resolucao de label/equate e insensivel a caixa desde a Tarefa 5
    # (msxasm.labels), e 'Estado' e 'ESTADO' sao o MESMO simbolo. Sem
    # normalizar aqui, os dois passavam como simbolos diferentes e recebiam
    # enderecos de RAM DIFERENTES em silencio -- a classe exata de corrupcao
    # que o BSS existe para eliminar (achado da revisao).
    declarados: dict[str, Simbolo] = {}
    # Faixas [inicio, fim) ja alocadas, na ordem de alocacao. Checar so o
    # NOME cobre metade do problema: dois modulos que declarem cada um a sua
    # base (`BSS 0C000h` nos dois, que e exatamente o que o exemplo da spec
    # 4.3 mostra) recebiam nomes diferentes nos MESMOS enderecos de RAM, sem
    # erro nenhum -- a ROM monta, roda, e as variaveis dos dois modulos se
    # corrompem mutuamente. A deteccao de nome duplicado dava a ilusao de
    # que colisao estava coberta (achado Critical da revisao final).
    faixas: list[Simbolo] = []
    cursor: int | None = None
    i = 0

    while i < len(linhas):
        # Corte de comentario via msxasm.texto (compartilhado com as
        # Tarefas 5 e 6) -- nao uma copia local. Sem isso, 'BSS;continua'
        # (sem espaco antes do ';') faz o '(\S+)?' do _BSS engolir
        # ';continua' inteiro como se fosse o endereco base, e
        # 'V: DS 1;comentario' faz o mesmo com o tamanho do DS -- os dois
        # iam parar em _numero() e escapavam como ValueError cru (achado da
        # revisao). O texto original (com o comentario) e preservado em
        # 'linhas[i]' para quem nao e BSS -- so a decisao de match usa o
        # texto sem comentario.
        codigo, _ = corta_comentario(linhas[i].texto)
        m = _BSS.match(codigo)
        if not m:
            resto.append(linhas[i])
            i += 1
            continue

        abertura = linhas[i]
        if m.group(1) is not None:
            cursor = _numero(m.group(1), linha=abertura.numero,
                             arquivo=abertura.arquivo, contexto="dentro de BSS")
        elif cursor is None:
            raise MontagemError(
                "primeiro bloco BSS precisa declarar o endereco base, ex: BSS 0C000h",
                linha=abertura.numero, arquivo=abertura.arquivo,
            )

        i += 1
        fechado = False

        while i < len(linhas):
            corpo = linhas[i]
            corpo_codigo, _ = corta_comentario(corpo.texto)

            if _ENDBSS.match(corpo_codigo):
                fechado = True
                i += 1
                break

            if corpo_codigo.strip():
                r = _RESERVA.match(corpo_codigo)
                if not r:
                    raise MontagemError(
                        f"dentro de BSS so cabe 'NOME: DS n', encontrado: {corpo.texto.strip()!r}",
                        linha=corpo.numero, arquivo=corpo.arquivo,
                    )

                nome = r.group(1)
                tamanho = _numero(r.group(2), linha=corpo.numero,
                                  arquivo=corpo.arquivo, contexto="dentro de BSS")
                chave = nome.upper()
                if chave in declarados:
                    raise MontagemError(
                        f"simbolo BSS duplicado: {nome} "
                        f"(ja declarado em {declarados[chave].origem})",
                        linha=corpo.numero, arquivo=corpo.arquivo,
                    )

                if cursor + tamanho - 1 > limite:
                    raise MontagemError(
                        f"RAM estourou ao alocar {nome} ({tamanho} bytes em "
                        f"0x{cursor:04X}); limite e 0x{limite:04X}",
                        linha=corpo.numero, arquivo=corpo.arquivo,
                    )

                simbolo = Simbolo(nome=nome, endereco=cursor, tamanho=tamanho,
                                  arquivo=corpo.arquivo, numero=corpo.numero)
                anterior = _sobreposto(simbolo, faixas)
                if anterior is not None:
                    raise MontagemError(
                        f"simbolo BSS {nome} ocupa "
                        f"{_faixa(simbolo)} e sobrepoe {anterior.nome}, que ocupa "
                        f"{_faixa(anterior)} (declarado em {anterior.origem})",
                        linha=corpo.numero, arquivo=corpo.arquivo,
                    )

                mapa[nome] = simbolo
                declarados[chave] = simbolo
                faixas.append(simbolo)
                cursor += tamanho

            i += 1

        if not fechado:
            raise MontagemError(
                "bloco BSS aberto sem ENDBSS",
                linha=abertura.numero, arquivo=abertura.arquivo,
            )

    return resto, mapa


def _faixa(s: Simbolo) -> str:
    if s.tamanho <= 0:
        return f"0 bytes em 0x{s.endereco:04X}"
    return f"0x{s.endereco:04X}..0x{s.endereco + s.tamanho - 1:04X}"


def _sobreposto(novo: Simbolo, faixas: list[Simbolo]) -> Simbolo | None:
    """Primeiro simbolo ja alocado cuja faixa intersecta a de `novo`.

    Reserva de tamanho zero nao ocupa endereco nenhum e por isso nunca
    sobrepoe -- a comparacao e de intervalos meio-abertos [inicio, fim).
    """
    inicio, fim = novo.endereco, novo.endereco + novo.tamanho
    for outro in faixas:
        o_inicio, o_fim = outro.endereco, outro.endereco + outro.tamanho
        if inicio < o_fim and o_inicio < fim:
            return outro
    return None
