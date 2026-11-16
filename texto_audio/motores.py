"""Motores de síntese de voz.

Um motor é qualquer objeto com `async sintetizar(texto, destino, voz,
velocidade)` que grava um MP3 em `destino`. Para trocar de provedor (Azure,
Google, OpenAI, ElevenLabs, Piper local...) basta escrever outra classe com
esse método e passá-la ao pipeline.

Há dois motores: `MotorEdge` (vozes neurais da Microsoft, online) e
`MotorLocal` (vozes do macOS, sem internet). A voz escolhida define o motor.
"""
from __future__ import annotations

import asyncio
import os
import re
import tempfile
from pathlib import Path
from typing import Protocol

import aiohttp
import edge_tts

from . import audio

VOZ_PADRAO = "pt-BR-AntonioNeural"

# id da voz local -> nome da voz no macOS (comando `say`)
VOZES_LOCAIS = {"local:Luciana": "Luciana"}

# id da voz -> rótulo para a interface
VOZES = {
    "pt-BR-AntonioNeural": "Antônio (masculina)",
    "pt-BR-FranciscaNeural": "Francisca (feminina)",
    "pt-BR-ThalitaMultilingualNeural": "Thalita (feminina, multilíngue)",
    "local:Luciana": "Luciana (neste Mac, sem internet)",
}


def eh_voz_local(voz: str) -> bool:
    """Vozes locais geram o áudio neste computador: o texto não sai dele."""
    return voz in VOZES_LOCAIS


class ErroSintese(Exception):
    """Falha ao gerar a voz (rede, serviço fora do ar, texto recusado)."""


class VozRecusada(ErroSintese):
    """A Microsoft recusou a conexão (HTTP 403).

    Acontece quando ela muda o acesso às vozes e o `edge-tts` embutido fica
    desatualizado. Repetir não adianta: só uma versão nova da biblioteca resolve.
    """

    def __init__(self):
        super().__init__(
            "A Microsoft recusou a conexão com o serviço de voz (erro 403). "
            "Isso costuma acontecer quando ela muda o acesso às vozes. Use "
            "“Verificar serviço de voz” para saber se já há correção.")


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
                if (isinstance(erro, aiohttp.WSServerHandshakeError)
                        and erro.status == 403):
                    raise VozRecusada() from erro
                if tentativa + 1 < self.tentativas:
                    await asyncio.sleep(1.5 * (tentativa + 1))
        raise ErroSintese(
            f"não foi possível gerar a voz após {self.tentativas} tentativas: "
            f"{type(ultimo_erro).__name__}: {ultimo_erro}") from ultimo_erro


# Ritmo do `say` na velocidade 0, em palavras por minuto (o padrão do macOS).
PALAVRAS_POR_MINUTO_LOCAL = 175
_VOZES_INSTALADAS: set[str] = set()


def _comando_say() -> str:
    caminho = os.environ.get("TEXTO_AUDIO_SAY", "/usr/bin/say")
    if not (Path(caminho).is_file() and os.access(caminho, os.X_OK)):
        raise ErroSintese("A voz local só funciona no macOS (comando 'say' não encontrado).")
    return caminho


async def _voz_instalada(say: str, nome: str) -> bool:
    # Com uma voz que não existe, o `say` não dá erro: lê com outra voz. Por isso
    # a lista de vozes é conferida antes. Só o resultado positivo fica guardado,
    # para a voz instalada com o app aberto passar a funcionar sem reiniciá-lo.
    if nome in _VOZES_INSTALADAS:
        return True
    try:
        lista = await audio._rodar(say, "-v", "?")
    except audio.ErroAudio as erro:
        raise ErroSintese(f"Não consegui listar as vozes do macOS: {erro}") from erro
    if re.search(rf"^{re.escape(nome)}\b.*\bpt_BR\b", lista, re.MULTILINE):
        _VOZES_INSTALADAS.add(nome)
        return True
    return False


class MotorLocal:
    """Vozes instaladas no macOS, pelo comando `say`. Não usa a internet.

    O texto vai ao `say` pela entrada padrão (não aparece na lista de
    processos) e o áudio temporário é apagado ao terminar.
    """

    async def sintetizar(self, texto: str, destino: Path, voz: str,
                         velocidade: int) -> None:
        nome = VOZES_LOCAIS.get(voz)
        if nome is None:
            raise ErroSintese(f"Voz local desconhecida: {voz}")
        say = _comando_say()
        if not await _voz_instalada(say, nome):
            raise ErroSintese(
                f"A voz {nome} não está instalada neste Mac. Instale-a em Ajustes "
                "do Sistema > Acessibilidade > Conteúdo Falado > Voz do sistema > "
                "Gerenciar Vozes > Português (Brasil).")
        ritmo = round(PALAVRAS_POR_MINUTO_LOCAL * (1 + velocidade / 100))
        try:
            with tempfile.TemporaryDirectory(prefix="texto-audio-local-") as tmp:
                bruto = Path(tmp) / "voz.aiff"
                await audio._rodar(say, "-v", nome, "-r", str(ritmo),
                                   "-o", str(bruto), "-f", "-",
                                   entrada=texto.encode("utf-8"))
                if not bruto.exists() or bruto.stat().st_size == 0:
                    raise ErroSintese("a voz local não devolveu áudio")
                await audio.para_mp3(bruto, destino)
        except audio.ErroAudio as erro:
            destino.unlink(missing_ok=True)
            raise ErroSintese(f"Falha na voz local: {erro}") from erro
