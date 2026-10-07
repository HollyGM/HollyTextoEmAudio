"""Servidor local (FastAPI) e interface web. Escuta só em 127.0.0.1."""
from __future__ import annotations

import asyncio
import logging
import tempfile
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from . import __version__
from .audio import ErroAudio
from .blocos import dividir
from .caminhos import ARQUIVO_PRONUNCIAS, PAGINA, PASTA_SAIDAS
from .extrair import ArquivoNaoSuportado, extrair_texto
from .motores import VOZ_PADRAO, VOZES, ErroSintese, MotorEdge
from .normalizar import Opcoes, carregar_pronuncias, contar_palavras, normalizar
from .pipeline import Configuracao, estimar_minutos, gerar_audio

LIMITE_TEXTO = 400_000          # caracteres (~60 mil palavras, ~7 h de áudio)
LIMITE_UPLOAD = 20 * 1024 * 1024
MAX_TAREFAS_GUARDADAS = 50
MAX_TAREFAS_PENDENTES = 10
AMOSTRA = ("Excelentíssimo Senhor Presidente, egrégia Turma, ilustres "
           "Ministros. Sustento, da tribuna, a tese que passo a expor.")

log = logging.getLogger("texto_audio")


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    # Uma conversão por vez; cada conversão já sintetiza vários blocos em paralelo.
    app.state.fila = asyncio.Lock()
    try:
        yield
    finally:
        pendentes = [t._tarefa for t in TAREFAS.values()
                     if t._tarefa is not None and not t._tarefa.done()]
        for tarefa in pendentes:
            tarefa.cancel()
        if pendentes:
            await asyncio.gather(*pendentes, return_exceptions=True)


app = FastAPI(title="Texto em Áudio", docs_url=None, redoc_url=None,
              openapi_url=None, lifespan=ciclo_de_vida)


@app.middleware("http")
async def acesso_local(request: Request, call_next):
    """Impede acesso por outros sites e nomes de domínio apontados ao loopback."""
    locais = {"127.0.0.1", "localhost", "::1"}
    try:
        destino = urlsplit(f"http://{request.headers.get('host', '')}")
        if destino.hostname not in locais or destino.username or destino.password:
            return JSONResponse({"detail": "Este aplicativo aceita apenas acesso local."},
                                status_code=403)
        origem = request.headers.get("origin")
        if origem:
            origem = urlsplit(origem)
            if (origem.scheme != request.url.scheme
                    or origem.hostname != destino.hostname
                    or (origem.port or 80) != (destino.port or 80)
                    or origem.username or origem.password):
                return JSONResponse({"detail": "Abra o aplicativo pelo endereço local."},
                                    status_code=403)
        elif request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Abra o aplicativo pelo endereço local."},
                                status_code=403)
    except ValueError:
        return JSONResponse({"detail": "Endereço de acesso inválido."}, status_code=403)
    resposta = await call_next(request)
    if request.url.path.startswith("/api/"):
        resposta.headers["Cache-Control"] = "no-store"
    return resposta


class Pedido(BaseModel):
    texto: str = Field(max_length=LIMITE_TEXTO)
    voz: str = VOZ_PADRAO
    velocidade: int = Field(0, ge=-50, le=100)
    siglas: str = Field("extenso", pattern="^(extenso|letras)$")
    omitir_referencias: bool = False
    omitir_numeracao: bool = True
    pausa_paragrafo_ms: int = Field(700, ge=0, le=3000)
    normalizar_volume: bool = True
    titulo: str = Field("Áudio", max_length=120)
    pronuncias: str = Field("", max_length=20_000)


def _opcoes(p: Pedido) -> Opcoes:
    mapa = {}
    if ARQUIVO_PRONUNCIAS.exists():
        mapa.update(carregar_pronuncias(
            ARQUIVO_PRONUNCIAS.read_text(encoding="utf-8")))
    mapa.update(carregar_pronuncias(p.pronuncias))
    return Opcoes(siglas=p.siglas, omitir_referencias=p.omitir_referencias,
                  omitir_numeracao=p.omitir_numeracao, pronuncias=mapa)


