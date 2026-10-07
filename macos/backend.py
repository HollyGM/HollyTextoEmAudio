"""Entrada do servidor incorporado ao aplicativo. Não abre navegador."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import socket
import sys
from pathlib import Path

import uvicorn

from texto_audio.caminhos import RAIZ, preparar_dados
from texto_audio.servidor import app


async def executar(estado: Path, parent_pid: int) -> None:
    preparar_dados()
    if getattr(sys, "frozen", False):
        for programa in ("ffmpeg", "ffprobe"):
            os.environ[f"TEXTO_AUDIO_{programa.upper()}"] = str(RAIZ / programa)
    servidor = uvicorn.Server(uvicorn.Config(
        app, host="127.0.0.1", port=0, loop="asyncio", http="h11", ws="none",
        log_level="warning", access_log=False, timeout_graceful_shutdown=5))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(128)
        porta = sock.getsockname()[1]
        # Uvicorn reaplica o sinal ao handler anterior após desligar. Um
        # handler próprio deixa o wrapper limpar o arquivo de estado antes
        # de terminar, inclusive ao receber SIGTERM do launcher.
        def encerrar(_sinal, _frame):
            servidor.should_exit = True

        handlers = {s: signal.signal(s, encerrar)
                    for s in (signal.SIGTERM, signal.SIGINT)}
        trabalho = asyncio.create_task(servidor.serve(sockets=[sock]))
        try:
            while not servidor.started:
                if trabalho.done():
                    await trabalho
                    raise RuntimeError("O servidor não conseguiu iniciar.")
                await asyncio.sleep(0.05)
            estado.parent.mkdir(parents=True, exist_ok=True)
            temporario = estado.with_suffix(".tmp")
            temporario.write_text(json.dumps({"url": f"http://127.0.0.1:{porta}"}),
                                  encoding="utf-8")
            temporario.replace(estado)
            while not trabalho.done():
                if parent_pid:
                    try:
                        os.kill(parent_pid, 0)
                    except ProcessLookupError:
                        servidor.should_exit = True
                await asyncio.sleep(0.5)
            await trabalho
        finally:
            servidor.should_exit = True
            try:
                if not trabalho.done():
                    await trabalho
            finally:
                estado.unlink(missing_ok=True)
                for sinal, handler in handlers.items():
                    signal.signal(sinal, handler)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--estado", required=True, type=Path)
    parser.add_argument("--parent-pid", type=int, default=0)
    args = parser.parse_args()
    asyncio.run(executar(args.estado, args.parent_pid))


if __name__ == "__main__":
    main()
