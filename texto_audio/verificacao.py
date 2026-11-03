"""Diagnóstico do serviço de voz.

Testa a voz da Microsoft com uma frase genérica e consulta no PyPI se há
versão do `edge-tts` mais nova que a embutida. Quando a Microsoft muda o
acesso às vozes, só uma versão nova da biblioteca resolve, e o aplicativo
precisa ser reconstruído com ela. Nada é baixado nem instalado aqui.
"""
from __future__ import annotations

import asyncio
import re
import ssl
import tempfile
from pathlib import Path

import aiohttp
import certifi
import edge_tts

from .motores import VOZ_PADRAO, ErroSintese, Motor, MotorEdge, VozRecusada

PYPI = "https://pypi.org/pypi/edge-tts/json"
FRASE_TESTE = "Teste do serviço de voz."


def _numeros(versao: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", versao))


async def versao_publicada() -> str | None:
    """Versão mais recente do `edge-tts` no PyPI, ou None se não der para saber."""
    contexto = ssl.create_default_context(cafile=certifi.where())
    try:
        async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)) as sessao:
            async with sessao.get(PYPI, ssl=contexto) as resposta:
                resposta.raise_for_status()
                return str((await resposta.json())["info"]["version"])
    except Exception:                   # sem internet, PyPI fora, resposta estranha
        return None


async def testar_voz(motor: Motor) -> str:
    """'ok', 'recusada' (Microsoft mudou o acesso) ou 'falhou' (rede, serviço)."""
    with tempfile.TemporaryDirectory(prefix="texto-audio-") as tmp:
        try:
            await motor.sintetizar(FRASE_TESTE, Path(tmp) / "teste.mp3",
                                   VOZ_PADRAO, 0)
        except VozRecusada:
            return "recusada"
        except ErroSintese:
            return "falhou"
    return "ok"


async def verificar(motor: Motor | None = None) -> dict:
    voz, publicada = await asyncio.gather(
        testar_voz(motor or MotorEdge(tentativas=1)), versao_publicada())
    instalada = edge_tts.__version__
    nova = publicada is not None and _numeros(publicada) > _numeros(instalada)

    partes = [{
        "ok": "O serviço de voz da Microsoft está funcionando.",
        "recusada": "A Microsoft está recusando a conexão: ela mudou o acesso às vozes.",
        "falhou": "Não consegui gerar a voz de teste. Confira a internet e tente de novo.",
    }[voz]]
    if publicada is None:
        partes.append("Também não consegui consultar se há versão nova da "
                      f"biblioteca de voz (o app usa a edge-tts {instalada}).")
    elif nova and voz == "recusada":
        partes.append(f"Já existe correção: a edge-tts {publicada} (o app usa a "
                      f"{instalada}). Para voltar a gerar áudio, atualize a "
                      "biblioteca e reconstrua o aplicativo, como explica o README.")
    elif nova:
        partes.append(f"Existe uma versão mais nova da biblioteca de voz "
                      f"(edge-tts {publicada}; o app usa a {instalada}). Ela "
                      "entra na próxima reconstrução do aplicativo.")
    elif voz == "recusada":
        partes.append(f"Ainda não há correção publicada (o app já usa a edge-tts "
                      f"{instalada}, a mais recente). Ela costuma sair em poucos "
                      "dias; verifique de novo mais tarde.")
    else:
        partes.append("A biblioteca de voz está na versão mais recente "
                      f"(edge-tts {instalada}).")
    return {"voz": voz, "instalada": instalada, "publicada": publicada,
            "atualizacao_disponivel": nova, "mensagem": " ".join(partes)}
