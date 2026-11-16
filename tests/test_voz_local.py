"""Voz local (macOS `say`): gera o áudio sem enviar o texto à Microsoft."""
import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from texto_audio import audio, motores, pipeline, servidor
from texto_audio.motores import ErroSintese, MotorLocal, eh_voz_local
from texto_audio.pipeline import Configuracao, gerar_audio

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"),
                                reason="ffmpeg não instalado")

LUCIANA = "local:Luciana"
LISTA_COM_LUCIANA = "Luciana (Português (Brasil)) pt_BR    # Olá, meu nome é Luciana."
LISTA_SEM_LUCIANA = "Samantha            en_US    # Hello, my name is Samantha."

SAY_FALSO = '''#!{python}
import json, os, shutil, sys
args = sys.argv[1:]
if args[:2] == ["-v", "?"]:
    print(os.environ["SAY_FALSO_VOZES"])
    sys.exit(0)
texto = sys.stdin.read()
with open(os.environ["SAY_FALSO_REGISTRO"], "a", encoding="utf-8") as f:
    f.write(json.dumps({{"args": args, "texto": texto}}) + "\\n")
shutil.copy(os.environ["SAY_FALSO_AUDIO"], args[args.index("-o") + 1])
'''


class MicrosoftProibida:
    async def sintetizar(self, *args, **kwargs):
        raise AssertionError("a voz local não pode usar o serviço da Microsoft")


@pytest.fixture
def say_falso(tmp_path, monkeypatch):
    """`say` falso: registra argumentos e texto e devolve um AIFF de verdade."""
    aiff = tmp_path / "tom.aiff"
    subprocess.run([shutil.which("ffmpeg"), "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "sine=frequency=220:duration=0.5", "-ar", "22050", "-ac", "1",
                    str(aiff)], check=True)
    script = tmp_path / "say"
    script.write_text(SAY_FALSO.format(python=sys.executable), encoding="utf-8")
    script.chmod(0o755)
    registro = tmp_path / "registro.jsonl"
    monkeypatch.setenv("TEXTO_AUDIO_SAY", str(script))
    monkeypatch.setenv("SAY_FALSO_AUDIO", str(aiff))
    monkeypatch.setenv("SAY_FALSO_REGISTRO", str(registro))
    monkeypatch.setenv("SAY_FALSO_VOZES", LISTA_COM_LUCIANA)
    monkeypatch.setattr(motores, "_VOZES_INSTALADAS", set())

    def chamadas():
        if not registro.exists():
            return []
        return [json.loads(linha) for linha in registro.read_text("utf-8").splitlines()]
    return chamadas


def formato(arquivo: Path) -> str:
    return subprocess.run(
        [shutil.which("ffprobe"), "-v", "error", "-show_entries", "format=format_name",
         "-of", "default=nw=1:nk=1", str(arquivo)],
        capture_output=True, text=True, check=True).stdout.strip()


def test_so_a_luciana_e_local():
    assert eh_voz_local(LUCIANA)
    assert not eh_voz_local(motores.VOZ_PADRAO)
    assert LUCIANA in motores.VOZES


def test_voz_local_gera_mp3_com_texto_pela_entrada_padrao(tmp_path, say_falso):
    destino = tmp_path / "voz.mp3"
    texto = "Excelentíssimo Senhor, artigo quinto."
    asyncio.run(MotorLocal().sintetizar(texto, destino, LUCIANA, 20))
    assert formato(destino) == "mp3"
    (chamada,) = say_falso()
    assert chamada["texto"] == texto
    assert texto not in " ".join(chamada["args"])        # fora da lista de processos
    assert chamada["args"][:4] == ["-v", "Luciana", "-r", "210"]   # 175 × 1,2


def test_voz_local_ausente_explica_e_nao_le_com_outra_voz(tmp_path, say_falso,
                                                         monkeypatch):
    monkeypatch.setenv("SAY_FALSO_VOZES", LISTA_SEM_LUCIANA)
    destino = tmp_path / "voz.mp3"
    with pytest.raises(ErroSintese, match="não está instalada.*Gerenciar Vozes"):
        asyncio.run(MotorLocal().sintetizar("Olá.", destino, LUCIANA, 0))
    assert say_falso() == []
    assert not destino.exists()


def test_sem_comando_say_explica(tmp_path, monkeypatch):
    monkeypatch.setenv("TEXTO_AUDIO_SAY", str(tmp_path / "nao-existe"))
    with pytest.raises(ErroSintese, match="só funciona no macOS"):
        asyncio.run(MotorLocal().sintetizar("Olá.", tmp_path / "v.mp3", LUCIANA, 0))


def test_conversao_com_voz_local_nao_usa_a_microsoft(tmp_path, say_falso,
                                                    monkeypatch):
    monkeypatch.setattr(pipeline, "MotorEdge", MicrosoftProibida)
    texto = "Primeiro parágrafo da sustentação.\n\nSegundo parágrafo, art. 5º da CF."
    r = asyncio.run(gerar_audio(texto, tmp_path, Configuracao(voz=LUCIANA)))
    assert r.caminho.is_file() and formato(r.caminho) == "mp3"
    lidos = " ".join(c["texto"] for c in say_falso())
    assert "artigo quinto" in lidos


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(servidor, "PASTA_SAIDAS", tmp_path)
    monkeypatch.setattr(servidor, "ARQUIVO_PRONUNCIAS", tmp_path / "nao-existe.txt")
    monkeypatch.setattr(servidor, "MotorEdge", MicrosoftProibida)
    servidor.TAREFAS.clear()
    with TestClient(servidor.app, base_url="http://127.0.0.1") as c:
        yield c


def test_lista_de_vozes_marca_a_voz_local(cliente):
    vozes = {v["id"]: v["local"] for v in cliente.get("/api/vozes").json()["vozes"]}
    assert vozes[LUCIANA] is True
    assert vozes[motores.VOZ_PADRAO] is False


def test_amostra_com_voz_local_nao_usa_a_microsoft(cliente, say_falso):
    r = cliente.get("/api/amostra", params={"voz": LUCIANA, "velocidade": 0})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert len(say_falso()) == 1


def _luciana_instalada() -> bool:
    if not Path("/usr/bin/say").exists():
        return False
    lista = subprocess.run(["/usr/bin/say", "-v", "?"], capture_output=True, check=False,
                           text=True).stdout
    return any(linha.startswith("Luciana") and "pt_BR" in linha
               for linha in lista.splitlines())


@pytest.mark.skipif(not _luciana_instalada(), reason="voz Luciana não instalada")
def test_luciana_de_verdade(tmp_path, monkeypatch):
    monkeypatch.delenv("TEXTO_AUDIO_SAY", raising=False)
    destino = tmp_path / "luciana.mp3"
    asyncio.run(MotorLocal().sintetizar(
        "Excelentíssimo Senhor Presidente, egrégia Turma.", destino, LUCIANA, 0))
    assert formato(destino) == "mp3"
    assert asyncio.run(audio.duracao(destino)) > 1.0
