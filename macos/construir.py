"""Cria o app macOS com Python, servidor e ffmpeg incorporados.

Uso: .venv/bin/python macos/construir.py [--instalar] [--ffmpeg-dir PASTA]
"""
from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BUILD = RAIZ / "build" / "macos"
DIST = RAIZ / "dist"
NOME = "Texto em Áudio.app"


def rodar(*args: str) -> None:
    subprocess.run(args, cwd=RAIZ, check=True)


def construir(instalar: bool = False, ffmpeg_dir: Path | None = None) -> Path:
    if sys.platform != "darwin":
        raise SystemExit("A construção do aplicativo exige macOS.")
    BUILD.mkdir(parents=True, exist_ok=True)
    DIST.mkdir(parents=True, exist_ok=True)
    binarios = {}
    for programa in ("ffmpeg", "ffprobe"):
        caminho = str(ffmpeg_dir / programa) if ffmpeg_dir else shutil.which(programa)
        if not caminho:
            raise SystemExit(f"Instale {programa} antes de construir o app.")
        teste = subprocess.run([caminho, "-version"], capture_output=True)
        if teste.returncode:
            raise SystemExit(f"{programa} não funciona. Use --ffmpeg-dir com binários válidos.")
        binarios[programa] = caminho
    comando = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
               "--onedir", "--windowed", "--name", "TextoAudioBackend",
               "--osx-bundle-identifier", "com.holly.textoemaudio",
               "--distpath", str(BUILD / "pyinstaller-dist"),
               "--workpath", str(BUILD / "pyinstaller-work"),
               "--specpath", str(BUILD), "--paths", str(RAIZ),
               "--add-data", f"{RAIZ / 'web'}:web",
               "--add-data", f"{RAIZ / 'pronuncias.txt'}:.",
               "--add-data", f"{RAIZ / 'README.md'}:.",
               "--hidden-import", "uvicorn.logging",
               "--hidden-import", "uvicorn.loops.asyncio",
               "--hidden-import", "uvicorn.protocols.http.h11_impl",
               "--hidden-import", "uvicorn.lifespan.on"]
    for caminho in binarios.values():
        comando += ["--add-binary", f"{caminho}:."]
    comando.append(str(RAIZ / "macos" / "backend.py"))
    rodar(*comando)
    app = DIST / NOME
    if app.exists():
        shutil.rmtree(app)
    shutil.copytree(BUILD / "pyinstaller-dist" / "TextoAudioBackend.app",
                    app, symlinks=True)
    rodar("xcrun", "swiftc", "-O", "-target", "arm64-apple-macosx13.0",
          "-framework", "Cocoa", "-framework", "WebKit",
          str(RAIZ / "macos" / "App.swift"), "-o",
          str(app / "Contents" / "MacOS" / "TextoEmAudio"))
    icone = RAIZ / "macos" / "icone.swift"
    if icone.exists():
        rodar("xcrun", "swift", str(icone), str(BUILD / "AppIcon.iconset"))
        rodar("iconutil", "-c", "icns", str(BUILD / "AppIcon.iconset"),
              "-o", str(app / "Contents" / "Resources" / "AppIcon.icns"))
    info = app / "Contents" / "Info.plist"
    with info.open("rb") as arquivo:
        dados = plistlib.load(arquivo)
    dados.update({
        "CFBundleExecutable": "TextoEmAudio",
        "CFBundleName": "Texto em Áudio",
        "CFBundleDisplayName": "Texto em Áudio",
        "CFBundleIdentifier": "com.holly.textoemaudio",
        "CFBundleShortVersionString": "1.1.0",
        "CFBundleVersion": "110",
        "CFBundleIconFile": "AppIcon.icns",
        "LSMinimumSystemVersion": "13.0",
        "LSApplicationCategoryType": "public.app-category.productivity",
        "NSHighResolutionCapable": True,
        "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
    })
    with info.open("wb") as arquivo:
        plistlib.dump(dados, arquivo)
    rodar("codesign", "--force", "--deep", "--sign", "-", str(app))
    rodar("codesign", "--verify", "--deep", "--strict", str(app))
    if instalar:
        destino = Path("/Applications") / NOME
        if not os.access(destino.parent, os.W_OK):
            destino = Path.home() / "Applications" / NOME
            destino.parent.mkdir(parents=True, exist_ok=True)
        if destino.exists():
            backup = destino.with_name("Texto em Áudio - anterior.app")
            if backup.exists():
                raise SystemExit(f"Já existe um backup em {backup}; preserve-o antes de reinstalar.")
            destino.rename(backup)
        shutil.copytree(app, destino, symlinks=True)
        rodar("codesign", "--verify", "--deep", "--strict", str(destino))
        app = destino
    print(app)
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instalar", action="store_true")
    parser.add_argument("--ffmpeg-dir", type=Path)
    args = parser.parse_args()
    construir(args.instalar, args.ffmpeg_dir.resolve() if args.ffmpeg_dir else None)
