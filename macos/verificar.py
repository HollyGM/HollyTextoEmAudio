"""Teste real do backend empacotado, com dados sintéticos e sem Homebrew no PATH."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path


def verificar(app: Path, online: bool = False) -> None:
    with tempfile.TemporaryDirectory(prefix="teste-texto-audio-") as pasta:
        raiz = Path(pasta)
        estado = raiz / "estado.json"
        ambiente = dict(os.environ, PATH="/usr/bin:/bin", PYTHONPATH="",
                        TEXTO_AUDIO_DATA_DIR=str(raiz / "dados"),
                        TEXTO_AUDIO_OUTPUT_DIR=str(raiz / "audios"))
        with (raiz / "log.txt").open("w+") as log:
            processo = subprocess.Popen(
                [str(app / "Contents/MacOS/TextoAudioBackend"), "--estado",
                 str(estado), "--parent-pid", str(os.getpid())],
                cwd=raiz, env=ambiente, stdout=log, stderr=log)
            try:
                inicio = time.monotonic()
                while not estado.exists():
                    if processo.poll() is not None or time.monotonic() - inicio > 30:
                        log.seek(0)
                        raise RuntimeError("O backend não iniciou: " + log.read())
                    time.sleep(0.1)
                url = json.loads(estado.read_text())["url"]

                def obter(caminho: str, dados: dict | None = None):
                    req = urllib.request.Request(url + caminho,
                        data=json.dumps(dados).encode() if dados is not None else None,
                        headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=60) as resposta:
                        conteudo = resposta.read()
                        if "application/json" in resposta.headers.get("Content-Type", ""):
                            return json.loads(conteudo)
                        return conteudo

                assert b"Texto" in obter("/")
                vozes = obter("/api/vozes")
                assert any(v["id"] == vozes["padrao"] for v in vozes["vozes"])
                preparo = obter("/api/preparar", {"texto": "O valor é R$ 1000,00, conforme o art. 5º."})
                assert "mil reais" in preparo["texto_falado"]
                assert "artigo quinto" in preparo["texto_falado"]
                info = obter("/api/info")
                assert info["versao"] == "1.1.0"
                assert info["pasta_saidas"] == str(raiz / "audios")
                assert (raiz / "dados/pronuncias.txt").exists()
                print("App empacotado: interface, API, pronúncias e normalização OK.")
                if online:
                    tarefa = obter("/api/audio", {"texto": "Teste de funcionamento do aplicativo Texto em Áudio.",
                                                   "titulo": "Teste do aplicativo"})["id"]
                    inicio = time.monotonic()
                    while True:
                        resultado = obter(f"/api/audio/{tarefa}")
                        if resultado["status"] == "erro":
                            raise RuntimeError(resultado["erro"])
                        if resultado["status"] == "pronto":
                            break
                        if time.monotonic() - inicio > 90:
                            raise TimeoutError("A geração online não terminou em 90 segundos.")
                        time.sleep(0.5)
                    mp3 = obter(f"/api/audio/{tarefa}/arquivo")
                    assert len(mp3) == resultado["tamanho_bytes"] > 1000
                    assert resultado["duracao_s"] > 1
                    assert (raiz / "audios" / resultado["arquivo"]).read_bytes() == mp3
                    print(f"Voz online + ffmpeg incorporado + download OK ({len(mp3)} bytes).")
            finally:
                processo.terminate()
                try:
                    processo.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    processo.kill()
                    processo.wait()
                assert not estado.exists(), "O backend não limpou o arquivo de estado."
                print("Encerramento e limpeza OK.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", type=Path)
    parser.add_argument("--online", action="store_true")
    args = parser.parse_args()
    verificar(args.app.resolve(), args.online)
