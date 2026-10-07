"""Montagem do MP3 final com ffmpeg: silêncios, concatenação, volume."""
from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from pathlib import Path

TAXA = 24000          # mesma do edge-tts: evita reamostrar


class ErroAudio(Exception):
    pass


def _exigir(programa: str) -> str:
    configurado = os.environ.get(f"TEXTO_AUDIO_{programa.upper()}")
    if configurado:
        if Path(configurado).is_file() and os.access(configurado, os.X_OK):
            return configurado
        raise ErroAudio(f"O executável configurado para '{programa}' não existe "
                        "ou não pode ser executado.")
    caminho = shutil.which(programa)
    if not caminho:
        raise ErroAudio(
            f"'{programa}' não foi encontrado. Instale o ffmpeg "
            "(macOS: brew install ffmpeg).")
    return caminho


async def _rodar(*args: str) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            *args, stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    except OSError as erro:
        raise ErroAudio(f"Não consegui executar '{args[0]}': {erro}") from erro
    try:
        saida, erro = await proc.communicate()
    except BaseException:
        if proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
        await proc.communicate()
        raise
    if proc.returncode != 0:
        raise ErroAudio(erro.decode("utf-8", "replace")[-600:])
    return saida.decode("utf-8", "replace")


async def silencio(ms: int, destino: Path) -> None:
    """Silêncio em WAV (os intermediários são WAV; o MP3 sai uma vez só)."""
    await _rodar(
        _exigir("ffmpeg"), "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"anullsrc=r={TAXA}:cl=mono",
        "-t", f"{ms / 1000:.3f}", "-c:a", "pcm_s16le", str(destino))


# O serviço de voz devolve cada trecho com ~0,2 s de silêncio antes e de 0,9 a
# 1,6 s depois. Aparamos os dois lados (deixando uma margem curta) para que as
# únicas pausas do áudio sejam as que o usuário escolheu.
_APARAR = ("silenceremove=start_periods=1:start_threshold=-45dB:"
           "start_silence=0.04,areverse,"
           "silenceremove=start_periods=1:start_threshold=-45dB:"
           "start_silence=0.08,areverse")


async def aparar(origem: Path, destino: Path) -> bool:
    """Grava `destino` (WAV) sem o silêncio das pontas. False se não sobrou som."""
    await _rodar(
        _exigir("ffmpeg"), "-y", "-loglevel", "error", "-i", str(origem),
        "-af", _APARAR, "-ar", str(TAXA), "-ac", "1", "-c:a", "pcm_s16le",
        str(destino))
    return destino.exists() and destino.stat().st_size > 1000


async def juntar(arquivos: list[Path], destino: Path, titulo: str = "",
                 normalizar_volume: bool = True, bitrate: str = "64k") -> None:
    """Concatena decodificando e recodificando (emendas sem estalo)."""
    if not arquivos:
        raise ErroAudio("Não há trechos de áudio para montar.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    # A saída só substitui o destino quando o ffmpeg termina com sucesso.
    # A lista temporária também não sobrescreve um .txt do usuário.
    with tempfile.TemporaryDirectory(prefix="montagem-", dir=destino.parent) as tmp:
        lista = Path(tmp) / "trechos.ffconcat"
        montado = Path(tmp) / "audio.mp3"
        caminhos = [str(a.resolve()) for a in arquivos]
        if any("\n" in c or "\r" in c for c in caminhos):
            raise ErroAudio("O nome de um trecho de áudio contém quebra de linha.")
        lista.write_text(
            "".join("file '{}'\n".format(c.replace("'", r"'\''"))
                    for c in caminhos), encoding="utf-8")

        def comando(com_filtro: bool) -> list[str]:
            c = [_exigir("ffmpeg"), "-y", "-loglevel", "error",
                 "-f", "concat", "-safe", "0", "-i", str(lista)]
            if com_filtro:
                c += ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"]
            c += ["-ar", str(TAXA), "-ac", "1", "-c:a", "libmp3lame",
                  "-b:a", bitrate]
            if titulo:
                c += ["-metadata", f"title={titulo}",
                      "-metadata", "artist=Texto em Áudio",
                      "-metadata", "genre=Speech"]
            return c + [str(montado)]

        try:
            await _rodar(*comando(normalizar_volume))
        except ErroAudio:
            if not normalizar_volume:
                raise
            # O loudnorm derruba o encoder MP3 quando não há sinal algum
            # (silêncio digital). Refaz sem igualar o volume.
            await _rodar(*comando(False))
        montado.replace(destino)


async def duracao(arquivo: Path) -> float:
    saida = await _rodar(
        _exigir("ffprobe"), "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(arquivo))
    return float(saida.strip())
