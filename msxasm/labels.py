# msxasm/labels.py
"""Escopo de labels locais.

'@@nome' pertence ao ultimo label global acima dele e vira
'GLOBAL@@nome' no fonte achatado. Sem isso, dois modulos do runtime que
usem '@@loop' colidem, e a colisao e silenciosa: o segundo simplesmente
salta para o primeiro.

Corte de comentario e protecao de string literal (msxasm.texto) sao
compartilhados com msxasm.macro -- mesma logica, mesmo motivo: um '@@'
dentro de uma string e dado, nao referencia a label local.
"""
import re

from msxasm.source import Linha
from msxasm.texto import LOCAL, corta_comentario, fora_de_strings, sem_strings

_GLOBAL = re.compile(r"^([A-Za-z_][A-Za-z_0-9]*):")


def expandir_locais(linhas: list[Linha]) -> list[Linha]:
    resultado: list[Linha] = []
    escopo = ""

    for linha in linhas:
        codigo, comentario = corta_comentario(linha.texto)

        m = _GLOBAL.match(codigo.strip())
        if m and not codigo.strip().startswith("@@"):
            escopo = m.group(1)

        if "@@" in sem_strings(codigo):
            if not escopo:
                from msxasm.errors import MontagemError
                raise MontagemError(
                    "label local '@@' sem nenhum label global acima dele",
                    linha=linha.numero, arquivo=linha.arquivo,
                )
            codigo = fora_de_strings(
                codigo,
                lambda parte: LOCAL.sub(lambda mm: f"{escopo}@@{mm.group(1)}", parte),
            )

        resultado.append(Linha(texto=codigo + comentario,
                               arquivo=linha.arquivo, numero=linha.numero))

    return resultado
