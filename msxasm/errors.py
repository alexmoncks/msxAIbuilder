# msxasm/errors.py
"""Erros de montagem.

Toda falha do assembler passa por aqui. A regra do projeto: e melhor
recusar montar do que produzir uma ROM que trava a maquina.
"""


class MontagemError(Exception):
    def __init__(self, mensagem: str, linha: int | None = None,
                 arquivo: str | None = None, pilha_include: list[str] | None = None):
        self.mensagem = mensagem
        self.linha = linha
        self.arquivo = arquivo
        self.pilha_include = pilha_include or []
        super().__init__(str(self))

    def __str__(self) -> str:
        local = ""
        if self.arquivo:
            local = self.arquivo
            if self.linha is not None:
                local += f":{self.linha}"
            local += ": "
        elif self.linha is not None:
            local = f"linha {self.linha}: "

        texto = f"{local}{self.mensagem}"
        if self.pilha_include:
            trilha = "\n".join(f"    incluido de {p}" for p in reversed(self.pilha_include))
            texto += "\n" + trilha
        return texto
