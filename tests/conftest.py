import shutil
from pathlib import Path

import pytest

from texto_audio import audio
from texto_audio.motores import ErroSintese

pytestmark_ffmpeg = pytest.mark.skipif(
    not shutil.which("ffmpeg"), reason="ffmpeg não instalado")


class MotorFalso:
    """Grava um MP3 real (silêncio) sem usar a rede."""

    def __init__(self):
        self.chamadas = []

    async def sintetizar(self, texto, destino: Path, voz, velocidade):
        self.chamadas.append((texto, voz, velocidade))
        await audio._rodar(          # tom (não silêncio): áudio realista
            audio._exigir("ffmpeg"), "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "sine=frequency=200:duration=0.3",
            "-ar", str(audio.TAXA), "-ac", "1", "-c:a", "libmp3lame",
            "-b:a", "48k", str(destino))


class MotorQuebrado:
    async def sintetizar(self, texto, destino, voz, velocidade):
        raise ErroSintese("serviço fora do ar")


@pytest.fixture
def motor_falso():
    return MotorFalso()