def _validar_voz(voz: str) -> None:
    if voz not in VOZES:
        raise HTTPException(422, f"Voz desconhecida: {voz}")


@dataclass
class Tarefa:
    status: str = "na_fila"         # na_fila | gerando | pronto | erro
    progresso: float = 0.0
    mensagem: str = "Na fila"
    erro: str | None = None
    caminho: Path | None = None
    duracao_s: float = 0.0
    tamanho_bytes: int = 0
    palavras: int = 0
    _tarefa: asyncio.Task | None = field(default=None, repr=False)


TAREFAS: dict[str, Tarefa] = {}


async def _executar(tarefa: Tarefa, pedido: Pedido) -> None:
    def avisar(fracao: float, mensagem: str) -> None:
        tarefa.progresso, tarefa.mensagem = fracao, mensagem

    try:
        async with app.state.fila:
            tarefa.status, tarefa.mensagem = "gerando", "Preparando o texto"
            cfg = Configuracao(
                voz=pedido.voz, velocidade=pedido.velocidade,
                pausa_paragrafo_ms=pedido.pausa_paragrafo_ms,
                normalizar_volume=pedido.normalizar_volume,
                titulo=pedido.titulo, texto=_opcoes(pedido))
            r = await gerar_audio(pedido.texto, PASTA_SAIDAS, cfg,
                                  progresso=avisar)
    except asyncio.CancelledError:
        tarefa.status, tarefa.erro = "erro", "A conversão foi interrompida ao fechar o aplicativo."
        tarefa.mensagem = "Conversão interrompida"
        raise
    except (ValueError, ErroSintese) as erro:
        tarefa.status, tarefa.erro = "erro", str(erro)
        tarefa.mensagem = "Falha ao gerar o áudio"
    except ErroAudio as erro:
        tarefa.status, tarefa.mensagem = "erro", "Falha ao montar o MP3"
        tarefa.erro = f"Não consegui montar o MP3: {erro}"
    except Exception:                   # nunca logar o texto da peça
        log.exception("falha inesperada ao gerar áudio")
        tarefa.status = "erro"
        tarefa.mensagem = "Falha ao gerar o áudio"
        tarefa.erro = "Falha inesperada ao gerar o áudio. Reinicie o aplicativo e tente novamente."
    else:
        tarefa.status, tarefa.mensagem = "pronto", "Pronto"
        tarefa.progresso = 1.0
        tarefa.caminho, tarefa.duracao_s = r.caminho, r.duracao_s
        tarefa.tamanho_bytes, tarefa.palavras = r.tamanho_bytes, r.palavras


@app.get("/")
def pagina():
    return FileResponse(PAGINA, headers={"Cache-Control": "no-store"})


@app.get("/api/vozes")
def vozes():
    return {"padrao": VOZ_PADRAO,
            "vozes": [{"id": k, "nome": v} for k, v in VOZES.items()]}


@app.get("/api/info")
async def informacoes():
    return {"versao": __version__, "status": "pronto",
            "pasta_saidas": str(PASTA_SAIDAS),
            "tarefas_ativas": sum(t.status in ("na_fila", "gerando")
                                  for t in TAREFAS.values())}


@app.post("/api/preparar")
def preparar(pedido: Pedido):
    """Mostra como o texto será lido e quanto tempo deve durar."""
    falado = normalizar(pedido.texto, _opcoes(pedido))
    palavras = contar_palavras(falado)
    blocos = dividir(falado, pausa_paragrafo_ms=pedido.pausa_paragrafo_ms)
    pausas_ms = sum(b.pausa_ms for b in blocos)
    return {
        "texto_falado": falado,
        "palavras": palavras,
        "blocos": len(blocos),
        "minutos": estimar_minutos(palavras, pedido.velocidade, pausas_ms),
        # para a interface calcular a velocidade que faz caber no tempo
        "minutos_fala_normal": estimar_minutos(palavras, 0),
        "minutos_pausas": pausas_ms / 60_000,
    }


