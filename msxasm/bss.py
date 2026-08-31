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

from msxasm.errors import MontagemError
from msxasm.source import Linha
from msxasm.texto import corta_comentario

_BSS = re.compile(r"^\s*BSS\s*(\S+)?\s*$", re.IGNORECASE)
_ENDBSS = re.compile(r"^\s*ENDBSS\s*$", re.IGNORECASE)
_RESERVA = re.compile(
    r"^\s*([A-Za-z_][A-Za-z_0-9@]*)\s*:\s*DS\s+(\S+)\s*$", re.IGNORECASE
)


def _numero(texto: str, *, linha: int | None, arquivo: str | None) -> int:
    t = texto.strip().upper()
    try:
        if t.endswith("H"):
            return int(t[:-1], 16)
        if t.startswith("0X"):
            return int(t, 16)
        return int(t, 10)
    except ValueError:
        # Entrada malformada dentro de um bloco BSS (ex.: base ou tamanho de
        # DS que nao e numero nenhum) nao pode escapar como ValueError cru --
        # isso atravessaria o "except MontagemError" da CLI como traceback,
        # sem arquivo nem linha (achado da revisao: e a mesma classe de furo
        # que os outros pontos de erro do assembler ja fecham).
        raise MontagemError(
            f"numero invalido dentro de BSS: {texto!r}",
            linha=linha, arquivo=arquivo,
        ) from None


def extrair(linhas: list[Linha], limite: int = 0xFFFF) -> tuple[list[Linha], dict[str, int]]:
    resto: list[Linha] = []
    mapa: dict[str, int] = {}
    # Chave normalizada em maiuscula -> "arquivo:linha" da primeira
    # declaracao. A comparacao de duplicata usa esta chave, nao o nome como
    # escrito -- a resolucao de label/equate e insensivel a caixa desde a
    # Tarefa 5 (msxasm.labels), e 'Estado' e 'ESTADO' sao o MESMO simbolo.
    # Sem normalizar aqui, os dois passavam como simbolos diferentes e
    # recebiam enderecos de RAM DIFERENTES em silencio -- a classe exata de
    # corrupcao que o BSS existe para eliminar (achado da revisao).
    origem: dict[str, str] = {}
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
            cursor = _numero(m.group(1), linha=abertura.numero, arquivo=abertura.arquivo)
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
                tamanho = _numero(r.group(2), linha=corpo.numero, arquivo=corpo.arquivo)
                chave = nome.upper()
                if chave in origem:
                    raise MontagemError(
                        f"simbolo BSS duplicado: {nome} (ja declarado em {origem[chave]})",
                        linha=corpo.numero, arquivo=corpo.arquivo,
                    )

                if cursor + tamanho - 1 > limite:
                    raise MontagemError(
                        f"RAM estourou ao alocar {nome} ({tamanho} bytes em "
                        f"0x{cursor:04X}); limite e 0x{limite:04X}",
                        linha=corpo.numero, arquivo=corpo.arquivo,
                    )

                mapa[nome] = cursor
                origem[chave] = f"{corpo.arquivo}:{corpo.numero}"
                cursor += tamanho

            i += 1

        if not fechado:
            raise MontagemError(
                "bloco BSS aberto sem ENDBSS",
                linha=abertura.numero, arquivo=abertura.arquivo,
            )

    return resto, mapa
