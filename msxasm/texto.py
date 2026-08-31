# msxasm/texto.py
"""Utilitarios de texto compartilhados pelas passagens de preparo do fonte.

Corte de comentario e protecao de string literal sao o mesmo problema em
toda passagem que reescreve uma linha de assembly: um ';' ou um '@@' (ou o
nome de um parametro de macro) dentro de uma string entre aspas duplas e
DADO, nao codigo -- reescrever ali corromperia a ROM em silencio.

As Tarefas 5 (msxasm.labels) e 6 (msxasm.macro) resolveram esse problema
cada uma na sua vez, em despachos separados, e cada uma escreveu sua propria
copia. Isto reune as duas em um lugar so, antes que uma terceira copia (a
Tarefa 7, BSS) fizesse a logica divergir sem que ninguem percebesse.
"""
import re

LOCAL = re.compile(r"@@([A-Za-z_][A-Za-z_0-9]*)")
_STRING = re.compile(r'"[^"]*"')


def corta_comentario(texto: str) -> tuple[str, str]:
    """Separa `texto` em (codigo, comentario), respeitando aspas duplas --
    um ';' dentro de uma string literal nao inicia um comentario.
    """
    dentro = False
    for i, c in enumerate(texto):
        if c == '"':
            dentro = not dentro
        elif c == ";" and not dentro:
            return texto[:i], texto[i:]
    return texto, ""


def fora_de_strings(codigo: str, transformar) -> str:
    """Aplica `transformar` apenas nos trechos de `codigo` fora de strings
    entre aspas duplas. O conteudo das strings e mantido intacto -- e dado,
    nao codigo, e reescrever ali corromperia a ROM em silencio.
    """
    partes = _STRING.split(codigo)
    literais = _STRING.findall(codigo)
    pedacos = []
    for i, parte in enumerate(partes):
        pedacos.append(transformar(parte))
        if i < len(literais):
            pedacos.append(literais[i])
    return "".join(pedacos)


def sem_strings(codigo: str) -> str:
    """Remove o conteudo de strings literais -- so para checar a presenca
    de algo (ex.: '@@') fora delas, sem reescrever nada. Um DB com
    '"e-mail: a@@b"' nao e uma referencia a label local -- e dado.
    """
    return _STRING.sub("", codigo)
