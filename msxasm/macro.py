# msxasm/macro.py
"""Macros com parametros posicionais.

Labels locais dentro do corpo (@@nome) recebem um sufixo por expansao, para
que duas invocacoes da mesma macro nao gerem dois labels iguais. Sem isso, a
segunda expansao redefine o label da primeira e todos os saltos passam a
apontar para o lugar errado -- sem erro de montagem.

Corte de comentario e protecao de string literal (msxasm.texto) sao
compartilhados com msxasm.labels -- mesma logica, mesmo motivo.

Duas protecoes cuidam do resto do risco de uma substituicao textual:

1. Parametro com nome de registrador/flag do Z80 (ex.: MACRO CARREGA a).
   `\\b{param}\\b` nao distingue "a, o parametro" de "a, o registrador" -- sao
   o mesmo token dentro do corpo. Em vez de arriscar reescrever um
   registrador de verdade em silencio (ex.: "xor a" virando "xor 5"),
   `expandir_macros` recusa a EXPANSAO (nao a definicao) com MontagemError,
   assim que uma invocacao valida (numero certo de argumentos) chegaria a
   fazer a substituicao. Uma macro perigosa nunca invocada nao produz erro
   -- nao ha nada para corromper se ela nao e usada.

2. Substituicao dentro de string literal ou de comentario. Mesma classe de
   bug que msxasm.labels corrige para '@@': um DB com "n pontos" nao pode
   virar "7 pontos" so porque o parametro se chama "n". Comentario e cortado
   fora antes de qualquer substituicao; string literal e preservada intacta
   dentro do que resta.

3. Comentario na linha de INVOCACAO (nao no corpo). Precisa ser cortado
   ANTES de dividir os argumentos -- do contrario ele entra no valor do
   ultimo argumento (rodada de correcao 1 da Tarefa 6: 'GUARDA 0C000h ;
   salva estado' com o parametro usado no meio do corpo virava 'ld
   (0C000h   ; salva estado),a' e quebrava com um erro interno de Python,
   sem relacao nenhuma com o texto escrito). E preservado -- anexado ao
   final da primeira linha expandida -- em vez de descartado.
"""
import re

from msxasm.errors import MontagemError
from msxasm.source import Linha
from msxasm.texto import LOCAL, corta_comentario, fora_de_strings

_MACRO = re.compile(r"^\s*MACRO\s+([A-Za-z_][A-Za-z_0-9]*)\s*(.*)$", re.IGNORECASE)
_ENDM = re.compile(r"^\s*ENDM\s*(?:;.*)?$", re.IGNORECASE)

# Registradores e flags de condicao do Z80. Um parametro com um destes nomes
# colide com o uso literal do registrador/flag dentro do corpo da macro --
# ver ponto 1 no docstring do modulo.
_RESERVADOS = {
    "A", "B", "C", "D", "E", "H", "L", "I", "R",
    "AF", "BC", "DE", "HL", "SP", "IX", "IY",
    "IXH", "IXL", "IYH", "IYL",
    "NZ", "Z", "NC", "PO", "PE", "P", "M",
}


class _Definicao:
    def __init__(self, nome: str, params: list[str], corpo: list[Linha]):
        self.nome = nome
        self.params = params
        self.corpo = corpo


def _coletar(linhas: list[Linha]) -> tuple[dict[str, _Definicao], list[Linha]]:
    macros: dict[str, _Definicao] = {}
    resto: list[Linha] = []
    i = 0

    while i < len(linhas):
        m = _MACRO.match(linhas[i].texto)
        if not m:
            resto.append(linhas[i])
            i += 1
            continue

        nome = m.group(1).upper()
        params = [p.strip() for p in m.group(2).split(",") if p.strip()]
        abertura = linhas[i]
        corpo: list[Linha] = []
        i += 1

        while i < len(linhas) and not _ENDM.match(linhas[i].texto):
            corpo.append(linhas[i])
            i += 1

        if i >= len(linhas):
            raise MontagemError(
                f"macro {nome} aberta sem ENDM",
                linha=abertura.numero, arquivo=abertura.arquivo,
            )

        macros[nome] = _Definicao(nome, params, corpo)
        i += 1

    return macros, resto


