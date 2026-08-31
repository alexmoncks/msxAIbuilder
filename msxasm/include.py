# msxasm/include.py
"""Achatamento de INCLUDE.

Resolve primeiro relativo ao arquivo que incluiu, depois pelo search path.
Cada linha do resultado carrega o arquivo e o numero de onde veio, para que
um erro no meio de um runtime de biblioteca aponte para a linha do modulo e
nao para um offset do fonte achatado.

Inclusao dupla entra uma vez so: modulos do runtime dependem uns dos outros
e um include-guard manual em cada arquivo seria ruido repetido.
"""
import re
from pathlib import Path

from msxasm.errors import MontagemError
from msxasm.source import Linha, carregar

_INCLUDE = re.compile(r'^\s*INCLUDE\s+"([^"]+)"\s*(?:;.*)?$', re.IGNORECASE)


def _resolver(alvo: str, incluidor: Path, search_paths: list[Path]) -> Path | None:
    candidato = incluidor.parent / alvo
    if candidato.is_file():
        return candidato.resolve()
    for base in search_paths:
        candidato = Path(base) / alvo
        if candidato.is_file():
            return candidato.resolve()
    return None


def expandir(caminho: Path, search_paths: list[Path]) -> list[Linha]:
    caminho = Path(caminho).resolve()
    ja_incluidos: set[Path] = set()
    return _expandir(caminho, search_paths, ja_incluidos, [], set())


def _expandir(caminho: Path, search_paths: list[Path],
              ja_incluidos: set[Path], pilha: list[str],
              em_andamento: set[Path]) -> list[Linha]:
    # em_andamento = arquivos ainda abertos na pilha de recursao atual (para
    # detectar ciclo). ja_incluidos = arquivos ja totalmente expandidos em
    # algum momento (para o guarda de repeticao). Sao coisas diferentes: um
    # arquivo que inclui a si mesmo (direta ou indiretamente) ainda esta
    # em_andamento quando a segunda ocorrencia do INCLUDE e vista -- ainda
    # nao foi para ja_incluidos, porque so entra la quando termina de
    # processar todas as suas linhas. Marcar em ja_incluidos na entrada (em
    # vez de na saida) faria o guarda de repeticao capturar o ciclo antes da
    # checagem abaixo rodar, e o ciclo viraria um "pular, ja incluido"
    # silencioso em vez de MontagemError.
    if caminho in em_andamento:
        trilha = " -> ".join(pilha + [str(caminho)])
        raise MontagemError(f"inclusao circular detectada: {trilha}")

    em_andamento = em_andamento | {caminho}
    resultado: list[Linha] = []

    for linha in carregar(caminho):
        m = _INCLUDE.match(linha.texto)
        if not m:
            resultado.append(linha)
            continue

        alvo = m.group(1)
        destino = _resolver(alvo, caminho, search_paths)
        if destino is None:
            tentativas = [str(caminho.parent)] + [str(p) for p in search_paths]
            raise MontagemError(
                f'INCLUDE nao encontrou "{alvo}" (procurado em: {", ".join(tentativas)})',
                linha=linha.numero,
                arquivo=linha.arquivo,
                pilha_include=pilha,
            )

        if destino in ja_incluidos:
            continue

        marca = f"{linha.arquivo}:{linha.numero}"
        resultado.extend(
            _expandir(destino, search_paths, ja_incluidos, pilha + [marca], em_andamento)
        )

    ja_incluidos.add(caminho)
    return resultado
