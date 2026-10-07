"""Uso:
    python -m texto_audio                    # abre a interface no navegador
    python -m texto_audio gerar peca.txt     # gera saidas/<nome>.mp3 sem interface
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import threading
import webbrowser
from pathlib import Path

from .audio import ErroAudio
from .caminhos import ARQUIVO_PRONUNCIAS, PASTA_SAIDAS, preparar_dados
from .extrair import ArquivoNaoSuportado, extrair_texto
from .motores import VOZ_PADRAO, VOZES, ErroSintese
from .normalizar import Opcoes, carregar_pronuncias
from .pipeline import Configuracao, gerar_audio

def servir(args) -> int:
    import uvicorn
    preparar_dados()
    url = f"http://127.0.0.1:{args.porta}"
    if not args.sem_navegador:
        threading.Timer(1.2, webbrowser.open, args=(url,)).start()
    print(f"Texto em Áudio em {url}  (Ctrl+C para encerrar)")
    uvicorn.run("texto_audio.servidor:app", host="127.0.0.1",
                port=args.porta, log_level="warning")
    return 0


def gerar(args) -> int:
    arquivo = Path(args.arquivo)
    try:
        texto = extrair_texto(arquivo.name, arquivo.read_bytes())
    except (OSError, ArquivoNaoSuportado) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 2

    pronuncias = {}
    padrao = ARQUIVO_PRONUNCIAS
    if padrao.exists():
        pronuncias = carregar_pronuncias(padrao.read_text(encoding="utf-8"))

    cfg = Configuracao(
        voz=args.voz, velocidade=args.velocidade,
        pausa_paragrafo_ms=args.pausa, titulo=args.titulo or arquivo.stem,
        normalizar_volume=not args.sem_normalizar_volume,
        texto=Opcoes(siglas=args.siglas,
                     omitir_referencias=args.omitir_referencias,
                     pronuncias=pronuncias))

    def progresso(fracao: float, msg: str) -> None:
        print(f"\r{fracao * 100:5.1f}%  {msg:<40}", end="", flush=True)

    try:
        r = asyncio.run(gerar_audio(texto, Path(args.saida), cfg,
                                    progresso=progresso))
    except (ValueError, ErroSintese, ErroAudio, OSError) as erro:
        print(f"\nErro: {erro}", file=sys.stderr)
        return 1
    minutos, segundos = divmod(round(r.duracao_s), 60)
    print(f"\n{r.caminho}  ({minutos}min{segundos:02d}s, "
          f"{r.tamanho_bytes / 1024:.0f} KB)")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="texto_audio", description=__doc__,
                                formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="comando")

    s = sub.add_parser("servir", help="abre a interface web (padrão)")
    s.add_argument("--porta", type=int, default=8765)
    s.add_argument("--sem-navegador", action="store_true")
    s.set_defaults(func=servir)

    g = sub.add_parser("gerar", help="converte um arquivo em MP3")
    g.add_argument("arquivo", help=".txt, .docx ou .pdf")
    g.add_argument("-o", "--saida", default=str(PASTA_SAIDAS),
                   help="pasta de saída (padrão: saidas/)")
    g.add_argument("--voz", default=VOZ_PADRAO, choices=list(VOZES))
    g.add_argument("--velocidade", type=int, default=0,
                   help="%% em relação ao normal, de -50 a 100")
    g.add_argument("--pausa", type=int, default=700,
                   help="pausa entre parágrafos, em ms")
    g.add_argument("--siglas", choices=["extenso", "letras"],
                   default="extenso")
    g.add_argument("--omitir-referencias", action="store_true",
                   help="não lê '(fls. 12)', '(Id. 123)'...")
    g.add_argument("--sem-normalizar-volume", action="store_true")
    g.add_argument("--titulo")
    g.set_defaults(func=gerar)

    args = p.parse_args()
    if not args.comando:
        args = p.parse_args(["servir"])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
