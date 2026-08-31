# msxasm/labels.py
"""Escopo de labels locais.

'@@nome' pertence ao ultimo label global acima dele e vira
'GLOBAL@@nome' no fonte achatado. Sem isso, dois modulos do runtime que
usem '@@loop' colidem, e a colisao e silenciosa: o segundo simplesmente
salta para o primeiro.
"""
import re

from msxasm.source import Linha

_GLOBAL = re.compile(r"^([A-Za-z_][A-Za-z_0-9]*):")
_LOCAL = re.compile(r"@@([A-Za-z_][A-Za-z_0-9]*)")
_STRING = re.compile(r'"[^"]*"')


def _corta_comentario(texto: str) -> tuple[str, str]:
    fora_de_string = True
    for i, c in enumerate(texto):
        if c == '"':
            fora_de_string = not fora_de_string
        elif c == ";" and fora_de_string:
            return texto[:i], texto[i:]
    return texto, ""


def _sem_strings(codigo: str) -> str:
    """Remove o conteudo de strings literais, so para checar presenca de
    '@@' fora delas. Um DB com '"e-mail: a@@b"' nao e uma referencia a
    label local -- e dado, e teria que ser preservado byte a byte na ROM.
    """
    return _STRING.sub("", codigo)


def _expandir_fora_de_strings(codigo: str, escopo: str) -> str:
    """Aplica a substituicao de '@@nome' apenas nos trechos de `codigo`
    que estao fora de strings entre aspas duplas. O conteudo das strings
    (indices impares de re.split com grupo de captura) e mantido intacto
    -- reescrever ali corromperia dados da ROM em silencio.
    """
    partes = _STRING.split(codigo)
    literais = _STRING.findall(codigo)
    pedacos = []
    for i, parte in enumerate(partes):
        pedacos.append(_LOCAL.sub(lambda mm: f"{escopo}@@{mm.group(1)}", parte))
        if i < len(literais):
            pedacos.append(literais[i])
    return "".join(pedacos)


def expandir_locais(linhas: list[Linha]) -> list[Linha]:
    resultado: list[Linha] = []
    escopo = ""

    for linha in linhas:
        codigo, comentario = _corta_comentario(linha.texto)

        m = _GLOBAL.match(codigo.strip())
        if m and not codigo.strip().startswith("@@"):
            escopo = m.group(1)

        if "@@" in _sem_strings(codigo):
            if not escopo:
                from msxasm.errors import MontagemError
                raise MontagemError(
                    "label local '@@' sem nenhum label global acima dele",
                    linha=linha.numero, arquivo=linha.arquivo,
                )
            codigo = _expandir_fora_de_strings(codigo, escopo)

        resultado.append(Linha(texto=codigo + comentario,
                               arquivo=linha.arquivo, numero=linha.numero))

    return resultado
