"""Orquestra: texto -> normalização -> blocos -> voz -> MP3 único."""
from __future__ import annotations

import asyncio
import re
import tempfile
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import audio
from .blocos import dividir
from .motores import VOZ_PADRAO, ErroSintese, Motor, MotorEdge
from .normalizar import Opcoes, contar_palavras, normalizar

# Palavras por minuto de fala pura (sem pausas) na velocidade 0. Medido com as
# vozes pt-BR do edge-tts em duas petições (169 e 175); serve só para estimar a
# duração antes de gerar. A velocidade do motor escala a fala linearmente.
PALAVRAS_POR_MINUTO_FALA = 172
SIMULTANEAS = 3

Progresso = Callable[[float, str], None]


@dataclass
class Configuracao:
    voz: str = VOZ_PADRAO
    velocidade: int = 0                 # % em relação ao normal (-50..+100)
    pausa_paragrafo_ms: int = 700
    normalizar_volume: bool = True
    titulo: str = "Áudio"
    texto: Opcoes = field(default_factory=Opcoes)


@dataclass
class Resultado:
    caminho: Path
    duracao_s: float
    tamanho_bytes: int
    palavras: int
    blocos: int


def estimar_minutos(palavras: int, velocidade: int = 0,
                    pausas_ms: int = 0) -> float:
    """Fala escala com a velocidade; as pausas entre parágrafos não."""
    fala = palavras / (PALAVRAS_POR_MINUTO_FALA * (1 + velocidade / 100))
    return fala + pausas_ms / 60_000


def nome_de_arquivo(titulo: str) -> str:
    base = unicodedata.normalize("NFKD", titulo)
    base = base.encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower() or "audio"
    return f"{base[:60]}_{datetime.now():%Y%m%d-%H%M%S}_{uuid.uuid4().hex[:8]}.mp3"


async def gerar_audio(texto: str, pasta: Path, cfg: Configuracao,
                      motor: Motor | None = None,
                      progresso: Progresso | None = None) -> Resultado:
    motor = motor or MotorEdge()
    avisar = progresso or (lambda fracao, msg: None)

    avisar(0.0, "Preparando o texto")
    falado = normalizar(texto, cfg.texto)
    blocos = dividir(falado, pausa_paragrafo_ms=cfg.pausa_paragrafo_ms)
    if not blocos:
        raise ValueError("O texto não tem nada para ser lido.")
    palavras = contar_palavras(falado)

    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / nome_de_arquivo(cfg.titulo)
    total = len(blocos)

    with tempfile.TemporaryDirectory(prefix="texto-audio-") as tmp:
        tmp = Path(tmp)
        partes = [tmp / f"b{i:05d}.wav" for i in range(total)]
        com_som = [False] * total
        feitos = 0
        limite = asyncio.Semaphore(SIMULTANEAS)

        async def sintetizar(i: int) -> None:
            nonlocal feitos
            bruto = tmp / f"r{i:05d}.mp3"
            async with limite:
                await motor.sintetizar(blocos[i].texto, bruto, cfg.voz,
                                       cfg.velocidade)
                com_som[i] = await audio.aparar(bruto, partes[i])
                bruto.unlink(missing_ok=True)
            feitos += 1
            avisar(0.05 + 0.85 * feitos / total,
                   f"Gerando a voz ({feitos} de {total})")

        tarefas = [asyncio.create_task(sintetizar(i)) for i in range(total)]
        try:
            await asyncio.gather(*tarefas)
        except BaseException:
            for t in tarefas:
                t.cancel()
            await asyncio.gather(*tarefas, return_exceptions=True)
            raise

        avisar(0.9, "Montando o MP3")
        sequencia: list[Path] = []
        silencios: dict[int, Path] = {}
        ultimo_com_som = max((i for i, som in enumerate(com_som) if som),
                            default=-1)
        for i, bloco in enumerate(blocos):
            if not com_som[i]:
                continue              # trecho que a voz deixou mudo: pula
            sequencia.append(partes[i])
            if bloco.pausa_ms and i != ultimo_com_som:
                if bloco.pausa_ms not in silencios:
                    silencios[bloco.pausa_ms] = tmp / f"s{bloco.pausa_ms}.wav"
                    await audio.silencio(bloco.pausa_ms,
                                         silencios[bloco.pausa_ms])
                sequencia.append(silencios[bloco.pausa_ms])
        if not sequencia:
            raise ErroSintese("A voz não devolveu áudio para este texto.")
        await audio.juntar(sequencia, destino, cfg.titulo,
                           cfg.normalizar_volume)

    try:
        segundos = await audio.duracao(destino)
    except BaseException:
        destino.unlink(missing_ok=True)
        raise
    avisar(1.0, "Pronto")
    return Resultado(destino, segundos, destino.stat().st_size, palavras, total)
