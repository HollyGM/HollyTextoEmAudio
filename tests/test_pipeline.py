import asyncio
import shutil
import sys

import pytest

from texto_audio import audio
from texto_audio.motores import ErroSintese
from texto_audio.pipeline import (Configuracao, estimar_minutos,
                                  gerar_audio, nome_de_arquivo)

from .conftest import MotorQuebrado

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"),
                                reason="ffmpeg não instalado")


def rodar(coro):
    return asyncio.run(coro)


def test_gera_um_mp3_unico_com_pausas(tmp_path, motor_falso):
    texto = "Primeiro parágrafo.\nSegundo parágrafo.\nTerceiro parágrafo."
    cfg = Configuracao(titulo="Minha peça", pausa_paragrafo_ms=1000)
    progressos = []
    r = rodar(gerar_audio(texto, tmp_path, cfg, motor=motor_falso,
                          progresso=lambda f, m: progressos.append(f)))

    assert r.caminho.suffix == ".mp3" and r.caminho.parent == tmp_path
    assert r.blocos == 3 and len(motor_falso.chamadas) == 3
    # 3 blocos de 0,3 s + 2 pausas de 1,4 s (parágrafo curto) = ~3,7 s
    assert 3.3 < r.duracao_s < 4.2
    assert progressos[0] == 0.0 and progressos[-1] == 1.0
    assert progressos == sorted(progressos)
    # não sobra lixo temporário na pasta de saída
    assert [p.name for p in tmp_path.iterdir()] == [r.caminho.name]


def test_envia_ao_motor_o_texto_ja_normalizado(tmp_path, motor_falso):
    rodar(gerar_audio("Conforme art. 5º da CF/88.", tmp_path, Configuracao(),
                      motor=motor_falso))
    falado = motor_falso.chamadas[0][0]
    assert "artigo quinto" in falado and "Constituição Federal" in falado


def test_repassa_voz_e_velocidade(tmp_path, motor_falso):
    cfg = Configuracao(voz="pt-BR-FranciscaNeural", velocidade=20)
    rodar(gerar_audio("Olá.", tmp_path, cfg, motor=motor_falso))
    assert motor_falso.chamadas[0][1:] == ("pt-BR-FranciscaNeural", 20)


def test_texto_vazio_e_erro_claro(tmp_path, motor_falso):
    with pytest.raises(ValueError, match="nada para ser lido"):
        rodar(gerar_audio("  \n ... ", tmp_path, Configuracao(),
                          motor=motor_falso))


def test_falha_da_voz_propaga_e_nao_deixa_arquivo(tmp_path):
    with pytest.raises(ErroSintese):
        rodar(gerar_audio("Olá.\nMundo.", tmp_path, Configuracao(),
                          motor=MotorQuebrado()))
    assert list(tmp_path.iterdir()) == []


def test_nome_de_arquivo_seguro():
    nome = nome_de_arquivo("Sustentação Oral – Apelação nº 1234/SP ../../etc")
    assert nome.endswith(".mp3")
    assert "/" not in nome and ".." not in nome and " " not in nome
    assert nome.startswith("sustentacao-oral-apelacao-no-1234-sp-etc_")


def test_nomes_distintos_para_geracoes_no_mesmo_segundo():
    assert len({nome_de_arquivo("Mesmo título") for _ in range(100)}) == 100


def test_estimativa_de_duracao():
    assert estimar_minutos(1720, 0) == pytest.approx(10)
    assert estimar_minutos(1720, 100) == pytest.approx(5)       # fala 2x mais rápida
    assert estimar_minutos(1720, -50) == pytest.approx(20)
    # pausas não aceleram com a velocidade
    assert estimar_minutos(1720, 100, pausas_ms=60_000) == pytest.approx(6)


def test_ffmpeg_ausente_da_mensagem_clara(monkeypatch):
    monkeypatch.setattr(audio.shutil, "which", lambda _: None)
    with pytest.raises(audio.ErroAudio, match="brew install ffmpeg"):
        audio._exigir("ffmpeg")


def test_audio_sem_sinal_algum_nao_derruba_a_geracao(tmp_path):
    """loudnorm + silêncio digital quebra o encoder; deve cair no plano B."""
    silencio = tmp_path / "s.wav"
    rodar(audio.silencio(300, silencio))
    destino = tmp_path / "saida.mp3"
    rodar(audio.juntar([silencio, silencio], destino, "t", normalizar_volume=True))
    assert destino.exists() and rodar(audio.duracao(destino)) > 0.4


def _tom(destino, duracao=0.3):
    rodar(audio._rodar(
        audio._exigir("ffmpeg"), "-y", "-loglevel", "error", "-f", "lavfi",
        "-i", f"sine=frequency=200:duration={duracao}", "-ar", str(audio.TAXA),
        "-ac", "1", "-c:a", "pcm_s16le", str(destino)))


def test_aparar_remove_silencio_das_pontas_e_preserva_a_fala(tmp_path):
    antes, tom, depois = tmp_path / "a.wav", tmp_path / "t.wav", tmp_path / "d.wav"
    rodar(audio.silencio(500, antes)); _tom(tom, 0.3); rodar(audio.silencio(1500, depois))
    bruto = tmp_path / "bruto.mp3"
    rodar(audio.juntar([antes, tom, depois], bruto, normalizar_volume=False))
    assert rodar(audio.duracao(bruto)) > 2.2            # 0,5 + 0,3 + 1,5

    aparado = tmp_path / "aparado.wav"
    assert rodar(audio.aparar(bruto, aparado)) is True
    assert 0.3 < rodar(audio.duracao(aparado)) < 0.6    # fala + margens curtas