def _dividir_args(texto: str) -> list[str]:
    args, atual, dentro = [], "", False
    for c in texto:
        if c == '"':
            dentro = not dentro
            atual += c
        elif c == "," and not dentro:
            args.append(atual.strip())
            atual = ""
        else:
            atual += c
    if atual.strip():
        args.append(atual.strip())
    return args


def expandir_macros(linhas: list[Linha]) -> list[Linha]:
    macros, corpo = _coletar(linhas)
    if not macros:
        return corpo

    resultado: list[Linha] = []
    contador = 0

    for linha in corpo:
        # Corta o comentario da linha de INVOCACAO antes de dividir os
        # argumentos -- ver ponto 3 no docstring do modulo. Reusa
        # corta_comentario (mesma funcao usada no corpo), so que aqui um
        # nivel acima: na linha que CHAMA a macro, nao dentro dela.
        codigo_invocacao, comentario_invocacao = corta_comentario(linha.texto)
        bruto = codigo_invocacao.strip()
        primeira = bruto.split()[0].upper() if bruto else ""

        if primeira not in macros:
            resultado.append(linha)
            continue

        definicao = macros[primeira]
        args = _dividir_args(bruto[len(primeira):])

        if len(args) != len(definicao.params):
            raise MontagemError(
                f"macro {definicao.nome} espera {len(definicao.params)} "
                f"argumento(s), recebeu {len(args)}",
                linha=linha.numero, arquivo=linha.arquivo,
            )

        # Ponto 1 (ver docstring do modulo): so recusamos aqui, na expansao
        # de verdade, e nao ja em _coletar(). Uma macro com parametro
        # perigoso que nunca chega a ser invocada nao produz nenhuma
        # substituicao e nao tem como corromper nada -- nao ha razao para
        # recusar a definicao antes de saber se ela sera usada.
        for p in definicao.params:
            if p.upper() in _RESERVADOS:
                raise MontagemError(
                    f"macro {definicao.nome}: parametro '{p}' tem nome de "
                    "registrador ou flag reservado do Z80 -- a substituicao "
                    "textual nao consegue distinguir o parametro do "
                    "registrador dentro do corpo da macro",
                    linha=linha.numero, arquivo=linha.arquivo,
                )

        contador += 1
        sufixo = f"_m{contador}"

        def _substitui_params(parte: str, _params=definicao.params, _args=args) -> str:
            for param, valor in zip(_params, _args):
                parte = re.sub(rf"\b{re.escape(param)}\b", valor, parte)
            return parte

        def _substitui_locais(parte: str, _sufixo=sufixo) -> str:
            return LOCAL.sub(lambda mm: f"@@{mm.group(1)}{_sufixo}", parte)

        expandidas: list[Linha] = []
        for corpo_linha in definicao.corpo:
            codigo, comentario = corta_comentario(corpo_linha.texto)
            codigo = fora_de_strings(codigo, _substitui_params)
            codigo = fora_de_strings(codigo, _substitui_locais)

            expandidas.append(
                Linha(texto=codigo + comentario, arquivo=linha.arquivo, numero=linha.numero)
            )

        if comentario_invocacao and expandidas:
            # Preserva o comentario da invocacao -- e informacao que a
            # pessoa escreveu de proposito, nao lixo para descartar.
            # Anexado ao final da primeira linha expandida; se essa linha
            # ja tiver comentario proprio, o texto so se junta ao mesmo
            # comentario (tudo apos o primeiro ';' ja e comentario).
            primeira_expandida = expandidas[0]
            expandidas[0] = Linha(
                texto=f"{primeira_expandida.texto} {comentario_invocacao}",
                arquivo=primeira_expandida.arquivo,
                numero=primeira_expandida.numero,
            )

        resultado.extend(expandidas)

    return resultado
