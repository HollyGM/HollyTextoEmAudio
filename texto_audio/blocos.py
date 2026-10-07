"""Divide o texto normalizado em blocos que o motor de voz aguenta de uma vez."""
from __future__ import annotations

import re
from dataclasses import dataclass

# Parágrafo curto (título, "Pede deferimento.") ganha pausa maior depois.
LIMITE_TITULO = 80
FATOR_PAUSA_TITULO = 1.4
PAUSA_ENTRE_BLOCOS_MS = 300   # corte (em fim de frase) no meio de um parágrafo


@dataclass
class Bloco:
    texto: str
    pausa_ms: int    # silêncio depois do bloco


def _partir_frase(frase: str, limite: int) -> list[str]:
    """Frase maior que o limite: parte em vírgulas, depois em espaços."""
    if len(frase) <= limite:
        return [frase]
    pedacos: list[str] = []
    atual = ""
    for parte in re.split(r"(?<=[,;:])\s+", frase):
        if len(parte) > limite:          # sem vírgula nenhuma: parte em palavras
            if atual:
                pedacos.append(atual)
                atual = ""
            for palavra in parte.split(" "):
                if len(atual) + len(palavra) + 1 > limite and atual:
                    pedacos.append(atual)
                    atual = palavra
                else:
                    atual = f"{atual} {palavra}".strip()
            continue
        if len(atual) + len(parte) + 1 > limite and atual:
            pedacos.append(atual)
            atual = parte
        else:
            atual = f"{atual} {parte}".strip()
    if atual:
        pedacos.append(atual)
    return pedacos


def _agrupar_paragrafo(paragrafo: str, limite: int) -> list[str]:
    if len(paragrafo) <= limite:
        return [paragrafo]
    blocos: list[str] = []
    atual = ""
    for frase in re.split(r"(?<=[.!?])\s+", paragrafo):
        for pedaco in _partir_frase(frase, limite):
            if atual and len(atual) + len(pedaco) + 1 > limite:
                blocos.append(atual)
                atual = pedaco
            else:
                atual = f"{atual} {pedaco}".strip()
    if atual:
        blocos.append(atual)
    return blocos


def dividir(texto: str, limite: int = 1500,
            pausa_paragrafo_ms: int = 700) -> list[Bloco]:
    """Um parágrafo por linha; devolve blocos com a pausa que vem depois."""
    blocos: list[Bloco] = []
    for paragrafo in (p.strip() for p in texto.split("\n")):
        if not re.search(r"\w", paragrafo):
            continue
        partes = _agrupar_paragrafo(paragrafo, limite)
        fator = FATOR_PAUSA_TITULO if len(paragrafo) <= LIMITE_TITULO else 1
        for i, parte in enumerate(partes):
            ultimo = i == len(partes) - 1
            pausa = int(pausa_paragrafo_ms * fator) if ultimo \
                else PAUSA_ENTRE_BLOCOS_MS
            blocos.append(Bloco(parte, pausa))
    if blocos:
        blocos[-1].pausa_ms = 0          # sem silêncio no fim do arquivo
    return blocos
