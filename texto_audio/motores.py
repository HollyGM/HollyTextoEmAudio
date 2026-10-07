"""Motores de síntese de voz.

Um motor é qualquer objeto com `async sintetizar(texto, destino, voz,
velocidade)` que grava um MP3 em `destino`. Para trocar de provedor (Azure,
Google, OpenAI, ElevenLabs, Piper local...) basta escrever outra classe com
esse método e passá-la ao pipeline.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol

import edge_tts

VOZ_PADRAO = "pt-BR-AntonioNeural"

# id da voz -> rótulo para a interface
VOZES = {
    "pt-BR-AntonioNeural": "Antônio (masculina)",
    "pt-BR-FranciscaNeural": "Francisca (feminina)",
    "pt-BR-ThalitaMultilingualNeural": "Thalita (feminina, multilíngue)",
}


class ErroSintese(Exception):
    """Falha ao gerar a voz (rede, serviço fora do ar, texto recusado)."""


class Motor(Protocol):
    async def sintetizar(self, texto: str, destino: Path, voz: str,
                         velocidade: int) -> None: ...


class MotorEdge:
    """Vozes neurais da Microsoft via `edge-tts` (sem chave de API).

    O texto é enviado aos servidores da Microsoft. Para peças sigilosas,
    prefira um motor local.
    """

    def __init__(self, tentativas: int = 4):
        if tentativas < 1:
            raise ValueError("Use pelo menos uma tentativa de síntese.")
        self.tentativas = tentativas

    async def sintetizar(self, texto: str, destino: Path, voz: str,
                         velocidade: int) -> None:
        ultimo_erro: Exception | None = None
        for tentativa in range(self.tentativas):
            try:
                comunicar = edge_tts.Communicate(
                    texto, voz, rate=f"{velocidade:+d}%")
                await comunicar.save(str(destino))
                if destino.exists() and destino.stat().st_size > 0:
                    return
                raise ErroSintese("o serviço devolveu áudio vazio")
            except asyncio.CancelledError:
                raise
            except Exception as erro:          # rede, websocket, timeout
                ultimo_erro = erro
                destino.unlink(missing_ok=True)
                if tentativa + 1 < self.tentativas:
                    await asyncio.sleep(1.5 * (tentativa + 1))
        raise ErroSintese(
            f"não foi possível gerar a voz após {self.tentativas} tentativas: "
            f"{type(ultimo_erro).__name__}: {ultimo_erro}") from ultimo_erro
