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

_BSS = re.compile(r"^\s*BSS\s*(\S+)?\s*(?:;.*)?$", re.IGNORECASE)
_ENDBSS = re.compile(r"^\s*ENDBSS\s*(?:;.*)?$", re.IGNORECASE)
_RESERVA = re.compile(
    r"^\s*([A-Za-z_][A-Za-z_0-9@]*)\s*:\s*DS\s+(\S+)\s*(?:;.*)?$", re.IGNORECASE
)


def _numero(texto: str) -> int:
    t = texto.strip().upper()
    if t.endswith("H"):
        return int(t[:-1], 16)
    if t.startswith("0X"):
        return int(t, 16)
    return int(t, 10)


def extrair(linhas: list[Linha], limite: int = 0xFFFF) -> tuple[list[Linha], dict[str, int]]:
    resto: list[Linha] = []
    mapa: dict[str, int] = {}
    origem: dict[str, str] = {}
    cursor: int | None = None
    i = 0

    while i < len(linhas):
        m = _BSS.match(linhas[i].texto)
        if not m:
            resto.append(linhas[i])
            i += 1
            continue

        abertura = linhas[i]
        if m.group(1) is not None:
            cursor = _numero(m.group(1))
        elif cursor is None:
            raise MontagemError(
                "primeiro bloco BSS precisa declarar o endereco base, ex: BSS 0C000h",
                linha=abertura.numero, arquivo=abertura.arquivo,
            )

        i += 1
        fechado = False

        while i < len(linhas):
            if _ENDBSS.match(linhas[i].texto):
                fechado = True
                i += 1
                break

            corpo = linhas[i]
            if corpo.texto.strip() and not corpo.texto.strip().startswith(";"):
                r = _RESERVA.match(corpo.texto)
                if not r:
                    raise MontagemError(
                        f"dentro de BSS so cabe 'NOME: DS n', encontrado: {corpo.texto.strip()!r}",
                        linha=corpo.numero, arquivo=corpo.arquivo,
                    )

                nome, tamanho = r.group(1), _numero(r.group(2))
                if nome in mapa:
                    raise MontagemError(
                        f"simbolo BSS duplicado: {nome} (ja declarado em {origem[nome]})",
                        linha=corpo.numero, arquivo=corpo.arquivo,
                    )

                if cursor + tamanho - 1 > limite:
                    raise MontagemError(
                        f"RAM estourou ao alocar {nome} ({tamanho} bytes em "
                        f"0x{cursor:04X}); limite e 0x{limite:04X}",
                        linha=corpo.numero, arquivo=corpo.arquivo,
                    )

                mapa[nome] = cursor
                origem[nome] = f"{corpo.arquivo}:{corpo.numero}"
                cursor += tamanho

            i += 1

        if not fechado:
            raise MontagemError(
                "bloco BSS aberto sem ENDBSS",
                linha=abertura.numero, arquivo=abertura.arquivo,
            )

    return resto, mapa