def test_aparar_trecho_totalmente_mudo_nao_quebra(tmp_path):
    mudo = tmp_path / "m.wav"
    rodar(audio.silencio(800, mudo))
    saida = tmp_path / "saida.wav"
    assert rodar(audio.aparar(mudo, saida)) is False


def test_pausas_do_usuario_sao_as_unicas_do_audio(tmp_path, motor_falso):
    """3 tons de 0,3 s + 2 pausas de título (700 x 1,4 = 0,98 s) ~ 2,9 s.
    Sem o corte, a cauda de silêncio do serviço somaria >1 s por trecho."""
    cfg = Configuracao(pausa_paragrafo_ms=700, normalizar_volume=False)
    r = rodar(gerar_audio("Um.\nDois.\nTrês.", tmp_path, cfg,
                          motor=motor_falso))
    assert 2.7 < r.duracao_s < 3.3


def test_ffmpeg_embutido_pode_ser_usado_sem_path(tmp_path, monkeypatch):
    executavel = tmp_path / "ffmpeg"
    executavel.write_text("#!/bin/sh\nexit 0\n")
    executavel.chmod(0o755)
    monkeypatch.setenv("TEXTO_AUDIO_FFMPEG", str(executavel))
    monkeypatch.setattr(audio.shutil, "which", lambda _: None)
    assert audio._exigir("ffmpeg") == str(executavel)


def test_cancelar_comando_encerra_processo_filho(monkeypatch):
    async def verificar():
        criado = asyncio.Event()
        processos = []
        original = asyncio.create_subprocess_exec

        async def capturar(*args, **kwargs):
            proc = await original(*args, **kwargs)
            processos.append(proc)
            criado.set()
            return proc

        monkeypatch.setattr(audio.asyncio, "create_subprocess_exec", capturar)
        tarefa = asyncio.create_task(audio._rodar(
            sys.executable, "-c", "import time; time.sleep(60)"))
        await criado.wait()
        tarefa.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarefa
        assert processos[0].returncode is not None

    rodar(verificar())


def test_falha_na_montagem_preserva_saida_anterior_e_txt(tmp_path):
    destino = tmp_path / "saida.mp3"
    destino.write_bytes(b"anterior")
    texto = destino.with_suffix(".txt")
    texto.write_text("Documento do usuário.")
    with pytest.raises(audio.ErroAudio):
        rodar(audio.juntar([tmp_path / "ausente.wav"], destino))
    assert destino.read_bytes() == b"anterior"
    assert texto.read_text() == "Documento do usuário."
    assert sorted(p.name for p in tmp_path.iterdir()) == ["saida.mp3", "saida.txt"]


def test_montagem_aceita_caminhos_relativos_e_apostrofo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pasta = tmp_path / "áudio d'água"
    pasta.mkdir()
    tom = pasta / "fala.wav"
    _tom(tom)
    destino = tmp_path / "saida.mp3"
    rodar(audio.juntar([tom.relative_to(tmp_path)], destino, normalizar_volume=False))
    assert rodar(audio.duracao(destino)) > 0.2


def test_falha_na_verificacao_final_remove_audio_incompleto(
        tmp_path, motor_falso, monkeypatch):
    async def falhar(arquivo):
        raise audio.ErroAudio("não consegui verificar o MP3")

    monkeypatch.setattr(audio, "duracao", falhar)
    with pytest.raises(audio.ErroAudio):
        rodar(gerar_audio("Olá.", tmp_path, Configuracao(), motor=motor_falso))
    assert list(tmp_path.iterdir()) == []


def test_ultimo_bloco_mudo_nao_acrescenta_pausa_ao_fim(tmp_path, motor_falso):
    class MotorComUltimoMudo:
        async def sintetizar(self, texto, destino, voz, velocidade):
            if texto == "Mudo.":
                mudo = destino.with_suffix(".wav")
                await audio.silencio(400, mudo)
                await audio.juntar([mudo], destino, normalizar_volume=False)
            else:
                await motor_falso.sintetizar(texto, destino, voz, velocidade)

    resultado = rodar(gerar_audio(
        "Audível.\nMudo.", tmp_path,
        Configuracao(pausa_paragrafo_ms=1000, normalizar_volume=False),
        motor=MotorComUltimoMudo()))
    assert 0.2 < resultado.duracao_s < 0.6


def test_limite_de_concorrencia_inclui_processamento_de_audio(tmp_path, monkeypatch):
    ativos = 0
    maximo = 0

    class MotorImediato:
        async def sintetizar(self, texto, destino, voz, velocidade):
            destino.write_bytes(b"voz")

    async def aparar(origem, destino):
        nonlocal ativos, maximo
        ativos += 1
        maximo = max(maximo, ativos)
        await asyncio.sleep(0.001)
        ativos -= 1
        destino.write_bytes(b"wav")
        return True

    async def silencio(ms, destino):
        destino.write_bytes(b"silencio")

    async def juntar(arquivos, destino, *args):
        destino.write_bytes(b"mp3")

    async def duracao(arquivo):
        return 1.0

    monkeypatch.setattr(audio, "aparar", aparar)
    monkeypatch.setattr(audio, "silencio", silencio)
    monkeypatch.setattr(audio, "juntar", juntar)
    monkeypatch.setattr(audio, "duracao", duracao)
    rodar(gerar_audio("\n".join("Parágrafo." for _ in range(10)),
                      tmp_path, Configuracao(), motor=MotorImediato()))
    assert maximo <= 3
