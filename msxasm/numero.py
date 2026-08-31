# msxasm/numero.py
"""Gramatica numerica unica do assembler.

Antes disto existiam TRES copias divergentes -- `cli._tamanho` (K, M e
`int(t, 0)`, sem `H`), `bss._numero` (H, 0X e decimal, sem K/M) e
`mapper._numero` (K, M, H, 0X e decimal). A divergencia era observavel pelo
usuario: `4000h` e a grafia hexadecimal que o proprio assembler usa em todo
lugar (`0C000h`, `BSS 0C000h`, `WINDOW 8000h`), e mesmo assim `--size 4000h`
e `--org 4000h` estouravam com `ValueError` cru da CLI.

E o mesmo motivo que justificou `msxasm.texto`: unificar antes que a terceira
copia divergisse sem ninguem perceber. Aqui ja tinha divergido.

Toda entrada malformada sai como `MontagemError` -- com `arquivo:linha`
quando a origem e conhecida (dentro de um fonte) e sem localizacao quando o
numero veio de um argumento de linha de comando.
"""
from msxasm.errors import MontagemError

_SUFIXOS = (
    ("K", 1024),
    ("M", 1024 * 1024),
)


def parse(texto: str, *, linha: int | None = None, arquivo: str | None = None,
          contexto: str | None = None) -> int:
    """Converte a grafia numerica do assembler para int.

    Aceita, em ordem de teste: sufixo `K`/`M` (multiplos de 1024), sufixo
    `H` (hexadecimal, estilo Intel: `0C000h`), prefixo `0x`/`0b`/`0o`
    (estilo Python) e decimal. Sinal negativo e aceito em qualquer forma.

    O sufixo e testado ANTES do prefixo de proposito: `0BEEFh` e um
    hexadecimal terminado em `h`, nao um binario comecando em `0b`.
    """
    bruto = "" if texto is None else str(texto)
    t = bruto.strip().upper()

    negativo = t.startswith("-")
    corpo = t[1:].strip() if negativo else t
    sinal = -1 if negativo else 1

    try:
        if not corpo:
            raise ValueError(bruto)
        for sufixo, fator in _SUFIXOS:
            if corpo.endswith(sufixo):
                return sinal * int(corpo[:-1], 10) * fator
        if corpo.endswith("H"):
            return sinal * int(corpo[:-1], 16)
        if corpo.startswith(("0X", "0B", "0O")):
            return sinal * int(corpo, 0)
        return sinal * int(corpo, 10)
    except ValueError:
        # Nunca deixar escapar ValueError cru: ele atravessaria o
        # "except MontagemError" da CLI como traceback de Python, sem
        # arquivo nem linha -- a mesma classe de furo que as Tarefas 3, 7
        # e 8 fecharam por dentro e que a fronteira da CLI deixou aberta.
        onde = f" {contexto}" if contexto else ""
        raise MontagemError(
            f"numero invalido{onde}: {bruto.strip()!r}",
            linha=linha, arquivo=arquivo,
        ) from None
