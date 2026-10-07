"""Recursos do programa e dados graváveis, inclusive no aplicativo macOS."""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = (Path(sys._MEIPASS) if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent.parent)
PASTA_DADOS = Path(os.environ.get("TEXTO_AUDIO_DATA_DIR", str(RAIZ))).expanduser()
PASTA_SAIDAS = Path(os.environ.get("TEXTO_AUDIO_OUTPUT_DIR",
                                  str(PASTA_DADOS / "saidas"))).expanduser()
ARQUIVO_PRONUNCIAS = PASTA_DADOS / "pronuncias.txt"
PAGINA = RAIZ / "web" / "index.html"


def preparar_dados() -> None:
    """Inicializa a pasta do app sem substituir as pronúncias do usuário."""
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    PASTA_SAIDAS.mkdir(parents=True, exist_ok=True)
    if ARQUIVO_PRONUNCIAS != RAIZ / "pronuncias.txt":
        try:
            with ARQUIVO_PRONUNCIAS.open("x", encoding="utf-8") as destino:
                origem = RAIZ / "pronuncias.txt"
                destino.write(origem.read_text(encoding="utf-8") if origem.exists() else "")
        except FileExistsError:
            pass
