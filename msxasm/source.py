# msxasm/source.py
"""Linhas de fonte com procedencia.

Uma linha sabe de que arquivo e de que numero veio. Sem isso, INCLUDE
transforma qualquer erro em "linha 2847 de um fonte que ninguem escreveu".
"""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Linha:
    texto: str
    arquivo: str
    numero: int


def carregar(caminho: Path) -> list[Linha]:
    nome = str(caminho)
    conteudo = caminho.read_text(encoding="utf-8")
    return [
        Linha(texto=t, arquivo=nome, numero=n)
        for n, t in enumerate(conteudo.split("\n"), start=1)
    ]