@app.post("/api/audio", status_code=202)
async def criar_audio(pedido: Pedido):
    _validar_voz(pedido.voz)
    if not pedido.texto.strip():
        raise HTTPException(422, "Cole ou envie um texto primeiro.")
    pendentes = sum(t.status in ("na_fila", "gerando") for t in TAREFAS.values())
    if pendentes >= MAX_TAREFAS_PENDENTES:
        raise HTTPException(429, "A fila está cheia. Aguarde uma conversão terminar.")
    while len(TAREFAS) >= MAX_TAREFAS_GUARDADAS:
        antiga = next((chave for chave, t in TAREFAS.items()
                       if t.status in ("pronto", "erro")), None)
        if antiga is None:
            break
        del TAREFAS[antiga]
    tarefa_id = uuid.uuid4().hex
    tarefa = Tarefa()
    TAREFAS[tarefa_id] = tarefa
    tarefa._tarefa = asyncio.create_task(_executar(tarefa, pedido))
    return {"id": tarefa_id}


@app.get("/api/audio/{tarefa_id}")
async def estado(tarefa_id: str):
    t = TAREFAS.get(tarefa_id)
    if not t:
        raise HTTPException(404, "Tarefa não encontrada.")
    posicao = 0
    if t.status == "na_fila":
        fila = [chave for chave, tarefa in TAREFAS.items()
                if tarefa.status in ("na_fila", "gerando")]
        posicao = fila.index(tarefa_id) + 1
    return {"status": t.status, "progresso": t.progresso,
            "mensagem": f"Na fila (posição {posicao})" if posicao else t.mensagem,
            "erro": t.erro, "posicao_fila": posicao,
            "duracao_s": t.duracao_s, "tamanho_bytes": t.tamanho_bytes,
            "palavras": t.palavras,
            "arquivo": t.caminho.name if t.caminho else None}


@app.get("/api/audio/{tarefa_id}/arquivo")
def arquivo(tarefa_id: str):
    t = TAREFAS.get(tarefa_id)
    if not t or t.status != "pronto" or not t.caminho:
        raise HTTPException(404, "Áudio ainda não está pronto.")
    if not t.caminho.is_file():
        raise HTTPException(404, "O MP3 foi movido ou excluído da pasta de saída.")
    return FileResponse(t.caminho, media_type="audio/mpeg",
                        filename=t.caminho.name)


@app.get("/api/amostra")
async def amostra(voz: str = VOZ_PADRAO, velocidade: int = 0):
    _validar_voz(voz)
    velocidade = max(-50, min(100, velocidade))
    with tempfile.TemporaryDirectory(prefix="texto-audio-") as tmp:
        destino = Path(tmp) / "amostra.mp3"
        try:
            await MotorEdge().sintetizar(AMOSTRA, destino, voz, velocidade)
        except ErroSintese as erro:
            raise HTTPException(502, str(erro)) from erro
        dados = destino.read_bytes()
    return Response(dados, media_type="audio/mpeg",
                    headers={"Cache-Control": "no-store"})


@app.post("/api/extrair")
async def extrair(arquivo: UploadFile = File(...)):
    try:
        dados = await arquivo.read(LIMITE_UPLOAD + 1)
    finally:
        await arquivo.close()
    if len(dados) > LIMITE_UPLOAD:
        raise HTTPException(413, "Arquivo maior que 20 MB.")
    try:
        texto = await asyncio.to_thread(extrair_texto, arquivo.filename or "", dados)
    except ArquivoNaoSuportado as erro:
        raise HTTPException(415, str(erro)) from erro
    except Exception as erro:
        raise HTTPException(422, "Não consegui ler esse arquivo.") from erro
    if not texto.strip():
        raise HTTPException(422, "O arquivo não contém texto para ser lido.")
    return {"texto": texto[:LIMITE_TEXTO],
            "truncado": len(texto) > LIMITE_TEXTO}
