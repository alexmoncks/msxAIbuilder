# msxasm/mapper.py
"""Layouts de mapper e particionamento em bancos.

Konami e o padrao para MegaROM por um motivo concreto, verificado em
CartridgeKonami.js do WebMSX: a janela 4000h-5FFFh e fixa no segmento 0 e
nunca pagina. E onde o cabecalho, o trampolim e a rotina de troca de banco
precisam morar, porque codigo que pagina nao pode ser paginado embaixo de si
mesmo.

O teto de 2MB nao e arbitrario: o registrador de banco tem 8 bits e o
emulador aplica 'value % numBanks', entao 256 bancos de 8KB e o limite.
"""
import re
from dataclasses import dataclass

from msxasm.errors import MontagemError
from msxasm.source import Linha
from msxasm.texto import corta_comentario


@dataclass(frozen=True)
class Layout:
    nome: str
    tamanho_banco: int
    janelas: tuple[int, ...]
    janela_residente: int | None
    max_bancos: int
    hint: str | None


LAYOUTS: dict[str, Layout] = {
    "KONAMI": Layout(
        nome="KONAMI", tamanho_banco=8192,
        janelas=(0x4000, 0x6000, 0x8000, 0xA000),
        janela_residente=0x4000, max_bancos=256, hint="Konami",
    ),
    "FLAT": Layout(
        nome="FLAT", tamanho_banco=0,
        janelas=(0x4000,), janela_residente=0x4000,
        max_bancos=1, hint=None,
    ),
}

@dataclass
class Banco:
    numero: int
    janela: int
    linhas: list[Linha]


# As regexes casam apenas o CODIGO (ja sem comentario, cortado via
# msxasm.texto.corta_comentario antes do match) -- por isso nao carregam
# '(?:;.*)?$' como no rascunho original. Com esse sufixo, '\S+' (o operando
# de WINDOW ou o tamanho apos a virgula do MAPPER) e guloso e engole um ';'
# colado sem espaco junto com o resto do comentario, porque ';' e
# nao-espaco: 'BANK 1 WINDOW 8000h;comentario' virava group(2) =
# '8000h;comentario', que _numero() nao reconhece (nao termina em K/M/H nem
# comeca com 0X) e estoura como ValueError cru -- o mesmo bug que a Tarefa 7
# (BSS) teve e corrigiu do mesmo jeito: cortar o comentario ANTES do match,
# em vez de tentar excluir ';' dentro da propria regex.
_MAPPER = re.compile(r"^\s*MAPPER\s+(\w+)\s*(?:,\s*(\S+))?\s*$", re.IGNORECASE)
_BANK = re.compile(r"^\s*BANK\s+(\d+)\s*(?:WINDOW\s+(\S+))?\s*$", re.IGNORECASE)


def _numero(texto: str) -> int:
    t = texto.strip().upper()
    if t.endswith("K"):
        return int(t[:-1]) * 1024
    if t.endswith("M"):
        return int(t[:-1]) * 1024 * 1024
    if t.endswith("H"):
        return int(t[:-1], 16)
    if t.startswith("0X"):
        return int(t, 16)
    return int(t, 10)


def hint_de_arquivo(nome_base: str, layout: Layout) -> str:
    """O colchete nao e enfeite.

    ASCII8 (911), ASCII16 (912), Konami (913) e KonamiSCC (914) tem regra de
    deteccao identica no WebMSX e vence a prioridade menor. Sem o hint, uma
    ROM de 2MB nossa carrega como ASCII8, em silencio, com janelas erradas.
    """
    if layout.hint is None:
        return f"{nome_base}.rom"
    return f"{nome_base} [{layout.hint}].rom"


def _janela_padrao(layout: Layout, numero: int) -> int:
    """Banco 0 e residente; os demais caem na primeira janela paginavel."""
    if numero == 0 and layout.janela_residente is not None:
        return layout.janela_residente
    paginaveis = [j for j in layout.janelas if j != layout.janela_residente]
    return paginaveis[0] if paginaveis else layout.janelas[0]


def particionar(linhas: list[Linha]) -> tuple[Layout, int, dict[int, Banco]]:
    layout = LAYOUTS["FLAT"]
    tamanho = 0
    bancos: dict[int, Banco] = {0: Banco(0, layout.janelas[0], [])}
    atual = 0

    for linha in linhas:
        # Comentario cortado via msxasm.texto (compartilhado com as Tarefas
        # 5, 6 e 7) antes de qualquer match -- ver nota acima das regexes.
        codigo, _ = corta_comentario(linha.texto)

        m = _MAPPER.match(codigo)
        if m:
            nome = m.group(1).upper()
            if nome not in LAYOUTS:
                raise MontagemError(
                    f"mapper desconhecido: {nome} (conhecidos: {', '.join(sorted(LAYOUTS))})",
                    linha=linha.numero, arquivo=linha.arquivo,
                )
            layout = LAYOUTS[nome]
            if m.group(2):
                tamanho = _numero(m.group(2))
                teto = layout.max_bancos * layout.tamanho_banco if layout.tamanho_banco else tamanho
                if tamanho > teto:
                    raise MontagemError(
                        f"{nome} suporta no maximo {teto // 1024}K "
                        f"({layout.max_bancos} bancos de {layout.tamanho_banco} bytes); "
                        f"pedido: {tamanho // 1024}K",
                        linha=linha.numero, arquivo=linha.arquivo,
                    )
            continue

        m = _BANK.match(codigo)
        if m:
            numero = int(m.group(1))
            # O teto de bancos validos e o TAMANHO DECLARADO no MAPPER
            # (quantos bancos aquela ROM realmente tem), nao o
            # layout.max_bancos absoluto do mapper (o teto de hardware,
            # sempre 256 para KONAMI). 'MAPPER KONAMI, 64K' tem so 8 bancos
            # de 8KB -- BANK 99 tem que estourar mesmo com max_bancos=256.
            # Quando o tamanho ainda nao foi declarado, cai no teto do
            # layout (ja garantido <= max_bancos pela checagem do MAPPER).
            if tamanho and layout.tamanho_banco:
                bancos_disponiveis = tamanho // layout.tamanho_banco
            else:
                bancos_disponiveis = layout.max_bancos
            if numero >= bancos_disponiveis:
                raise MontagemError(
                    f"banco {numero} nao existe em {layout.nome}: "
                    f"o maximo e {bancos_disponiveis - 1}",
                    linha=linha.numero, arquivo=linha.arquivo,
                )
            if m.group(2):
                janela = _numero(m.group(2))
                if janela not in layout.janelas:
                    validas = ", ".join(f"0x{j:04X}" for j in layout.janelas)
                    raise MontagemError(
                        f"janela 0x{janela:04X} nao existe em {layout.nome} "
                        f"(validas: {validas})",
                        linha=linha.numero, arquivo=linha.arquivo,
                    )
            else:
                janela = _janela_padrao(layout, numero)

            atual = numero
            if atual in bancos:
                bancos[atual].janela = janela
            else:
                bancos[atual] = Banco(atual, janela, [])
            continue

        if atual not in bancos:
            bancos[atual] = Banco(atual, _janela_padrao(layout, atual), [])
        bancos[atual].linhas.append(linha)

    return layout, tamanho, bancos
